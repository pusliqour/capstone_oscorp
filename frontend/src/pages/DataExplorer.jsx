import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { supabase } from "../supaBase/Client";
import "../styles/Management.css";
import "../styles/DataExplorer.css";

const number = value => value == null ? "Unavailable" : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
const date = value => value ? new Date(value).toLocaleDateString() : "Unavailable";
export default function DataExplorer() {
  const [overview, setOverview] = useState(null);
  const [store, setStore] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [result, setResult] = useState({ rows: [], total: 0 });
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [sales, setSales] = useState([]);
  const [salesBusy, setSalesBusy] = useState(false);
  const [salesError, setSalesError] = useState("");
  useEffect(() => {
    let active = true;
    supabase.rpc("archive_overview").then(({ data, error }) => { if (active) { if (error) setError(error.message); else setOverview(data); } });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    setBusy(true); setError("");
    supabase.rpc("archive_inventory", { source_store: store || null, search_text: query, page_number: page }).then(({ data, error }) => {
      if (!active) return;
      if (error) { setError(error.message); setResult({ rows: [], total: 0 }); } else setResult(data);
      setBusy(false);
    });
    return () => { active = false; };
  }, [store, query, page]);
  useEffect(() => {
    let active = true;
    setSales([]); setSalesError("");
    if (!selected) { setSalesBusy(false); return () => { active = false; }; }
    setSalesBusy(true);
    supabase.rpc("archive_sales", { source_store: selected.store_id, source_product: selected.product_id }).then(({ data, error }) => {
      if (!active) return;
      setSalesBusy(false);
      if (error) setSalesError(error.message); else setSales(data || []);
    });
    return () => { active = false; };
  }, [selected]);
  return <div className="management-page archive-page">
    <header className="management-header"><Link to="/retailer-dashboard">Jiran</Link><nav className="management-nav" aria-label="Primary navigation"><Link to="/retailer-dashboard">Dashboard</Link><Link to="/inventory">Inventory</Link><Link to="/exchange">Marketplace</Link><Link to="/settings">Settings</Link><Link to="/data-explorer" aria-current="page">Archive data</Link></nav></header>
    <main className="archive-main"><h1>Recovered archive data</h1><p className="archive-notice"><strong>Synthetic research dataset.</strong> Recovered from your supplied Jiran.zip. These are historical generated records, not current trading activity. The three original team stores retain their existing inventory.</p>
      {error && <p role="alert" className="management-error">{error}</p>}
      {overview && <><div className="archive-stats">{[["Stores",overview.stores],["Catalog products",overview.products],["Inventory records",overview.stock_rows],["Daily sales records",overview.daily_rows],["Source transaction lines",overview.transaction_lines]].map(([label,value]) => <article className="management-card" key={label}><h2>{label}</h2><strong>{number(value)}</strong></article>)}</div>
        <p>Sales coverage: {date(overview.first_date)} – {date(overview.last_date)}. Stock snapshot: {date(overview.snapshot_date)}. Prices use the archive catalog; sales values in store analytics are estimates from those prices.</p>
        <details className="management-card"><summary>Data gaps and model limitations</summary><p>{overview.model_limit}</p><ul>{overview.missing_fields.map(field => <li key={field}>{field} — absent from the source; not invented.</li>)}</ul><p>Archive stores are labelled “Synthetic archive” in the marketplace. They include explicitly fictional address/contact placeholders added at your request. Geographic coordinates remain unset until entered by an owner. Import events and subsequent actions create the activity history.</p></details>
      </>}
      <form className="archive-filters" onSubmit={event => { event.preventDefault(); setPage(0); setQuery(search.trim()); setSelected(null); }}>
        <label htmlFor="archive-store">Store<select id="archive-store" aria-label="Store" value={store} onChange={event => { setStore(event.target.value); setPage(0); setSelected(null); }}><option value="">All 50 archive stores</option>{overview?.stores_available?.map(item => <option key={item.store_id} value={item.store_id}>{item.store_id} ({item.products} products)</option>)}</select></label>
        <label htmlFor="archive-search">Product name or ID<input id="archive-search" aria-label="Product name or ID" value={search} maxLength={120} onChange={event => setSearch(event.target.value)} /></label><button className="btn primary" type="submit">Search</button>
      </form>
      <p role="status">{busy ? "Loading archive inventory…" : `${number(result.total)} matching inventory records`}</p>
      <div className="archive-table" tabIndex="0" aria-label="Archive inventory, scroll horizontally"><table><thead><tr>{["Store / product ID","Product","Stock","Policy / model","30-day forecast","History"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{result.rows.map(row => <tr key={`${row.store_id}/${row.product_id}`}><td>{row.store_id}<br/><small>{row.product_id}</small></td><td>{row.product_name}<br/><small>{row.category} · AED {number(row.retail_price)}</small></td><td>{number(row.stock_qty)}</td><td>{row.policy_prediction || "Unavailable"} / {row.model_prediction || "Unavailable"}{row.review_required && <strong> · Review required</strong>}</td><td>{number(row.forecast_30d)}<br/><small>{row.method}</small></td><td><button className="btn" onClick={() => setSelected(row)} aria-label={`View sales for ${row.product_name} at ${row.store_id}`}>View sales</button></td></tr>)}</tbody></table></div>
      {!busy && !result.rows.length && <p>No products match these filters.</p>}
      <div className="archive-pagination"><button className="btn" disabled={busy || page === 0} onClick={() => setPage(page - 1)}>Previous</button><span>Page {page + 1} of {Math.max(1,Math.ceil(result.total / 50))}</span><button className="btn" disabled={busy || (page + 1) * 50 >= result.total} onClick={() => setPage(page + 1)}>Next</button></div>
      {selected && <section className="management-card" aria-label="Selected product sales"><h2>{selected.product_name} — {selected.store_id}</h2><button className="btn" onClick={() => setSelected(null)}>Close history</button>{salesError && <p role="alert">{salesError}</p>}{salesBusy ? <p role="status">Loading daily history…</p> : <><p>{sales.length} selling days · {number(sales.reduce((sum,row) => sum + Number(row.quantity),0))} units. Missing days indicate no recorded sales.</p><div className="archive-table archive-history"><table><thead><tr><th>Date</th><th>Units sold</th><th>Source lines</th></tr></thead><tbody>{sales.map(row => <tr key={row.sales_date}><td>{date(row.sales_date)}</td><td>{number(row.quantity)}</td><td>{number(row.transaction_count)}</td></tr>)}</tbody></table></div></>}</section>}
    </main>
  </div>;
}
