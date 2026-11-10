import Icon from "../components/Icon";
// src/pages/Analytics.jsx
import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { supabase } from "../supaBase/Client";
import "../styles/Analytics.css";
import Logo from "/src/styles/Logo.png";
import Avatar from "/src/styles/avatar.png";

/* ===============================
  Helper Components
================================ */

function TimeRangeFilter({ value, onChange, options = [] }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "flex-end",
        gap: "0.75rem",
        minWidth: "220px",
      }}
    >
      <label
        htmlFor="analytics-time-range"
        style={{
          fontSize: "0.9rem",
          fontWeight: 600,
          color: "#475467",
          whiteSpace: "nowrap",
        }}
      >
        Filter by
      </label>

      <select
        id="analytics-time-range"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        style={{
          width: "100%",
          minWidth: "180px",
          padding: "0.7rem 0.9rem",
          borderRadius: "12px",
          border: "1px solid #d0d5dd",
          background: "#ffffff",
          color: "#101828",
          fontSize: "0.95rem",
          fontWeight: 500,
          outline: "none",
          cursor: "pointer",
          boxShadow: "0 1px 2px rgba(16, 24, 40, 0.05)",
        }}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

const TIME_RANGE_OPTIONS = [
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "last_week", label: "Last Week" },
  { value: "last_month", label: "Last Month" },
  { value: "last_3_months", label: "Last 3 Months" },
  { value: "last_6_months", label: "Last 6 Months" },
  { value: "all", label: "All Time" },
];

function getTimeRangeBounds(range) {
  if (range === "all") return null;

  const now = new Date();
  const start = new Date(now);
  const end = new Date(now);

  const setStartOfDay = (date) => date.setHours(0, 0, 0, 0);
  const setEndOfDay = (date) => date.setHours(23, 59, 59, 999);

  switch (range) {
    case "today":
      setStartOfDay(start);
      setEndOfDay(end);
      break;

    case "yesterday":
      start.setDate(start.getDate() - 1);
      end.setDate(end.getDate() - 1);
      setStartOfDay(start);
      setEndOfDay(end);
      break;

    case "last_week":
      start.setDate(start.getDate() - 6);
      setStartOfDay(start);
      setEndOfDay(end);
      break;

    case "last_month":
      start.setDate(start.getDate() - 29);
      setStartOfDay(start);
      setEndOfDay(end);
      break;

    case "last_3_months":
      start.setMonth(start.getMonth() - 3);
      setStartOfDay(start);
      setEndOfDay(end);
      break;

    case "last_6_months":
      start.setMonth(start.getMonth() - 6);
      setStartOfDay(start);
      setEndOfDay(end);
      break;

    default:
      return null;
  }

  return {
    start: start.toISOString(),
    end: end.toISOString(),
  };
}

function applyTimeRangeToQuery(query, column, range) {
  const bounds = getTimeRangeBounds(range);
  if (!bounds) return query;
  return query.gte(column, bounds.start).lte(column, bounds.end);
}

const EmptyChartState = ({ title, type }) => (
  <Panel className="panel-compact chart-empty-panel">
    <div className="panel-head">
      <div className="panel-title">
        <h3>{title}</h3>
      </div>
    </div>
    <div className="empty-chart-content">
      <div
        className={`empty-placeholder-visual ${type === "pie" ? "circular-dot" : "rect-dash"}`}
      >
        <span className="empty-placeholder-text">
          {type === "pie" ? "No Orders Imported" : "No Inventory Loaded"}
        </span>
      </div>
    </div>
  </Panel>
);

