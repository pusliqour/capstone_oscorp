export default function StockPlanningMatrix({ plan, product }) {
  if (!plan?.rows?.length) return <p style={{padding:"8px 16px",color:"#617167"}}>Stock ranges await the next prediction refresh.</p>;
  const a=plan.assumptions || {};
  return <details style={{padding:"12px 16px"}}><summary style={{cursor:"pointer",fontWeight:600}}>Stock ranges · 7 / 14 / 30 / 60 days — {product}</summary>
    <p>Recommended on-hand stock targets, not statistical confidence intervals or guaranteed optimal quantities. Current stock: {plan.stock_on_hand}. Supplier lead time: {a.lead_time_known ? `${a.lead_time_days} days` : "unknown (provisional range)"}. Safety buffer: {a.safety_days} days. Review cycle: {a.review_cycle_days} days.</p>
    {plan.as_of && <p>Historical snapshot: {plan.as_of}.</p>}
    <div style={{overflowX:"auto"}}><table style={{width:"100%",borderCollapse:"collapse",textAlign:"left"}} aria-label={`Stock planning matrix for ${product}`}><thead><tr>{["Horizon","Forecast demand","Recommended stock","Position","Add to range","Above maximum"].map(h=><th key={h} style={{padding:8}}>{h}</th>)}</tr></thead><tbody>{plan.rows.map(r=><tr key={r.horizon_days}><td style={{padding:8}}>{r.horizon_days} days</td><td>{r.forecast_units}</td><td>{r.recommended_min == null ? "Collecting own-store history" : `${r.recommended_min}–${r.recommended_max}`}</td><td>{r.status}</td><td>{r.add_to_min == null ? "—" : `${r.add_to_min}–${r.add_to_max}`}</td><td>{r.above_max ?? "—"}</td></tr>)}</tbody></table></div>
    {plan.warnings?.length>0 && <ul>{plan.warnings.map(w=><li key={w}>{w}</li>)}</ul>}
  </details>;
}
