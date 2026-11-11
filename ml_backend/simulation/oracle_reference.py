"""Add an 'oracle' row to forecasts.json: the true expected demand from the generator.

It is the best a forecaster could do without knowing the day's random draw, so it
shows the noise floor of each metric. Never available to any model.
"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from evaluate_forecasts import HORIZONS, score  # noqa: E402

res_dir = HERE / "output/results"; lam = np.load(HERE / "output/sim1000_v1/expected_demand.npy", mmap_mode="r")
folds = json.loads((res_dir / "forecast_folds_test.json").read_text())
for f in folds: f["oracle"] = np.asarray(lam[f["series_id"], f["origin"] + 1:f["origin"] + 31], float).tolist()
out = json.loads((res_dir / "forecasts.json").read_text()); t = out["results"]["test"]
t["all"]["oracle"] = [score(folds, "oracle", h) for h in HORIZONS]
for c in t["by_class"]: t["by_class"][c]["oracle"] = [score([f for f in folds if f["class"] == c], "oracle", h) for h in HORIZONS]
(res_dir / "forecasts.json").write_text(json.dumps(out, indent=1)); (res_dir / "forecast_folds_test.json").write_text(json.dumps(folds))
for r in t["all"]["oracle"]: print({k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()})
