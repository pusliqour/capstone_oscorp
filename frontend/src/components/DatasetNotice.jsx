import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { supabase } from "../supaBase/Client";
export default function DatasetNotice() {
  const { retailerProfile } = useAuth();
  const { pathname } = useLocation();
  const [reference, setReference] = useState(null);
  useEffect(() => {
    let active = true;setReference(null);
    if (retailerProfile?.reference_business_id) supabase.rpc("get_retailer_contact",{target_user_id:retailerProfile.id}).then(({data,error}) => { if(active && !error) setReference(data?.[0] || null); });
    return () => { active=false; };
  }, [retailerProfile?.id,retailerProfile?.reference_business_id]);
  if (retailerProfile?.data_origin !== "synthetic_generated" || ["/", "/login", "/signup"].includes(pathname)) return null;
  return <aside style={{padding:"14px 24px",background:"#fff5cc",color:"#493b00",lineHeight:1.6}} aria-label="Dataset source"><strong>Synthetic archive store.</strong> Stock snapshot: 25 February 2026. Sales orders are daily aggregates; monetary totals estimate catalog value. {reference ? <span>Location/contact reference: <strong>{reference.reference_business_name}</strong> (<a href={reference.reference_source_url} target="_blank" rel="noopener noreferrer">official source</a>). This business is not a verified participant and did not supply the synthetic inventory. </span> : "Locations and contacts are demonstration references, not verified retailer identities. "}<Link to="/data-explorer">Inspect sources and limitations</Link></aside>;
}
