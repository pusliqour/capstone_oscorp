// src/pages/Exchange.jsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { supabase } from "../supaBase/Client";

import "../styles/Exchange.css";
import Logo from "/src/styles/Logo.png";
import Avatar from "/src/styles/avatar.png";

/* ===============================
  Distance helpers
================================ */
const toRad = (v) => (v * Math.PI) / 180;

function haversineKm(lat1, lon1, lat2, lon2) {
  const nums = [lat1, lon1, lat2, lon2].map((v) =>
    typeof v === "string" ? Number(v) : v,
  );
  if (nums.some((v) => !Number.isFinite(v))) return null;

  const [aLat, aLon, bLat, bLon] = nums;

  const R = 6371; // km
  const dLat = toRad(bLat - aLat);
  const dLon = toRad(bLon - aLon);

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2;

  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

const estimateMinutes = (km) =>
  km && km > 0 ? Math.max(1, Math.round((km / 35) * 60)) : null;

/* ===============================
  Topbar
================================ */
function Topbar({ displayName, role, onLogout, activePage }) {
  return (
    <header className="topbar">
      <Link
        to="/"
        className="brand brand-link"
        // target="_blank"
        rel="noopener noreferrer"
        aria-label="Go to landing page"
      >
        <img src={Logo} alt="Jiran Logo" className="nav-logo" />
        <div className="brand-text">
          <h1>Jiran</h1>
          <p>Retailer Dashboard</p>
        </div>
      </Link>

      <nav className="nav" aria-label="Primary navigation">
        <Link
          className={`nav-item ${activePage === "dashboard" ? "active" : ""}`}
          to="/retailer-dashboard"
        >
          Dashboard
        </Link>
        <Link
          className={`nav-item ${activePage === "inventory" ? "active" : ""}`}
          to="/inventory"
        >
          Inventory
        </Link>
        <Link
          className={`nav-item ${activePage === "exchange" ? "active" : ""}`}
          to="/exchange"
        >
          Marketplace
        </Link>
        <Link
          className={`nav-item ${activePage === "analytics" ? "active" : ""}`}
          to="/analytics"
        >
          Analytics
        </Link>
        <Link
          className={`nav-item ${activePage === "settings" ? "active" : ""}`}
          to="/settings"
        >
          Settings
        </Link>
      </nav>

      <div className="top-actions">
        <Link className="account" to="/settings" aria-label="Open account settings">
          <span className="avatar">
            <img src={Avatar} alt="avatar" />
          </span>{" "}
          <span className="acct-text">
            <span className="acct-name">{displayName}</span>
            <span className="acct-sub">{role}</span>
          </span>
        </Link>

        <button className="btn ghost small" onClick={onLogout}>
          Logout
        </button>
      </div>
    </header>
  );
}

/* ===============================
  UI helpers
================================ */
const Panel = ({ children, className = "" }) => (
  <section className={`panel ${className}`}>{children}</section>
);

/* ===============================
  Phone helpers
================================ */
const digitsOnly = (s) => String(s || "").replace(/[^\d]/g, "");

function toWhatsAppNumber(rawPhone) {
  let d = digitsOnly(rawPhone);
  if (!d) return "";

  if (d.startsWith("00")) d = d.slice(2);
  if (d.startsWith("971")) return d;
  if (d.length === 10 && d.startsWith("0")) return `971${d.slice(1)}`;
  if (d.length === 9 && d.startsWith("5")) return `971${d}`;

  return d;
}

/* ===============================
  Contact Modal
================================ */
function ContactModal({
  open,
  onClose,
  retailerMeta,
  contact,
  loading,
  error,
  myLocation,
}) {
  if (!open) return null;

  // FIX: Destructure map_link from the contact object
  const {
    location_label,
    phone: contactPhone,
    full_name,
    latitude: contactLat,
    longitude: contactLon,
    map_link, // <--- Added identifier here
  } = contact || {};

  const shop =
    retailerMeta?.shop_name ||
    `Retailer ${String(retailerMeta?.id || "").slice(0, 6)}`;

  const area = location_label || retailerMeta?.location_label || "—";
  const phone = contactPhone || "";
  const fullName = full_name || "";

  const waNumber = toWhatsAppNumber(phone);
  const waLink = waNumber ? `https://wa.me/${waNumber}` : "";

  const distanceKm =
    myLocation?.latitude != null &&
    myLocation?.longitude != null &&
    contactLat != null &&
    contactLon != null
      ? haversineKm(
          myLocation.latitude,
          myLocation.longitude,
          contactLat,
          contactLon,
        )
      : null;

  const minutes = estimateMinutes(distanceKm);

  return (
    <div
      className="ex-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Retailer contact info"
      onClick={onClose}
    >
      <div className="ex-modal" onClick={(e) => e.stopPropagation()}>
        <div className="ex-modal-head">
          <div>
            <div className="ex-modal-title">Contact info</div>
            <div className="ex-modal-sub">
              Only shown after a request is accepted.
            </div>
          </div>
          <button
            className="iconbtn"
            type="button"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="ex-modal-body">
          <div className="contact-grid">
            <div className="contact-card">
              <div className="contact-label">Shop</div>
              <div className="contact-value">{shop}</div>
            </div>

            <div className="contact-card">
              <div className="contact-label">Location</div>
              <div className="contact-value">
                {area}
                {/* The Green Button */}
                {map_link && (
                  <a
                    href={map_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn"
                    style={{
                      backgroundColor: "#22c55e", // Green
                      color: "white",
                      padding: "6px 12px",
                      borderRadius: "6px",
                      fontSize: "0.85em",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      textDecoration: "none",
                      whiteSpace: "nowrap",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
                    }}
                  >
                    View on Map 📍
                  </a>
                )}
              </div>

              <div className="contact-help muted" style={{ marginTop: 6 }}>
                {distanceKm && minutes ? (
                  <>
                    📍 {distanceKm.toFixed(1)} km away · 🚗 ~{minutes} min
                  </>
                ) : (
                  <>Distance unavailable</>
                )}
              </div>
            </div>

            <div className="contact-card span2">
              <div className="contact-label">Owner</div>
              <div className="contact-value">
                {fullName || <span className="muted">—</span>}
              </div>
            </div>

            <div className="contact-card span2">
              <div className="contact-label">Phone</div>
              <div className="contact-value">
                {loading ? (
                  <span className="muted">Loading phone number…</span>
                ) : error ? (
                  <span className="muted">{error}</span>
                ) : phone ? (
                  <a className="contact-link" href={`tel:${phone}`}>
                    {phone} (tap to call)
                  </a>
                ) : (
                  <span className="muted">No phone number on file yet.</span>
                )}
              </div>
              <div className="contact-help muted">
                WhatsApp button will open a chat using the correct number
                format.
              </div>
            </div>
          </div>
        </div>

        <div className="ex-modal-actions">
          {phone && !loading && !error ? (
            <a className="btn primary" href={`tel:${phone}`}>
              Call
            </a>
          ) : (
            <button
              className="btn primary"
              type="button"
              disabled
              title="No phone number available"
            >
              Call
            </button>
          )}

          {waLink && !loading && !error ? (
            <a
              className="btn warn"
              href={waLink}
              target="_blank"
              rel="noreferrer"
            >
              Message on WhatsApp
            </a>
          ) : (
            <button
              className="btn warn"
              type="button"
              disabled
              title="WhatsApp number not available"
            >
              Message on WhatsApp
            </button>
          )}

          <button className="btn ghost" type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

/* ===============================
  Small helpers
================================ */
const normalizeSku = (sku) =>
  String(sku || "")
    .trim()
    .replace(/\s+/g, "")
    .toUpperCase();
const toNumber = (v) => {
  if (v === "" || v === null || v === undefined) return NaN;
  const n = Number(String(v).replace(/,/g, "").trim());
  return Number.isFinite(n) ? n : NaN;
};
const toInt = (v) => {
  if (v === "" || v === null || v === undefined) return NaN;
  const n = Number(String(v).trim());
  return Number.isInteger(n) ? n : NaN;
};
const safeLower = (v) =>
  String(v || "")
    .trim()
    .toLowerCase();

// ===============================
// Highlight matched text helper
// ===============================
function highlightMatch(text, query) {
  if (!query || !text) return text;

  const safeText = String(text);
  const safeQuery = String(query).trim();
  if (!safeQuery) return safeText;

  const regex = new RegExp(`(${safeQuery})`, "ig");
  const parts = safeText.split(regex);

  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark key={i} className="highlight">
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

const formatDateTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return "";
  return d.toLocaleString();
};

/* ===============================
  Inventory Picker (searchable dropdown)
================================ */
function InventoryPicker({
  options = [],
  selectedKey,
  onSelect,
  disabled,
  placeholder = "Search your inventory by name or SKU…",
}) {
  const wrapRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");

  const selected = useMemo(
    () => options.find((x) => String(x.key) === String(selectedKey)) || null,
    [options, selectedKey],
  );

  useEffect(() => {
    if (selectedKey == null || selectedKey === "") return;
    setQ("");
    setOpen(false);
  }, [selectedKey]);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return options.slice(0, 30);
    const out = options.filter((o) => {
      return (
        String(o.name || "")
          .toLowerCase()
          .includes(query) ||
        String(o.sku || "")
          .toLowerCase()
          .includes(query) ||
        String(o.category || "")
          .toLowerCase()
          .includes(query)
      );
    });
    return out.slice(0, 30);
  }, [options, q]);

  useEffect(() => {
    const onDown = (e) => {
      if (!wrapRef.current) return;
      if (!wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const renderValue = () => {
    if (!selected) return q;
    return q ? q : `${selected.name} — ${selected.sku}`;
  };

  return (
    <div className={`combo ${disabled ? "disabled" : ""}`} ref={wrapRef}>
      <input
        className="input combo-input"
        value={renderValue()}
        onChange={(e) => {
          setQ(e.target.value);
          if (!open) setOpen(true);
        }}
        onFocus={() => !disabled && setOpen(true)}
        placeholder={placeholder}
        disabled={disabled}
        aria-label="Search inventory"
      />

      {open && !disabled ? (
        <div
          className="combo-pop"
          role="listbox"
          aria-label="Inventory results"
        >
          {filtered.length === 0 ? (
            <div className="combo-empty">
              No matches. Try a different search.
            </div>
          ) : (
            filtered.map((o) => (
              <button
                type="button"
                className="combo-item"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onSelect(o);
                  setQ("");
                  setOpen(false);
                }}
                role="option"
              >
                <div className="combo-main">
                  <div className="combo-name">{o.name}</div>
                  <div className="combo-sub">
                    SKU: {o.sku} • {o.category ?? "—"}
                  </div>
                </div>

                <div className="combo-meta">
                  <span
                    className={`pill ${Number(o.stock ?? 0) <= 0 ? "pill-bad" : ""}`}
                  >
                    In stock: {o.stock}
                  </span>
                </div>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}

/* ===============================
   Generic Searchable Select
================================ */
function SearchableSelect({
  options = [],
  value,
  onChange,
  placeholder = "Search...",
  disabled = false,
  getLabel = (o) => o.label,
  getValue = (o) => o.value,
}) {
  const wrapRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const selectedOption = options.find(
    (o) => String(getValue(o)) === String(value),
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options.slice(0, 20);

    return options
      .filter((o) => getLabel(o).toLowerCase().includes(q))
      .slice(0, 20);
  }, [options, query, getLabel]);

  useEffect(() => {
    const onClickOutside = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  return (
    <div ref={wrapRef} className={`combo ${disabled ? "disabled" : ""}`}>
      <input
        className="input combo-input"
        value={query || (selectedOption ? getLabel(selectedOption) : "")}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => {
          setQuery(e.target.value);
          if (!open) setOpen(true);
        }}
        onFocus={() => !disabled && setOpen(true)}
      />

      {open && !disabled && (
        <div className="combo-pop">
          {filtered.length === 0 ? (
            <div className="combo-empty">No matches</div>
          ) : (
            filtered.map((o) => (
              <button
                type="button"
                className="combo-item"
                onClick={() => {
                  onChange(getValue(o));
                  setQuery("");
                  setOpen(false);
                }}
              >
                {getLabel(o)}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

/* ===============================
  Listing Modal (Sell a product + Edit listing)
================================ */
function ListingModal({
  open,
  onClose,
  sending,
  categoryOptions = [],
  inventoryOptions = [],
  listingName,
  setListingName,
  listingSku,
  setListingSku,
  listingCategory,
  setListingCategory,
  listingStock,
  setListingStock,
  listingPrice,
  setListingPrice,
  selectedInvKey,
  setSelectedInvKey,
  selectedInvStock,
  setSelectedInvStock,
  selectedInvPrice,
  setSelectedInvPrice,
  isEditingListing,
  onSubmit,
  onClear,
  showAddCategory,
  setShowAddCategory,
  newCategory,
  setNewCategory,
  sellCategoryOptions = [],
  setExtraCategories,
}) {
  const ADD_NEW = "__add_new__";
  const [categoryMode, setCategoryMode] = useState("select"); // select | custom
  const [categorySelect, setCategorySelect] = useState("");
  const [categoryCustom, setCategoryCustom] = useState("");
  const [stockError, setStockError] = useState("");

  const hasPickedInventory =
    selectedInvKey != null && String(selectedInvKey).trim() !== "";

  useEffect(() => {
    if (!open) return;
    setStockError("");
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (selectedInvKey == null || selectedInvKey === "") return;

    const picked = (inventoryOptions ?? []).find(
      (x) => String(x.key) === String(selectedInvKey),
    );

    if (!picked) return;

    setListingName(picked.name ?? "");
    setListingSku(picked.sku ?? "");
    setListingCategory(picked.category ?? "");
    setSelectedInvStock(Number(picked.stock ?? 0));
    setSelectedInvPrice(Number(picked.price ?? NaN));

    // Only clear quantity when creating a new listing.
    // In edit mode, keep the existing listing quantity that openEditListing already set.
    if (!isEditingListing) {
      setListingStock("");
    }

    setStockError("");
  }, [
    open,
    selectedInvKey,
    inventoryOptions,
    isEditingListing,
    setListingName,
    setListingSku,
    setListingCategory,
    setSelectedInvStock,
    setSelectedInvPrice,
    setListingStock,
  ]);

  useEffect(() => {
    if (!open) return;

    const initCat = String(listingCategory || "").trim();
    const hasInOptions = initCat && categoryOptions.includes(initCat);

    setCategoryMode(hasInOptions || !initCat ? "select" : "custom");
    setCategorySelect(hasInOptions ? initCat : "");
    setCategoryCustom(!hasInOptions ? initCat : "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, listingCategory, categoryOptions.join("|")]);

  const onCategoryChange = (val) => {
    if (val === ADD_NEW) {
      setCategoryMode("custom");
      setCategorySelect("");
      setCategoryCustom("");
      setListingCategory("");
      return;
    }
    setCategoryMode("select");
    setCategorySelect(val);
    setCategoryCustom("");
    setListingCategory(val);
  };

  const onCustomCategoryChange = (val) => {
    setCategoryCustom(val);
    setListingCategory(val);
  };

  const handlePickInventory = (o) => {
    setSelectedInvKey(o.key);
    setSelectedInvStock(Number(o.stock ?? 0));
    setSelectedInvPrice(Number(o.price ?? NaN));
    setListingName(o.name ?? "");
    setListingSku(o.sku ?? "");
    setListingCategory(o.category ?? "");
    setListingStock("");
    setStockError("");
  };

  const onStockChange = (val) => {
    setListingStock(val);

    const n = toInt(val);
    if (!Number.isFinite(n)) {
      setStockError("");
      return;
    }
    if (n < 0) {
      setStockError("Quantity must be 0 or more.");
      return;
    }

    const max = Number.isFinite(selectedInvStock)
      ? Number(selectedInvStock)
      : null;
    if (max != null && n > max) {
      setStockError(`You can’t list ${n} — you only have ${max} in inventory.`);
      return;
    }

    setStockError("");
  };

  if (!open) return null;

  const title = isEditingListing ? "Edit listing" : "Sell a product";
  const sub =
    "List a product so other retailers can buy it from Available Products.";

  return (
    <div
      className="ex-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
    >
      <div
        className="ex-modal ex-modal-wide"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="ex-modal-head">
          <div>
            <div className="ex-modal-title">{title}</div>
            <div className="ex-modal-sub">{sub}</div>
          </div>
          <button
            className="iconbtn"
            type="button"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="ex-modal-body">
          <form className="form" onSubmit={onSubmit}>
            <div className="field span-2">
              <label>Pick from your inventory</label>
              <InventoryPicker
                options={inventoryOptions}
                selectedKey={selectedInvKey}
                onSelect={handlePickInventory}
                disabled={sending}
                placeholder="Search your inventory by name or SKU…"
              />
              <div className="help-row">
                <span className="muted">
                  Select a product first to activate and auto-fill other fields.
                </span>
                {Number.isFinite(selectedInvStock) ? (
                  <span className="pill subtle">
                    Available: {selectedInvStock}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="field">
              <label>Product name</label>
              <input
                className="input"
                value={listingName}
                onChange={(e) => setListingName(e.target.value)}
                placeholder="Auto-filled from inventory"
                readOnly
                disabled={!hasPickedInventory || sending}
              />
            </div>

            <div className="field">
              <label>SKU</label>
              <input
                className="input"
                value={listingSku}
                onChange={(e) => setListingSku(e.target.value)}
                placeholder="Auto-filled from inventory"
                readOnly
                disabled={!hasPickedInventory || sending}
              />
            </div>

            <div className="field">
              <label htmlFor="s_category">Category</label>

              <select
                className="input"
                value={listingCategory}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === "__add_cat__") {
                    setShowAddCategory(true);
                    setNewCategory("");
                    return;
                  }
                  setListingCategory(val);
                }}
                disabled={!hasPickedInventory || sending}
              >
                <option value="">Select a category</option>
                {categoryOptions.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
                <option value="__add_cat__">+ Add a new category…</option>
              </select>
              {/* Graphical "New Category" Input Slide-in */}
              {showAddCategory && (
                <div
                  className="category-new-panel"
                  style={{
                    marginTop: 12,
                    padding: 12,
                    background: "#f8fafc",
                    borderRadius: 8,
                    border: "1px dashed #cbd5e1",
                  }}
                >
                  <div style={{ display: "flex", gap: 10 }}>
                    <input
                      className="input"
                      autoFocus
                      value={newCategory}
                      onChange={(e) => setNewCategory(e.target.value)}
                      placeholder="e.g. Beverages"
                      disabled={sending}
                    />
                    <button
                      type="button"
                      className="btn primary small"
                      disabled={sending || !newCategory.trim()}
                      onClick={() => {
                        const c = newCategory.trim();
                        // Check if it already exists (case insensitive)
                        const exists = sellCategoryOptions.some(
                          (opt) => opt.toLowerCase() === c.toLowerCase(),
                        );

                        if (!exists) {
                          setExtraCategories((prev) => [...prev, c]);
                        }
                        setListingCategory(c);
                        setShowAddCategory(false);
                      }}
                    >
                      Add
                    </button>
                    <button
                      type="button"
                      className="btn ghost small"
                      onClick={() => setShowAddCategory(false)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="field">
              <label>Quantity available</label>
              <input
                className="input"
                type="number"
                min="0"
                max={
                  Number.isFinite(selectedInvStock)
                    ? Number(selectedInvStock)
                    : undefined
                }
                value={listingStock}
                onChange={(e) => onStockChange(e.target.value)}
                placeholder={
                  Number.isFinite(selectedInvStock)
                    ? `Max ${selectedInvStock}`
                    : "Select inventory first"
                }
                disabled={!hasPickedInventory || sending}
              />
              {stockError ? (
                <div className="inline-warn">{stockError}</div>
              ) : null}
            </div>

            {Number.isFinite(selectedInvPrice) ? (
              <div className="help-row">
                <span className="pill subtle">
                  Current price per unit (AED): AED{" "}
                  {Number(selectedInvPrice).toFixed(2)}
                </span>
              </div>
            ) : null}

            <div className="field span-2">
              <label>Price per unit (AED)</label>
              <input
                className="input"
                type="number"
                min="0"
                step="0.01"
                value={listingPrice}
                onChange={(e) => setListingPrice(e.target.value)}
                placeholder={
                  hasPickedInventory ? "e.g., 4.00" : "Select inventory first"
                }
                disabled={!hasPickedInventory || sending}
              />
            </div>

            <div className="form-actions span-2">
              <button
                className="btn ghost"
                type="button"
                onClick={onClear}
                disabled={sending}
              >
                Clear
              </button>
              <button
                className="btn primary"
                type="submit"
                disabled={sending || !!stockError}
              >
                {sending
                  ? "Saving..."
                  : isEditingListing
                    ? "Save Changes"
                    : "Post Listing"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

/* ===============================
  Buy from listing modal
================================ */
function BuyListingModal({
  open,
  onClose,
  listing,
  maxQty,
  sending,
  qty,
  setQty,
  note,
  setNote,
  onSubmit,
}) {
  if (!open) return null;

  return (
    <div
      className="ex-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Buy from listing"
      onClick={onClose}
    >
      <div
        className="ex-modal ex-modal-wide"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="ex-modal-head">
          <div>
            <div className="ex-modal-title">Buy this product</div>
            <div className="ex-modal-sub">
              Choose a quantity. You can’t exceed available stock.
            </div>
          </div>
          <button
            className="iconbtn"
            type="button"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="ex-modal-body">
          <div className="buy-card">
            <div className="buy-title">{listing?.name}</div>
            <div className="buy-sub muted">
              SKU: {listing?.sku} • {listing?.category} • Seller:{" "}
              {listing?.retailer_shop}
            </div>

            <form className="form buy-form" onSubmit={onSubmit}>
              <div className="field">
                <label htmlFor="b_qty">Quantity</label>
                <input
                  id="b_qty"
                  className="input"
                  type="number"
                  min="1"
                  max={maxQty}
                  value={qty}
                  onChange={(e) => setQty(e.target.value)}
                  placeholder={`Max ${maxQty}`}
                />
                <div className="help-row" style={{ marginTop: 6 }}>
                  <span className="muted">Available right now: {maxQty}</span>
                </div>
              </div>

              <div className="field">
                <label htmlFor="b_note">Note (optional)</label>
                <input
                  id="b_note"
                  className="input"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g., Can pick up now"
                />
              </div>

              <div
                className="form-actions span-2"
                style={{ justifyContent: "flex-end" }}
              >
                <button
                  className="btn ghost"
                  type="button"
                  onClick={onClose}
                  disabled={sending}
                >
                  Cancel
                </button>
                <button
                  className="btn primary"
                  type="submit"
                  disabled={sending}
                >
                  {sending ? "Sending..." : "Send request"}
                </button>
              </div>

              <div className="hint-row span-2" style={{ marginTop: 8 }}>
                <span className="status warn">Tip</span>
                <p className="hint-text">
                  This request will appear under{" "}
                  <strong>Manage my requests</strong> with status{" "}
                  <strong>Pending vendor approval</strong>.
                </p>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ===============================
  Page
================================ */
export default function ExchangePage() {
  const { user, profile, loading, signOut } = useAuth();
  const navigate = useNavigate();
  // TEMP: expose supabase for console debugging (remove after)
  useEffect(() => {
    window.supabase = supabase;
  }, []);

  const handleLogout = async () => {
    await signOut();
    navigate("/login");
  };

  const [retailerId, setRetailerId] = useState(null);
  const [retailerIdLoading, setRetailerIdLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        setRetailerIdLoading(true);

        if (profile?.retailer_id) {
          if (!cancelled) setRetailerId(profile.retailer_id);
          return;
        }

        if (user?.id) {
          const { data, error } = await supabase
            .from("retailer_profiles")
            .select("id")
            .eq("user_id", user.id)
            .maybeSingle();
          if (!error && data?.id) {
            if (!cancelled) setRetailerId(data.id);
            return;
          }
        }

        if (user?.id) {
          const { data, error } = await supabase
            .from("retailer_profiles")
            .select("id")
            .eq("id", user.id)
            .maybeSingle();
          if (!error && data?.id) {
            if (!cancelled) setRetailerId(data.id);
            return;
          }
        }

        if (!cancelled) setRetailerId(null);
      } finally {
        if (!cancelled) setRetailerIdLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [user?.id, profile?.retailer_id]);

  const displayName =
    profile?.full_name ||
    user?.user_metadata?.full_name ||
    user?.email ||
    "there";
  const role = profile?.role || "User";

  const [selectedCategory, setSelectedCategory] = useState("All");
  const [selectedCity, setSelectedCity] = useState("All");
  const [searchQuery, setSearchQuery] = useState("");

  /* ===============================
    Main mode + sub tabs
  ================================ */
  const [mode, setMode] = useState("buy"); // buy | sell
  const [buyTab, setBuyTab] = useState("buy_product"); // buy_product | available_products | manage_requests
  const [sellTab, setSellTab] = useState("sell_product"); // sell_product | view_requests | manage_listings

  /* ===============================
    Retailers + locations
  ================================ */
  const [retailers, setRetailers] = useState([]);
  const [retailersLoading, setRetailersLoading] = useState(true);
  const [retailersError, setRetailersError] = useState("");

  const [retailerLocations, setRetailerLocations] = useState({}); // { [retailer_id]: { latitude, longitude } }
  const [myLocation, setMyLocation] = useState(null);
  const [retailerGeoMeta, setRetailerGeoMeta] = useState({});
  const [claimedTotals, setClaimedTotals] = useState({});

  /* ===============================
    Listings
  ================================ */
  const [marketListings, setMarketListings] = useState([]);
  const [marketLoading, setMarketLoading] = useState(true);
  const [marketError, setMarketError] = useState("");

  const [myListings, setMyListings] = useState([]);
  const [myLoading, setMyLoading] = useState(true);
  const [myError, setMyError] = useState("");

  /* ===============================
    Requests (single source of truth)
    - buyer side: from_retailer_id = me
    - seller side: to_retailer_id = me OR open requests where to_retailer_id is null
  ================================ */
  const [myRequests, setMyRequests] = useState([]);
  const [myListingsCount, setMyListingsCount] = useState(0);
  const [myReqLoading, setMyReqLoading] = useState(true);
  const [myReqError, setMyReqError] = useState("");

  const [sellerRequests, setSellerRequests] = useState([]);
  const [sellerReqLoading, setSellerReqLoading] = useState(true);
  const [sellerReqError, setSellerReqError] = useState("");
  const [dismissedOpenIds, setDismissedOpenIds] = useState([]);

  /* ===============================
    Contact modal state
  ================================ */
  const [contactOpen, setContactOpen] = useState(false);
  const [contactRetailerId, setContactRetailerId] = useState(null);
  const [contactLoading, setContactLoading] = useState(false);
  const [contactError, setContactError] = useState("");
  const [contactInfo, setContactInfo] = useState(null);

  const contactRetailerMeta = useMemo(
    () =>
      retailers.find((r) => String(r.id) === String(contactRetailerId)) || null,
    [retailers, contactRetailerId],
  );

  /* ===============================
    Inventory options for listing modal
  ================================ */
  const [inventoryOptions, setInventoryOptions] = useState([]);
  const [invLoading, setInvLoading] = useState(false);
  const [invError, setInvError] = useState("");

  /* ===============================
    Listing modal state
  ================================ */
  const [listingOpen, setListingOpen] = useState(false);
  const [sending, setSending] = useState(false);

  const [listingName, setListingName] = useState("");
  const [listingSku, setListingSku] = useState("");
  const [listingCategory, setListingCategory] = useState("");
  const [listingStock, setListingStock] = useState("");
  const [listingPrice, setListingPrice] = useState("");

  const [selectedInvKey, setSelectedInvKey] = useState(null);
  const [selectedInvStock, setSelectedInvStock] = useState(NaN);
  const [selectedInvPrice, setSelectedInvPrice] = useState(NaN);

  const [extraCategories, setExtraCategories] = useState([]);
  const [newCategoryInput, setNewCategoryInput] = useState("");

  const [editingListingId, setEditingListingId] = useState(null);
  const [editingIsActive, setEditingIsActive] = useState(true);
  const isEditingListing = !!editingListingId;

  const ADD_NEW = "__add_new__";
  const ADD_NEW_CATEGORY = "_add_new_";

  const [categoryMode, setCategoryMode] = useState("select"); // select | custom
  const [categorySelect, setCategorySelect] = useState("");
  const [categoryCustom, setCategoryCustom] = useState("");
  const [stockError, setStockError] = useState("");

  const [showAddCategory, setShowAddCategory] = useState(false);
  const [newCategory, setNewCategory] = useState("");
  /* ===============================
    Buy a product form (open request)
  ================================ */
  const [buyProductName, setBuyProductName] = useState("");
  const [buyQty, setBuyQty] = useState("");
  const [buyMaxPrice, setBuyMaxPrice] = useState("");
  const [buyNote, setBuyNote] = useState("");

  /* ===============================
    Buy from listing modal
  ================================ */
  const [buyListingOpen, setBuyListingOpen] = useState(false);
  const [buyListingTarget, setBuyListingTarget] = useState(null);
  const [buyListingQty, setBuyListingQty] = useState("");
  const [buyListingNote, setBuyListingNote] = useState("");
  const autoOpenedSellRef = useRef(false);

  // ===============================
  // Buy → Available Products filters (NEW)
  // ===============================
  const [buyNameQuery, setBuyNameQuery] = useState("");
  const [buyCategory, setBuyCategory] = useState("All");
  const [buyCountry, setBuyCountry] = useState("All");
  const [buyState, setBuyState] = useState("All");
  const [buyDateFrom, setBuyDateFrom] = useState("");
  const [buyDateTo, setBuyDateTo] = useState("");

  // ===============================
  // Sell → View Requests filters (NEW)
  // ===============================
  const [sellProductQuery, setSellProductQuery] = useState("");
  const [sellBuyerQuery, setSellBuyerQuery] = useState("");
  const [sellStatus, setSellStatus] = useState("All");
  const [sellCountry, setSellCountry] = useState("All");
  const [sellState, setSellState] = useState("All");
  const [sellDateRange, setSellDateRange] = useState("All");
  const [sellDateFrom, setSellDateFrom] = useState("");
  const [sellDateTo, setSellDateTo] = useState("");

  // ===============================
  // INLINE SELL FORM handlers (Fix category + quantity)
  // ===============================
  const onCategoryChange = (val) => {
    if (val === ADD_NEW_CATEGORY) {
      setCategoryMode("custom");
      setCategorySelect("");
      setCategoryCustom("");
      setListingCategory("");
      return;
    }

    setCategoryMode("select");
    setCategorySelect(val);
    setCategoryCustom("");
    setListingCategory(val);
  };

  const onCustomCategoryChange = (val) => {
    setCategoryCustom(val);
    setListingCategory(val);
  };

  const onStockChange = (val) => {
    setListingStock(val);

    const n = toInt(val);
    if (!Number.isFinite(n)) {
      setStockError("");
      return;
    }
    if (n < 0) {
      setStockError("Quantity must be 0 or more.");
      return;
    }

    const max = Number.isFinite(selectedInvStock)
      ? Number(selectedInvStock)
      : null;
    if (max != null && n > max) {
      setStockError(`You can’t list ${n} — you only have ${max} in inventory.`);
      return;
    }

    setStockError("");
  };

  const q = searchQuery.trim().toLowerCase();
  const match = (text) =>
    String(text || "")
      .toLowerCase()
      .includes(q);

  /* ===============================
    Supabase loaders
  ================================ */
  const loadRetailers = async () => {
    setRetailersError("");
    setRetailersLoading(true);

    const { data, error } = await supabase
      .from("retailer_profiles")
      .select("id, shop_name, store_id")
      .order("shop_name", { ascending: true });

    if (error) {
      setRetailersError(error.message || "Failed to load retailers.");
      setRetailers([]);
      setRetailersLoading(false);
      return;
    }

    const list = (data || []).map((r) => ({
      id: r.id,
      shop_name: r.shop_name,
      store_id: r.store_id,
      area: r.store_id || "—",
    }));
    setRetailers(list);
    setRetailersLoading(false);
  };

  const loadRetailerLocations = async () => {
    try {
      const { data, error } = await supabase
        .from("retailer_locations")
        .select("retailer_id, latitude, longitude,map_link")
        .eq("is_primary", true);
      if (error) throw error;

      const map = {};
      (data || []).forEach((r) => {
        if (
          r?.retailer_id != null &&
          r?.latitude != null &&
          r?.longitude != null
        ) {
          map[String(r.retailer_id)] = {
            latitude: r.latitude,
            longitude: r.longitude,
            map_link: r.map_link, // <--- Add this line
          };
        }
      });

      setRetailerLocations(map);
    } catch {
      setRetailerLocations({});
    }
  };

  const loadClaimedTotals = async () => {
    try {
      const { data, error } = await supabase
        .from("exchange_requests")
        .select("listing_id, quantity, status, request_kind")
        .not("listing_id", "is", null)
        .eq("request_kind", "listing")
        .in("status", ["pending_vendor_approval", "accepted"]);

      if (error) throw error;

      const map = {};
      (data ?? []).forEach((r) => {
        const id = String(r.listing_id);
        map[id] = (map[id] ?? 0) + Number(r.quantity ?? 0);
      });

      setClaimedTotals(map);
    } catch (e) {
      console.error("Failed to load claimed totals:", e);
      setClaimedTotals({});
    }
  };

  const loadRetailerGeoMeta = async () => {
    try {
      const { data, error } = await supabase
        .from("retailer_locations")
        .select("retailer_id, city, state, country")
        .eq("is_primary", true);

      if (error) throw error;

      const map = {};
      (data || []).forEach((row) => {
        map[String(row.retailer_id)] = {
          city: row.city || "",
          state: row.state || "",
          country: row.country || "",
        };
      });

      setRetailerGeoMeta(map);
    } catch {
      setRetailerGeoMeta({});
    }
  };

  const loadMyLocation = async () => {
    if (!retailerId) return;
    try {
      const { data, error } = await supabase
        .from("retailer_locations")
        .select("latitude, longitude")
        .eq("retailer_id", retailerId)
        .eq("is_primary", true)
        .maybeSingle();

      if (error) throw error;

      if (data?.latitude != null && data?.longitude != null)
        setMyLocation({ latitude: data.latitude, longitude: data.longitude });
      else setMyLocation(null);
    } catch {
      setMyLocation(null);
    }
  };

  const loadMarketplaceListings = async () => {
    setMarketError("");
    setMarketLoading(true);

    try {
      let query = supabase
        .from("retailer_listings")
        .select(
          `
          id,
          retailer_id,
          product_id,
          price,
          stock,
          is_active,
          created_at,
          product:products!inner (
            id,
            sku,
            name,
            category
          ),
          retailer:retailer_profiles!inner (
            id,
            shop_name,
            retailer_locations!inner (
              city,
              state,
              country
            )
          )
        `,
        )
        .eq("is_active", true)
        .gt("stock", 0)
        .order("created_at", { ascending: false });

      // ✅ ONLY exclude own listings if retailerId is known
      if (retailerId) {
        query = query.neq("retailer_id", retailerId);
      }

      const { data, error } = await query;
      if (error) throw error;

      const rows = (data || []).map((r) => {
        const loc = r.retailer?.retailer_locations?.[0] || {};
        return {
          id: r.id,
          retailer_id: r.retailer_id,
          retailer_shop: r.retailer?.shop_name || null,
          product_id: r.product_id,
          name: r.product?.name || "Unnamed product",
          sku: r.product?.sku || r.product_id,
          category: r.product?.category || "—",
          price: Number(r.price ?? 0),
          stock: Number(r.stock ?? 0),
          created_at: r.created_at,
          city: loc.city || "",
          state: loc.state || "",
          country: loc.country || "",
          location: [loc.city, loc.state, loc.country]
            .filter(Boolean)
            .join(", "),
        };
      });

      setMarketListings(rows);
    } catch (err) {
      setMarketError(err.message || "Failed to load marketplace listings.");
      setMarketListings([]);
    } finally {
      setMarketLoading(false);
    }
  };

  const loadMyListings = async () => {
    if (!retailerId) {
      setMyLoading(false);
      return;
    }

    setMyError("");
    setMyLoading(true);

    const { data, error } = await supabase
      .from("retailer_listings")
      .select(
        `
        id,
        retailer_id,
        product_id,
        price,
        stock,
        is_active,
        updated_at,
        product:products ( id, sku, name, category )
      `,
      )
      .eq("retailer_id", retailerId)
      .order("updated_at", { ascending: false });

    if (error) {
      setMyError(error.message || "Failed to load your listings.");
      setMyListings([]);
      setMyLoading(false);
      return;
    }

    const rows = (data || []).map((r) => ({
      id: r.id,
      retailer_id: r.retailer_id,
      product_id: r.product_id,
      name: r.product?.name || "Unnamed product",
      sku: r.product?.sku || r.product_id,
      category: r.product?.category || "—",
      price: Number(r.price ?? 0),
      stock: Number(r.stock ?? 0),
      is_active: !!r.is_active,
      updated_at: r.updated_at,
    }));

    setMyListings(rows);
    setMyListingsCount(data.length);
    setMyLoading(false);
  };

  // Buyer-side: ONLY requests I created
  const loadMyRequests = async () => {
    if (!retailerId) {
      setMyReqLoading(false);
      return;
    }

    setMyReqError("");
    setMyReqLoading(true);

    const { data, error } = await supabase
      .from("exchange_requests")
      .select(
        `
        id,
        from_retailer_id,
        to_retailer_id,
        product_name,
        quantity,
        max_price,
        note,
        status,
        request_kind,
        listing_id,
        buyer_completed,
        seller_completed,
        created_at
      `,
      )
      .eq("from_retailer_id", retailerId)
      .neq("status", "completed")
      .order("created_at", { ascending: false });

    if (error) {
      setMyReqError(error.message || "Could not load your requests.");
      setMyRequests([]);
      setMyReqLoading(false);
      return;
    }

    setMyRequests(data || []);
    setMyReqLoading(false);
  };

  // Seller-side view:
  // - listing requests aimed at me: to_retailer_id = me
  // - open requests not yet matched: to_retailer_id is null AND from_retailer_id != me
  const loadSellerRequests = async () => {
    if (!retailerId) {
      setSellerReqLoading(false);
      return;
    }

    setSellerReqError("");
    setSellerReqLoading(true);

    // matched-to-me (listing + open accepted/declined)
    const mine = await supabase
      .from("exchange_requests")
      .select(
        `
        id,
        from_retailer_id,
        to_retailer_id,
        product_name,
        quantity,
        max_price,
        note,
        status,
        request_kind,
        listing_id,
        buyer_completed,
        seller_completed,
        created_at
      `,
      )
      .eq("to_retailer_id", retailerId)
      .order("created_at", { ascending: false });

    // open requests not matched yet
    const open = await supabase
      .from("exchange_requests")
      .select(
        `
        id,
        from_retailer_id,
        to_retailer_id,
        product_name,
        quantity,
        max_price,
        note,
        status,
        request_kind,
        listing_id,
        buyer_completed,
        seller_completed,
        created_at
      `,
      )
      .is("to_retailer_id", null)
      .eq("request_kind", "open")
      .in("status", ["requested", "accepted"])
      .order("created_at", { ascending: false });

    if (mine.error || open.error) {
      setSellerReqError(
        mine.error?.message ||
          open.error?.message ||
          "Could not load requests.",
      );
      setSellerRequests([]);
      setSellerReqLoading(false);
      return;
    }

    // keep ONLY:
    // - open requests from other retailers (status requested)
    // - mine requests (any status)
    const openRows = (open.data || []).filter(
      (r) => String(r.from_retailer_id) !== String(retailerId),
    );
    const rows = [...(mine.data || []), ...openRows];

    // de-dupe in case weird overlaps
    const uniq = new Map();
    rows.forEach((r) => uniq.set(String(r.id), r));

    setSellerRequests(Array.from(uniq.values()));
    setSellerReqLoading(false);
  };

  const loadMyInventoryOptions = async () => {
    if (!retailerId) return [];
    setInvError("");
    setInvLoading(true);

    try {
      const { data: activeConn, error: connErr } = await supabase
        .from("pos_connections")
        .select("id")
        .eq("retailer_id", retailerId)
        .eq("is_active", true)
        .maybeSingle();

      if (connErr) throw connErr;

      const activePosConnectionId = activeConn?.id ?? null;

      if (!activePosConnectionId) {
        setInventoryOptions([]);
        return [];
      }

      const { data, error } = await supabase
        .from("products")
        .select(
          `
          id,
          name,
          category,
          retailer_id,
          product_variations (
            id,
            sku,
            price,
            active,
            pos_connection_id,
            product_inventory ( quantity )
          )
        `,
        )
        .eq("retailer_id", retailerId)
        .eq("active", true)
        .order("id", { ascending: false });

      if (error) throw error;

      const rows = [];
      (data ?? []).forEach((product) => {
        (product.product_variations ?? []).forEach((v) => {
          if (v?.active === false) return;
          if (String(v?.pos_connection_id) !== String(activePosConnectionId))
            return;

          rows.push({
            key: v.id,
            variation_id: v.id,
            product_id: product.id,
            name: product.name,
            category: product.category,
            sku: v.sku,
            price: Number(v.price ?? 0),
            stock: Number(v.product_inventory?.[0]?.quantity ?? 0),
          });
        });
      });

      rows.sort((a, b) => {
        const ai = (a.stock ?? 0) > 0 ? 0 : 1;
        const bi = (b.stock ?? 0) > 0 ? 0 : 1;
        if (ai !== bi) return ai - bi;
        return String(a.name ?? "").localeCompare(String(b.name ?? ""));
      });

      setInventoryOptions(rows);
      return rows;
    } catch (e) {
      setInventoryOptions([]);
      setInvError(e?.message ?? "Failed to load your inventory options.");
      return [];
    } finally {
      setInvLoading(false);
    }
  };
  const loadMyDismissedOpen = async () => {
    if (!retailerId) return;

    const { data, error } = await supabase
      .from("exchange_request_dismissals")
      .select("request_id")
      .eq("retailer_id", retailerId);

    if (error) {
      setDismissedOpenIds([]);
      return;
    }

    setDismissedOpenIds((data || []).map((r) => String(r.request_id)));
  };

  /* ===============================
    Effects + realtime
  ================================ */
  useEffect(() => {
    if (!user) return;

    loadRetailers();
    loadRetailerLocations();
    loadMarketplaceListings();
    loadRetailerGeoMeta();
    loadClaimedTotals();

    if (!retailerIdLoading && retailerId) {
      loadMyLocation();
      loadMyListings();
      loadMyRequests();
      loadSellerRequests();
      loadMyInventoryOptions();
      loadMyDismissedOpen();
    }

    const ch = supabase
      .channel("exchange_market_live_v2")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "retailer_profiles" },
        () => loadRetailers(),
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "retailer_locations" },
        () => {
          loadRetailerLocations();
          loadRetailerGeoMeta();
          if (!retailerIdLoading && retailerId) loadMyLocation();
        },
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "retailer_listings" },
        () => {
          loadMarketplaceListings();
          if (!retailerIdLoading && retailerId) loadMyListings();
        },
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "products" },
        () => {
          loadMarketplaceListings();
          if (!retailerIdLoading && retailerId) {
            loadMyListings();
            loadMyInventoryOptions();
          }
        },
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "product_variations" },
        () => {
          if (!retailerIdLoading && retailerId) loadMyInventoryOptions();
        },
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "product_inventory" },
        () => {
          if (!retailerIdLoading && retailerId) loadMyInventoryOptions();
        },
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "exchange_requests" },
        () => {
          if (!retailerIdLoading && retailerId) {
            loadMyRequests();
            loadSellerRequests();
            loadMarketplaceListings();
          }
          loadClaimedTotals();
        },
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "exchange_request_dismissals" },
        () => {
          if (!retailerIdLoading && retailerId) {
            loadMyDismissedOpen();
          }
        },
      )
      .subscribe();

    return () => supabase.removeChannel(ch);
  }, [user, retailerId, retailerIdLoading]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const modeParam = params.get("mode");

    if (modeParam === "sell") {
      setMode("sell");
      setSellTab("sell_product");
    }

    if (modeParam === "buy") {
      setMode("buy");
      setBuyTab("buy_product");
    }
  }, [location.search]);

  useEffect(() => {
    setMyRequests([]);
    setMyReqError("");
    setMyReqLoading(true);

    setSellerRequests([]);
    setSellerReqError("");
    setSellerReqLoading(true);
  }, [retailerId]);

  useEffect(() => {
    // no auto-open for Sell form
  }, [mode, sellTab, retailerId, retailerIdLoading]);
  /* ===============================
    Derived helpers
  ================================ */
  const prettyRetailerName = (id) => {
    const r = retailers.find((x) => String(x.id) === String(id));
    return r?.shop_name || `Retailer ${String(id).slice(0, 6)}`;
  };

  const categoryOptions = useMemo(() => {
    const set = new Set();
    (marketListings || []).forEach((r) => {
      const c = r?.category;
      if (c && c !== "—") set.add(c);
    });
    (myListings || []).forEach((r) => {
      const c = r?.category;
      if (c && c !== "—") set.add(c);
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [marketListings, myListings]);

  useEffect(() => {
    const initCat = String(listingCategory || "").trim();
    const hasInOptions = initCat && categoryOptions.includes(initCat);

    setCategoryMode(hasInOptions || !initCat ? "select" : "custom");
    setCategorySelect(hasInOptions ? initCat : "");
    setCategoryCustom(!hasInOptions ? initCat : "");
  }, [listingCategory, categoryOptions]);

  const marketListingsSortedByDistance = useMemo(() => {
    const base = marketListings || [];

    const myLat = myLocation?.latitude;
    const myLon = myLocation?.longitude;
    const canCalcMine = myLat != null && myLon != null;

    const withDistance = base.map((p, idx) => {
      const loc = retailerLocations?.[String(p.retailer_id)];
      const hasSeller = loc?.latitude != null && loc?.longitude != null;
      const dist =
        canCalcMine && hasSeller
          ? haversineKm(myLat, myLon, loc.latitude, loc.longitude)
          : null;
      return { ...p, _distanceKm: dist, _idx: idx };
    });

    withDistance.sort((a, b) => {
      const da = a._distanceKm;
      const db = b._distanceKm;

      const aHas = Number.isFinite(da);
      const bHas = Number.isFinite(db);

      if (aHas && bHas) {
        if (da !== db) return da - db;
        return a._idx - b._idx;
      }
      if (aHas && !bHas) return -1;
      if (!aHas && bHas) return 1;
      return a._idx - b._idx;
    });

    return withDistance;
  }, [marketListings, myLocation, retailerLocations]);

  // claimed/reserved per listing from requests tied to a listing and not finished/declined
  const claimedByListingId = useMemo(() => {
    const map = {};
    (myRequests || []).forEach((r) => {
      if (!r?.listing_id) return;
      const st = safeLower(r.status);
      if (st === "declined" || st === "completed") return;
      const id = String(r.listing_id);
      map[id] = (map[id] || 0) + Number(r.quantity || 0);
    });
    // Also include other buyers requests to a listing (sellerRequests contains those for my listings; but for market view we need all,
    // so best-effort: include sellerRequests too because that covers my listings; for others we won't have global per listing without a query)
    (sellerRequests || []).forEach((r) => {
      if (!r?.listing_id) return;
      const st = safeLower(r.status);
      if (st === "declined" || st === "completed") return;
      const id = String(r.listing_id);
      map[id] = (map[id] || 0) + Number(r.quantity || 0);
    });
    return map;
  }, [myRequests, sellerRequests]);

  const filteredAvailableProducts = useMemo(() => {
    let list = marketListingsSortedByDistance ?? [];

    // Product name filter
    if (buyNameQuery) {
      list = list.filter((p) =>
        String(p.name ?? "")
          .toLowerCase()
          .includes(buyNameQuery.toLowerCase()),
      );
    }

    // Category filter
    if (buyCategory && buyCategory !== "All") {
      list = list.filter((p) => p.category === buyCategory);
    }

    // Country filter
    if (buyCountry && buyCountry !== "All") {
      list = list.filter((p) => p.country === buyCountry);
    }

    // State filter
    if (buyState && buyState !== "All") {
      list = list.filter((p) => p.state === buyState);
    }

    // Date range filter
    if (buyDateFrom) {
      const from = new Date(`${buyDateFrom}T00:00:00`);
      list = list.filter((p) => {
        const created = new Date(p.created_at);
        return Number.isFinite(created.getTime()) && created >= from;
      });
    }

    if (buyDateTo) {
      const to = new Date(`${buyDateTo}T23:59:59`);
      list = list.filter((p) => {
        const created = new Date(p.created_at);
        return Number.isFinite(created.getTime()) && created <= to;
      });
    }

    // NEW: remove listings that have no effective available quantity left
    list = list.filter((p) => {
      const claimed = Number(claimedTotals[String(p.id)] ?? 0);
      const total = Number(p.stock ?? 0);
      const available = Math.max(0, total - claimed);
      return available > 0;
    });

    return list;
  }, [
    marketListingsSortedByDistance,
    buyNameQuery,
    buyCategory,
    buyCountry,
    buyState,
    buyDateFrom,
    buyDateTo,
    claimedTotals,
  ]);

  const filteredMyListings = useMemo(() => {
    if (!q) return myListings;
    return myListings.filter(
      (p) => match(p.name) || match(p.sku) || match(p.category),
    );
  }, [q, myListings]);

  const myRequestsView = useMemo(() => {
    const rows = (myRequests || []).map((r) => {
      const kind =
        safeLower(r.request_kind) || (r.listing_id ? "listing" : "open");
      return {
        ...r,
        _source: kind,
        _status: safeLower(r.status || ""),
        _sellerName: r.to_retailer_id
          ? prettyRetailerName(r.to_retailer_id)
          : null,
      };
    });

    if (!q) return rows;
    return rows.filter(
      (r) =>
        match(r.product_name) ||
        match(r._status) ||
        match(r.note) ||
        match(r._source) ||
        match(r._sellerName),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myRequests, q, retailers]);

  const sellerViewFromYourListings = useMemo(() => {
    let rows = (sellerRequests || [])
      .filter(
        (r) =>
          safeLower(r.request_kind) === "listing" &&
          String(r.to_retailer_id) === String(retailerId),
      )
      .map((r) => ({
        ...r,
        _status: safeLower(r.status || ""),
        _buyerName: prettyRetailerName(r.from_retailer_id),
      }));

    // ✅ Product filter
    if (sellProductQuery) {
      rows = rows.filter((r) =>
        r.product_name?.toLowerCase().includes(sellProductQuery.toLowerCase()),
      );
    }

    // ✅ Buyer filter
    if (sellBuyerQuery) {
      rows = rows.filter((r) =>
        r._buyerName?.toLowerCase().includes(sellBuyerQuery.toLowerCase()),
      );
    }

    // ✅ Status filter
    if (sellStatus && sellStatus !== "All") {
      rows = rows.filter((r) => r._status === sellStatus);
    }

    // ✅ Date range filter
    if (sellDateFrom) {
      const from = new Date(`${sellDateFrom}T00:00:00`);
      rows = rows.filter((r) => new Date(r.created_at) >= from);
    }

    if (sellDateTo) {
      const to = new Date(`${sellDateTo}T23:59:59`);
      rows = rows.filter((r) => new Date(r.created_at) <= to);
    }

    // ✅ Buyer country filter
    if (sellCountry !== "All") {
      rows = rows.filter((r) => {
        const meta = retailerGeoMeta?.[String(r.from_retailer_id)];
        return meta?.country === sellCountry;
      });
    }

    // ✅ Buyer state filter
    if (sellState !== "All") {
      rows = rows.filter((r) => {
        const meta = retailerGeoMeta?.[String(r.from_retailer_id)];
        return meta?.state === sellState;
      });
    }

    return rows;
  }, [
    sellerRequests,
    retailerId,
    sellProductQuery,
    sellBuyerQuery,
    sellStatus,
    sellDateFrom,
    sellDateTo,
    retailers,
  ]);

  const sellerViewOpenRequests = useMemo(() => {
    let rows = (sellerRequests || [])
      .filter(
        (r) =>
          safeLower(r.request_kind) === "open" &&
          !r.listing_id &&
          !dismissedOpenIds.includes(String(r.id)),
      )
      .filter((r) => {
        if (r.to_retailer_id == null) return true;
        return String(r.to_retailer_id) === String(retailerId);
      })
      .map((r) => ({
        ...r,
        _status: safeLower(r.status || ""),
        _buyerName: prettyRetailerName(r.from_retailer_id),
      }));

    // ✅ Product filter
    if (sellProductQuery) {
      rows = rows.filter((r) =>
        r.product_name?.toLowerCase().includes(sellProductQuery.toLowerCase()),
      );
    }

    // ✅ Buyer filter
    if (sellBuyerQuery) {
      rows = rows.filter((r) =>
        r._buyerName?.toLowerCase().includes(sellBuyerQuery.toLowerCase()),
      );
    }

    // ✅ Status filter
    if (sellStatus && sellStatus !== "All") {
      rows = rows.filter((r) => r._status === sellStatus);
    }

    // ✅ Date range filter
    if (sellDateFrom) {
      const from = new Date(`${sellDateFrom}T00:00:00`);
      rows = rows.filter((r) => new Date(r.created_at) >= from);
    }

    if (sellDateTo) {
      const to = new Date(`${sellDateTo}T23:59:59`);
      rows = rows.filter((r) => new Date(r.created_at) <= to);
    }

    // ✅ Buyer country filter
    if (sellCountry !== "All") {
      rows = rows.filter((r) => {
        const meta = retailerGeoMeta?.[String(r.from_retailer_id)];
        return meta?.country === sellCountry;
      });
    }

    // ✅ Buyer state filter
    if (sellState !== "All") {
      rows = rows.filter((r) => {
        const meta = retailerGeoMeta?.[String(r.from_retailer_id)];
        return meta?.state === sellState;
      });
    }

    return rows;
  }, [
    sellerRequests,
    retailerId,
    dismissedOpenIds,
    sellProductQuery,
    sellBuyerQuery,
    sellStatus,
    sellDateFrom,
    sellDateTo,
    retailers,
  ]);

  /* ===============================
    Contact fetch (RPC -> profiles)
  ================================ */
  const openContact = async (targetId) => {
    if (!targetId) return;

    setContactRetailerId(targetId);
    setContactOpen(true);

    setContactInfo(null);
    setContactError("");
    setContactLoading(true);

    try {
      const { data, error } = await supabase.rpc("get_retailer_contact", {
        target_user_id: targetId,
      });
      if (error) throw error;

      const row = Array.isArray(data) ? data[0] : data;
      setContactInfo(row || null);
    } catch (e) {
      setContactError(e?.message || "Failed to load contact info.");
      setContactInfo(null);
    } finally {
      setContactLoading(false);
    }
  };

  /* ===============================
    Actions — Open request (Buy a product)
  ================================ */
  const submitOpenRequest = async (e) => {
    e.preventDefault();
    if (retailerIdLoading)
      return alert(
        "Still loading your retailer account. Try again in a second.",
      );
    if (!retailerId)
      return alert(
        "Missing retailer id. Please complete your retailer profile in Settings.",
      );

    const name = buyProductName.trim();
    if (!name) return alert("Please enter a product name.");

    const qtyN = toInt(buyQty);
    if (!Number.isFinite(qtyN) || qtyN <= 0)
      return alert("Quantity must be a positive whole number.");

    const priceN = toNumber(buyMaxPrice);
    if (!Number.isFinite(priceN) || priceN < 0)
      return alert("Max price must be a valid number.");

    try {
      setSending(true);

      const { error } = await supabase.from("exchange_requests").insert([
        {
          from_retailer_id: retailerId,
          to_retailer_id: null, // open to sellers until accepted
          product_name: name,
          quantity: qtyN,
          max_price: priceN,
          note: buyNote.trim() || null,
          status: "requested",
          request_kind: "open",
          listing_id: null,
          buyer_completed: false,
          seller_completed: false,
        },
      ]);

      if (error) throw error;

      setBuyProductName("");
      setBuyQty("");
      setBuyMaxPrice("");
      setBuyNote("");

      await loadMyRequests();
      await loadSellerRequests();

      setMode("buy");
      setBuyTab("manage_requests");
      alert("Request posted.");
    } catch (err) {
      alert(err?.message || "Failed to post request.");
    } finally {
      setSending(false);
    }
  };

  /* ===============================
    Actions — Buy from listing
  ================================ */
  const openBuyListing = (listing, maxQty) => {
    if (!listing) return;
    if (!retailerId) return alert("Missing retailer id.");
    if (maxQty <= 0)
      return alert("This product is fully claimed or out of stock.");

    setBuyListingTarget({ ...listing, _maxQty: maxQty });
    setBuyListingQty("");
    setBuyListingNote("");
    setBuyListingOpen(true);
  };

  const submitBuyFromListing = async (e) => {
    e.preventDefault();
    if (!retailerId) return alert("Missing retailer id.");
    if (!buyListingTarget?.id) return alert("Missing listing.");

    const qtyN = toInt(buyListingQty);
    const maxQty = Number(buyListingTarget?._maxQty || 0);

    if (!Number.isFinite(qtyN) || qtyN <= 0)
      return alert("Quantity must be a positive whole number.");
    if (qtyN > maxQty)
      return alert(
        `You can’t request ${qtyN}. Only ${maxQty} available right now.`,
      );

    try {
      setSending(true);

      const { error } = await supabase.from("exchange_requests").insert([
        {
          from_retailer_id: retailerId,
          to_retailer_id: buyListingTarget.retailer_id, // direct seller for listing buy
          product_name: buyListingTarget.name,
          quantity: qtyN,
          max_price: Number(buyListingTarget.price || 0),
          note: buyListingNote.trim() || null,
          status: "pending_vendor_approval",
          request_kind: "listing",
          listing_id: buyListingTarget.id,
          buyer_completed: false,
          seller_completed: false,
        },
      ]);

      if (error) throw error;

      setBuyListingOpen(false);
      setBuyListingTarget(null);

      await loadMyRequests();
      await loadSellerRequests();

      setMode("buy");
      setBuyTab("manage_requests");
      alert("Request sent to seller.");
    } catch (err) {
      alert(err?.message || "Failed to send request.");
    } finally {
      setSending(false);
    }
  };

  /* ===============================
    Actions — Seller accept/decline
  ================================ */
  const acceptRequest = async (row) => {
    if (!retailerId) return alert("Missing retailer id.");
    if (!row?.id) return;

    try {
      setSending(true);

      // accepting seller becomes matched seller (and request is no longer open)
      const { error } = await supabase
        .from("exchange_requests")
        .update({
          to_retailer_id: retailerId,
          status: "accepted",
        })
        .eq("id", row.id);

      if (error) throw error;

      await loadMyRequests();
      await loadSellerRequests();
      alert("Accepted.");
    } catch (e) {
      alert(e?.message || "Failed to accept request.");
    } finally {
      setSending(false);
    }
  };

  const declineRequest = async (row) => {
    if (!retailerId) return alert("Missing retailer id.");
    if (!row?.id) return;

    try {
      setSending(true);

      // decline closes it (buyer sees declined; seller removes it)
      const { error } = await supabase
        .from("exchange_requests")
        .update({
          to_retailer_id: retailerId,
          status: "declined",
        })
        .eq("id", row.id);

      if (error) throw error;

      await loadMyRequests();
      await loadSellerRequests();
      alert("Declined.");
    } catch (e) {
      alert(e?.message || "Failed to decline request.");
    } finally {
      setSending(false);
    }
  };

  const dismissOpenRequest = async (row) => {
    if (!retailerId) return alert("Missing retailer id.");
    if (!row?.id) return;

    const ok = confirm("Remove this request from your Open requests list?");
    if (!ok) return;

    try {
      setSending(true);

      const { error } = await supabase
        .from("exchange_request_dismissals")
        .upsert([{ request_id: row.id, retailer_id: retailerId }], {
          onConflict: "request_id,retailer_id",
        });

      if (error) throw error;

      // hide instantly in UI
      setDismissedOpenIds((prev) =>
        Array.from(new Set([...prev, String(row.id)])),
      );

      await loadMyDismissedOpen();
      alert("Removed from your Open requests.");
    } catch (e) {
      alert(e?.message || "Failed to remove request.");
    } finally {
      setSending(false);
    }
  };

  /* ===============================
    Actions — Delete request (buyer side)
    - if open request: removes from open requests as well (same row)
    - if listing request: removes from seller "from your listings" and unreserves
  ================================ */
  const deleteMyRequest = async (row) => {
    if (!retailerId) return alert("Missing retailer id.");
    if (!row?.id) return;

    const st = safeLower(row.status);
    // you wanted delete while requested (open request) and also for listing-based before completion
    if (st === "completed") return alert("This request is already completed.");

    const ok = confirm("Delete this request? This can’t be undone.");
    if (!ok) return;

    try {
      setSending(true);

      const { error } = await supabase
        .from("exchange_requests")
        .delete()
        .match({ id: row.id, from_retailer_id: retailerId });
      if (error) throw error;

      await loadMyRequests();
      await loadSellerRequests();
      alert("Deleted.");
    } catch (e) {
      alert(e?.message || "Failed to delete request.");
    } finally {
      setSending(false);
    }
  };

  /* ===============================
    Actions — Completion handshake
    - Each side sets their completion flag
    - If both true => status completed + remove from views
    - If listing-based: subtract from listing stock (reserved becomes actual deduction)
  ================================ */
  const markCompleted = async (row, who) => {
    if (!retailerId) return alert("Missing retailer id.");
    if (!row?.id) return;

    const isBuyer = who === "buyer";
    const isSeller = who === "seller";

    try {
      setSending(true);

      // 1) set my completion flag
      const update = isBuyer
        ? { buyer_completed: true }
        : { seller_completed: true };

      const { error: uErr } = await supabase
        .from("exchange_requests")
        .update(update)
        .eq("id", row.id);
      if (uErr) throw uErr;

      // 2) re-fetch the row to check if both completed
      const { data: fresh, error: fErr } = await supabase
        .from("exchange_requests")
        .select(
          "id, request_kind, listing_id, quantity, buyer_completed, seller_completed, status",
        )
        .eq("id", row.id)
        .maybeSingle();

      if (fErr) throw fErr;

      const bothDone = !!fresh?.buyer_completed && !!fresh?.seller_completed;

      if (!bothDone) {
        // status stays accepted, UI shows "Confirm completion" for other side
        await loadMyRequests();
        await loadSellerRequests();
        alert(
          "Marked as completed. Waiting for the other retailer to confirm completion.",
        );
        return;
      }

      // 3) both done -> finalize
      const { error: sErr } = await supabase
        .from("exchange_requests")
        .update({ status: "completed" })
        .eq("id", row.id);
      if (sErr) throw sErr;

      // 4) if listing-based, subtract from listing stock
      if (safeLower(fresh?.request_kind) === "listing" && fresh?.listing_id) {
        // best-effort: decrement listing stock by request quantity
        // (clamp at >= 0 done in SQL via GREATEST if you want, but here we just try)
        const qtyN = Number(fresh?.quantity || 0);

        // fetch current stock
        const cur = await supabase
          .from("retailer_listings")
          .select("id, stock")
          .eq("id", fresh.listing_id)
          .maybeSingle();
        if (!cur.error && cur.data) {
          const next = Math.max(0, Number(cur.data.stock ?? 0) - qtyN);

          await supabase
            .from("retailer_listings")
            .update({
              stock: next,
              is_active: next > 0,
            })
            .eq("id", fresh.listing_id);
        }
      }

      await loadMarketplaceListings();
      await loadMyListings();
      await loadMyRequests();
      await loadSellerRequests();

      alert("Completed! Please update your inventory now.");
    } catch (e) {
      alert(e?.message || "Failed to complete request.");
    } finally {
      setSending(false);
    }
  };

  /* ===============================
    Listing modal open/close + submit
  ================================ */
  const clearListingForm = () => {
    setListingName("");
    setListingSku("");
    setListingCategory("");
    setListingStock("");
    setListingPrice("");
    setSelectedInvKey(null);
    setSelectedInvStock(NaN);
    setSelectedInvPrice(NaN);
    setEditingListingId(null);
    setEditingIsActive(true);
  };

  const openSellModal = async () => {
    if (retailerId) loadMyInventoryOptions();
    setEditingListingId(null);
    setEditingIsActive(true);
    setListingOpen(true);
  };

  const openEditListing = async (row) => {
    if (!row?.id) return;

    let invRows = inventoryOptions;
    if (retailerId) {
      invRows = await loadMyInventoryOptions();
    }

    const invMatch =
      (invRows ?? []).find(
        (o) => normalizeSku(o.sku) === normalizeSku(row.sku),
      ) ?? null;

    const matchedStock = Number(invMatch?.stock ?? NaN);
    const matchedPrice = Number(invMatch?.price ?? NaN);
    const currentListingStock = Number(row.stock ?? 0);

    setEditingListingId(row.id);
    setEditingIsActive(!!row.is_active);

    setListingName(row.name ?? "");
    setListingSku(row.sku ?? "");
    setListingCategory(row.category ?? "");

    setSelectedInvKey(invMatch?.key ?? null);
    setSelectedInvStock(matchedStock);
    setSelectedInvPrice(matchedPrice);

    const safeStock = Number.isFinite(matchedStock)
      ? Math.min(currentListingStock, matchedStock)
      : currentListingStock;

    setListingStock(String(safeStock));
    setListingPrice(String(row.price ?? ""));

    setShowAddCategory(false);
    setNewCategory("");

    setListingOpen(true);
  };

  const deleteListing = async (listingId) => {
    if (
      !window.confirm(
        "Are you sure you want to delete this listing from the Exchange?",
      )
    )
      return;

    try {
      // Logic: Delete from retailer_listings where ID matches
      const { error } = await supabase
        .from("retailer_listings")
        .delete()
        .eq("id", listingId)
        .eq("retailer_id", retailerId); // Mentor tip: always verify ownership

      if (error) throw error;

      alert("Listing removed successfully.");

      // Refresh the data so it disappears from the list
      if (loadMyListings) await loadMyListings();
    } catch (err) {
      console.error("Delete error:", err);
      alert(err.message || "Failed to delete listing.");
    }
  };

  const closeListingModal = () => setListingOpen(false);

  const saveListing = async (e) => {
    e.preventDefault();
    if (!retailerId) return alert("Missing retailer id.");

    const name = listingName.trim();
    const sku = normalizeSku(listingSku);
    const cat = String(listingCategory || "").trim() || "—";
    const stockN = toInt(listingStock);
    const priceN = toNumber(listingPrice);

    if (!name) return alert("Please enter product name.");
    if (!sku) return alert("Please enter SKU.");
    if (!cat || cat === "—")
      return alert("Please choose a category or add a new one.");
    if (!Number.isFinite(stockN) || stockN < 0)
      return alert("Quantity must be 0 or more.");
    if (!Number.isFinite(priceN) || priceN < 0)
      return alert("Price must be 0 or more.");

    if (Number.isFinite(selectedInvStock)) {
      const max = Number(selectedInvStock);
      if (stockN > max)
        return alert(
          `You can’t list ${stockN} — you only have ${max} in inventory.`,
        );
    }

    try {
      setSending(true);

      // Resolve product by SKU (create or update)
      const existing = await supabase
        .from("products")
        .select("id, sku")
        .eq("sku", sku)
        .maybeSingle();
      let productId = existing?.data?.id || null;

      if (!productId) {
        const created = await supabase
          .from("products")
          .insert([{ sku, name, category: cat }])
          .select("id")
          .single();
        if (created.error) throw created.error;
        productId = created.data.id;
      } else {
        await supabase
          .from("products")
          .update({ name, category: cat })
          .eq("id", productId);
      }

      if (isEditingListing) {
        const { error } = await supabase
          .from("retailer_listings")
          .update({
            product_id: productId,
            price: priceN,
            stock: stockN,
            is_active: editingIsActive,
          })
          .eq("id", editingListingId)
          .eq("retailer_id", retailerId);

        if (error) throw error;

        clearListingForm();
        closeListingModal();
        await loadMyListings();
        await loadMarketplaceListings();

        setMode("sell");
        setSellTab("manage_listings");
        alert("Listing updated.");
        return;
      }

      const { error: upsertErr } = await supabase
        .from("retailer_listings")
        .upsert(
          [
            {
              retailer_id: retailerId,
              product_id: productId,
              price: priceN,
              stock: stockN,
              is_active: true,
            },
          ],
          { onConflict: "retailer_id,product_id" },
        );

      if (upsertErr) throw upsertErr;

      clearListingForm();
      closeListingModal();
      await loadMyListings();
      await loadMarketplaceListings();

      setMode("sell");
      setSellTab("manage_listings");
      alert("Listing posted.");
    } catch (err) {
      alert(
        err?.message ||
          "Failed to save listing. Check policies for products + retailer_listings.",
      );
    } finally {
      setSending(false);
    }
  };

  /* ===============================
    Active count label
  ================================ */
  const activeCountLabel = useMemo(() => {
    if (mode === "buy") {
      if (buyTab === "available_products")
        return marketLoading
          ? "Loading…"
          : `${filteredAvailableProducts.length} items`;
      if (buyTab === "manage_requests")
        return myReqLoading ? "Loading…" : `${myRequestsView.length} items`;
      return "Buy a product";
    }

    if (sellTab === "manage_listings")
      return myLoading ? "Loading…" : `${filteredMyListings.length} items`;
    if (sellTab === "view_requests")
      return sellerReqLoading
        ? "Loading…"
        : `${sellerViewFromYourListings.length + sellerViewOpenRequests.length} items`;
    return "Sell a product";
  }, [
    mode,
    buyTab,
    sellTab,
    marketLoading,
    filteredAvailableProducts.length,
    myReqLoading,
    myRequestsView.length,
    myLoading,
    filteredMyListings.length,
    sellerReqLoading,
    sellerViewFromYourListings.length,
    sellerViewOpenRequests.length,
  ]);

  const refresh = async () => {
    await loadMarketplaceListings();
    if (!retailerIdLoading && retailerId) {
      await loadMyListings();
      await loadMyRequests();
      await loadSellerRequests();
      await loadRetailerLocations();
      await loadMyLocation();
    }
  };

  const buyCategoryOptions = useMemo(() => {
    const set = new Set();
    marketListings.forEach((l) => {
      if (l.category && l.category !== "—") set.add(l.category);
    });
    return ["All", ...Array.from(set).sort()];
  }, [marketListings]);

  const buyCountryOptions = useMemo(() => {
    const set = new Set();
    marketListings.forEach((l) => {
      if (l.country) set.add(l.country);
    });
    return ["All", ...Array.from(set).sort()];
  }, [marketListings]);

  const buyStateOptions = useMemo(() => {
    const set = new Set();
    marketListings.forEach((l) => {
      if ((buyCountry === "All" || l.country === buyCountry) && l.state) {
        set.add(l.state);
      }
    });
    return ["All", ...Array.from(set).sort()];
  }, [marketListings, buyCountry]);

  // ===============================
  // Location option helpers
  // ===============================
  const countryOptionsFromListings = useMemo(() => {
    const set = new Set();
    (marketListings || []).forEach((p) => {
      if (p.country) set.add(p.country);
    });
    return Array.from(set).sort();
  }, [marketListings]);

  const stateOptionsFromListings = useMemo(() => {
    const set = new Set();
    (marketListings || []).forEach((p) => {
      if (p.state && (buyCountry === "All" || p.country === buyCountry)) {
        set.add(p.state);
      }
    });
    return Array.from(set).sort();
  }, [marketListings, buyCountry]);

  // Seller-side (buyer location) options
  const sellerCountryOptions = useMemo(() => {
    const set = new Set();
    (sellerRequests || []).forEach((r) => {
      const meta = retailerGeoMeta?.[String(r.from_retailer_id)];
      if (meta?.country) set.add(meta.country);
    });
    return Array.from(set).sort();
  }, [sellerRequests, retailerGeoMeta]);

  const sellerStateOptions = useMemo(() => {
    const set = new Set();
    (sellerRequests || []).forEach((r) => {
      const meta = retailerGeoMeta?.[String(r.from_retailer_id)];
      if (
        meta?.state &&
        (sellCountry === "All" || meta.country === sellCountry)
      ) {
        set.add(meta.state);
      }
    });
    return Array.from(set).sort();
  }, [sellerRequests, retailerGeoMeta, sellCountry]);

  // Add this near your other useMemo hooks in Exchange.jsx
  // Add this inside the Exchange component
  // Add this inside ExchangePage component
  const sellCategoryOptions = useMemo(() => {
    const categories = new Set();

    // 1. Pull from current inventory (POS sync/manual)
    inventoryOptions.forEach((item) => {
      if (item.category) categories.add(item.category.trim());
    });

    // 2. Pull from existing marketplace listings
    myListings.forEach((listing) => {
      if (listing.category) categories.add(listing.category.trim());
    });

    // 3. Add extra categories added in this session
    extraCategories.forEach((cat) => {
      if (cat) categories.add(cat.trim());
    });

    return Array.from(categories).sort((a, b) => a.localeCompare(b));
  }, [inventoryOptions, myListings, extraCategories]);
  /* ===============================
    Render helpers for status/handshake
  ================================ */
  const completionLabelForBuyer = (r) => {
    const st = safeLower(r.status);
    if (st === "completed") return null;
    if (st !== "accepted") return null;

    if (r?.buyer_completed && !r?.seller_completed)
      return "Waiting seller confirmation";
    if (!r?.buyer_completed && r?.seller_completed) return "Confirm completion";
    return "Completed";
  };

  const completionLabelForSeller = (r) => {
    const st = safeLower(r.status);
    if (st === "completed") return null;
    if (st !== "accepted") return null;

    if (r?.seller_completed && !r?.buyer_completed)
      return "Waiting buyer confirmation";
    if (!r?.seller_completed && r?.buyer_completed) return "Confirm completion";
    return "Completed";
  };

  const canShowContactBuyer = (r) =>
    safeLower(r.status) === "accepted" && !!r.to_retailer_id;
  const canShowContactSeller = (r) =>
    safeLower(r.status) === "accepted" && !!r.from_retailer_id;

  return (
    <main
      className="slide retail-page exchange-page"
      aria-label="Retailer Exchange Page"
    >
      <Topbar
        displayName={displayName}
        role={role}
        onLogout={handleLogout}
        activePage="exchange"
      />

      <section className="exchange-layout">
        <Panel className="market-hero">
          <div className="market-hero-inner">
            <h2 className="market-title">
              Welcome to Jiran&apos;s Marketplace
            </h2>
            <p className="market-sub">
              {loading
                ? "Checking your account..."
                : "Buy products, sell stock, and manage requests - all in one place."}
            </p>

            <div className="market-head">
              {/* TOP: Buy / Sell (2 buttons only) */}
              <div
                className="market-tabs"
                role="tablist"
                aria-label="Marketplace mode tabs"
              >
                <button
                  type="button"
                  className={`tab ${mode === "buy" ? "active" : ""}`}
                  onClick={() => setMode("buy")}
                  role="tab"
                  aria-selected={mode === "buy"}
                >
                  Buy
                </button>
                <button
                  type="button"
                  className={`tab ${mode === "sell" ? "active" : ""}`}
                  onClick={() => setMode("sell")}
                  role="tab"
                  aria-selected={mode === "sell"}
                >
                  Sell
                </button>
              </div>
            </div>

            {retailersError ||
            marketError ||
            myError ||
            myReqError ||
            sellerReqError ||
            invError ? (
              <div className="inline-error" style={{ marginTop: 12 }}>
                {retailersError ||
                  marketError ||
                  myError ||
                  myReqError ||
                  sellerReqError ||
                  invError}
              </div>
            ) : null}
          </div>
        </Panel>

        <section className="market-layout">
          <section className="market-main">
            <Panel>
              {/* SUB TABS */}
              <div
                className="subtabs"
                role="tablist"
                aria-label="Sub navigation"
              >
                {mode === "buy" ? (
                  <>
                    <button
                      type="button"
                      className={`subtab ${buyTab === "buy_product" ? "active" : ""}`}
                      onClick={() => setBuyTab("buy_product")}
                    >
                      Buy a product
                    </button>
                    <button
                      type="button"
                      className={`subtab ${buyTab === "available_products" ? "active" : ""}`}
                      onClick={() => setBuyTab("available_products")}
                    >
                      Available products
                    </button>
                    <button
                      type="button"
                      className={`subtab ${buyTab === "manage_requests" ? "active" : ""}`}
                      onClick={() => setBuyTab("manage_requests")}
                    >
                      Manage my requests
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className={`subtab ${sellTab === "sell_product" ? "active" : ""}`}
                      onClick={() => setSellTab("sell_product")}
                    >
                      Sell a product
                    </button>
                    <button
                      type="button"
                      className={`subtab ${sellTab === "view_requests" ? "active" : ""}`}
                      onClick={() => setSellTab("view_requests")}
                    >
                      View requests
                    </button>
                    <button
                      type="button"
                      className={`subtab ${sellTab === "manage_listings" ? "active" : ""}`}
                      onClick={() => setSellTab("manage_listings")}
                    >
                      Manage my listings
                    </button>
                  </>
                )}
              </div>
              {/* =========================
                  BUY → Buy a product (open request form)
                 ========================= */}
              {mode === "buy" && buyTab === "buy_product" ? (
                <div className="page-block">
                  <form className="form" onSubmit={submitOpenRequest}>
                    <div className="field">
                      <label htmlFor="bp_name">Product name</label>
                      <input
                        id="bp_name"
                        className="input"
                        value={buyProductName}
                        onChange={(e) => setBuyProductName(e.target.value)}
                        placeholder="e.g., Bottled Water 500ml / SKU..."
                      />
                    </div>

                    <div className="field">
                      <label htmlFor="bp_qty">Quantity</label>
                      <input
                        id="bp_qty"
                        className="input"
                        type="number"
                        min="1"
                        value={buyQty}
                        onChange={(e) => setBuyQty(e.target.value)}
                        placeholder="e.g., 30"
                      />
                    </div>

                    <div className="field">
                      <label htmlFor="bp_price">
                        Max price willing to pay (AED)
                      </label>
                      <input
                        id="bp_price"
                        className="input"
                        inputMode="decimal"
                        value={buyMaxPrice}
                        onChange={(e) => setBuyMaxPrice(e.target.value)}
                        placeholder="e.g., 2.50"
                      />
                    </div>

                    <div className="field span-2">
                      <label htmlFor="bp_note">Note (optional)</label>
                      <input
                        id="bp_note"
                        className="input"
                        value={buyNote}
                        onChange={(e) => setBuyNote(e.target.value)}
                        placeholder="e.g., Need today, can pick up now"
                      />
                    </div>

                    <div className="form-actions span-2">
                      <button
                        className="btn ghost"
                        type="button"
                        onClick={() => {
                          setBuyProductName("");
                          setBuyQty("");
                          setBuyMaxPrice("");
                          setBuyNote("");
                        }}
                        disabled={sending}
                      >
                        Clear
                      </button>
                      <button
                        className="btn primary"
                        type="submit"
                        disabled={sending}
                      >
                        {sending ? "Posting..." : "Post request"}
                      </button>
                    </div>
                  </form>
                </div>
              ) : null}

              {/* =========================
                  BUY → Available products (listings + Buy)
                 ========================= */}
              {mode === "buy" && buyTab === "available_products" ? (
                marketLoading ? (
                  <div className="empty">
                    <div className="empty-title">
                      Loading available products…
                    </div>
                    <div className="empty-sub">
                      Fetching listings from retailers.
                    </div>
                  </div>
                ) : filteredAvailableProducts.length === 0 ? (
                  <div className="empty">
                    <div className="empty-title">
                      {searchQuery ? "No matches" : "No available products"}
                    </div>
                    <div className="empty-sub">
                      {searchQuery
                        ? "Try a different search."
                        : "When retailers list stock, it will appear here."}
                    </div>
                  </div>
                ) : (
                  <>
                    {/* BUY → Search & Filters */}
                    <div className="page-block buy-search-panel">
                      <div className="search-grid">
                        <div className="search-field">
                          <label className="search-label">Product</label>
                          <SearchableSelect
                            placeholder="Search product name"
                            value={buyNameQuery}
                            onChange={setBuyNameQuery}
                            options={Array.from(
                              new Set(marketListings.map((p) => p.name)),
                            ).map((name) => ({ label: name, value: name }))}
                          />
                        </div>

                        <div className="search-field">
                          <label className="search-label">Category</label>
                          <SearchableSelect
                            placeholder="Search category"
                            value={buyCategory}
                            onChange={setBuyCategory}
                            options={buyCategoryOptions
                              .filter((c) => c !== "All")
                              .map((c) => ({ label: c, value: c }))}
                          />
                        </div>

                        <div className="search-field">
                          <label className="search-label">Country</label>
                          <SearchableSelect
                            placeholder="Select country"
                            value={buyCountry}
                            onChange={(val) => {
                              setBuyCountry(val);
                              setBuyState("All");
                            }}
                            options={buyCountryOptions
                              .filter((c) => c !== "All")
                              .map((c) => ({ label: c, value: c }))}
                          />
                        </div>

                        <div className="search-field">
                          <label className="search-label">State</label>
                          <SearchableSelect
                            placeholder="Select state (choose country first)"
                            value={buyState}
                            disabled={buyCountry === "All"}
                            onChange={setBuyState}
                            options={buyStateOptions
                              .filter((s) => s !== "All")
                              .map((s) => ({ label: s, value: s }))}
                          />
                        </div>

                        <div className="search-field">
                          <label className="search-label">From</label>
                          <input
                            type="date"
                            className="input"
                            value={buyDateFrom}
                            onChange={(e) => setBuyDateFrom(e.target.value)}
                          />
                        </div>

                        <div className="search-field">
                          <label className="search-label">To</label>
                          <input
                            type="date"
                            className="input"
                            value={buyDateTo}
                            onChange={(e) => setBuyDateTo(e.target.value)}
                          />
                        </div>
                      </div>
                    </div>
                    <div className="ex-table">
                      <div className="ex-thead ex-thead-market2">
                        <div>Product</div>
                        <div>Seller</div>
                        <div>Location</div>
                        <div>Qty.</div>
                        <div>Price/unit</div>
                        <div></div>
                      </div>

                      <div className="exchange-scroll">
                        {filteredAvailableProducts.map((p) => {
                          const claimed = Number(
                            claimedTotals[String(p.id)] ?? 0,
                          );
                          const total = Number(p.stock || 0);
                          const available = Math.max(0, total - claimed);

                          const updatedLabel = formatDateTime(p.updated_at);

                          return (
                            <div className="ex-row ex-row-market2" key={p.id}>
                              <div className="ex-prod">
                                <span className="thumb" aria-hidden="true">
                                  {" "}
                                  🏷️
                                </span>
                                <div className="ex-prod-text">
                                  <div className="ex-prod-name">
                                    {highlightMatch(p.name, buyNameQuery)}
                                  </div>
                                  <div className="ex-prod-sub muted">
                                    <span className="sku" title={p.sku}>
                                      SKU: {p.sku}
                                    </span>
                                    <span className="meta">
                                      •{" "}
                                      {highlightMatch(
                                        p.category,
                                        buyCategory !== "All"
                                          ? buyCategory
                                          : "",
                                      )}
                                    </span>
                                    {updatedLabel ? (
                                      <span className="meta">
                                        • Updated: {updatedLabel}
                                      </span>
                                    ) : null}
                                  </div>
                                </div>
                              </div>

                              <div className="seller-cell">
                                <div className="seller-name">
                                  {p.retailer_shop ||
                                    prettyRetailerName(p.retailer_id)}
                                </div>
                                {/* contact only upon acceptance -> not shown here */}
                                <span
                                  className="muted"
                                  style={{ fontSize: 12 }}
                                ></span>
                              </div>

                              <p className="listing-location">
                                {p.city}, {p.country}
                              </p>

                              <div>
                                <div className="qty-stack">
                                  <div className="qty-main">{available}</div>
                                  <div className="qty-sub muted">
                                    {claimed}/{total} claimed
                                  </div>
                                </div>
                              </div>

                              <div>AED {Number(p.price || 0).toFixed(2)}</div>

                              <div className="manage-actions">
                                <button
                                  className="rowbtn"
                                  type="button"
                                  onClick={() => openBuyListing(p, available)}
                                  disabled={available <= 0 || sending}
                                >
                                  Buy
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </>
                )
              ) : null}

              {/* =========================
                  BUY → Manage my requests
                 ========================= */}
              {mode === "buy" && buyTab === "manage_requests" ? (
                myReqError ? (
                  <div className="hint-row">
                    <span className="status warn">Setup</span>
                    <p className="hint-text">
                      {myReqError}{" "}
                      <span className="muted">
                        (Check your policies / columns.)
                      </span>
                    </p>
                  </div>
                ) : myReqLoading ? (
                  <div className="empty">
                    <div className="empty-title">Loading your requests…</div>
                    <div className="empty-sub">
                      Fetching requests you created.
                    </div>
                  </div>
                ) : myRequestsView.length === 0 ? (
                  <div className="empty">
                    <div className="empty-title">
                      {searchQuery ? "No matches" : "No requests yet"}
                    </div>
                    <div className="empty-sub">
                      {searchQuery
                        ? "Try a different search."
                        : "Create one from “Buy a product” or “Available products”."}
                    </div>
                  </div>
                ) : (
                  <div className="req-sections">
                    <div className="req-section">
                      <div className="req-section-head">
                        <div className="req-section-title">
                          Manage my requests
                        </div>
                        <div className="req-section-sub muted">
                          Your outgoing requests (open + listing-based).
                        </div>
                        <span className="pill subtle">
                          {myRequestsView.length} items
                        </span>
                      </div>

                      <div className="ex-table">
                        <div className="ex-thead ex-thead-req2">
                          <div>Request</div>
                          <div>Seller</div>
                          <div>Location</div>
                          <div>Qty.</div>
                          <div>Status</div>
                          <div></div>
                        </div>

                        <div className="exchange-scroll">
                          {myRequestsView.map((r) => {
                            const source = r._source;
                            const st = r._status;

                            const sellerName = r.to_retailer_id
                              ? prettyRetailerName(r.to_retailer_id)
                              : "Waiting to find seller";
                            const showContact = canShowContactBuyer(r);

                            // delete rules:
                            // - open requests: allowed while requested
                            // - listing requests: allowed any time before completed (you asked delete removes from your listings section too)
                            const canDelete = st !== "completed";

                            const completionLabel = completionLabelForBuyer(r);
                            const createdLabel = formatDateTime(r.created_at);

                            return (
                              <div className="ex-row ex-row-req2" key={r.id}>
                                <div className="req-mini req-mini-compact">
                                  <div className="req-product">
                                    {highlightMatch(
                                      r.product_name,
                                      sellProductQuery,
                                    )}
                                  </div>
                                  <div className="req-note muted">
                                    Type:{" "}
                                    <strong>
                                      {source === "listing"
                                        ? "From available products"
                                        : "Open request"}
                                    </strong>
                                    {createdLabel ? (
                                      <> • Posted: {createdLabel}</>
                                    ) : null}
                                  </div>
                                  {r.note ? (
                                    <div className="req-note muted">
                                      {r.note}
                                    </div>
                                  ) : null}
                                </div>

                                <div className="seller-cell">
                                  <div className="seller-name">
                                    {sellerName}
                                  </div>
                                  <button
                                    className="rowbtn"
                                    type="button"
                                    onClick={() =>
                                      showContact &&
                                      openContact(r.to_retailer_id)
                                    }
                                    disabled={!showContact || sending}
                                    title={
                                      !showContact
                                        ? "Contact is available after the request is accepted."
                                        : undefined
                                    }
                                  >
                                    Contact
                                  </button>
                                </div>

                                <div className="location-cell">
                                  {retailerGeoMeta?.[r.to_retailer_id]?.state ||
                                    "—"}
                                  {retailerGeoMeta?.[r.to_retailer_id]?.country
                                    ? `, ${retailerGeoMeta[r.to_retailer_id].country}`
                                    : ""}
                                </div>

                                <div>{r.quantity}</div>

                                <div>
                                  <div className="status-stack">
                                    <span
                                      className={`chip ${st === "accepted" ? "ok" : st === "declined" ? "bad" : "neutral"}`}
                                    >
                                      {st === "pending_vendor_approval"
                                        ? "Pending vendor approval"
                                        : st}
                                    </span>
                                    {completionLabel ? (
                                      <div
                                        className="muted"
                                        style={{ fontSize: 12, marginTop: 4 }}
                                      >
                                        {completionLabel}
                                      </div>
                                    ) : null}
                                  </div>
                                </div>

                                <div className="manage-actions">
                                  {st === "accepted" ? (
                                    <button
                                      className="rowbtn"
                                      type="button"
                                      onClick={() => markCompleted(r, "buyer")}
                                      disabled={sending || !!r?.buyer_completed}
                                    >
                                      {r?.buyer_completed
                                        ? "Completed"
                                        : "Completed"}
                                    </button>
                                  ) : null}

                                  {canDelete ? (
                                    <button
                                      className="rowbtn danger"
                                      type="button"
                                      onClick={() => deleteMyRequest(r)}
                                      disabled={sending}
                                    >
                                      Delete
                                    </button>
                                  ) : null}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              ) : null}

              {/* =========================
                  SELL → Sell a product
                 ========================= */}
              {/* =========================
    SELL → Sell a product (INLINE FORM)
   ========================= */}
              {mode === "sell" && sellTab === "sell_product" ? (
                <div className="page-block">
                  {invLoading ? (
                    <div
                      className="muted"
                      style={{ fontSize: 12, marginBottom: 10 }}
                    >
                      Loading your inventory for the picker…
                    </div>
                  ) : null}

                  {/* Inline sell form (same style as Buy a product) */}
                  <form className="form" onSubmit={saveListing}>
                    <div className="field span-2">
                      <label>Pick from your inventory</label>
                      <InventoryPicker
                        options={inventoryOptions}
                        selectedKey={selectedInvKey}
                        onSelect={(o) => {
                          setSelectedInvKey(o.key);
                          setSelectedInvStock(Number(o.stock ?? 0));
                          setSelectedInvPrice(Number(o.price ?? NaN));
                          setListingName(o.name ?? "");
                          setListingSku(o.sku ?? "");
                          setListingCategory(o.category ?? "");
                          setListingStock("");
                          setStockError("");
                        }}
                        disabled={sending}
                      />
                      <div className="help-row">
                        {Number.isFinite(selectedInvStock) ? (
                          <span className="pill subtle">
                            Available: {selectedInvStock}
                          </span>
                        ) : null}
                      </div>
                    </div>

                    <div className="field">
                      <label htmlFor="s_name">Product name</label>
                      <input
                        id="s_name"
                        className="input"
                        value={listingName}
                        readOnly
                        placeholder="Auto-filled from inventory"
                      />
                    </div>

                    <div className="field">
                      <label htmlFor="s_sku">SKU</label>
                      <input
                        id="s_sku"
                        className="input"
                        value={listingSku}
                        readOnly
                        placeholder="Auto-filled from inventory"
                      />
                    </div>

                    <div className="field">
                      <label htmlFor="s_category">Category</label>

                      <select
                        id="s_category"
                        className="input"
                        value={listingCategory || ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (val === "__add_cat__") {
                            setShowAddCategory(true);
                            setNewCategory("");
                            return;
                          }
                          setListingCategory(val);
                        }}
                        disabled={sending}
                      >
                        <option value="" disabled>
                          Select a category
                        </option>

                        {/* This list is now dynamically derived from Inventory + Listings */}
                        {sellCategoryOptions.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}

                        <option
                          value="__add_cat__"
                          style={{
                            fontWeight: "bold",
                            color: "var(--primary)",
                          }}
                        >
                          + Add a new category…
                        </option>
                      </select>

                      {showAddCategory && (
                        <div
                          className="category-new-wrapper"
                          style={{ marginTop: 10 }}
                        >
                          <div style={{ display: "flex", gap: 10 }}>
                            <input
                              className="input"
                              autoFocus
                              value={newCategory}
                              onChange={(e) => setNewCategory(e.target.value)}
                              placeholder="Type a new category…"
                              disabled={sending}
                            />
                            <button
                              type="button"
                              className="btn primary small"
                              disabled={sending || !newCategory.trim()}
                              onClick={() => {
                                const c = newCategory.trim();
                                // Case-insensitive check to prevent duplicates
                                const isDuplicate = sellCategoryOptions.some(
                                  (existing) =>
                                    existing.toLowerCase() === c.toLowerCase(),
                                );

                                if (!isDuplicate) {
                                  setExtraCategories((prev) => [...prev, c]);
                                }

                                setListingCategory(c);
                                setShowAddCategory(false);
                                setNewCategory("");
                              }}
                            >
                              Add
                            </button>
                            <button
                              type="button"
                              className="btn ghost small"
                              onClick={() => setShowAddCategory(false)}
                            >
                              Cancel
                            </button>
                          </div>
                          <small className="muted">
                            This will be saved to your listing.
                          </small>
                        </div>
                      )}
                    </div>

                    <div className="field">
                      <label htmlFor="s_stock">Quantity available</label>
                      <input
                        id="s_stock"
                        className={`input ${stockError ? "invalid" : ""}`}
                        type="number"
                        min="0"
                        max={
                          Number.isFinite(selectedInvStock)
                            ? selectedInvStock
                            : undefined
                        }
                        value={listingStock}
                        onChange={(e) => onStockChange(e.target.value)}
                        placeholder="e.g., 240"
                        disabled={sending}
                      />
                      {stockError ? (
                        <div className="inline-warn">{stockError}</div>
                      ) : null}
                    </div>

                    <div className="field">
                      <label htmlFor="s_current_price">
                        Current price per unit (AED)
                      </label>
                      <input
                        id="s_current_price"
                        className="input"
                        value={
                          Number.isFinite(selectedInvPrice)
                            ? Number(selectedInvPrice).toFixed(2)
                            : ""
                        }
                        placeholder="Select a product"
                        readOnly
                      />
                    </div>

                    <div className="field">
                      <label htmlFor="s_price">Price per unit (AED)</label>
                      <input
                        id="s_price"
                        className="input"
                        inputMode="decimal"
                        value={listingPrice}
                        onChange={(e) => setListingPrice(e.target.value)}
                        placeholder="e.g., 4.00"
                        disabled={sending}
                      />
                    </div>

                    <div className="form-actions span-2">
                      <button
                        className="btn ghost"
                        type="button"
                        onClick={clearListingForm}
                        disabled={sending}
                      >
                        Clear
                      </button>

                      <button
                        className="btn primary"
                        type="submit"
                        disabled={sending || !!stockError}
                      >
                        {sending
                          ? "Saving..."
                          : isEditingListing
                            ? "Save Changes"
                            : "Post Listing"}
                      </button>
                    </div>
                  </form>
                </div>
              ) : null}

              {/* =========================
                  SELL → View requests (two sections)
                 ========================= */}
              {mode === "sell" && sellTab === "view_requests" ? (
                sellerReqError ? (
                  <div className="hint-row">
                    <span className="status warn">Setup</span>
                    <p className="hint-text">{sellerReqError}</p>
                  </div>
                ) : sellerReqLoading ? (
                  <div className="empty">
                    <div className="empty-title">Loading requests…</div>
                    <div className="empty-sub">
                      Fetching requests you can respond to.
                    </div>
                  </div>
                ) : (
                  <>
                    {/* SELL → Search & Filters */}
                    <div className="page-block sell-search-panel">
                      <div className="search-grid">
                        <div className="search-field">
                          <label className="search-label">Product</label>
                          <SearchableSelect
                            placeholder="Search product name"
                            value={sellProductQuery}
                            onChange={setSellProductQuery}
                            options={Array.from(
                              new Set(
                                sellerRequests
                                  .map((r) => r.product_name)
                                  .filter(Boolean),
                              ),
                            ).map((name) => ({ label: name, value: name }))}
                          />
                        </div>

                        <div className="search-field">
                          <label className="search-label">Buyer</label>
                          <SearchableSelect
                            placeholder="Search buyer"
                            value={sellBuyerQuery}
                            onChange={setSellBuyerQuery}
                            options={Array.from(
                              new Set(
                                sellerRequests.map((r) =>
                                  prettyRetailerName(r.from_retailer_id),
                                ),
                              ),
                            ).map((name) => ({ label: name, value: name }))}
                          />
                        </div>

                        <div className="search-field">
                          <label className="search-label">Status</label>
                          <SearchableSelect
                            placeholder="Select status"
                            value={sellStatus}
                            onChange={setSellStatus}
                            options={[
                              "requested",
                              "pending_vendor_approval",
                              "accepted",
                              "declined",
                              "completed",
                            ].map((s) => ({ label: s, value: s }))}
                          />
                        </div>

                        <div className="search-field">
                          <label className="search-label">From</label>
                          <input
                            type="date"
                            className="input"
                            value={sellDateFrom}
                            onChange={(e) => setSellDateFrom(e.target.value)}
                          />
                        </div>

                        <div className="search-field">
                          <label className="search-label">To</label>
                          <input
                            type="date"
                            className="input"
                            value={sellDateTo}
                            onChange={(e) => setSellDateTo(e.target.value)}
                          />
                        </div>
                      </div>
                    </div>
                    <div className="req-sections">
                      {/* From your listings */}
                      <div className="req-section">
                        <div className="req-section-head">
                          <div className="req-section-title">
                            From your listings
                          </div>
                          <div className="req-section-sub muted">
                            Requests created when buyers clicked “Buy” on your
                            listed products.
                          </div>
                          <span className="pill subtle">
                            {sellerViewFromYourListings.length} items
                          </span>
                        </div>

                        {sellerViewFromYourListings.length === 0 ? (
                          <div className="empty">
                            <div className="empty-title">
                              {searchQuery
                                ? "No matches"
                                : "No requests from your listings"}
                            </div>
                            <div className="empty-sub">
                              {searchQuery
                                ? "Try a different search."
                                : "When buyers request your listings, they’ll appear here."}
                            </div>
                          </div>
                        ) : (
                          <div className="ex-table">
                            <div className="ex-thead ex-thead-sellreq">
                              <div>Request</div>
                              <div>Buyer</div>
                              <div>Qty.</div>
                              <div>Status</div>
                              <div></div>
                            </div>

                            <div className="exchange-scroll">
                              {sellerViewFromYourListings.map((r) => {
                                const st = r._status;
                                const showActions =
                                  st === "pending_vendor_approval";
                                const showCompletion = st === "accepted";
                                const showContact = canShowContactSeller(r);

                                const completionLabel =
                                  completionLabelForSeller(r);
                                const createdLabel = formatDateTime(
                                  r.created_at,
                                );

                                return (
                                  <div
                                    className="ex-row ex-row-sellreq"
                                    key={r.id}
                                  >
                                    <div className="req-mini req-mini-compact">
                                      <div className="req-product">
                                        {r.product_name}
                                      </div>
                                      {createdLabel ? (
                                        <div className="req-note muted">
                                          Posted: {createdLabel}
                                        </div>
                                      ) : null}
                                      {r.note ? (
                                        <div className="req-note muted">
                                          {r.note}
                                        </div>
                                      ) : null}
                                    </div>

                                    <div className="seller-cell">
                                      <div className="seller-name">
                                        {highlightMatch(
                                          prettyRetailerName(
                                            r.from_retailer_id,
                                          ),
                                          sellBuyerQuery,
                                        )}
                                      </div>
                                      {showContact ? (
                                        <button
                                          className="rowbtn"
                                          type="button"
                                          onClick={() =>
                                            openContact(r.from_retailer_id)
                                          }
                                          disabled={sending}
                                        >
                                          Contact
                                        </button>
                                      ) : (
                                        <span
                                          className="muted"
                                          style={{ fontSize: 12 }}
                                        >
                                          —
                                        </span>
                                      )}
                                    </div>

                                    <div>{r.quantity}</div>

                                    <div>
                                      <div className="status-stack">
                                        <span
                                          className={`chip ${st === "accepted" ? "ok" : st === "declined" ? "bad" : "neutral"}`}
                                        >
                                          {st === "pending_vendor_approval"
                                            ? "Pending vendor approval"
                                            : st}
                                        </span>
                                        {completionLabel ? (
                                          <div
                                            className="muted"
                                            style={{
                                              fontSize: 12,
                                              marginTop: 4,
                                            }}
                                          >
                                            {completionLabel}
                                          </div>
                                        ) : null}
                                      </div>
                                    </div>

                                    <div className="manage-actions">
                                      {showActions ? (
                                        <>
                                          <button
                                            className="rowbtn"
                                            type="button"
                                            onClick={() => acceptRequest(r)}
                                            disabled={sending}
                                          >
                                            Accept
                                          </button>
                                          <button
                                            className="rowbtn danger"
                                            type="button"
                                            onClick={() => declineRequest(r)}
                                            disabled={sending}
                                          >
                                            Decline
                                          </button>
                                        </>
                                      ) : null}

                                      {showCompletion ? (
                                        <button
                                          className="rowbtn"
                                          type="button"
                                          onClick={() =>
                                            markCompleted(r, "seller")
                                          }
                                          disabled={
                                            sending || !!r?.seller_completed
                                          }
                                        >
                                          {r?.seller_completed
                                            ? "Completed"
                                            : "Completed"}
                                        </button>
                                      ) : null}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Open requests */}
                      <div className="req-section">
                        <div className="req-section-head">
                          <div className="req-section-title">Open requests</div>
                          <div className="req-section-sub muted">
                            Requests posted from “Buy a product”. First accept =
                            matched seller.
                          </div>
                          <span className="pill subtle">
                            {sellerViewOpenRequests.length} items
                          </span>
                        </div>

                        {sellerViewOpenRequests.length === 0 ? (
                          <div className="empty">
                            <div className="empty-title">
                              {searchQuery
                                ? "No matches"
                                : "No open requests right now"}
                            </div>
                            <div className="empty-sub">
                              {searchQuery
                                ? "Try a different search."
                                : "When retailers post open requests, they’ll appear here."}
                            </div>
                          </div>
                        ) : (
                          <div className="ex-table">
                            <div className="ex-thead ex-thead-sellreq">
                              <div>Request</div>
                              <div>Buyer</div>
                              <div>Qty.</div>
                              <div>Status</div>
                              <div></div>
                            </div>

                            <div className="exchange-scroll">
                              {sellerViewOpenRequests.map((r) => {
                                const st = r._status;

                                // unmatched open request => status requested, to_retailer_id null
                                const isUnmatched = r.to_retailer_id == null;
                                const showActions =
                                  isUnmatched && st === "requested";
                                const showCompletion =
                                  st === "accepted" &&
                                  String(r.to_retailer_id) ===
                                    String(retailerId);
                                const showContact = canShowContactSeller(r);

                                const completionLabel =
                                  completionLabelForSeller(r);
                                const createdLabel = formatDateTime(
                                  r.created_at,
                                );

                                // Hide finished/closed requests from Open requests list
                                if (
                                  st === "completed" ||
                                  st === "rejected" ||
                                  st === "cancelled"
                                )
                                  return null;

                                return (
                                  <div
                                    className="ex-row ex-row-sellreq"
                                    key={r.id}
                                  >
                                    <div className="req-mini req-mini-compact">
                                      <div className="req-product">
                                        {r.product_name}
                                      </div>
                                      {createdLabel ? (
                                        <div className="req-note muted">
                                          Posted: {createdLabel}
                                        </div>
                                      ) : null}
                                      {r.note ? (
                                        <div className="req-note muted">
                                          {r.note}
                                        </div>
                                      ) : null}
                                    </div>

                                    <div className="seller-cell">
                                      <div className="seller-name">
                                        {prettyRetailerName(r.from_retailer_id)}
                                      </div>
                                      {showContact ? (
                                        <button
                                          className="rowbtn"
                                          type="button"
                                          onClick={() =>
                                            openContact(r.from_retailer_id)
                                          }
                                          disabled={sending}
                                        >
                                          Contact
                                        </button>
                                      ) : (
                                        <span
                                          className="muted"
                                          style={{ fontSize: 12 }}
                                        >
                                          —
                                        </span>
                                      )}
                                    </div>

                                    <div>{r.quantity}</div>

                                    <div>
                                      <div className="status-stack">
                                        <span
                                          className={`chip ${st === "accepted" ? "ok" : "neutral"}`}
                                        >
                                          {st}
                                        </span>
                                        {completionLabel ? (
                                          <div
                                            className="muted"
                                            style={{
                                              fontSize: 12,
                                              marginTop: 4,
                                            }}
                                          >
                                            {completionLabel}
                                          </div>
                                        ) : null}
                                      </div>
                                    </div>

                                    <div className="manage-actions">
                                      {showActions ? (
                                        <>
                                          <button
                                            className="rowbtn"
                                            type="button"
                                            onClick={() => acceptRequest(r)}
                                            disabled={sending}
                                          >
                                            Accept
                                          </button>
                                          <button
                                            className="rowbtn danger"
                                            type="button"
                                            onClick={() =>
                                              dismissOpenRequest(r)
                                            }
                                            disabled={sending}
                                          >
                                            Delete
                                          </button>
                                        </>
                                      ) : null}

                                      {showCompletion ? (
                                        <button
                                          className="rowbtn"
                                          type="button"
                                          onClick={() =>
                                            markCompleted(r, "seller")
                                          }
                                          disabled={
                                            sending || !!r?.seller_completed
                                          }
                                        >
                                          {r?.seller_completed
                                            ? "Completed"
                                            : "Completed"}
                                        </button>
                                      ) : null}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )
              ) : null}

              {/* =========================
                  SELL → Manage my listings
                 ========================= */}
              {mode === "sell" && sellTab === "manage_listings" ? (
                myError ? (
                  <div className="inline-error">{myError}</div>
                ) : myLoading ? (
                  <div className="empty">
                    <div className="empty-title">Loading your listings…</div>
                    <div className="empty-sub">
                      Fetching your products from <code>retailer_listings</code>
                      .
                    </div>
                  </div>
                ) : filteredMyListings.length === 0 ? (
                  <div className="empty">
                    <div className="empty-title">
                      {searchQuery ? "No matches" : "No listings yet"}
                    </div>
                    <div className="empty-sub">
                      {searchQuery
                        ? "Try a different search."
                        : "Go to “Sell a product” to post your first item."}
                    </div>
                  </div>
                ) : (
                  <div className="ex-table">
                    <div className="ex-thead ex-thead-manage">
                      <div>Product</div>
                      <div>Status</div>
                      <div>Qty.</div>
                      <div>Price/unit</div>
                      <div></div>
                    </div>

                    <div className="exchange-scroll">
                      {filteredMyListings.map((p) => {
                        const updatedLabel = formatDateTime(p.updated_at);

                        return (
                          <div className="ex-row ex-row-manage" key={p.id}>
                            <div className="ex-prod">
                              <span className="thumb" aria-hidden="true">
                                {" "}
                                🏷️
                              </span>
                              <div className="ex-prod-text">
                                <div className="ex-prod-name">{p.name}</div>
                                <div className="ex-prod-sub muted">
                                  <span className="sku" title={p.sku}>
                                    SKU: {p.sku}
                                  </span>
                                  <span className="meta">• {p.category}</span>
                                  {updatedLabel ? (
                                    <span className="meta">
                                      • Updated: {updatedLabel}
                                    </span>
                                  ) : null}
                                </div>
                              </div>
                            </div>

                            <div>
                              <span
                                className={`chip ${p.is_active ? "ok" : "neutral"}`}
                              >
                                {p.is_active ? "Active" : "Hidden"}
                              </span>
                            </div>

                            <div>{p.stock}</div>
                            <div>AED {p.price.toFixed(2)}</div>

                            <div className="manage-actions">
                              <button
                                className="rowbtn"
                                type="button"
                                onClick={() => openEditListing(p)}
                                disabled={sending}
                              >
                                Edit
                              </button>
                              <button
                                className="btn ghost small"
                                style={{
                                  color: "#ff4d4f",
                                  borderColor: "#ff4d4f",
                                  padding: "4px 8px",
                                  fontSize: "12px",
                                }}
                                onClick={() => deleteListing(p.id)}
                              >
                                Remove
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )
              ) : null}
            </Panel>
          </section>

          {/* Side panel: keeps KPIs only */}
          <aside className="market-side">
            <Panel className="side-panel">
              <div className="side-kpis">
                <div className="kpi-refresh">
                  <button
                    className="btn ghost refresh-btn"
                    type="button"
                    onClick={refresh}
                  >
                    Refresh
                  </button>
                </div>
                <div className="side-kpi">
                  <div className="side-kpi-value">
                    {myLoading ? "—" : myListingsCount}{" "}
                  </div>
                  <div className="side-kpi-label">My listings</div>
                </div>

                <div className="side-kpi">
                  <div className="side-kpi-value">
                    {myReqLoading ? "—" : myRequests.length}
                  </div>
                  <div className="side-kpi-label">Your requests</div>
                </div>
              </div>

              <div className="side-foot muted"></div>
            </Panel>
          </aside>
        </section>
      </section>

      {/* Listing modal */}
      <ListingModal
        open={listingOpen}
        onClose={closeListingModal}
        sending={sending}
        categoryOptions={categoryOptions}
        inventoryOptions={inventoryOptions}
        listingName={listingName}
        setListingName={setListingName}
        listingSku={listingSku}
        setListingSku={setListingSku}
        listingCategory={listingCategory}
        setListingCategory={setListingCategory}
        listingStock={listingStock}
        setListingStock={setListingStock}
        listingPrice={listingPrice}
        setListingPrice={setListingPrice}
        selectedInvKey={selectedInvKey}
        setSelectedInvKey={setSelectedInvKey}
        selectedInvStock={selectedInvStock}
        setSelectedInvStock={setSelectedInvStock}
        isEditingListing={isEditingListing}
        onSubmit={saveListing}
        onClear={clearListingForm}
        showAddCategory={showAddCategory}
        setShowAddCategory={setShowAddCategory}
        newCategory={newCategory}
        setNewCategory={setNewCategory}
        sellCategoryOptions={sellCategoryOptions}
        setExtraCategories={setExtraCategories}
        selectedInvPrice={selectedInvPrice}
        setSelectedInvPrice={setSelectedInvPrice}
      />

      {/* Buy listing modal */}
      <BuyListingModal
        open={buyListingOpen}
        onClose={() => {
          if (sending) return;
          setBuyListingOpen(false);
          setBuyListingTarget(null);
        }}
        listing={buyListingTarget}
        maxQty={Number(buyListingTarget?._maxQty || 0)}
        sending={sending}
        qty={buyListingQty}
        setQty={setBuyListingQty}
        note={buyListingNote}
        setNote={setBuyListingNote}
        onSubmit={submitBuyFromListing}
      />

      {/* Contact modal */}
      <ContactModal
        open={contactOpen}
        onClose={() => {
          setContactOpen(false);
          setContactRetailerId(null);
          setContactInfo(null);
          setContactError("");
          setContactLoading(false);
        }}
        retailerMeta={contactRetailerMeta}
        contact={contactInfo}
        loading={contactLoading}
        error={contactError}
        myLocation={myLocation}
      />
    </main>
  );
}
