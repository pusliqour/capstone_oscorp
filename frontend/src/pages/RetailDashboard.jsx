// src/pages/RetailDashboard.jsx
import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { supabase } from "../supaBase/Client";
import "../styles/RetailDashboard.css";
import Logo from "/src/styles/Logo.png";
import Avatar from "/src/styles/avatar.png";

function Topbar({ displayName, role, onLogout }) {
  return (
    <header className="topbar">
      <Link to="/" className="brand brand-link">
        <img src={Logo} alt="Jiran logo" className="nav-logo" />
        <div className="brand-text">
          <h1>Jiran</h1>
          <p>Retailer Dashboard</p>
        </div>
      </Link>

      <nav className="nav">
        <Link className="nav-item active" to="/retailer-dashboard">
          Dashboard
        </Link>
        <Link className="nav-item" to="/inventory">
          Inventory
        </Link>
        <Link className="nav-item" to="/exchange">
          Marketplace
        </Link>
        <Link className="nav-item" to="/analytics">
          Analytics
        </Link>
        <Link className="nav-item" to="/settings">
          Settings
        </Link>
      </nav>

      <div className="top-actions">
        <div className="account">
          <span className="avatar">
            <img src={Avatar} alt="avatar" />
          </span>{" "}
          <span className="acct-text">
            <span className="acct-name">{displayName}</span>
            <span className="acct-sub">{role}</span>
          </span>
        </div>

        <button className="btn ghost small" onClick={onLogout}>
          Logout
        </button>
      </div>
    </header>
  );
}

function WidgetHeader({ title, right }) {
  return (
    <div className="widget-head">
      <h3>{title}</h3>
      {right ? <div className="widget-head-right">{right}</div> : null}
    </div>
  );
}

