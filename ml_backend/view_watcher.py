"""
view_watcher.py — Watches Supabase view tables for changes, triggers ML pipeline.

HOW IT WORKS
------------
1. Polls v_inventory_snapshot, v_store_products, v_store_transactions every
   POLL_INTERVAL seconds.
2. Detects changes by fingerprinting each view (row count + latest timestamp).
3. On any change: downloads fresh data from all 3 views → saves JSON files →
   runs run_local_view_ml.py --push (ML + Supabase upload).
4. Never dies: crashes are caught, logged, and the loop restarts automatically
   with exponential backoff. A watchdog thread revives the main loop if it
   somehow stops.

RUN
---
  python3 view_watcher.py

  POLL_INTERVAL=120 python3 view_watcher.py   # check every 2 minutes
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

POLL_INTERVAL    = int(os.getenv("POLL_INTERVAL", "60"))   # seconds between polls
DOWNLOAD_DIR     = os.path.expanduser("~/Downloads")
ML_SCRIPT        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_local_view_ml.py")
MAX_BACKOFF      = 300   # max seconds to wait after repeated errors
WATCHDOG_TIMEOUT = 600   # restart main loop if silent for this many seconds

VIEWS = {
    "v_inventory_snapshot":  {"ts_col": "updated_at"},
    "v_store_products":      {"ts_col": None},           # no timestamp col
    "v_store_transactions":  {"ts_col": "timestamp"},
}

OUTPUT_FILES = {
    "v_inventory_snapshot": os.path.join(DOWNLOAD_DIR, "v_inventory_snapshot.json"),
    "v_store_products":     os.path.join(DOWNLOAD_DIR, "v_store_products.json"),
    "v_store_transactions": os.path.join(DOWNLOAD_DIR, "v_store_transactions.json"),
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [view_watcher] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("view_watcher")

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------
_client: Client = None

def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client

def reset_client():
    """Force a fresh client on next get_client() call (used after connection errors)."""
    global _client
    _client = None

# ---------------------------------------------------------------------------
# Fingerprint: detect changes without downloading full data
# ---------------------------------------------------------------------------

def fingerprint(view: str, ts_col: str | None) -> dict:
    """
    Returns {count, latest_ts} for a view.
    Used to detect whether the view has changed since last poll.
    """
    client = get_client()

    # Row count via head=True (returns count only, no data)
    res = client.table(view).select("*", count="exact").limit(1).execute()
    count = res.count if res.count is not None else 0

    latest_ts = None
    if ts_col:
        try:
            row = (
                client.table(view)
                .select(ts_col)
                .order(ts_col, desc=True)
                .limit(1)
                .execute()
                .data
            )
            if row:
                latest_ts = row[0][ts_col]
        except Exception:
            pass

    return {"count": count, "latest_ts": latest_ts}


def views_changed(old: dict, new: dict) -> list[str]:
    """Return list of view names that changed between two fingerprint snapshots."""
    changed = []
    for view in VIEWS:
        if old.get(view) != new.get(view):
            changed.append(view)
    return changed

# ---------------------------------------------------------------------------
# Download full view data and save as JSON
# ---------------------------------------------------------------------------

def download_view(view: str, path: str) -> int:
    """
    Downloads all rows from a view using pagination and writes to a JSON file.
    Returns row count written.
    """
    client  = get_client()
    rows    = []
    page    = 1000
    offset  = 0

    while True:
        res = (
            client.table(view)
            .select("*")
            .range(offset, offset + page - 1)
            .execute()
        )
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page

    # Atomic write: write to temp file first, then rename
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rows, f, indent=2, default=str)
    os.replace(tmp, path)   # atomic on POSIX

    return len(rows)


def download_all_views() -> bool:
    """
    Downloads all 3 views. Returns True if all succeeded.
    """
    log.info("Downloading fresh data from Supabase views...")
    try:
        for view, path in OUTPUT_FILES.items():
            n = download_view(view, path)
            log.info("  %-35s → %d rows  →  %s", view, n, path)
        return True
    except Exception as e:
        log.error("Download failed: %s", e)
        reset_client()
        return False

# ---------------------------------------------------------------------------
# Run ML pipeline
# ---------------------------------------------------------------------------

def run_ml() -> bool:
    """
    Runs run_local_view_ml.py --push as a subprocess.
    Returns True if it exited successfully.
    """
    log.info("Running ML pipeline...")
    try:
        result = subprocess.run(
            [sys.executable, ML_SCRIPT, "--push"],
            capture_output=True,
            text=True,
            timeout=600,
        )

        # Print stdout line by line (filters out httpx noise)
        for line in result.stdout.splitlines():
            if "HTTP Request" not in line:
                log.info("  [ml] %s", line)

        if result.returncode != 0:
            log.error("ML script exited with code %d", result.returncode)
            for line in result.stderr.splitlines():
                log.error("  [ml stderr] %s", line)
            return False

        log.info("ML pipeline completed successfully.")
        return True

    except subprocess.TimeoutExpired:
        log.error("ML script timed out after 600s.")
        return False
    except Exception as e:
        log.error("Failed to run ML script: %s", e)
        return False

# ---------------------------------------------------------------------------
# Main poll loop
# ---------------------------------------------------------------------------

# Shared heartbeat timestamp — watchdog uses this to detect a frozen loop
_last_heartbeat: float = time.time()


def poll_loop():
    global _last_heartbeat

    log.info("View watcher started | url=%s | interval=%ds", SUPABASE_URL, POLL_INTERVAL)
    log.info("Watching: %s", ", ".join(VIEWS.keys()))

    # Build initial fingerprint (no ML run on startup)
    fingerprints: dict = {}
    while not fingerprints:
        try:
            fingerprints = {v: fingerprint(v, cfg["ts_col"]) for v, cfg in VIEWS.items()}
            log.info("Initial fingerprint captured.")
        except Exception as e:
            log.error("Could not get initial fingerprint: %s — retrying in 30s", e)
            reset_client()
            time.sleep(30)

    consecutive_errors = 0

    while True:
        _last_heartbeat = time.time()

        try:
            # --- Poll ---
            new_fps = {v: fingerprint(v, cfg["ts_col"]) for v, cfg in VIEWS.items()}
            changed = views_changed(fingerprints, new_fps)

            if changed:
                log.info("Change detected in: %s", ", ".join(changed))

                ok = download_all_views()
                if ok:
                    ml_ok = run_ml()
                    if ml_ok:
                        # Only update fingerprint on full success so a partial
                        # failure retries next poll
                        fingerprints = new_fps
                        log.info("Cycle complete. Watching for next change...")
                    else:
                        log.warning("ML run failed — will retry on next poll.")
                else:
                    log.warning("Download failed — will retry on next poll.")
            else:
                log.info("No changes. Next check in %ds.", POLL_INTERVAL)

            consecutive_errors = 0

        except Exception as e:
            consecutive_errors += 1
            backoff = min(POLL_INTERVAL * consecutive_errors, MAX_BACKOFF)
            log.error("Poll error (#%d): %s — backing off %ds", consecutive_errors, e, backoff)
            reset_client()
            time.sleep(backoff)
            continue

        time.sleep(POLL_INTERVAL)

# ---------------------------------------------------------------------------
# Watchdog thread — restarts poll_loop if it freezes or crashes
# ---------------------------------------------------------------------------

def watchdog(main_thread: threading.Thread):
    """
    Monitors the main poll loop. If the heartbeat goes stale for WATCHDOG_TIMEOUT
    seconds, logs a warning. If the main thread dies, restarts it.
    """
    while True:
        time.sleep(30)

        # Check heartbeat staleness
        silent_for = time.time() - _last_heartbeat
        if silent_for > WATCHDOG_TIMEOUT:
            log.warning("Watchdog: main loop silent for %.0fs — possible freeze.", silent_for)

        # Restart if main thread died
        if not main_thread.is_alive():
            log.error("Watchdog: main poll loop died — restarting...")
            new_thread = threading.Thread(target=safe_poll_loop, daemon=True, name="poll-loop")
            new_thread.start()
            main_thread = new_thread


def safe_poll_loop():
    """Wraps poll_loop with a top-level catch so the thread never silently exits."""
    while True:
        try:
            poll_loop()
        except Exception as e:
            log.error("poll_loop crashed: %s — restarting in 30s", e)
            time.sleep(30)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("Jiran View Watcher")
    log.info("Poll interval : %ds", POLL_INTERVAL)
    log.info("Download dir  : %s", DOWNLOAD_DIR)
    log.info("ML script     : %s", ML_SCRIPT)
    log.info("=" * 60)

    # Start main loop in a thread so watchdog can monitor it
    main = threading.Thread(target=safe_poll_loop, daemon=True, name="poll-loop")
    main.start()

    # Start watchdog in a thread
    wd = threading.Thread(target=watchdog, args=(main,), daemon=True, name="watchdog")
    wd.start()

    # Keep the main process alive
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        log.info("Shutting down.")
        sys.exit(0)
