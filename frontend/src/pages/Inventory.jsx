import Icon from "../components/Icon";
// src/pages/Inventory.jsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { supabase } from "../supaBase/Client";
import "../styles/Inventory.css";
import "../styles/Management.css";
import ConfirmDialog from "../components/ConfirmDialog";
// import "../styles/RetailDashboard.css";
import Logo from "/src/styles/Logo.png";
import Avatar from "/src/styles/avatar.png";
import Papa from "papaparse";
import * as XLSX from "xlsx";

/* =========================
   Utils
========================= */
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

const statusFromStock = (stock) => {
  if (stock <= 0) return { label: "Out of stock", type: "bad" };
  if (stock <= 10) return { label: "Low stock", type: "warn" };
  return { label: "In stock", type: "ok" };
};

const formatMoney = (amount, currency) => {
  const c = String(currency || "AED").trim() || "AED";
  const n = Number(amount);
  if (!Number.isFinite(n)) return `${c} 0.00`;
  return `${c} ${n.toFixed(2)}`;
};

const formatDateTime = (iso) => {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString();
};

// Shared normalization helpers (used by inventory + orders import)
const normalizeKey = (k) =>
  String(k || "")
    .trim()
    .toLowerCase();
const toCleanString = (v) => String(v ?? "").trim();
const toNumberSafe = (v) => {
  const n = Number(
    String(v ?? "")
      .replace(/,/g, "")
      .trim(),
  );
  return Number.isFinite(n) ? n : NaN;
};
const toIntSafe = (v) => {
  const n = Number(String(v ?? "").trim());
  return Number.isInteger(n) ? n : NaN;
};

// =========================
// Mapping helpers (manual uploads)
// =========================
const normMapKey = (s) =>
  String(s || "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");

const autoGuessMapping = (headers, requiredFields) => {
  const h = headers || [];

  const normHeaders = h.map((raw) => {
    const mainPart = raw.split(" - ")[0];
    return {
      raw: raw,
      nMain: normMapKey(mainPart),
      nFull: normMapKey(raw),
    };
  });

  const out = {};
  requiredFields.forEach((field) => {
    const friendlyName = INVENTORY_DISPLAY_NAMES[field] || field;
    const nf = normMapKey(friendlyName);

    // 1. EXACT TITLE MATCH
    const exactMatch = normHeaders.find((x) => x.nMain === nf);
    if (exactMatch) {
      out[field] = exactMatch.raw;
      return;
    }

    // 2. STARTS WITH MATCH (Fixed the variable name error here)
    const prefixMatch = normHeaders.find((x) => x.nFull.startsWith(nf));
    if (prefixMatch) {
      out[field] = prefixMatch.raw;
      return;
    }

    // 3. FUZZY INCLUDES
    const fuzzyMatch = normHeaders.find(
      (x) => x.nFull.includes(nf) || nf.includes(x.nMain),
    );
    if (fuzzyMatch) {
      out[field] = fuzzyMatch.raw;
      return;
    }

    out[field] = "";
  });

  return out;
};

/* =========================
   Topbar
========================= */
const Topbar = ({ displayName, role, onLogout, activePage }) => (
  <header className="topbar">
    <a
      href="/"
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
    </a>

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

/* =========================
   Small UI helpers
========================= */
const Panel = ({ children }) => <section className="panel">{children}</section>;

/* =========================
   Modal: Add / Update Product
========================= */
function ProductModal({
  open,
  onClose,
  onSubmit,
  submitting,
  initial,
  categoryOptions = [],
  saveError,
}) {
  const dialogRef = useRef(null);
  const ADD_NEW = "__add_new__";
  useEffect(() => {
    if (!open || !dialogRef.current) return;
    const previous = document.activeElement;
    const dialog = dialogRef.current;
    dialog.showModal();
    return () => { dialog.close(); previous?.focus?.(); };
  }, [open]);

  const [name, setName] = useState(initial?.name || "");
  const [sku, setSku] = useState(initial?.sku || "");

  const [categoryMode, setCategoryMode] = useState("select"); // select | custom
  const [categorySelect, setCategorySelect] = useState(initial?.category || "");

  const [categoryCustom, setCategoryCustom] = useState("");

  const [price, setPrice] = useState(initial?.price ?? "");
  const [stock, setStock] = useState(initial?.stock ?? "");
  const [customerNote, setCustomerNote] = useState(
    initial?.customer_note || initial?.note || "",
  );

  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!open) return;

    const initCat = initial?.category || "";
    setName(initial?.name || "");
    setSku(initial?.sku || "");

    const hasInOptions = initCat && categoryOptions.includes(initCat);
    setCategoryMode(hasInOptions || !initCat ? "select" : "custom");
    setCategorySelect(hasInOptions ? initCat : "");
    setCategoryCustom(!hasInOptions ? initCat : "");

    setPrice(initial?.price ?? "");
    setStock(initial?.stock ?? "");
    setCustomerNote(initial?.customer_note || initial?.note || "");
    setErrors({});
  }, [open, initial]);

  const resolvedCategory = () => {
    const v = categoryMode === "custom" ? categoryCustom : categorySelect;
    return String(v || "").trim();
  };

  const validate = () => {
    const e = {};
    const nSku = normalizeSku(sku);
    const cat = resolvedCategory();

    if (!name.trim()) e.name = "Product name is required.";
    if (!nSku) e.sku = "SKU is required.";
    if (nSku && !/^[A-Z0-9\-_:.]+$/.test(nSku))
      e.sku = "SKU may contain letters, numbers, hyphens, underscores, colons and dots.";
    if (!cat) e.category = "Category is required.";

    const p = toNumber(price);
    if (!Number.isFinite(p))
      e.price = "Price must be a valid number (example: 2.50).";
    if (Number.isFinite(p) && p < 0) e.price = "Price cannot be negative.";

    const s = toInt(stock);
    if (!Number.isInteger(s))
      e.stock = "Stock must be a whole number (example: 12).";
    if (Number.isInteger(s) && s < 0) e.stock = "Stock cannot be negative.";

    setErrors(e);
    return {
      ok: Object.keys(e).length === 0,
      values: {
        name,
        sku: nSku,
        category: cat,
        price: p,
        stock: s,
        customer_note: String(customerNote || "").trim(),
      },
    };
  };

  const handleSave = async (e) => {
    e.preventDefault();
    const { ok, values } = validate();
    if (!ok) return;
    await onSubmit(values);
  };

  const onCategoryChange = (val) => {
    if (val === ADD_NEW) {
      setCategoryMode("custom");
      setCategorySelect("");
      setCategoryCustom("");
      return;
    }
    setCategoryMode("select");
    setCategorySelect(val);
    setCategoryCustom("");
  };

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      className="modal-backdrop product-dialog"
      onCancel={event => { event.preventDefault(); if (!submitting) onClose(); }}
      role="dialog"
      aria-modal="true"
      aria-label={initial ? "Edit product" : "Add product"}
    >
      <div className="modal">
        <div className="modal-head">
          <div>
            <h3 className="modal-title">
              {initial ? "Edit product" : "Add product"}
            </h3>
            <p className="modal-sub">
              Update your store inventory. Marketplace listings are managed separately.
            </p>
          </div>
          <button
            className="iconbtn"
            type="button"
            onClick={onClose}
            aria-label="Close"
            disabled={submitting}
          >
            <Icon name="close" />
          </button>
        </div>

        <form className="form" onSubmit={handleSave}>
          <div className="grid2">
            <label className="field">
              <span className="label">Product name</span>
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Bottled Water (500ml)"
                className={errors.name ? "invalid" : ""}
              />
              {errors.name && <span className="error">{errors.name}</span>}
            </label>

            <label className="field">
              <span className="label">SKU</span>
              <input
                value={sku}
                onChange={(e) => setSku(e.target.value)}
                placeholder="e.g. WTR-500"
                className={errors.sku ? "invalid" : ""}
              />
              {errors.sku && <span className="error">{errors.sku}</span>}
            </label>
          </div>

          <div className="grid2">
            <label className="field">
              <span className="label">Category</span>

              <select
                aria-label="Category"
                value={
                  categoryMode === "custom" ? "__add_new__" : categorySelect
                }
                onChange={(e) => onCategoryChange(e.target.value)}
                className={errors.category ? "invalid" : ""}
              >
                <option value="" disabled>
                  Select a category
                </option>
                {categoryOptions
                  .filter((c) => c !== "all")
                  .map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                <option value="__add_new__">+ Add a new category…</option>
              </select>

              {categoryMode === "custom" && (
                <div className="category-new">
                  <input
                    value={categoryCustom}
                    onChange={(e) => setCategoryCustom(e.target.value)}
                    placeholder="Type a new category…"
                    className={errors.category ? "invalid" : ""}
                  />
                </div>
              )}

              {errors.category && (
                <span className="error">{errors.category}</span>
              )}
            </label>

            <div className="grid2 tight">
              <label className="field">
                <span className="label">Price (AED)</span>
                <input
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  inputMode="decimal"
                  placeholder="e.g. 2.50"
                  className={errors.price ? "invalid" : ""}
                />
                {errors.price && <span className="error">{errors.price}</span>}
              </label>

              <label className="field">
                <span className="label">Stock</span>
                <input
                  value={stock}
                  onChange={(e) => setStock(e.target.value)}
                  inputMode="numeric"
                  placeholder="e.g. 12"
                  className={errors.stock ? "invalid" : ""}
                />
                {errors.stock && <span className="error">{errors.stock}</span>}
              </label>
            </div>
          </div>

          {saveError && <p className="management-error" role="alert">{saveError}</p>}

          <div className="modal-actions">
            <button
              className="btn ghost"
              type="button"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button className="btn primary" type="submit" disabled={submitting}>
              {submitting ? "Saving..." : "Save product"}
            </button>
          </div>
        </form>
      </div>
    </dialog>
  );
}