/* ===============================
  Topbar
================================ */
function Topbar({ displayName, role, onLogout, activePage }) {
  return (
    <header className="topbar">
      <Link to="/" className="brand brand-link" rel="noopener noreferrer">
        <img src={Logo} alt="Jiran Logo" className="nav-logo" />
        <div className="brand-text">
          <h1>Jiran</h1>
          <p>Retailer Dashboard</p>
        </div>
      </Link>

      <nav className="nav">
        <Link className="nav-item" to="/data-explorer">Archive data</Link>
        {["dashboard", "inventory", "marketplace", "analytics", "settings"].map(
          (page) => (
            <Link
              key={page}
              className={`nav-item ${activePage === page ? "active" : ""}`}
              to={`/${
                page === "dashboard"
                  ? "retailer-dashboard"
                  : page === "marketplace"
                    ? "exchange"
                    : page
              }`}
            >
              {page.charAt(0).toUpperCase() + page.slice(1)}
            </Link>
          ),
        )}
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
  UI Components
================================ */
const Panel = ({ children, className = "" }) => (
  <section className={`panel ${className}`.trim()}>{children}</section>
);

const KPI = ({ label, value, sub, chip, chipType, tone = "neutral" }) => (
  <div className={`kpi-tile tone-${tone}`}>
    <div className="kpi-top">
      <div className="kpi-label">{label}</div>
      {chip && <span className={`chip ${chipType}`}>{chip}</span>}
    </div>
    <div className="kpi-value">{value}</div>
    <div className="kpi-sub">{sub}</div>
  </div>
);

/* ===============================
  Helpers
================================ */
function formatAED(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  const num = Number(n);
  const isWhole = Math.abs(num - Math.round(num)) < 0.000001;
  return `AED ${isWhole ? Math.round(num) : num.toFixed(2)}`;
}

/* ===============================
  Charts
================================ */
const StockHealthChart = ({ data }) => {
  const [selectedCategory, setSelectedCategory] = useState("");

  const categories = [...new Set(data.map((d) => d.category))];

  const filtered =
    selectedCategory === ""
      ? data.filter((d) => d.category === categories[0])
      : data.filter((d) => d.category === selectedCategory);

  const maxStock = Math.max(...filtered.map((d) => d.stock), 1);
  const demand = 50;

  const getStatusColor = (stock) => {
    if (stock <= demand - 30) return "#EF4444";
    if (stock >= demand + 30) return "#10B981";
    return "#F59E0B";
  };

  return (
    <div className="chart-card">
      <div className="chart-header">
        <h3>Stock Health</h3>
        <select
          value={selectedCategory || categories[0]}
          onChange={(e) => setSelectedCategory(e.target.value)}
        >
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <div className="stock-chart-horizontal">
        <div className="stock-chart-scroll">
          {filtered.map((item) => (
            <div className="stock-bar-row" key={item.id}>
              <div className="stock-label" style={{ flex: 3 }}>
                {item.name}
              </div>

              <div className="stock-bar-wrapper" style={{ flex: 4 }}>
                <div
                  className="stock-bar"
                  style={{
                    width: `${(item.stock / maxStock) * 100}%`,
                    backgroundColor: getStatusColor(item.stock),
                  }}
                >
                  <span className="bar-value">{item.stock}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const RevenuePieChart = ({ data = [] }) => {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const total = data.reduce((sum, d) => sum + Number(d.value || 0), 0);
  const colors = [
    "#6366F1",
    "#10B981",
    "#F59E0B",
    "#EF4444",
    "#3B82F6",
    "#8B5CF6",
  ];

  const radius = 150;
  const center = radius;

  const polarToCartesian = (cx, cy, r, angle) => {
    const rad = (angle - 90) * (Math.PI / 180);
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };

  let cumulativeAngle = 0;

  const paths = data.map((d, i) => {
    const value = Number(d.value || 0);
    const fraction = total ? value / total : 0;
    const angle = fraction * 360;
    const startAngle = cumulativeAngle;
    const endAngle = cumulativeAngle + angle;

    const start = polarToCartesian(center, center, radius, endAngle);
    const end = polarToCartesian(center, center, radius, startAngle);
    const largeArcFlag = angle > 180 ? 1 : 0;

    const pathData = [
      `M ${center} ${center}`,
      `L ${start.x} ${start.y}`,
      `A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`,
      "Z",
    ].join(" ");

    cumulativeAngle += angle;

    return (
      <path
        key={d.label}
        d={pathData}
        fill={colors[i % colors.length]}
        onMouseEnter={() => setHoveredIndex(i)}
        onMouseLeave={() => setHoveredIndex(null)}
        style={{
          opacity: hoveredIndex === i ? 0.9 : 1,
          transition:
            "transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s",
          transform: hoveredIndex === i ? "scale(1.05)" : "scale(1)",
          transformOrigin: `${center}px ${center}px`,
          cursor: "pointer",
        }}
      />
    );
  });

  return (
    <div className="chart-card pie-chart-wrapper">
      <h3>Revenue Distribution</h3>

      <div
        className="pie-chart-container"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <svg
          width={radius * 2}
          height={radius * 2}
          viewBox={`0 0 ${radius * 2} ${radius * 2}`}
          style={{ overflow: "visible", margin: "30px 0" }}
        >
          {paths}
        </svg>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, 1fr)",
            gap: "12px",
            width: "100%",
            marginTop: "10px",
          }}
        >
          {data.map((d, i) => {
            const value = Number(d.value || 0);
            const percent = total ? ((value / total) * 100).toFixed(1) : 0;
            return (
              <div
                key={d.label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  fontSize: "0.85rem",
                  padding: "4px",
                  opacity:
                    hoveredIndex === null || hoveredIndex === i ? 1 : 0.5,
                  transition: "opacity 0.2s",
                }}
              >
                <span
                  style={{
                    background: colors[i % colors.length],
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    marginRight: 8,
                    flexShrink: 0,
                  }}
                />
                <span style={{ fontWeight: 500 }}>{d.label}</span>
                <span style={{ color: "#6b7280", marginLeft: "4px" }}>
                  ({percent}%)
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

/* ===============================
  Analytics Page
================================ */
export default function AnalyticsPage() {
  const { user, profile, signOut } = useAuth();
  const navigate = useNavigate();

  const retailerId = profile?.id || profile?.retailer_id || user?.id || null;

  const [activeConnectionId, setActiveConnectionId] = useState(null);
  const [productStockData, setProductStockData] = useState([]);
  const [categoryRevenue, setCategoryRevenue] = useState([]);
  const [ordersData, setOrdersData] = useState({
    totalRevenue: 0,
    totalOrders: 0,
    lastUpdated: null,
  });

  const [predictionCounts, setPredictionCounts] = useState({
    Dead: 0,
    Excess: 0,
    Low: 0,
    Optimum: 0,
    Slow: 0,
  });

  const [loading, setLoading] = useState(true);
  const [hasDataWarning, setHasDataWarning] = useState(false);
  const [timeRange, setTimeRange] = useState("all");
  const [filterAnchorDate, setFilterAnchorDate] = useState(null);

  const [predictionRows, setPredictionRows] = useState([]);
  const [predictionLoading, setPredictionLoading] = useState(false);
  const [selectedPredictionCategory, setSelectedPredictionCategory] =
    useState("Dead");

  const [transferRows, setTransferRows] = useState([]);
  const [transferLoading, setTransferLoading] = useState(false);
  const [analyticsTab, setAnalyticsTab] = useState("orders");
  const buyTransferRows = transferRows.filter(
    (row) => row.to_pos_connection_id === activeConnectionId,
  );

  const sellTransferRows = transferRows.filter(
    (row) => row.from_pos_connection_id === activeConnectionId,
  );

  const formatAEDLocal = (val) =>
    new Intl.NumberFormat("en-AE", {
      style: "currency",
      currency: "AED",
    }).format(val || 0);

  const handleLogout = async () => {
    await signOut();
    navigate("/login");
  };

  const displayName =
    profile?.full_name ||
    user?.user_metadata?.full_name ||
    user?.email ||
    "there";
  const role = profile?.role || "User";
  const subText = loading
    ? "Checking your account..."
    : "Track sales,performance and transfer insights.";

  /* 1. Fetch Active Connection */
  useEffect(() => {
    if (!retailerId) return;

    const fetchActiveConnection = async () => {
      const { data: activeConn, error: connError } = await supabase
        .from("pos_connections")
        .select("id")
        .eq("retailer_id", retailerId)
        .eq("is_active", true)
        .single();

      if (connError) {
        console.error("Connection Fetch Error:", connError);
        setLoading(false);
        return;
      }

      setActiveConnectionId(activeConn?.id || null);
    };

    fetchActiveConnection();
  }, [retailerId]);

  /* 1b. Fetch latest order time */
  useEffect(() => {
    if (!activeConnectionId) return;

    const fetchLatestOrderTime = async () => {
      const { data, error } = await supabase
        .from("orders")
        .select("order_time")
        .eq("pos_connection_id", activeConnectionId)
        .eq("is_active", true)
        .order("order_time", { ascending: false })
        .limit(1)
        .maybeSingle();

      if (error) {
        console.error("Latest Order Time Fetch Error:", error);
        return;
      }

      setFilterAnchorDate(data?.order_time || null);
    };

    fetchLatestOrderTime();
  }, [activeConnectionId]);

  /* 2. Fetch headline KPIs */
  useEffect(() => {
    if (!retailerId || !activeConnectionId) return;

    const fetchIntelligence = async () => {
      setLoading(true);

      try {
        const intelligenceReq = supabase
          .from("connection_intelligence")
          .select("needs_more_data, units_sold")
          .eq("pos_connection_id", activeConnectionId);

        let uniqueOrdersReq = supabase
          .from("orders")
          .select("id", { count: "exact", head: true })
          .eq("pos_connection_id", activeConnectionId);

        uniqueOrdersReq = applyTimeRangeToQuery(
          uniqueOrdersReq,
          "order_time",
          timeRange,
        );

        let revenueReq = supabase
          .from("orders")
          .select("total_amount")
          .eq("pos_connection_id", activeConnectionId)
          .eq("is_active", true);

        revenueReq = applyTimeRangeToQuery(revenueReq, "order_time", timeRange);

        let predictionsData = [];
        let predictionsError = null;

        const {
          data: predictionRowsByConnection,
          error: predictionErrByConnection,
        } = await supabase
          .from("ml_inventory_predictions")
          .select("prediction")
          .eq("pos_connection_id", activeConnectionId);

        if (predictionErrByConnection) {
          predictionsError = predictionErrByConnection;
        } else {
          predictionsData = predictionRowsByConnection || [];
        }

        if (!predictionsError && predictionsData.length === 0) {
          const {
            data: predictionRowsByRetailer,
            error: predictionErrByRetailer,
          } = await supabase
            .from("ml_inventory_predictions")
            .select("prediction")
            .eq("retailer_id", retailerId);

          if (predictionErrByRetailer) {
            predictionsError = predictionErrByRetailer;
          } else {
            predictionsData = predictionRowsByRetailer || [];
          }
        }

        if (predictionsError) throw predictionsError;

        const [intelRes, ordersRes, revenueRes] = await Promise.all([
          intelligenceReq,
          uniqueOrdersReq,
          revenueReq,
        ]);

        if (intelRes.error) throw intelRes.error;
        if (ordersRes.error) throw ordersRes.error;
        if (revenueRes.error) throw revenueRes.error;

        const data = intelRes.data || [];
        setHasDataWarning(data.length > 0 ? data[0].needs_more_data : false);

        const totalRev = (revenueRes.data || []).reduce(
          (acc, row) => acc + Number(row.total_amount || 0),
          0,
        );

        const counts = {
          Dead: 0,
          Excess: 0,
          Low: 0,
          Optimum: 0,
          Slow: 0,
        };

        (predictionsData || []).forEach((row) => {
          const key = row.prediction;
          if (counts[key] !== undefined) counts[key] += 1;
        });

        setPredictionCounts(counts);

        setOrdersData({
          totalRevenue: totalRev,
          totalOrders: ordersRes.count || 0,
          lastUpdated: new Date().toISOString(),
        });
      } catch (err) {
        console.error("Intelligence Error:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchIntelligence();
  }, [retailerId, activeConnectionId, timeRange, filterAnchorDate]);

  /* 3. Fetch Product Stock */
  useEffect(() => {
    if (!retailerId || !activeConnectionId) return;

    const fetchProductStock = async () => {
      const { data: activeProducts, error: prodErr } = await supabase
        .from("products")
        .select("id, name, category")
        .eq("pos_connection_id", activeConnectionId)
        .eq("active", true);

      if (prodErr || !activeProducts) return;

      const productIds = activeProducts.map((p) => p.id);

      const { data: invData, error: invErr } = await supabase
        .from("product_inventory")
        .select(
          `
          quantity,
          product_variations!inner (
            name,
            product_id
          )
        `,
        )
        .eq("pos_connection_id", activeConnectionId)
        .in("product_variations.product_id", productIds);

      if (!invErr && invData) {
        const flattened = invData.map((item) => {
          const parentProduct = activeProducts.find(
            (p) => p.id === item.product_variations.product_id,
          );
          return {
            id: item.product_variations.product_id,
            name: `${parentProduct?.name} (${item.product_variations?.name || "Regular"})`,
            category: parentProduct?.category || "Uncategorized",
            stock: Number(item.quantity || 0),
          };
        });
        setProductStockData(flattened);
      }
    };

    fetchProductStock();
  }, [retailerId, activeConnectionId]);

  /* 4. Fetch Category Revenue */
  useEffect(() => {
    if (!retailerId || !activeConnectionId) return;

    const fetchCategoryRevenue = async () => {
      try {
        const bounds = getTimeRangeBounds(timeRange);
        const { data, error } = await supabase.rpc("my_sales_summary", { connection_id: activeConnectionId, since_time: bounds?.start || null, until_time: bounds?.end || null });
        if (error) throw error;
        setCategoryRevenue(data.categories);
      } catch (err) {
        console.error("Revenue Mapping Error:", err);
      }
    };

    fetchCategoryRevenue();
  }, [retailerId, activeConnectionId, timeRange, filterAnchorDate]);

  /* 5. Fetch Prediction Table Rows */
  useEffect(() => {
    if (!activeConnectionId || !retailerId) return;

    const fetchPredictionRows = async () => {
      setPredictionLoading(true);

      try {
        let { data: predictionsData, error: predictionsError } = await supabase
          .from("ml_inventory_predictions")
          .select(
            `
            retailer_id,
            pos_connection_id,
            product_variation_id,
            product_name,
            prediction,
            confidence,
            demand_30d
          `,
          )
          .eq("pos_connection_id", activeConnectionId)
          .eq("prediction", selectedPredictionCategory);

        if (predictionsError) throw predictionsError;

        if (!predictionsData || predictionsData.length === 0) {
          const {
            data: retailerPredictionRows,
            error: retailerPredictionError,
          } = await supabase
            .from("ml_inventory_predictions")
            .select(
              `
              retailer_id,
              pos_connection_id,
              product_variation_id,
              product_name,
              prediction,
              confidence,
            demand_30d
            `,
            )
            .eq("retailer_id", retailerId)
            .eq("prediction", selectedPredictionCategory);

          if (retailerPredictionError) throw retailerPredictionError;
          predictionsData = retailerPredictionRows || [];
        }

        const variationIds = (predictionsData || []).map(
          (row) => row.product_variation_id,
        );

        if (variationIds.length === 0) {
          setPredictionRows([]);
          return;
        }

        const { data: inventoryData, error: inventoryError } = await supabase
          .from("product_inventory")
          .select("product_variation_id, quantity")
          .eq("pos_connection_id", activeConnectionId)
          .in("product_variation_id", variationIds);

        if (inventoryError) throw inventoryError;

        const stockMap = {};
        (inventoryData || []).forEach((row) => {
          const key = row.product_variation_id;
          stockMap[key] = (stockMap[key] || 0) + Number(row.quantity || 0);
        });

        const merged = (predictionsData || []).map((row) => ({
          id: row.product_variation_id,
          product: row.product_name,
          currentStock: stockMap[row.product_variation_id] || 0,
          demand: row.demand_30d == null ? "Unavailable" : Number(row.demand_30d).toFixed(1),
          confidence: row.confidence == null ? null : Number(row.confidence),
        }));

        setPredictionRows(merged);
      } catch (err) {
        console.error("Prediction rows fetch error:", err);
        setPredictionRows([]);
      } finally {
        setPredictionLoading(false);
      }
    };

    fetchPredictionRows();
  }, [activeConnectionId, retailerId, selectedPredictionCategory]);

  /* 6. Fetch Transfer Recommendations */
  useEffect(() => {
    if (!activeConnectionId || !retailerId) return;

    const fetchTransfers = async () => {
      setTransferLoading(true);

      try {
        let { data, error } = await supabase
          .from("ml_inventory_transfer_recommendations")
          .select(
            `
    id,
    product_name,
    transfer_qty,
    from_stock_before,
    from_stock_after,
    to_stock_before,
    to_stock_after,
    demand_30d,
    from_coverage_after,
    to_coverage_after,
    from_retailer_id,
    to_retailer_id,
    from_pos_connection_id,
    to_pos_connection_id
  `,
          )
          .or(
            `to_pos_connection_id.eq.${activeConnectionId},from_pos_connection_id.eq.${activeConnectionId}`,
          )
          .order("transfer_qty", { ascending: false });

        if (error) throw error;

        if (!data || data.length === 0) {
          const { data: retailerTransferData, error: retailerTransferError } =
            await supabase
              .from("ml_inventory_transfer_recommendations")
              .select(
                `
    id,
    product_name,
    transfer_qty,
    from_label,
    to_label,
    from_stock_before,
    from_stock_after,
    to_stock_before,
    to_stock_after,
    demand_30d,
    from_coverage_after,
    to_coverage_after,
    from_retailer_id,
    to_retailer_id,
    from_pos_connection_id,
    to_pos_connection_id
  `,
              )
              .or(
                `from_retailer_id.eq.${retailerId},to_retailer_id.eq.${retailerId}`,
              )
              .order("transfer_qty", { ascending: false });

          if (retailerTransferError) throw retailerTransferError;
          data = retailerTransferData || [];
        }

        // 1. collect all retailer ids
        const retailerIds = [
          ...new Set(
            (data || []).flatMap((row) => [
              row.from_retailer_id,
              row.to_retailer_id,
            ]),
          ),
        ];

        // 2. fetch shop names
        let shopNameMap = {};

        if (retailerIds.length > 0) {
          const { data: retailerProfiles } = await supabase
            .rpc("get_retailer_names", { retailer_ids: retailerIds });

          shopNameMap = Object.fromEntries(
            (retailerProfiles || []).map((r) => [r.id, r.shop_name]),
          );
        }

        // 3. enrich rows
        const enriched = (data || []).map((row) => ({
          id: row.id,
          product_name: row.product_name,
          transfer_qty: row.transfer_qty,

          from_stock_before: row.from_stock_before,
          from_stock_after: row.from_stock_after,
          to_stock_before: row.to_stock_before,
          to_stock_after: row.to_stock_after,

          demand_30d: row.demand_30d,

          from_coverage_after: row.from_coverage_after,
          to_coverage_after: row.to_coverage_after,

          from_retailer_id: row.from_retailer_id,
          to_retailer_id: row.to_retailer_id,

          from_pos_connection_id: row.from_pos_connection_id,
          to_pos_connection_id: row.to_pos_connection_id,

          from_shop_name:
            shopNameMap[row.from_retailer_id] ||
            row.from_label ||
            "Unknown Store",

          to_shop_name:
            shopNameMap[row.to_retailer_id] || row.to_label || "Unknown Store",
        }));

        setTransferRows(enriched);
      } catch (err) {
        console.error("Transfer Recommendations Error:", err);
        setTransferRows([]);
      } finally {
        setTransferLoading(false);
      }
    };

    fetchTransfers();
  }, [activeConnectionId, retailerId]);

  return (
    <main className="slide retail-page analytics-page">
      <Topbar
        displayName={displayName}
        role={role}
        onLogout={handleLogout}
        activePage="analytics"
      />

      <section className="analytics-layout">
        <Panel className="analytics-overview">
          <div className="overview-head">
            <div className="panel-title">
              <h2>Analytics</h2>
              <p>{subText}</p>
              <div className="title-divider" />
            </div>
            <div className="overview-actions">
              <TimeRangeFilter
                value={timeRange}
                onChange={setTimeRange}
                options={TIME_RANGE_OPTIONS}
              />
            </div>
          </div>

          <div className="analytics-subnav">
            <button
              className={`analytics-subtab ${analyticsTab === "orders" ? "active" : ""}`}
              onClick={() => setAnalyticsTab("orders")}
            >
              Order Revenue
            </button>

            <button
              className={`analytics-subtab ${analyticsTab === "stock" ? "active" : ""}`}
              onClick={() => setAnalyticsTab("stock")}
            >
              Stock Metrics
            </button>

            <button
              className={`analytics-subtab ${analyticsTab === "transfer" ? "active" : ""}`}
              onClick={() => setAnalyticsTab("transfer")}
            >
              Transfer Recommendations
            </button>
          </div>

          <div className="kpi-stack">
            {analyticsTab === "orders" && (
              <div className="kpi-tiles kpi-tiles-primary">
                <KPI
                  label="Revenue"
                  value={formatAEDLocal(ordersData.totalRevenue)}
                  sub="All matched orders"
                  tone="blue"
                />
                <KPI
                  label="Orders"
                  value={ordersData.totalOrders}
                  sub="Orders in selected range"
                  tone="slate"
                />
              </div>
            )}

            {analyticsTab === "stock" && (
              <div className="kpi-tiles kpi-tiles-secondary">
                <KPI
                  label="Dead"
                  value={predictionCounts.Dead}
                  sub="Stock policy"
                  tone="amber"
                />
                <KPI
                  label="Excess"
                  value={predictionCounts.Excess}
                  sub="Stock policy"
                  tone="purple"
                />
                <KPI
                  label="Low"
                  value={predictionCounts.Low}
                  sub="Stock policy"
                  tone="blue"
                />
                <KPI
                  label="Optimum"
                  value={predictionCounts.Optimum}
                  sub="Stock policy"
                  tone="slate"
                />
                <KPI
                  label="Slow"
                  value={predictionCounts.Slow}
                  sub="Stock policy"
                  tone="purple"
                />
              </div>
            )}
          </div>

          {analyticsTab === "stock" && (
            <>
              <div className="overview-divider" />
              <div className="charts-row">
                {productStockData.length > 0 ? (
                  <StockHealthChart data={productStockData} />
                ) : (
                  <EmptyChartState title="Stock Health" type="stock" />
                )}

                <div
                  className="revenue-card-container"
                  style={{ flex: 1, display: "flex", flexDirection: "column" }}
                >
                  {hasDataWarning && (
                    <div
                      className="inline-disclaimer"
                      style={{
                        backgroundColor: "#fffbeb",
                        border: "1px solid #fef3c7",
                        color: "#92400e",
                        padding: "8px 12px",
                        borderRadius: "20px",
                        fontSize: "0.75rem",
                        fontWeight: "600",
                        marginBottom: "10px",
                        textAlign: "center",
                        alignSelf: "center",
                      }}
                    >
                      <Icon name="warning" /> Provided orders data less than 30 days: Results may be
                      inaccurate.
                    </div>
                  )}

                  <Panel className="panel-compact prediction-panel">
                    <div className="panel-head">
                      <div className="panel-title">
                        <h3>ML Category Items</h3>
                        <p>
                          Items in the selected ML classification for the active
                          store.
                        </p>
                      </div>

                      <div className="ml-tab-container">
                        {[
                          { id: "Dead", label: "Dead", color: "#ef4444" },
                          { id: "Excess", label: "Excess", color: "#f59e0b" },
                          { id: "Low", label: "Low", color: "#f97316" },
                          {
                            id: "Optimum",
                            label: "Optimum",
                            color: "#10b981",
                          },
                          { id: "Slow", label: "Slow", color: "#6366f1" },
                        ].map((tab) => (
                          <button
                            key={tab.id}
                            className={`ml-tab-button ${
                              selectedPredictionCategory === tab.id
                                ? "active"
                                : ""
                            }`}
                            onClick={() =>
                              setSelectedPredictionCategory(tab.id)
                            }
                            style={{
                              "--ml-color": tab.color,
                              "--ml-bg": `${tab.color}15`,
                            }}
                          >
                            <span className="ml-indicator"></span>
                            <span className="ml-label">{tab.label}</span>
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="prediction-table">
                      <div className="prediction-table-head">
                        <div>PRODUCT</div>
                        <div>CURRENT STOCK</div>
                        <div>DEMAND</div>
                        <div>MODEL SUPPORT</div>
                      </div>

                      <div className="prediction-table-body">
                        {predictionLoading ? (
                          <div>Loading category items...</div>
                        ) : predictionRows.length > 0 ? (
                          predictionRows.map((row) => (
                            <div key={row.id} className="prediction-table-row">
                              <div className="prediction-product">
                                {row.product}
                              </div>
                              <div>{row.currentStock}</div>
                              <div>{row.demand}</div>
                              <div>{row.confidence == null ? "Not calibrated" : `${(row.confidence * 100).toFixed(1)}%`}</div>
                            </div>
                          ))
                        ) : (
                          <div>No items in this category.</div>
                        )}
                      </div>
                    </div>
                  </Panel>
                </div>
              </div>
            </>
          )}
        </Panel>

        {analyticsTab === "orders" && (
          <section className="analytics-main">
            <section className="analytics-left">
              <Panel className="panel-compact product-table-panel">
                <div className="panel-head">
                  <div className="panel-title">
                    <h3>Your product stock & orders</h3>
                    <p>
                      Overview of product listings, stock, and recent orders.
                    </p>
                  </div>
                </div>
                <ProductTable
                  retailerId={retailerId}
                  activeConnectionId={activeConnectionId}
                  timeRange={timeRange}
                  filterAnchorDate={filterAnchorDate}
                />
              </Panel>
            </section>

            <aside className="analytics-right">
              {categoryRevenue.length > 0 ? (
                <RevenuePieChart data={categoryRevenue} />
              ) : (
                <EmptyChartState title="Revenue Distribution" type="pie" />
              )}
            </aside>
          </section>
        )}

        {analyticsTab === "transfer" && (
          <>
            <Panel className="panel-compact transfer-panel">
              <div className="panel-head">
                <div className="panel-title">
                  <h3>Buy Recommendations</h3>
                  <p>Stock this store should receive from other outlets</p>
                </div>
              </div>

              <div className="transfer-table">
                <div className="transfer-head">
                  <div>PRODUCT</div>
                  <div>FROM STORE</div>
                  <div>TRANSFER QTY</div>
                  <div>CURRENT STOCK</div>
                  <div>POST-TRANSFER</div>
                  <div>30-DAY DEMAND</div>
                  <div>SELL-OUT (DAYS)</div>
                </div>

                <div className="transfer-body">
                  {transferLoading ? (
                    <div>Loading buy recommendations...</div>
                  ) : buyTransferRows.length > 0 ? (
                    buyTransferRows.map((row) => (
                      <div key={row.id} className="transfer-row">
                        <div className="tx-product">{row.product_name}</div>
                        <div>{row.from_shop_name}</div>
                        <div>{row.transfer_qty}</div>
                        <div>{row.to_stock_before}</div>
                        <div>{row.to_stock_after}</div>
                        <div>{row.demand_30d}</div>
                        <div>
                          {row.to_coverage_after != null
                            ? `${Math.ceil(Number(row.to_coverage_after))} days`
                            : "Today"}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div>No buy recommendations available.</div>
                  )}
                </div>
              </div>
            </Panel>

            <Panel
              className="panel-compact transfer-panel"
              style={{ marginTop: "16px" }}
            >
              <div className="panel-head">
                <div className="panel-title">
                  <h3>Sell Recommendations</h3>
                  <p>Stock this store should send to other outlets</p>
                </div>
              </div>

              <div className="transfer-table">
                <div className="transfer-head">
                  <div>PRODUCT</div>
                  <div>TO STORE</div>
                  <div>TRANSFER QTY</div>
                  <div>CURRENT STOCK</div>
                  <div>POST-TRANSFER</div>
                  <div>30-DAY DEMAND</div>
                  <div>SELL-OUT (DAYS)</div>
                </div>

                <div className="transfer-body">
                  {transferLoading ? (
                    <div>Loading sell recommendations...</div>
                  ) : sellTransferRows.length > 0 ? (
                    sellTransferRows.map((row) => (
                      <div key={row.id} className="transfer-row">
                        <div className="tx-product">{row.product_name}</div>
                        <div>{row.to_shop_name}</div>
                        <div>{row.transfer_qty}</div>
                        <div>{row.from_stock_before}</div>
                        <div>{row.from_stock_after}</div>
                        <div>{row.demand_30d}</div>
                        <div>
                          {row.to_coverage_after != null
                            ? `${Math.ceil(Number(row.to_coverage_after))} days`
                            : "Today"}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div>No sell recommendations available.</div>
                  )}
                </div>
              </div>
            </Panel>
          </>
        )}
      </section>
    </main>
  );
}

/* ===============================
  Product Table Component
================================ */
function ProductTable({
  retailerId,
  activeConnectionId,
  timeRange,
  filterAnchorDate,
}) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const [abcFilter, setAbcFilter] = useState("A");

  const filteredRows = rows.filter((row) => row.abc_class === abcFilter);

  useEffect(() => {
    if (!retailerId || !activeConnectionId) return;

    const fetchRows = async () => {
      setLoading(true);

      try {
        const intelligenceReq = supabase
          .from("products")
          .select("product_id:id, name, updated_at")
          .eq("pos_connection_id", activeConnectionId);

        const bounds = getTimeRangeBounds(timeRange);
        const salesReq = supabase.rpc("my_sales_summary", { connection_id: activeConnectionId, since_time: bounds?.start || null, until_time: bounds?.end || null });

        const [intelRes, salesRes] = await Promise.all([
          intelligenceReq,
          salesReq,
        ]);

        if (intelRes.error) throw intelRes.error;
        if (salesRes.error) throw salesRes.error;

        const intelligence = intelRes.data || [];
        const salesData = salesRes.data?.product_sales || [];

        if (intelligence.length > 0) {
          const productMatchers = intelligence
            .map((item) => ({
              productId: item.product_id,
              normalizedName: item.name?.toLowerCase().trim() || "",
            }))
            .filter((item) => item.normalizedName)
            .sort((a, b) => b.normalizedName.length - a.normalizedName.length);

          const salesMap = {};

          salesData.forEach((item) => {
            const itemName = item.item_name?.toLowerCase().trim() || "";

            const matchedProduct = productMatchers.find((product) =>
              itemName.includes(product.normalizedName),
            );

            if (!matchedProduct) return;

            const current = salesMap[matchedProduct.productId] || {
              revenue: 0,
              orderCount: 0,
            };

            current.revenue += Number(item.total_amount || 0);

            current.orderCount += Number(item.order_count || 0);

            salesMap[matchedProduct.productId] = current;
          });

          const enriched = await Promise.all(
            intelligence.map(async (item) => {
              const { data: vars } = await supabase
                .from("product_variations")
                .select("id")
                .eq("product_id", item.product_id);

              const varIds = vars?.map((v) => v.id) || [];

              const { data: invData } = await supabase
                .from("product_inventory")
                .select("quantity")
                .eq("pos_connection_id", activeConnectionId)
                .in("product_variation_id", varIds);

              const totalStock = (invData ?? []).reduce(
                (sum, row) => sum + (row.quantity || 0),
                0,
              );

              const salesForProduct = salesMap[item.product_id];

              return {
                id: item.product_id,
                product: item.name,
                abc_class: item.abc_class,
                stock: totalStock,
                totalOrders: salesForProduct
                  ? salesForProduct.orderCount
                  : 0,
                revenue: salesForProduct ? salesForProduct.revenue : 0,
                lastUpdated: item.updated_at || new Date().toISOString(),
              };
            }),
          );
          const ranked = enriched.sort((a, b) => b.revenue - a.revenue);
          const totalRevenue = ranked.reduce((sum, row) => sum + row.revenue, 0);
          let cumulative = 0;
          ranked.forEach((row) => {
            const shareBefore = totalRevenue > 0 ? cumulative / totalRevenue : 1;
            row.abc_class = shareBefore < 0.8 ? "A" : shareBefore < 0.95 ? "B" : "C";
            cumulative += row.revenue;
          });
          setRows(ranked);
        }
      } catch (err) {
        console.error("Analytics fetch error:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchRows();
  }, [retailerId, activeConnectionId, timeRange, filterAnchorDate]);

  if (loading)
    return <div className="loading-state">Loading Intelligence...</div>;

  return (
    <div className="intelligence-widget">
      <div className="abc-tab-container">
        {[
          {
            id: "A",
            label: "Top 80% Revenue",
            color: "#047857",
          },
          {
            id: "B",
            label: "Steady Movers",
            color: "#d2e005",
          },
          { id: "C", label: "Low Velocity", color: "#fc2222" },
        ].map((tab) => (
          <button
            key={tab.id}
            className={`abc-tab-button ${abcFilter === tab.id ? "active" : ""}`}
            onClick={() => setAbcFilter(tab.id)}
            style={{
              "--brand-color": tab.color,
              "--brand-bg": `${tab.color}15`,
            }}
          >
            <div className="tab-indicator" />
            <div className="tab-content">
              <span className="tab-label">{tab.label}</span>
              <span className="tab-desc">{tab.desc}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="intel-table-wrapper">
        <div className="intel-table-header">
          <div className="col-main">PRODUCT</div>
          <div className="col-stat">STOCK</div>
          <div className="col-stat">ORDERS</div>
          <div className="col-stat">REVENUE</div>
          <div className="col-date">UPDATED</div>
        </div>

        <div className="intel-table-body">
          {filteredRows.length > 0 ? (
            filteredRows.map((row) => (
              <div
                className="intel-row"
                key={row.id}
                onClick={() =>
                  navigate(
                    `/inventory?filter=${encodeURIComponent(row.product)}`,
                  )
                }
              >
                <div className="col-main">
                  <span className="product-name">{row.product}</span>
                </div>
                <div className="col-stat">{row.stock}</div>
                <div className="col-stat">{row.totalOrders}</div>
                <div className="col-stat font-mono">
                  {formatAED(row.revenue)}
                </div>
                <div className="col-date">
                  {new Date(row.lastUpdated).toLocaleDateString()}
                </div>
              </div>
            ))
          ) : (
            <div className="intel-empty">
              <span className="empty-icon"></span>
              <p>
                <Icon name="warning" /> Orders data needed to classify products into {abcFilter}{" "}
                category
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
