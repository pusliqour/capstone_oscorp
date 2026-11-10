import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
export default function DatasetNotice() {
  const { retailerProfile } = useAuth();
  const { pathname } = useLocation();
  if (retailerProfile?.data_origin !== "synthetic_generated" || ["/", "/login", "/signup"].includes(pathname)) return null;
  return <aside style={{padding:"14px 24px",background:"#fff5cc",color:"#493b00",lineHeight:1.6}} aria-label="Dataset source"><strong>Synthetic archive store.</strong> Stock snapshot: 25 February 2026. Sales orders are daily aggregates; monetary totals estimate catalog value. Locations and real contact details were not supplied. <Link to="/data-explorer">Inspect source data and limitations</Link></aside>;
}