function ConnectPOSModal({ open, onClose, onConnectSquare, connecting }) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <div className="modal-head">
          <div>
            <h3 className="modal-title">Connect to POS</h3>
            <p className="modal-sub">
              Connect your Square account to sync products automatically.
            </p>
          </div>
          <button
            className="iconbtn"
            type="button"
            onClick={onClose}
            disabled={connecting}
           aria-label="Close dialog">
            <Icon name="close" />
          </button>
        </div>

        <div className="form">
          <div className="info-card">
            <div className="info-title">Square Integration</div>
            <div className="info-text">
              You’ll be redirected to authorize Square. Once connected, your
              items can be imported into your inventory.
            </div>
          </div>

          <div className="modal-actions">
            <button
              className="btn primary"
              type="button"
              onClick={onConnectSquare}
              disabled={connecting}
            >
              {connecting ? "Connecting..." : "Connect Square"}
            </button>
            <button
              className="btn ghost"
              type="button"
              onClick={onClose}
              disabled={connecting}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* =========================
   Modal: Order Details
========================= */
function OrderDetailsModal({ open, onClose, order, items, loading, error }) {
  if (!open) return null;

  const orderTitle = order?.external_order_id
    ? `Order ${order.external_order_id}`
    : "Order details";

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Order details"
    >
      <div className="modal">
        <div className="modal-head">
          <div>
            <h3 className="modal-title">{orderTitle}</h3>
            <p className="modal-sub">
              {order?.order_time
                ? `Placed: ${formatDateTime(order.order_time)}`
                : ""}
              {order?.status ? ` • Status: ${order.status}` : ""}
              {order?.source ? ` • Source: ${order.source}` : ""}
            </p>
          </div>
          <button
            className="iconbtn"
            type="button"
            onClick={onClose}
            aria-label="Close"
          >
            <Icon name="close" />
          </button>
        </div>

        <div className="form">
          {error && <div className="inline-error">{error}</div>}

          <div className="table table-order-items">
            <div className="thead">
              <div>Item</div>
              <div>Quantity</div>
              <div>Total</div>
            </div>

            <div className="inventory-scroll" style={{ maxHeight: 360 }}>
              {loading ? (
                <div className="trow trow-single">
                  <div className="muted">Loading items...</div>
                </div>
              ) : !items || items.length === 0 ? (
                <div className="trow trow-single">
                  <div className="muted">No items found for this order.</div>
                </div>
              ) : (
                items.map((it) => (
                  <div className="trow" key={it.id}>
                    <div className="cell-clip">{it.item_name || "-"}</div>
                    <div className="cell-mono">{Number(it.quantity || 0)}</div>
                    <div className="cell-mono">
                      {formatMoney(
                        it.total_amount ?? 0,
                        it.currency || order?.currency,
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="modal-actions">
            <button className="btn primary" type="button" onClick={onClose}>
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
const INVENTORY_DISPLAY_NAMES = {
  // Inventory Labels
  product_name: "Product name",
  category: "Category",
  price: "Price",
  stock_quantity: "Quantity",
  sku: "Product SKU",
  pos_location_id: "Location",
  variation_sku: "Product variation SKU",
  variation_name: "Variation name",

  // Orders Labels (Added these)
  status: "Order status",
  source: "Order source",
  item_total_amount: "Item amount (Total)",
  currency: "Currency",
  external_order_id: "Order ID",
  order_time: "Date & Time",
  item_name: "Product Name",
  quantity: "Quantity",
  total_amount: "Total Amount",
  product_sku: "SKU",
  customer_name: "Customer Name",
  order_status: "Status",
  external_location_id: "Location",
};

/* =========================
   Inventory Page
========================= */
export default function Inventory() {
  const { user, profile, signOut } = useAuth();
  const navigate = useNavigate();

  const retailerId = useMemo(
    () => profile?.id || profile?.retailer_id || user?.id || null,
    [profile, user],
  );
  const displayName =
    profile?.full_name ||
    user?.user_metadata?.full_name ||
    user?.email ||
    "there";
  const role = profile?.role || "User";

  // Tabs
  const [activeTab, setActiveTab] = useState("inventory"); // "inventory" | "orders"

  // Inventory state
  const [inventory, setInventory] = useState([]);
  const [invLoading, setInvLoading] = useState(true);
  const [invError, setInvError] = useState("");

  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("updated");

  const [modalOpen, setModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [productSaveError, setProductSaveError] = useState("");
  const [deleteProduct, setDeleteProduct] = useState(null);
  const [deleteError, setDeleteError] = useState("");
  const [inventoryNotice, setInventoryNotice] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [posModalOpen, setPosModalOpen] = useState(false);
  const [connectingPOS, setConnectingPOS] = useState(false);

  // Live-sync state
  const [posConnection, setPosConnection] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const [importing, setImporting] = useState(false);
  const importInputId = "inv-import-input";

  // Import menu card state
  const [importMenuOpen, setImportMenuOpen] = useState(false);
  const importMenuRef = useRef(null);

  const [manualImportOpen, setManualImportOpen] = useState(false);
  const [manualImportType, setManualImportType] = useState(null); // "inventory" | "orders"

  const [mappingOpen, setMappingOpen] = useState(false);
  const [fileHeaders, setFileHeaders] = useState([]);
  const [parsedRows, setParsedRows] = useState([]);

  const [ordersImporting, setOrdersImporting] = useState(false);
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  // Orders state
  const [orders, setOrders] = useState([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersError, setOrdersError] = useState("");
  const [orderSort, setOrderSort] = useState("desc"); // desc = latest->oldest

  // Order details
  const [orderDetailsOpen, setOrderDetailsOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [orderItems, setOrderItems] = useState([]);
  const [orderItemsLoading, setOrderItemsLoading] = useState(false);
  const [orderItemsError, setOrderItemsError] = useState("");

  const [headerMapping, setHeaderMapping] = useState({});
  const [mappingError, setMappingError] = useState("");

  const handleLogout = async () => {
    await signOut();
    navigate("/login");
  };

  const loadInventory = async () => {
    if (!retailerId) {
      setInvLoading(false);
      setInvError("Missing retailer id.");
      return;
    }

    //  require active connection to decide what inventory to show
    const connId = posConnection?.id;
    if (!connId) {
      setInventory([]);
      setInvLoading(false);
      return;
    }

    setInvError("");
    setInvLoading(true);

    const { data, error } = await supabase
      .from("products")
      .select(
        `
        id,
        name,
        category,
        retailer_id,
        sku,
        price,
        product_variations (
          id,
          sku,
          name,
          price,
          currency,
          active,
          updated_at,
          product_inventory (
            pos_connection_id,
            quantity
          )
        ),
        updated_at
      `,
      )
      .eq("retailer_id", retailerId)
      .order("id", { ascending: false })
      .eq("active", true);

    if (error) {
      setInvError(error.message || "Failed to load inventory.");
      setInventory([]);
      setInvLoading(false);
      return;
    }

    const rows = [];

    (data || []).forEach((product) => {
      const vars = product.product_variations || [];

      //  only show variations that have inventory for this connection
      vars.forEach((variation) => {
        if (!variation.active) return;

        const invRows = (variation.product_inventory || []).filter(
          (x) => x.pos_connection_id === connId,
        );

        if (invRows.length === 0) return;

        const totalQty = invRows.reduce(
          (sum, x) => sum + Number(x.quantity || 0),
          0,
        );

        rows.push({
          id: variation.id,
          product_id: product.id,
          name: product.name,
          category: product.category,
          sku: variation.sku,
          price: Number(variation.price || 0),
          stock: totalQty,
          updated_at:
            variation.updated_at ||
            product.updated_at ||
            new Date().toISOString(),
        });
      });
    });

    setInventory(rows);
    setInvLoading(false);
  };

  const loadPosConnection = async () => {
    if (!retailerId) return;

    const { data, error } = await supabase
      .from("pos_connections")
      .select(
        "id, provider, status, is_active, last_error, last_synced_at, updated_at",
      )
      .eq("retailer_id", retailerId)
      .eq("is_active", true)
      .maybeSingle();

    setPosConnection(error ? null : (data ?? null));
  };

  const loadOrders = async () => {
    if (!retailerId) {
      setOrders([]);
      setOrdersError("Missing retailer id.");
      return;
    }

    //  require active connection (same idea as inventory)
    const connId = posConnection?.id;
    if (!connId) {
      setOrders([]);
      return;
    }

    setOrdersError("");
    setOrdersLoading(true);

    const ascending = orderSort === "asc";

    const { data, error } = await supabase
      .from("orders")
      .select(
        "id, retailer_id, pos_connection_id, source, status, order_time, total_amount, currency, external_order_id, external_location_id, is_active",
      )
      .eq("retailer_id", retailerId)
      .eq("pos_connection_id", connId)
      .eq("is_active", true)
      .order("order_time", { ascending });

    if (error) {
      setOrdersError(error.message || "Failed to load orders.");
      setOrders([]);
    } else {
      setOrders(data || []);
    }

    setOrdersLoading(false);
  };

  const openOrderDetails = async (order) => {
    if (!order?.id) return;

    // safety: only allow details for active orders
    if (order.is_active === false) {
      alert(
        "This order belongs to a different connection/mode. Switch provider to view it.",
      );
      return;
    }

    setSelectedOrder(order);
    setOrderItems([]);
    setOrderItemsError("");
    setOrderItemsLoading(true);
    setOrderDetailsOpen(true);

    try {
      const { data, error } = await supabase
        .from("order_items")
        .select("id, order_id, item_name, quantity, total_amount, currency")
        .eq("order_id", order.id)
        .eq("is_active", true)
        .order("created_at", { ascending: true });

      if (error) throw error;
      setOrderItems(data || []);
    } catch (e) {
      setOrderItemsError(e?.message || "Failed to load order items.");
      setOrderItems([]);
    } finally {
      setOrderItemsLoading(false);
    }
  };

  useEffect(() => {
    if (!user || !retailerId) return;

    (async () => {
      await loadPosConnection(); // <Icon name="success" /> first
    })();
  }, [user, retailerId]);

  useEffect(() => {
    if (!user || !retailerId) return;
    if (!posConnection?.id) { setInventory([]); setInvLoading(false); return; }

    loadInventory(); // <Icon name="success" /> only when we know which connection is active
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, retailerId, posConnection?.id]);

  // Load orders when switching to Orders tab, and whenever sort changes while on Orders
  useEffect(() => {
    if (!user || !retailerId) return;
    if (activeTab !== "orders") return;
    loadOrders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, orderSort, user, retailerId]);

  // Close import menu on outside click + escape
  useEffect(() => {
    if (!importMenuOpen) return;

    const onDown = (e) => {
      if (!importMenuRef.current) return;
      if (!importMenuRef.current.contains(e.target)) setImportMenuOpen(false);
    };

    const onKey = (e) => {
      if (e.key === "Escape") setImportMenuOpen(false);
    };

    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [importMenuOpen]);

  /* =========================
     POS Connect Handler
  ========================== */
  const handleConnect = async () => {
    try {
      setConnectingPOS(true);

      const { data, error } = await supabase.auth.getSession();
      if (error) throw error;

      const session = data.session;
      if (!session?.access_token) {
        alert("Please log in first.");
        return;
      }

      const { data: funcData, error: funcError } =
        await supabase.functions.invoke("connect-square");
      if (funcError) throw funcError;

      if (funcData?.vault_url) {
        window.location.href = funcData.vault_url; // same tab, hard redirect
        return;
      } else {
        throw new Error("No vault_url returned");
      }
    } catch (err) {
      console.error("Connect Square error:", err);
      alert("Failed to connect to Square: " + (err.message || err));
    } finally {
      setConnectingPOS(false);
    }
  };

  function computeLiveSyncState(conn) {
    if (!conn) return { state: "not_connected", label: "Not connected" };
    const isConnected = conn.status === "connected" && !conn.last_error;
    const staleMs = 24 * 60 * 60 * 1000;
    const lastSyncTs = conn.last_synced_at
      ? new Date(conn.last_synced_at).getTime()
      : 0;
    const isStale = !lastSyncTs || Date.now() - lastSyncTs > staleMs;
    if (isConnected && !isStale)
      return { state: "connected", label: "Connected" };
    return { state: "refresh", label: "Refresh connection" };
  }
  const liveSync = computeLiveSyncState(posConnection);

  const handleSyncNow = async () => {
    if (!retailerId) return;

    try {
      setSyncing(true);
      const { error } = await supabase.functions.invoke("pos-sync", {
        body: { retailer_id: retailerId },
      });
      if (error) throw error;

      await loadPosConnection();
      await loadInventory();
      alert("Sync complete.");
    } catch (e) {
      console.error(e);
      alert(e?.message || "Failed to sync.");
      await loadPosConnection();
    } finally {
      setSyncing(false);
    }
  };

  const handleModalSubmit = async values => {
    setSubmitting(true); setProductSaveError("");
    try {
      const { error } = await supabase.rpc("save_my_product", {
        variation_id: editingProduct?.id || null, product_name: values.name.trim(),
        sku: values.sku, category: values.category, price: values.price, quantity: values.stock,
      });
      if (error) throw error;
      await loadInventory(); setModalOpen(false);
      setInventoryNotice(editingProduct ? "Product updated. Stock recommendations are being refreshed." : "Product added to your inventory.");
    } catch (error) { setProductSaveError(error.message || "Could not save product. Try again."); }
    finally { setSubmitting(false); }
  };
  const confirmProductDelete = async text => {
    setSubmitting(true); setDeleteError("");
    try {
      const { error } = await supabase.rpc("delete_my_product", { variation_id: deleteProduct.id, confirmation: text });
      if (error) throw error;
      await loadInventory(); setDeleteProduct(null); setInventoryNotice("Product deleted. Historical orders have been retained.");
    } catch (error) { setDeleteError(error.message || "Could not delete this product."); }
    finally { setSubmitting(false); }
  };

  const parseCSV = (file) =>
    new Promise((resolve, reject) => {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: (results) => resolve(results.data || []),
        error: (err) => reject(err),
      });
    });

  const parseExcel = async (file) => {
    const buf = await file.arrayBuffer();
    const wb = XLSX.read(buf, { type: "array" });
    const sheetName = wb.SheetNames[0]; // single-sheet expectation
    const sheet = wb.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json(sheet, { defval: "" });
    return rows || [];
  };

  // ---- auto map Square export headers -> our internal inventory import schema ----

  const downloadTemplate = (type) => {
    let headers = [];
    const fileName =
      type === "inventory" ? "Inventory_Template.xlsx" : "Orders_Template.xlsx";

    if (type === "inventory") {
      headers = [
        "product_name",
        "category",
        "price",
        "stock_quantity",
        "sku",
        "pos_location_id",
        "variation_sku",
        "variation_name",
      ];
    } else {
      headers = [
        "external_order_id",
        "order_time",
        "item_name",
        "quantity",
        "total_amount",
        "product_sku",
        "customer_name",
        "order_status",
      ];
    }

    // Row 1: Headers, Row 2: Empty (User starts here)
    const data = [headers, []];
    const ws = XLSX.utils.aoa_to_sheet(data);
    const wb = XLSX.utils.book_new();

    ws["!cols"] = headers.map(() => ({ wch: 20 }));
    XLSX.utils.book_append_sheet(wb, ws, "Template");
    XLSX.writeFile(wb, fileName);
  };

  const validateAndNormalizeInventoryRows = (rows) => {
    const errors = [];
    const okRows = [];

    if (!Array.isArray(rows) || rows.length === 0) {
      return { okRows: [], errors: ["File has no rows."] };
    }

    const first = rows[0] || {};
    const keys = Object.keys(first).map(normalizeKey);

    const required = [
      "product_name",
      "category",
      "product_sku",
      "variation_sku",
      "variation_name",
      "price",
      "quantity",
      "pos_location_id",
    ];

    const missing = required.filter((c) => !keys.includes(c));
    if (missing.length) {
      return {
        okRows: [],
        errors: [
          `Missing required columns: ${missing.join(", ")}`,
          `Found columns: ${Object.keys(first).join(", ")}`,
        ],
      };
    }

    rows.forEach((raw, idx) => {
      const rowNum = idx + 2;

      const get = (col) => {
        const exact = raw[col];
        if (exact !== undefined) return exact;
        const foundKey = Object.keys(raw).find((k) => normalizeKey(k) === col);
        return foundKey ? raw[foundKey] : undefined;
      };

      const product_name = toCleanString(get("product_name"));
      const category = toCleanString(get("category"));
      const product_sku = toCleanString(get("product_sku"));
      const variation_sku = toCleanString(get("variation_sku"));
      const variation_name = toCleanString(get("variation_name"));
      const pos_location_id = toCleanString(get("pos_location_id"));

      const price = toNumberSafe(get("price"));
      const quantity = toIntSafe(get("quantity"));
      const currency = toCleanString(get("currency")) || "AED";

      const rowErrors = [];
      if (!product_name) rowErrors.push("product_name is empty");
      if (!category) rowErrors.push("category is empty");
      if (!product_sku) rowErrors.push("product_sku is empty");
      if (!variation_sku) rowErrors.push("variation_sku is empty");
      if (!variation_name) rowErrors.push("variation_name is empty");
      if (!pos_location_id) rowErrors.push("pos_location_id is empty");
      if (!Number.isFinite(price) || price < 0)
        rowErrors.push("price must be a valid number >= 0");
      if (!Number.isInteger(quantity) || quantity < 0)
        rowErrors.push("quantity must be a whole number >= 0");

      if (rowErrors.length) {
        errors.push(`Row ${rowNum}: ${rowErrors.join("; ")}`);
        return;
      }

      okRows.push({
        product_name,
        category,
        product_sku,
        variation_sku,
        variation_name,
        price,
        quantity,
        pos_location_id,
        currency,
      });
    });

    return { okRows, errors };
  };

  // =========================
  // Orders import helpers (single-sheet)
  // =========================
  const getByNormalizedKey = (obj, key) => {
    const want = normalizeKey(key);
    const foundKey = Object.keys(obj || {}).find(
      (k) => normalizeKey(k) === want,
    );
    return foundKey ? obj[foundKey] : undefined;
  };

  const validateAndNormalizeOrderRows = (rows) => {
    const errors = [];
    const okRows = [];

    if (!Array.isArray(rows) || rows.length === 0) {
      return { okRows: [], errors: ["File has no rows."] };
    }

    const first = rows[0] || {};
    const keys = Object.keys(first).map(normalizeKey);

    const required = [
      "external_order_id",
      "order_time",
      "status",
      "source",
      "item_name",
      "quantity",
      "item_total_amount",
      "currency",
    ];

    const missing = required.filter((c) => !keys.includes(c));
    if (missing.length) {
      return {
        okRows: [],
        errors: [
          `Missing required columns: ${missing.join(", ")}`,
          `Found columns: ${Object.keys(first).join(", ")}`,
        ],
      };
    }

    rows.forEach((raw, idx) => {
      const rowNum = idx + 2;

      const external_order_id = toCleanString(
        getByNormalizedKey(raw, "external_order_id"),
      );
      const order_time = toCleanString(getByNormalizedKey(raw, "order_time"));
      const status =
        toCleanString(getByNormalizedKey(raw, "status")) || "completed";
      const source =
        toCleanString(getByNormalizedKey(raw, "source")) || "manual";
      const external_location_id = toCleanString(
        getByNormalizedKey(raw, "external_location_id"),
      );

      const item_name = toCleanString(getByNormalizedKey(raw, "item_name"));
      const sku = toCleanString(getByNormalizedKey(raw, "sku"));

      const quantity = toNumberSafe(getByNormalizedKey(raw, "quantity"));
      const item_total_amount = toNumberSafe(
        getByNormalizedKey(raw, "item_total_amount"),
      );
      const currency =
        toCleanString(getByNormalizedKey(raw, "currency")) || "AED";

      const rowErrors = [];

      if (!external_order_id) rowErrors.push("external_order_id is empty");
      if (!order_time) rowErrors.push("order_time is empty");
      if (!item_name) rowErrors.push("item_name is empty");
      if (!Number.isFinite(quantity) || quantity <= 0)
        rowErrors.push("quantity must be a number > 0");
      if (!Number.isFinite(item_total_amount) || item_total_amount < 0)
        rowErrors.push("item_total_amount must be a number >= 0");

      // DB constraints (from your schema)
      const allowedStatus = ["completed", "cancelled", "refunded", "unknown"];
      const allowedSource = ["square", "manual"];
      if (!allowedStatus.includes(status))
        rowErrors.push(`status must be one of: ${allowedStatus.join(", ")}`);
      if (!allowedSource.includes(source))
        rowErrors.push(`source must be one of: ${allowedSource.join(", ")}`);

      if (rowErrors.length) {
        errors.push(`Row ${rowNum}: ${rowErrors.join("; ")}`);
        return;
      }

      okRows.push({
        external_order_id,
        order_time,
        status,
        source,
        external_location_id: external_location_id || null,
        item_name,
        sku: sku || null,
        quantity,
        item_total_amount,
        currency,
      });
    });

    return { okRows, errors };
  };

  const importOrdersFromSingleSheet = async (okRows) => {
    if (!retailerId) throw new Error("Missing retailer id.");
    if (!posConnection?.id)
      throw new Error(
        "No active manual POS connection. Switch to manual mode first.",
      );

    const connId = posConnection?.id || null;

    // group by external_order_id
    const groups = new Map();
    for (const r of okRows) {
      const key = r.external_order_id;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(r);
    }

    const orderPayload = Array.from(groups.entries()).map(
      ([external_order_id, rows]) => {
        const first = rows[0];
        const total_amount = rows.reduce(
          (sum, x) => sum + (Number(x.item_total_amount) || 0),
          0,
        );

        return {
          retailer_id: retailerId,
          source: first.source,
          pos_connection_id: connId,
          external_order_id,
          external_location_id: first.external_location_id,
          status: first.status,
          order_time: first.order_time,
          total_amount: Number(total_amount.toFixed(2)),
          currency: first.currency || "AED",
          is_active: true,
          updated_at: new Date().toISOString(),
        };
      },
    );

    const extIds = orderPayload.map((o) => o.external_order_id);

    // Duplicate guard without DB constraint
    const { data: existing, error: existingErr } = await supabase
      .from("orders")
      .select("external_order_id")
      .eq("retailer_id", retailerId)
      .eq("pos_connection_id", connId)
      .in("external_order_id", extIds);

    if (existingErr) throw existingErr;

    const existingSet = new Set(
      (existing || []).map((x) => x.external_order_id),
    );

    const existingExtIds = orderPayload
      .filter((o) => existingSet.has(o.external_order_id))
      .map((o) => o.external_order_id);

    if (existingExtIds.length > 0) {
      const now = new Date().toISOString();

      // reactivate existing matching orders for THIS connection
      const { error: reactErr } = await supabase
        .from("orders")
        .update({ is_active: true, updated_at: now })
        .eq("retailer_id", retailerId)
        .eq("pos_connection_id", connId)
        .in("external_order_id", existingExtIds);

      if (reactErr) throw reactErr;
    }
    const newOrdersOnly = orderPayload.filter(
      (o) => !existingSet.has(o.external_order_id),
    );

    // Insert only new orders (safe when 0)
    if (newOrdersOnly.length > 0) {
      const { error } = await supabase.from("orders").insert(newOrdersOnly);
      if (error) throw error;
    }
    const { data: allOrders, error: allOrdersErr } = await supabase
      .from("orders")
      .select("id, external_order_id")
      .eq("retailer_id", retailerId)
      .eq("pos_connection_id", connId)
      .in("external_order_id", extIds);

    if (allOrdersErr) throw allOrdersErr;
    // Fetch ALL matching orders (new + existing) so we can map items
    const orderIdByExternal = new Map(
      (allOrders ?? []).map((o) => [o.external_order_id, o.id]),
    );

    // Prevent duplicates: delete existing items for these orders, then re-insert
    const orderIds = [
      ...new Set(
        Array.from(orderIdByExternal.values()).filter(
          (id) => typeof id === "string" && id.trim().length > 0,
        ),
      ),
    ];

    console.log("Resolved orderIds for RPC delete:", {
      count: orderIds.length,
      connId,
      retailerId,
    });

    if (orderIds.length > 0) {
      const { error: delErr } = await supabase.rpc(
        "delete_order_items_for_orders",
        {
          p_retailer_id: retailerId,
          p_conn_id: connId,
          p_order_ids: orderIds,
        },
      );

      if (delErr) {
        console.error("RPC delete_order_items_for_orders failed:", {
          message: delErr.message,
          details: delErr.details,
          hint: delErr.hint,
          code: delErr.code,
          full: delErr,
          retailerId,
          connId,
          orderIdsCount: orderIds.length,
        });
        throw delErr;
      }
    }

    const itemsPayload = okRows.map((r) => {
      const order_id = orderIdByExternal.get(r.external_order_id);
      if (!order_id)
        throw new Error(
          `Could not resolve order_id for external_order_id: ${r.external_order_id}`,
        );
      return {
        order_id,
        item_name: r.item_name,
        pos_connection_id: connId,
        quantity: r.quantity,
        total_amount: r.item_total_amount,
        currency: r.currency || "AED",
        is_active: true,
        updated_at: new Date().toISOString(),
      };
    });

    const { error: itemsErr } = await supabase
      .from("order_items")
      .insert(itemsPayload);

    if (itemsErr) throw itemsErr;

    return {
      totalOrdersInFile: groups.size,
      newOrdersInserted: newOrdersOnly.length,
      itemsCount: itemsPayload.length,
    };
  };

  const categories = useMemo(() => {
    const set = new Set();
    inventory.forEach((r) => {
      if (r?.category) set.add(r.category);
    });
    return ["all", ...Array.from(set).sort()];
  }, [inventory]);

  const filteredInventory = useMemo(() => {
    const q = search.trim().toLowerCase();

    let rows = [...inventory].filter((row) => {
      const matchesSearch =
        !q ||
        row.name?.toLowerCase().includes(q) ||
        row.sku?.toLowerCase().includes(q) ||
        row.category?.toLowerCase().includes(q);

      const matchesCategory =
        categoryFilter === "all"
          ? true
          : (row.category || "") === categoryFilter;

      const st = row.stock ?? 0;
      const matchesStatus =
        statusFilter === "all"
          ? true
          : statusFilter === "in"
            ? st > 10
            : statusFilter === "low"
              ? st > 0 && st <= 10
              : statusFilter === "oos"
                ? st <= 0
                : true;

      return matchesSearch && matchesCategory && matchesStatus;
    });

    rows.sort((a, b) => {
      if (sortBy === "updated")
        return (
          (new Date(b.updated_at).getTime() || 0) -
          (new Date(a.updated_at).getTime() || 0)
        );
      if (sortBy === "price_asc") return (a.price ?? 0) - (b.price ?? 0);
      if (sortBy === "price_desc") return (b.price ?? 0) - (a.price ?? 0);
      if (sortBy === "stock_asc") return (a.stock ?? 0) - (b.stock ?? 0);
      if (sortBy === "stock_desc") return (b.stock ?? 0) - (a.stock ?? 0);
      return 0;
    });

    return rows;
  }, [inventory, search, categoryFilter, statusFilter, sortBy]);

  const stockStats = useMemo(() => {
    const inStock = inventory.filter((r) => (r.stock ?? 0) > 10).length;
    const low = inventory.filter(
      (r) => (r.stock ?? 0) > 0 && (r.stock ?? 0) <= 10,
    ).length;
    const oos = inventory.filter((r) => (r.stock ?? 0) <= 0).length;
    return { inStock, low, oos };
  }, [inventory]);

  const resetInventoryFilters = () => {
    setSearch("");
    setCategoryFilter("all");
    setStatusFilter("all");
    setSortBy("updated");
  };

  const resetOrdersFilters = () => {
    setOrderSort("desc");
  };

  const handleImportPick = () => {
    const el = document.getElementById(importInputId);
    if (el) el.click();
  };

  const importInventoryIntoThreeTables = async (rows) => {
    if (!retailerId) throw new Error("Missing retailer id");

    const manualConnId = posConnection?.id;
    if (!manualConnId)
      throw new Error("Missing active POS connection id (manual).");

    const now = new Date().toISOString();

    // =========================
    //  SAFE CLEANUP (TENANT SCOPED)
    // =========================
    const { error: resetErr } = await supabase.rpc(
      "reset_inventory_for_connection",
      {
        p_retailer_id: retailerId,
        p_conn_id: manualConnId,
      },
    );

    if (resetErr) {
      console.error("reset_inventory_for_connection failed:", {
        message: resetErr.message,
        details: resetErr.details,
        hint: resetErr.hint,
        code: resetErr.code,
        full: resetErr,
        retailerId,
        manualConnId,
      });
      throw resetErr;
    }

    // =========================
    // 1) PRODUCTS UPSERT
    // =========================

    const productMap = new Map();

    for (const r of rows) {
      if (!r.product_sku) continue;

      if (!productMap.has(r.product_sku)) {
        productMap.set(r.product_sku, {
          retailer_id: retailerId,
          pos_connection_id: manualConnId,
          name: r.product_name,
          sku: r.product_sku,
          category: r.category,
          price: r.price,
          active: true,
          updated_at: now,
        });
      }
    }

    const productPayload = Array.from(productMap.values());

    const { error: prodErr } = await supabase
      .from("products")
      .upsert(productPayload, {
        onConflict: "retailer_id,pos_connection_id,sku",
      });

    if (prodErr) throw prodErr;

    // Fetch ONLY scoped products
    const uniqueSkus = [
      ...new Set(rows.map((r) => r.product_sku).filter(Boolean)),
    ];

    const { data: productsFound, error: prodFetchErr } = await supabase
      .from("products")
      .select("id, sku")
      .eq("retailer_id", retailerId)
      .eq("pos_connection_id", manualConnId)
      .in("sku", uniqueSkus);

    if (prodFetchErr) throw prodFetchErr;

    const productIdBySku = new Map(
      (productsFound || []).map((p) => [p.sku, p.id]),
    );

    // =========================
    // 2) VARIATIONS UPSERT
    // =========================

    const variationPayload = rows.map((r) => {
      const pid = productIdBySku.get(r.product_sku);
      if (!pid) throw new Error(`Missing product_id for SKU: ${r.product_sku}`);

      return {
        product_id: pid,
        pos_connection_id: manualConnId,
        sku: r.variation_sku || r.product_sku,
        name: r.variation_name || r.product_name,
        price: r.price,
        currency: r.currency || "AED",
        stock_quantity: Number(r.quantity || 0),
        total_quantity: Number(r.quantity || 0),
        active: true,
        updated_at: now,
      };
    });

    const { error: varErr } = await supabase
      .from("product_variations")
      .upsert(variationPayload, {
        onConflict: "product_id,sku,pos_connection_id",
      });

    if (varErr) throw varErr;

    // Fetch variations for mapping
    const { data: varsFound, error: varFetchErr } = await supabase
      .from("product_variations")
      .select("id, product_id, sku")
      .in(
        "product_id",
        Array.from(new Set(variationPayload.map((v) => v.product_id))),
      );

    if (varFetchErr) throw varFetchErr;

    const varIdByKey = new Map(
      (varsFound || []).map((v) => [`${v.product_id}__${v.sku}`, v.id]),
    );

    // =========================
    // 3) INVENTORY UPSERT
    // =========================

    const inventoryMap = new Map();

    for (const r of rows) {
      const pid = productIdBySku.get(r.product_sku);
      const vsku = r.variation_sku || r.product_sku;
      const vid = varIdByKey.get(`${pid}__${vsku}`);

      if (!vid) {
        throw new Error(
          `Missing variation_id for SKU: ${vsku} (product SKU: ${r.product_sku})`,
        );
      }

      const key = `${vid}__${r.pos_location_id}__${manualConnId}`;

      inventoryMap.set(key, {
        product_variation_id: vid,
        pos_connection_id: manualConnId,
        pos_location_id: r.pos_location_id,
        quantity: Number(r.quantity || 0),
        updated_at: now,
      });
    }

    const inventoryPayload = Array.from(inventoryMap.values());

    const { error: invErr } = await supabase
      .from("product_inventory")
      .upsert(inventoryPayload, {
        onConflict: "product_variation_id,pos_location_id,pos_connection_id",
      });

    if (invErr) throw invErr;
  };

  // =========================
  // Required fields per import type
  // =========================
  const inventoryRequiredFields = [
    "product_name",
    "category",
    "product_sku",
    "variation_sku",
    "variation_name",
    "price",
    "quantity",
    "pos_location_id",
  ];

  const ordersRequiredFields = [
    "external_order_id",
    "order_time",
    "status",
    "source",
    "item_name",
    "quantity",
    "item_total_amount",
    "currency",
  ];

  // const INVENTORY_DISPLAY_NAMES = {
  //   // Inventory Labels
  //   product_name: "Product name",
  //   category: "Category",
  //   price: "Price",
  //   stock_quantity: "Quantity",
  //   sku: "Product SKU",
  //   pos_location_id: "Location",
  //   variation_sku: "Product variation SKU",
  //   variation_name: "Variation name",

  //   // Orders Labels (Added these)
  //   status: "Order status",
  //   source: "Order source",
  //   item_total_amount: "Item amount (Total)",
  //   currency: "Currency",
  //   external_order_id: "Order ID",
  //   order_time: "Date & Time",
  //   item_name: "Product Name",
  //   quantity: "Quantity",
  //   total_amount: "Total Amount",
  //   product_sku: "SKU",
  //   customer_name: "Customer Name",
  //   order_status: "Status",
  //   external_location_id: "Location",
  //   sku: "Product SKU",
  // };

  // optional fields we support for orders mapping
  const ordersOptionalFields = ["external_location_id", "sku"];

  const getRequiredFieldsForType = () => {
    if (manualImportType === "inventory") return inventoryRequiredFields;
    if (manualImportType === "orders") return ordersRequiredFields;
    return [];
  };

  const buildMappedRowsFromHeaders = (
    rows,
    mapping,
    requiredFields,
    optionalFields = [],
  ) => {
    const allFields = [...requiredFields, ...optionalFields];

    return (rows || []).map((r) => {
      const out = {};
      allFields.forEach((field) => {
        const chosenHeader = mapping?.[field];
        out[field] = chosenHeader ? r?.[chosenHeader] : "";
      });
      return out;
    });
  };

  const updateMappingField = (field, header) => {
    setHeaderMapping((prev) => ({ ...prev, [field]: header }));
  };

  const validateMappingPicked = (requiredFields, mapping) => {
    const missing = requiredFields.filter((f) => !mapping?.[f]);
    if (missing.length) {
      return `Please map all required fields: ${missing.join(", ")}`;
    }
    return "";
  };

  const handleMappingNext = async () => {
    try {
      const required = getRequiredFieldsForType();
      const optional =
        manualImportType === "orders" ? ordersOptionalFields : [];

      const msg = validateMappingPicked(required, headerMapping);
      if (msg) {
        setMappingError(msg);
        return;
      }

      setMappingError("");
      setMappingOpen(false);

      const mappedRows = buildMappedRowsFromHeaders(
        parsedRows,
        headerMapping,
        required,
        optional,
      );

      if (manualImportType === "inventory") {
        // --- DUPLICATE NAME CHECKER ---
        const seenNames = new Set();
        const uniqueRows = [];
        const duplicateNames = new Set();

        mappedRows.forEach((row) => {
          const name = String(row.product_name || "")
            .trim()
            .toLowerCase();
          if (seenNames.has(name)) {
            duplicateNames.add(row.product_name);
          } else {
            seenNames.add(name);
            uniqueRows.push(row);
          }
        });

        if (duplicateNames.size > 0) {
          alert(
            `Duplicate product names found in file:\n${Array.from(duplicateNames).slice(0, 5).join(", ")}${duplicateNames.size > 5 ? "..." : ""}`,
          );
          return;
        }
        // --- END DUPLICATE CHECKER ---
        const { okRows, errors } =
          validateAndNormalizeInventoryRows(mappedRows);

        if (errors.length) {
          alert(
            `Validation failed:\n${errors.slice(0, 5).join("\n")}${errors.length > 5 ? "\n..." : ""}`,
          );
          return;
        }

        // 3. CLEANUP: CLEAR ORDERS FOR THIS RETAILER
        // We do this because re-importing inventory changes product IDs,
        // which would break existing order links.
        const confirmClear = window.confirm(
          "Re-importing inventory will DELETE all existing orders for your account to ensure data consistency. Do you want to proceed?",
        );

        if (!confirmClear) return; // USER ABORTED

        // Delete order_items first (child), then orders (parent)
        // Note: Using the retailerId variable from your context
        const { error: clearOrdersErr } = await supabase.rpc(
          "clear_orders_for_inventory_reset",
          {
            p_retailer_id: retailerId,
          },
        );

        if (clearOrdersErr) {
          console.error("clear_orders_for_inventory_reset failed:", {
            message: clearOrdersErr.message,
            details: clearOrdersErr.details,
            hint: clearOrdersErr.hint,
            code: clearOrdersErr.code,
            full: clearOrdersErr,
            retailerId,
          });
          alert(
            "Error clearing old orders: " +
              (clearOrdersErr.message || "Unknown error"),
          );
          return;
        }

        // 4. FINAL IMPORT
        await importInventoryIntoThreeTables(okRows);
        await loadInventory();
        if (activeTab === "orders") await loadOrders(); // Refresh orders view to show it's empty

        alert(
          `Inventory reset! Imported ${okRows.length} products. Existing orders cleared successfully`,
        );
        return;
      }

      if (manualImportType === "orders") {
        setOrdersImporting(true);

        const { okRows, errors } = validateAndNormalizeOrderRows(mappedRows);
        if (errors.length) {
          setOrdersImporting(false);
          alert(
            `Validation failed:\n${errors.slice(0, 5).join("\n")}${errors.length > 5 ? "\n..." : ""}`,
          );
          return;
        }

        // --- START OF CHECKER ---
        // 1. Fetch existing products for this retailer to verify existence
        const { data: existingProducts, error: fetchErr } = await supabase
          .from("products")
          .select("name")
          .eq("retailer_id", retailerId);

        if (fetchErr) {
          setOrdersImporting(false);
          alert("Could not verify inventory: " + fetchErr.message);
          return;
        }

        // 2. Create a Set of normalized names for efficient lookup
        const validNames = new Set(
          (existingProducts || []).map((p) => p.name?.trim().toLowerCase()),
        );

        // 3. Identify items in the file that do not exist in the 'products' table
        const missingItems = new Set();
        okRows.forEach((row) => {
          const nameInFile = row.item_name?.trim().toLowerCase();
          if (!validNames.has(nameInFile)) {
            missingItems.add(row.item_name);
          }
        });

        // 4. Alert and Abort if missing items found
        if (missingItems.size > 0) {
          const missingList = Array.from(missingItems);
          const errorMsg =
            `Upload Aborted!\n\n` +
            `The following items were not found in your inventory:\n` +
            `${missingList
              .slice(0, 10)
              .map((item) => `- ${item}`)
              .join("\n")}\n` +
            `${missingList.length > 10 ? "...and more\n" : ""}\n` +
            `Please ensure all products are added to the Inventory tab before uploading orders.`;

          alert(errorMsg);
          setOrdersImporting(false);
          return; // Aborts the upload
        }

        const res = await importOrdersFromSingleSheet(okRows);
        setOrdersImporting(false);

        if (activeTab === "orders") await loadOrders();
        alert(
          `Processed ${res.totalOrdersInFile} orders: ${res.newOrdersInserted} new, ${res.totalOrdersInFile - res.newOrdersInserted} updated. Items: ${res.itemsCount}`,
        );

        return;
      }

      alert("Please choose what you want to import.");
    } catch (e) {
      console.error("handleMappingNext failed:", {
        message: e?.message,
        details: e?.details,
        hint: e?.hint,
        code: e?.code,
        full: e,
      });

      setOrdersImporting(false);

      const msg = e?.message || e?.details || e?.hint || "Failed to proceed.";

      alert(`Failed: ${msg}`);
    }
  };

  const handleImportChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    if (!manualImportType) {
      alert("Please choose what you want to import.");
      return;
    }

    const name = file.name.toLowerCase();
    const ok =
      name.endsWith(".csv") || name.endsWith(".xlsx") || name.endsWith(".xls");
    if (!ok) {
      alert("Please upload a CSV or Excel file (.csv, .xlsx, .xls).");
      return;
    }

    try {
      setImporting(true);

      const ext = file.name.split(".").pop().toLowerCase();
      let rows = [];
      if (ext === "csv") rows = await parseCSV(file);
      else rows = await parseExcel(file);

      const headers = Object.keys(rows?.[0] || {});
      setParsedRows(rows);
      setFileHeaders(headers);

      const required =
        manualImportType === "inventory"
          ? inventoryRequiredFields
          : ordersRequiredFields;
      const optional =
        manualImportType === "orders" ? ordersOptionalFields : [];

      const guessed = autoGuessMapping(headers, [...required, ...optional]);
      setHeaderMapping(guessed);

      setMappingError("");
      setMappingOpen(true);
    } catch (err) {
      console.error(err);
      alert("Failed to parse file. Check console.");
    } finally {
      setImporting(false);
    }
  };

  const switchToManualIfNeeded = async () => {
    if (!retailerId) return false;

    if (posConnection?.provider === "manual") return true;

    const { error } = await supabase.functions.invoke("pos-switch-provider", {
      body: { retailer_id: retailerId, target_provider: "manual" },
    });

    if (error) {
      console.error("Failed to switch to manual:", error);
      alert("Could not switch to manual import mode.");
      throw error;
    }

    const { data, error: fetchErr } = await supabase
      .from("pos_connections")
      .select("provider")
      .eq("retailer_id", retailerId)
      .eq("is_active", true)
      .maybeSingle();

    if (fetchErr) return false;

    await loadPosConnection();
    return data?.provider === "manual";
  };

  // Import card actions
  const toggleImportMenu = () => {
    if (importing) return;
    setImportMenuOpen((v) => !v);
  };

  const handleUploadFromMenu = async () => {
    try {
      setImportMenuOpen(false);

      const isManualNow = await switchToManualIfNeeded();

      setManualImportType(null);
      setManualImportOpen(true);

      if (!isManualNow) {
        // optional warning
      }
    } catch {
      // handled above
    }
  };

  //  NEW: Connect to POS button where Update Inventory used to be
  const handleConnectPosButton = () => {
    setImportMenuOpen(false);
    setPosModalOpen(true);
  };

  return (
    <main className="slide retail-page" aria-label="Jiran Inventory">
      <Topbar
        displayName={displayName}
        role={role}
        onLogout={handleLogout}
        activePage="inventory"
      />

      <section className="inventory-layout">
        <section className="dash-main">
          <Panel>
            <div className="inv-hero">
              <div className="inv-left">
                <div className="panel-title">
                  <h2>Inventory</h2>
                  <p>
                    Add products, update stock, and manage pricing. Updates go
                    live instantly.
                  </p>
                </div>

                <div className="hero-actions">
                  <button className="btn primary" disabled={!posConnection?.id || submitting} onClick={() => { setEditingProduct(null); setProductSaveError(""); setModalOpen(true); }}>Add product</button>
                  {/* Import Data stays EXACTLY the same */}
                  <div className="action-col import-wrap">
                    <div className="action-row">
                      <div className="import-menu-wrap" ref={importMenuRef}>
                        <button
                          className="btn ghost"
                          type="button"
                          onClick={toggleImportMenu}
                          disabled={importing}
                          aria-haspopup="true"
                          aria-expanded={importMenuOpen}
                        >
                          {importing ? "Importing..." : "Import Data"}
                        </button>

                        {importMenuOpen && (
                          <div
                            className="import-menu"
                            role="menu"
                            aria-label="Import options"
                          >
                            <div className="import-menu-title">
                              Import & POS
                            </div>

                            <button
                              className="btn ghost"
                              type="button"
                              onClick={handleUploadFromMenu}
                              disabled={importing}
                              role="menuitem"
                            >
                              Upload CSV / Excel
                            </button>

                            <button
                              className="btn ghost"
                              onClick={() => setTemplateModalOpen(true)}
                              style={{ marginLeft: "8px" }}
                            >
                              Download Templates
                            </button>

                            <div className="import-menu-foot">
                              Accepted formats: <strong>.csv</strong>,{" "}
                              <strong>.xlsx</strong>, <strong>.xls</strong>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <input
                    id={importInputId}
                    type="file"
                    accept=".csv,.xlsx,.xls,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                    style={{ display: "none" }}
                    onChange={handleImportChange}
                  />

                  {/*  Connect to POS now sits where Update Inventory used to be */}
                  <div className="action-col import-wrap">
                    <div className="action-row">
                      <button
                        className="btn ghost"
                        type="button"
                        onClick={handleConnectPosButton}
                        disabled={connectingPOS}
                      >
                        {connectingPOS ? "Connecting..." : "Connect to POS"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="inv-stats" aria-label="Stock summary">
                <div className="inv-stat ok">
                  <div className="inv-stat-num">{stockStats.inStock}</div>
                  <div className="inv-stat-label">In stock</div>
                </div>
                <div className="inv-stat warn">
                  <div className="inv-stat-num">{stockStats.low}</div>
                  <div className="inv-stat-label">Low</div>
                </div>
                <div className="inv-stat bad">
                  <div className="inv-stat-num">{stockStats.oos}</div>
                  <div className="inv-stat-label">Out</div>
                </div>
              </div>
            </div>
          </Panel>

          <Panel>
            <div className="panel-head">
              <div className="panel-title">
                <div
                  className="inv-tabs"
                  role="tablist"
                  aria-label="Inventory and orders"
                >
                  <button
                    type="button"
                    className={`inv-tab ${activeTab === "inventory" ? "active" : ""}`}
                    onClick={() => setActiveTab("inventory")}
                    role="tab"
                    aria-selected={activeTab === "inventory"}
                  >
                    Your Inventory
                  </button>

                  <button
                    type="button"
                    className={`inv-tab ${activeTab === "orders" ? "active" : ""}`}
                    onClick={() => setActiveTab("orders")}
                    role="tab"
                    aria-selected={activeTab === "orders"}
                  >
                    Your Orders
                  </button>
                </div>

                {activeTab === "inventory" ? (
                  <div style={{ marginLeft: 5, marginBottom: 10 }}>
                    <p>Search, filter, and edit your active products. </p>
                  </div>
                ) : (
                  <div style={{ marginLeft: 5, marginBottom: 10 }}>
                    <p>View and track your recent orders.</p>
                  </div>
                )}
              </div>

              <div className="panel-actions">
                {/*  Sync now moved next to Reset filters */}
                {activeTab === "inventory" ? (
                  <>
                    <button
                      className="btn ghost small"
                      type="button"
                      onClick={handleSyncNow}
                      disabled={syncing}
                    >
                      {syncing
                        ? "Syncing..."
                        : liveSync.state === "connected"
                          ? "Sync now"
                          : "Refresh connection"}
                    </button>
                  </>
                ) : (
                  <button
                    className="btn ghost small"
                    type="button"
                    onClick={resetOrdersFilters}
                  >
                    Reset filters
                  </button>
                )}
              </div>
            </div>

            {activeTab === "inventory" ? (
              <>
                <div className="filters">
                  <input
                    className="search"
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search by name, SKU, category..."
                  />

                  <select
                    className="select"
                    value={categoryFilter}
                    onChange={(e) => setCategoryFilter(e.target.value)}
                  >
                    {categories.map((c) => (
                      <option key={c} value={c}>
                        {c === "all" ? "All categories" : c}
                      </option>
                    ))}
                  </select>

                  <select
                    className="select"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="all">Any status</option>
                    <option value="in">In stock</option>
                    <option value="low">Low stock</option>
                    <option value="oos">Out of stock</option>
                  </select>

                  <select
                    className="select"
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                  >
                    <option value="updated">Recently updated</option>
                    <option value="price_asc">Price (low to high)</option>
                    <option value="price_desc">Price (high to low)</option>
                    <option value="stock_asc">Stock (low to high)</option>
                    <option value="stock_desc">Stock (high to low)</option>
                  </select>
                  <div className="panel-actions">
                    <button
                      className="btn ghost small"
                      type="button"
                      onClick={resetInventoryFilters}
                    >
                      Reset filters
                    </button>
                  </div>
                </div>

                {inventoryNotice && <p role="status" className="management-notice">{inventoryNotice}</p>}
                {!posConnection?.id && !invLoading && <p className="management-notice">Create a store in <Link to="/settings">Settings</Link> to start adding products.</p>}
                {invError && <div className="inline-error" role="alert">{invError}</div>}

                <div className="table inventory-management-table">
                  <div className="thead">
                    <div>Product</div>
                    <div>Category</div>
                    <div>Price</div>
                    <div>Quantity</div>
                    <div>Status</div>
                    <div>Actions</div>
                  </div>

                  <div className="inventory-scroll">
                    {invLoading ? (
                      <div className="trow trow-single">
                        <div className="muted">Loading inventory...</div>
                      </div>
                    ) : filteredInventory.length === 0 ? (
                      <div className="trow trow-single">
                        <div className="muted">
                          No products match your filters. Add a product or reset your filters.
                        </div>
                      </div>
                    ) : (
                      filteredInventory.map((row) => {
                        const st = statusFromStock(row.stock ?? 0);
                        return (
                          <div className="trow" key={row.id}>
                            <div className="prod">
                              <div className="prod-text">
                                <div className="prod-name">
                                  {row.name || "Unnamed product"}
                                </div>
                                <div className="prod-sub">
                                  SKU: {row.sku || "-"}
                                </div>
                              </div>
                            </div>

                            <div className="cell-clip">
                              {row.category || "-"}
                            </div>
                            <div className="cell-mono">
                              AED {Number(row.price || 0).toFixed(2)}
                            </div>
                            <div className="cell-mono">
                              {Number(row.stock ?? 0)}
                            </div>

                            <div>
                              <span className={`status ${st.type}`}>
                                {st.label}
                              </span>
                            </div>
                            <div className="inventory-row-actions">
                              <button aria-label={`Edit ${row.name}`} onClick={() => { setEditingProduct(row); setProductSaveError(""); setModalOpen(true); }}>Edit</button>
                              <button aria-label={`Delete ${row.name}`} onClick={() => { setDeleteError(""); setDeleteProduct(row); }}>Delete</button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="filters">
                  <select
                    className="select"
                    value={orderSort}
                    onChange={(e) => setOrderSort(e.target.value)}
                  >
                    <option value="desc">Latest to oldest</option>
                    <option value="asc">Oldest to latest</option>
                  </select>

                  <button
                    className="btn ghost small"
                    type="button"
                    onClick={loadOrders}
                    disabled={ordersLoading}
                  >
                    {ordersLoading ? "Loading..." : "Refresh"}
                  </button>
                </div>

                {ordersError && (
                  <div className="inline-error">{ordersError}</div>
                )}

                <div className="table table-orders">
                  <div className="thead">
                    <div>Order time</div>
                    <div>Status</div>
                    <div>Source</div>
                    <div>Total</div>
                    <div></div>
                  </div>

                  <div className="inventory-scroll">
                    {ordersLoading ? (
                      <div className="trow trow-single">
                        <div className="muted">Loading orders...</div>
                      </div>
                    ) : (orders || []).length === 0 ? (
                      <div className="trow trow-single">
                        <div className="muted">No orders yet.</div>
                      </div>
                    ) : (
                      orders.map((o) => (
                        <div className="trow" key={o.id}>
                          <div className="cell-clip">
                            {formatDateTime(o.order_time)}
                          </div>
                          <div className="cell-clip">{o.status || "-"}</div>
                          <div className="cell-clip">{o.source || "-"}</div>
                          <div className="cell-mono">
                            {formatMoney(o.total_amount ?? 0, o.currency)}
                          </div>
                          <div className="cell-actions">
                            <button
                              className="btn ghost small"
                              type="button"
                              onClick={() => openOrderDetails(o)}
                            >
                              Order details
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </>
            )}
          </Panel>
        </section>
      </section>

      <ConnectPOSModal
        open={posModalOpen}
        onClose={() => !connectingPOS && setPosModalOpen(false)}
        onConnectSquare={handleConnect}
        connecting={connectingPOS}
      />

      <ProductModal
        open={modalOpen}
        onClose={() => !submitting && setModalOpen(false)}
        onSubmit={handleModalSubmit}
        submitting={submitting}
        initial={editingProduct}
        saveError={productSaveError}
        categoryOptions={categories.filter((c) => c !== "all")}
      />

      {deleteProduct && <ConfirmDialog title="Delete this product?" match={deleteProduct.name} busy={submitting} error={deleteError} action="Delete product" onClose={() => setDeleteProduct(null)} onConfirm={confirmProductDelete}><p>The selected variation and its stock will be removed. If it is the last variation, its product and marketplace listing are also removed. Historical orders remain available. This cannot be undone.</p></ConfirmDialog>}

      <OrderDetailsModal
        open={orderDetailsOpen}
        onClose={() => setOrderDetailsOpen(false)}
        order={selectedOrder}
        items={orderItems}
        loading={orderItemsLoading}
        error={orderItemsError}
      />

      {manualImportOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="modal-head">
              <h3 className="modal-title">Import data</h3>
              <button
                className="iconbtn"
                onClick={() => setManualImportOpen(false)}
               aria-label="Close dialog" type="button">
                <Icon name="close" />
              </button>
            </div>

            <div className="form">
              <p className="muted">What would you like to import?</p>

              <div className="modal-actions">
                <button
                  className="btn primary"
                  onClick={() => {
                    setManualImportType("inventory");
                    setManualImportOpen(false);
                    handleImportPick();
                  }}
                >
                  Import inventory
                </button>

                <button
                  className="btn ghost"
                  onClick={() => {
                    setManualImportType("orders");
                    setManualImportOpen(false);
                    handleImportPick();
                  }}
                >
                  Import orders
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {mappingOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="modal-head">
              <div>
                <h3 className="modal-title">Map columns</h3>
                <p className="modal-sub">
                  Choose which column in your file maps to each required field.
                </p>
              </div>
              <button className="iconbtn" onClick={() => setMappingOpen(false)} aria-label="Close dialog" type="button">
                <Icon name="close" />
              </button>
            </div>

            <div className="form">
              <div
                style={{
                  display: "flex",
                  gap: 10,
                  alignItems: "center",
                  marginBottom: 12,
                }}
              >
                <div className="muted" style={{ flex: 1 }}>
                  Detected headers: <strong>{fileHeaders.length}</strong>
                </div>

                <button
                  className="btn ghost small"
                  type="button"
                  onClick={() => {
                    const required = getRequiredFieldsForType();
                    const optional =
                      manualImportType === "orders" ? ordersOptionalFields : [];
                    const guessed = autoGuessMapping(fileHeaders, [
                      ...required,
                      ...optional,
                    ]);
                    setHeaderMapping(guessed);
                    setMappingError("");
                  }}
                >
                  Auto match
                </button>
              </div>

              {mappingError && (
                <div className="inline-error">{mappingError}</div>
              )}

              <div
                style={{
                  maxHeight: 320,
                  overflow: "auto",
                  border: "1px solid #eee",
                  borderRadius: 10,
                  padding: 10,
                }}
              >
                {getRequiredFieldsForType().map((field) => (
                  <div
                    key={field}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "200px 1fr",
                      gap: 10,
                      alignItems: "center",
                      padding: "10px 0",
                      borderBottom: "1px solid #f2f2f2",
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>
                      {INVENTORY_DISPLAY_NAMES[field] || field}
                    </div>

                    <select
                      className="select"
                      value={headerMapping?.[field] || ""}
                      onChange={(e) =>
                        updateMappingField(field, e.target.value)
                      }
                    >
                      <option value="">Select a header...</option>
                      {fileHeaders.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}

                {manualImportType === "orders" && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontWeight: 700, marginBottom: 8 }}>
                      Optional
                    </div>

                    {manualImportType === "orders" && (
                      <div style={{ marginTop: 12 }}>
                        <div style={{ fontWeight: 700, marginBottom: 8 }}>
                          {/* Optional Fields */}
                        </div>

                        {ordersOptionalFields.map((field) => (
                          <div
                            key={field}
                            style={{
                              display: "grid",
                              gridTemplateColumns: "160px 1fr",
                              gap: 10,
                              alignItems: "center",
                              padding: "10px 0",
                              borderBottom: "1px solid #f2f2f2",
                            }}
                          >
                            {/* Update this line right here */}
                            <div style={{ fontWeight: 600 }}>
                              {INVENTORY_DISPLAY_NAMES[field] || field}
                            </div>

                            <select
                              className="select"
                              value={headerMapping?.[field] || ""}
                              onChange={(e) =>
                                updateMappingField(field, e.target.value)
                              }
                            >
                              <option value="">(Skip)</option>
                              {fileHeaders.map((h) => (
                                <option key={h} value={h}>
                                  {h}
                                </option>
                              ))}
                            </select>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="modal-actions">
                <button
                  className="btn ghost"
                  type="button"
                  onClick={() => setMappingOpen(false)}
                >
                  Back
                </button>

                <button
                  className="btn primary"
                  onClick={handleMappingNext}
                  disabled={ordersImporting}
                >
                  {ordersImporting ? "Importing..." : "Next"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      {templateModalOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ maxWidth: "500px" }}>
            <div className="modal-head">
              <div>
                <h3 className="modal-title">Download templates</h3>
                <p className="modal-sub">
                  Follow these formatting rules to ensure a perfect import.
                </p>
              </div>
              <button
                className="iconbtn"
                onClick={() => setTemplateModalOpen(false)}
               aria-label="Close dialog" type="button">
                <Icon name="close" />
              </button>
            </div>

            <div className="form">
              <div style={{ padding: "10px 0" }}>
                {/* Detailed Instructions Box */}
                <div
                  style={{
                    background: "#f8fafc",
                    padding: "16px",
                    borderRadius: "8px",
                    border: "1px solid #e2e8f0",
                    marginBottom: "20px",
                    fontSize: "13px",
                    lineHeight: "1.5",
                  }}
                >
                  <div
                    style={{
                      marginBottom: "12px",
                      borderBottom: "1px solid #edf2f7",
                      paddingBottom: "8px",
                    }}
                  >
                    <strong
                      style={{
                        color: "#0f172a",
                        display: "block",
                        marginBottom: "4px",
                      }}
                    >
                      <Icon name="package" /> Inventory Details:
                    </strong>
                    <div style={{ color: "#64748b" }}>
                      • <strong>Price / Qty:</strong> Numbers only (e.g.{" "}
                      <code>45.00</code>, <code>10</code>)<br />•{" "}
                      <strong>SKU:</strong> Unique identifier (e.g.{" "}
                      <code>TSH-RED-L</code>)<br />• <strong>Location:</strong>{" "}
                      Use your ID (e.g. <code>WAREHOUSE-1</code>)
                    </div>
                  </div>

                  <div>
                    <strong
                      style={{
                        color: "#0f172a",
                        display: "block",
                        marginBottom: "4px",
                      }}
                    >
                      <Icon name="cart" /> Order Details:
                    </strong>
                    <div style={{ color: "#64748b" }}>
                      • <strong>Date:</strong> <code>YYYY-MM-DD</code> (e.g.{" "}
                      <code>2024-03-25</code>)<br />• <strong>SKU:</strong> Must
                      match an existing product SKU
                      <br />• <strong>Status:</strong> <code>Paid</code>,{" "}
                      <code>Pending</code>, <code>Cancelled</code>, or{" "}
                      <code>Refunded</code>
                    </div>
                  </div>
                </div>

                <div
                  className="modal-actions"
                  style={{ flexDirection: "column", gap: 12 }}
                >
                  <button
                    className="btn primary"
                    style={{
                      width: "100%",
                      justifyContent: "center",
                      height: "45px",
                    }}
                    onClick={() => {
                      downloadTemplate("inventory");
                      setTemplateModalOpen(false);
                    }}
                  >
                    Download Inventory Template
                  </button>

                  <button
                    className="btn ghost"
                    style={{
                      width: "100%",
                      justifyContent: "center",
                      height: "45px",
                      border: "1px solid #e2e8f0",
                      color: "#475569",
                    }}
                    onClick={() => {
                      downloadTemplate("orders");
                      setTemplateModalOpen(false);
                    }}
                  >
                    Download Orders Template
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