const getRelativeTime = (date) => {
  if (!date) return null;

  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60000);

  if (minutes < 60) {
    return `${Math.max(1, minutes)} min ago`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} hr${hours > 1 ? "s" : ""} ago`;
  }

  const days = Math.floor(hours / 24);
  if (days < 30) {
    return `${days} day${days > 1 ? "s" : ""} ago`;
  }

  const months = Math.floor(days / 30);
  if (months < 12) {
    return `${months} month${months > 1 ? "s" : ""} ago`;
  }

  const years = Math.floor(months / 12);
  return `${years} year${years > 1 ? "s" : ""} ago`;
};

export default function RetailDashboard() {
  const { user, profile, signOut } = useAuth();
  const navigate = useNavigate();
  const retailerId = profile?.id || user?.id;

  // UI State
  const [alertsOpen, setAlertsOpen] = useState(true);
  const [topSellersOpen, setTopSellersOpen] = useState(true);

  // Data State (Initialized to null to prevent flickering "empty" messages)
  const [products, setProducts] = useState([]);
  const [lowStockAlerts, setLowStockAlerts] = useState(null);
  const [oosAlerts, setOosAlerts] = useState(null);
  const [topSellers, setTopSellers] = useState([]);
  const [provider, setProvider] = useState(null);
  const [lastInventoryUpdate, setLastInventoryUpdate] = useState(null);

  // Settings State
  const [showTopSellers, setShowTopSellers] = useState(false);
  const [lowStockEnabled, setLowStockEnabled] = useState(true);
  const [oosEnabled, setOosEnabled] = useState(true);

  useEffect(() => {
    if (!retailerId) return;

    const fetchAllDashboardData = async () => {
      try {
        // 1. Fetch Settings First
        const { data: settings } = await supabase
          .from("retailer_profiles")
          .select(
            "low_stock_notifications, oos_notifications, show_top_products_widget",
          )
          .eq("id", retailerId)
          .maybeSingle();

        const lS_on = settings?.low_stock_notifications ?? true;
        const oos_on = settings?.oos_notifications ?? true;
        const top_on = settings?.show_top_products_widget ?? false;

        setLowStockEnabled(lS_on);
        setOosEnabled(oos_on);
        setShowTopSellers(top_on);

        // 2. Fetch Active Connection & Products
        const { data: posData } = await supabase
          .from("pos_connections")
          .select("id, provider, status, last_synced_at, last_error")
          .eq("retailer_id", retailerId)
          .eq("is_active", true)
          .maybeSingle();

        const { data: productsData } = await supabase
          .from("products")
          .select(
            `
            id, name, active,
            product_variations (
              active,
              product_inventory (quantity, updated_at)
            )
          `,
          )
          .eq("retailer_id", retailerId)
          .eq("pos_connection_id", posData?.id || "00000000-0000-0000-0000-000000000000")
          .eq("active", true);

        if (!posData) {
          setProducts([]); setLowStockAlerts([]); setOosAlerts([]); setTopSellers([]);
          setProvider(null); setLastInventoryUpdate(null); return;
        }

        // 3. Process Inventory & Alerts
        const aggregated = [];
        const lowStock = [];
        const oosStock = [];
        let latestInventory = null;

        (productsData || []).forEach((p) => {
          let minQty = Infinity;
          let latestDate = null;

          (p.product_variations || []).forEach((v) => {
            if (!v.active) return;
            const inv = v.product_inventory?.[0];
            if (!inv) return;

            const qty = Number(inv.quantity ?? 0);
            const updatedAt = inv.updated_at ? new Date(inv.updated_at) : null;
            minQty = Math.min(minQty, qty);
            if (updatedAt && (!latestDate || updatedAt > latestDate))
              latestDate = updatedAt;
          });

          if (!Number.isFinite(minQty)) return;

          aggregated.push({
            id: p.id,
            name: p.name,
            qty: minQty,
            lastUpdate: latestDate,
          });

          // Apply filters based on the settings we just fetched
          if (oos_on && minQty <= 0) {
            oosStock.push({
              id: p.id,
              name: p.name,
              qty: minQty,
              level: "critical",
            });
          } else if (lS_on && minQty <= 10) {
            lowStock.push({
              id: p.id,
              name: p.name,
              qty: minQty,
              level: "low",
            });
          }

          if (
            latestDate &&
            (!latestInventory || latestDate > latestInventory)
          ) {
            latestInventory = latestDate;
          }
        });

        setProducts(aggregated);
        setLowStockAlerts(lowStock);
        setOosAlerts(oosStock);
        setLastInventoryUpdate(latestInventory);

        // 4. Set Provider Info
        if (posData) {
          const isManual = ["manual", "local_import", "jiran_square_import"].includes(posData.provider);
          const syncDate = isManual
            ? latestInventory
            : new Date(posData.last_synced_at);
          setProvider({
            label: isManual ? "CSV/Excel" : "POS",
            online: posData.status === "connected" || isManual,
            lastError: posData.last_error,
            lastSync: syncDate || null,
          });
        }

        // 5. Fetch Top Sellers if enabled. Historical demo imports are anchored
        // to their newest order so the dashboard still shows a meaningful week.
        if (top_on) {
          const { data: latestOrder } = await supabase
            .from("orders")
            .select("order_time")
            .eq("retailer_id", retailerId)
            .eq("pos_connection_id", posData?.id)
            .eq("status", "completed")
            .eq("is_active", true)
            .order("order_time", { ascending: false })
            .limit(1)
            .maybeSingle();

          const anchor = latestOrder?.order_time
            ? new Date(latestOrder.order_time)
            : new Date();
          const since = new Date(anchor);
          since.setDate(since.getDate() - 7);

          const { data: topData } = await supabase
            .from("order_items")
            .select(
              `
              item_name, quantity,
              orders:order_id!inner ( retailer_id, order_time, status, is_active )
            `,
            )
            .eq("orders.retailer_id", retailerId)
            .eq("orders.pos_connection_id", posData?.id)
            .eq("orders.status", "completed")
            .eq("orders.is_active", true)
            .gte("orders.order_time", since.toISOString());

          const totals = new Map();
          (topData || []).forEach((row) => {
            const name = row.item_name?.trim();
            if (!name) return;
            const prev = totals.get(name) || { name, sold: 0 };
            prev.sold += Number(row.quantity ?? 0);
            totals.set(name, prev);
          });

          setTopSellers(
            Array.from(totals.values())
              .sort((a, b) => b.sold - a.sold)
              .slice(0, 10),
          );
        }
      } catch (err) {
        console.error("Dashboard Load Error:", err);
      }
    };

    fetchAllDashboardData();
  }, [retailerId]);

  // Rest of your logic (stats useMemo, connectionStatusText, etc.) stays the same...
  const stats = useMemo(() => {
    let inStock = 0,
      low = 0,
      out = 0;
    products.forEach((p) => {
      if (p.qty <= 0) out++;
      else if (p.qty <= 10) low++;
      else inStock++;
    });
    return { inStock, low, out };
  }, [products]);

  const isManual = provider?.label === "CSV/Excel";

  const freshnessDate = isManual ? lastInventoryUpdate : provider?.lastSync;

  const freshnessText = provider?.lastError
    ? "Update failed"
    : freshnessDate
      ? `Updated ${getRelativeTime(freshnessDate)}`
      : isManual
        ? "No update recorded yet"
        : "No sync recorded yet";

  const providerTone = provider?.lastError
    ? "tone-danger"
    : isManual
      ? "tone-neutral"
      : provider?.online
        ? "tone-success"
        : "tone-neutral";

  const topSellerPreview = topSellers[0];

  return (
    <main className="retail-page">
      <Topbar
        displayName={profile?.full_name || user?.email}
        role={profile?.role || "retailer"}
        onLogout={signOut}
      />

      <section className="dash-layout">
        <div className="widgets-shell">
          {/* SNAPSHOT */}
          <section className="panel widget-card snapshot-widget">
            <WidgetHeader title="Dashboard" />

            <div className="snapshot-mini-grid">
              <div className="mini-stat tone-info">
                <div className="mini-content">
                  <span className="mini-label">In stock</span>
                  <strong className="mini-value">{stats.inStock}</strong>
                </div>
              </div>

              <div className="mini-stat tone-warn">
                <div className="mini-content">
                  <span className="mini-label">Low stock</span>
                  <strong className="mini-value">{stats.low}</strong>
                </div>
                <button
                  className="btn danger mini-cta"
                  onClick={() => navigate("/exchange?mode=buy")}
                >
                  Get more
                </button>
              </div>

              <div
                className={`mini-stat ${stats.out > 0 ? "tone-danger" : "tone-success"}`}
              >
                <div className="mini-content">
                  <span className="mini-label">Out of stock</span>
                  <strong className="mini-value">{stats.out}</strong>
                </div>
                {stats.out > 0 && (
                  <button
                    className="btn warn"
                    onClick={() => navigate("/exchange?mode=buy")}
                  >
                    Restock now
                  </button>
                )}
              </div>

              <div className={`mini-stat mini-source-card ${providerTone}`}>
                <span className="mini-source-status">{freshnessText}</span>
                <div className="mini-content mini-source-content">
                  <span className="mini-label">Source</span>
                  <strong className="mini-value mini-text">
                    {provider?.label || "None"}
                  </strong>
                </div>
              </div>
            </div>
          </section>

          {/* DETAILS ROW */}
          <div className="details-grid">
            {/* INVENTORY ALERTS PANEL */}
            <section
              className={`panel widget-card collapsible-card ${alertsOpen ? "is-open" : ""}`}
            >
              <WidgetHeader
                title={`Inventory Alerts (${
                  (lowStockEnabled ? lowStockAlerts?.length || 0 : 0) +
                  (oosEnabled ? oosAlerts?.length || 0 : 0)
                })`}
              />

              <div className="alerts-scroll">
                <div className="list">
                  {lowStockAlerts === null || oosAlerts === null ? (
                    <p className="muted">Loading...</p>
                  ) : lowStockAlerts.length === 0 && oosAlerts.length === 0 ? (
                    <div className="status-card-success">
                      <span>✅ Nothing to worry about!</span>
                    </div>
                  ) : (
                    <>
                      {/* OUT OF STOCK ALERTS */}
                      {oosEnabled && oosAlerts.length > 0 && (
                        <div className="alert-group">
                          {oosAlerts.map((a) => (
                            <div
                              key={a.id}
                              className={`list-item ${
                                a.level === "low" ? "tone-warn" : "tone-danger"
                              }`}
                            >
                              <div className="list-body">
                                <div className="list-title">{a.name}</div>
                                <div className="list-sub">
                                  {a.qty} units left ·{" "}
                                  {a.level === "low"
                                    ? "Low stock"
                                    : "Out of stock"}
                                </div>
                              </div>
                              <button
                                className={`rowbtn ${a.level === "low" ? "btn-warn" : "btn-danger"}`}
                                onClick={() =>
                                  navigate("/inventory", {
                                    state: { highlight: a.id },
                                  })
                                }
                              >
                                View
                              </button>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* LOW STOCK ALERTS */}
                      {lowStockEnabled && lowStockAlerts.length > 0 && (
                        <div className="alert-group">
                          {lowStockAlerts.map((a) => (
                            <div
                              key={a.id}
                              className={`list-item ${
                                a.level === "low" ? "tone-warn" : "tone-danger"
                              }`}
                            >
                              <div className="list-body">
                                <div className="list-title">{a.name}</div>
                                <div className="list-sub">
                                  {a.qty} units left ·{" "}
                                  {a.level === "low"
                                    ? "Low stock"
                                    : "Out of stock"}
                                </div>
                              </div>
                              <button
                                className={`rowbtn ${a.level === "low" ? "btn-warn" : "btn-danger"}`}
                                onClick={() =>
                                  navigate("/inventory", {
                                    state: { highlight: a.id },
                                  })
                                }
                              >
                                View
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </section>
            {showTopSellers && (
              <section
                className={`panel widget-card collapsible-card ${topSellersOpen ? "is-open" : ""}`}
              >
                <WidgetHeader
                  title="Top sellers this week"
                  // right={
                  //   // <button
                  //   //   type="button"
                  //   //   className="collapse-btn"
                  //   //   onClick={() => setTopSellersOpen((v) => !v)}
                  //   // >
                  //   //   {topSellersOpen ? "Hide" : "Open"}
                  //   // </button>
                  // }
                />

                {!topSellersOpen ? (
                  <div className="collapsed-preview">
                    <div className="preview-line single">
                      <span>{topSellers.length} items ranked</span>
                    </div>
                    <div className="preview-sub muted">
                      {topSellerPreview
                        ? `${topSellerPreview.name} · ${topSellerPreview.sold} sold`
                        : "No sales recorded this week."}
                    </div>
                  </div>
                ) : (
                  <div className="top-sellers-scroll">
                    {topSellers.length === 0 ? (
                      <p className="muted">No sales recorded this week.</p>
                    ) : (
                      <ol className="top-sellers">
                        {topSellers.map((p, idx) => (
                          <li key={`${p.name}-${idx}`}>
                            <span>{p.name}</span>
                            <strong>{p.sold} sold</strong>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                )}
              </section>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
