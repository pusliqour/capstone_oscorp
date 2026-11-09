import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { supabase } from "../supaBase/Client";
import ConfirmDialog from "../components/ConfirmDialog";
import "../styles/Management.css";

const emptyLocation = { location_label: "", latitude: "", longitude: "", city: "", country: "" };
const routes = [["Dashboard", "/retailer-dashboard"], ["Inventory", "/inventory"], ["Marketplace", "/exchange"], ["Analytics", "/analytics"], ["Settings", "/settings"]];
const locationDraft = data => Object.fromEntries(Object.keys(emptyLocation).map(key => [key, data?.[key] == null ? "" : String(data[key])]));
function Field({ label, help, ...props }) {
  return <label className="management-field">{label}<input {...props} />{help && <small className="management-help">{help}</small>}</label>;
}

export default function Settings() {
  const { user, profile, retailerProfile, refreshProfile, signOut } = useAuth();
  const navigate = useNavigate();
  const [editingProfile, setEditingProfile] = useState(false);
  const [draft, setDraft] = useState({ full_name: "", phone: "", shop_name: "" });
  const [location, setLocation] = useState(null);
  const [locationForm, setLocationForm] = useState(emptyLocation);
  const [editingLocation, setEditingLocation] = useState(false);
  const [locationLoading, setLocationLoading] = useState(true);
  const [storeName, setStoreName] = useState("");
  const [password, setPassword] = useState({ current: "", next: "", confirm: "" });
  const [showPasswords, setShowPasswords] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [errors, setErrors] = useState({});
  const [dialog, setDialog] = useState(null);
  const [dialogError, setDialogError] = useState("");
  const [activity, setActivity] = useState([]);
  const hasStore = Boolean(retailerProfile);
  const storedProfile = { full_name: profile?.full_name || "", phone: profile?.phone || "", shop_name: retailerProfile?.shop_name || "" };
  const dirty = (editingProfile && JSON.stringify(draft) !== JSON.stringify(storedProfile)) || (editingLocation && JSON.stringify(locationForm) !== JSON.stringify(locationDraft(location))) || Boolean(password.current || password.next || password.confirm || storeName);

  useEffect(() => { setDraft({ full_name: profile?.full_name || "", phone: profile?.phone || "", shop_name: retailerProfile?.shop_name || "" }); }, [profile?.full_name, profile?.phone, retailerProfile?.shop_name]);
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLocationLoading(true);
      const { data, error } = await supabase.from("retailer_locations").select("id,location_label,latitude,longitude,map_link,city,country").eq("retailer_id", user.id).eq("is_primary", true).maybeSingle();
      if (cancelled) return;
      if (error) setErrors(previous => ({ ...previous, location: "Could not load your location. Please refresh and try again." }));
      else { setLocation(data); setLocationForm(locationDraft(data)); }
      setLocationLoading(false);
    };
    if (user?.id && hasStore) load(); else { setLocation(null); setLocationLoading(false); }
    return () => { cancelled = true; };
  }, [user?.id, hasStore]);
  useEffect(() => {
    const handler = event => { if (dirty) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  const loadActivity = async () => {
    const { data } = await supabase.from("account_activity").select("id,action,created_at").order("created_at", { ascending: false }).limit(8);
    setActivity(data || []);
  };
  useEffect(() => { if (user?.id) loadActivity(); }, [user?.id]);
  const run = async (section, action, success) => {
    setBusy(section); setErrors(previous => ({ ...previous, [section]: "" })); setNotice("");
    try { await action(); setNotice(success); await loadActivity(); return true; }
    catch (error) { setErrors(previous => ({ ...previous, [section]: error.message || "Something went wrong. Your changes were not saved." })); return false; }
    finally { setBusy(""); }
  };
  const rpc = async (name, args) => { const { error } = await supabase.rpc(name, args); if (error) throw error; };
  const leave = async target => { if (target === "logout") { await signOut(); navigate("/login"); } else navigate(target); };
  const guard = (event, target) => { if (busy) { event.preventDefault(); return; } if (dirty) { event.preventDefault(); setDialog({ type: "discard", target }); } };
  const saveProfile = event => {
    event.preventDefault();
    run("profile", async () => {
      await rpc("save_my_profile", { full_name: draft.full_name.trim(), phone: draft.phone.trim(), shop_name: hasStore ? draft.shop_name.trim() : null });
      await refreshProfile(); setEditingProfile(false);
    }, "Profile and store details saved.");
  };
  const saveLocation = event => {
    event.preventDefault();
    run("location", async () => {
      const latitude = locationForm.latitude.trim() === "" ? null : Number(locationForm.latitude);
      const longitude = locationForm.longitude.trim() === "" ? null : Number(locationForm.longitude);
      if ((latitude === null) !== (longitude === null)) throw new Error("Enter both coordinates, or leave both blank.");
      await rpc("save_my_location", { location_label: locationForm.location_label.trim(), latitude, longitude, city: locationForm.city.trim(), country: locationForm.country.trim() });
      const { data, error } = await supabase.from("retailer_locations").select("id,location_label,latitude,longitude,map_link,city,country").eq("retailer_id", user.id).eq("is_primary", true).single();
      if (error) throw error;
      setLocation(data); setLocationForm(locationDraft(data)); setEditingLocation(false);
    }, "Store location saved.");
  };
  const locate = () => {
    if (!navigator.geolocation) { setErrors(previous => ({ ...previous, location: "Location access is unavailable. You can enter coordinates manually." })); return; }
    setBusy("locating");
    navigator.geolocation.getCurrentPosition(position => { setLocationForm(previous => ({ ...previous, latitude: position.coords.latitude.toFixed(6), longitude: position.coords.longitude.toFixed(6) })); setBusy(""); setErrors(previous => ({ ...previous, location: "" })); }, () => { setBusy(""); setErrors(previous => ({ ...previous, location: "Location access was denied or unavailable. Enter coordinates manually instead." })); }, { timeout: 10000 });
  };
  const savePassword = event => {
    event.preventDefault();
    run("password", async () => {
      if (password.next !== password.confirm) throw new Error("The new passwords do not match.");
      if (password.next.length < 10 || password.next.length > 128) throw new Error("Use a password between 10 and 128 characters.");
      if (password.next === password.current) throw new Error("Choose a different password from your current password.");
      const verified = await supabase.auth.signInWithPassword({ email: user.email, password: password.current });
      if (verified.error) throw new Error("Your current password is incorrect.");
      const { error } = await supabase.auth.updateUser({ password: password.next });
      if (error) throw error;
      setPassword({ current: "", next: "", confirm: "" }); setPasswordOpen(false);
    }, "Password changed. Use your new password the next time you sign in.");
  };
  const confirm = async text => {
    if (dialog.type === "discard") { const target = dialog.target; setDialog(null); setEditingProfile(false); setEditingLocation(false); setPassword({ current: "", next: "", confirm: "" }); setStoreName(""); await leave(target); return; }
    setBusy("delete"); setDialogError("");
    try {
      if (dialog.type === "store") { await rpc("delete_my_store", { confirmation: text }); await refreshProfile(); setLocation(null); setLocationForm(emptyLocation); setEditingLocation(false); setEditingProfile(false); setNotice("Store deleted. Your login account and personal profile are still available. You can create a new store below."); }
      else { await rpc("remove_my_location"); setLocation(null); setLocationForm(emptyLocation); setNotice("Location removed. You can set a new store location at any time."); }
      setDialog(null); await loadActivity();
    } catch (error) { setDialogError(error.message); } finally { setBusy(""); }
  };
  const errorFor = name => errors[name] && <p className="management-error" role="alert">{errors[name]}</p>;

  return <div className="management-page">
    <header className="management-header"><Link className="brand-link" to="/" onClick={event => guard(event, "/")}>Jiran</Link><nav className="management-nav" aria-label="Main navigation">{routes.map(([label, to]) => <Link key={to} to={to} aria-current={to === "/settings" ? "page" : undefined} onClick={event => guard(event, to)}>{label}</Link>)}</nav><button className="btn ghost" disabled={Boolean(busy)} onClick={event => { if (dirty) guard(event, "logout"); else leave("logout"); }}>Log out</button></header>
    <main className="management-main"><div className="management-intro"><h1>Account & store settings</h1><p>Keep your contact details, store location, and account preferences up to date.</p></div>
      {notice && <p className="management-notice" role="status">{notice}</p>}
      <div className="management-grid">
        <section className="management-card" aria-labelledby="profile-title"><h2 id="profile-title">Profile & contact</h2><p className="management-help">Your personal details and the store name shown to other retailers.</p>
          {editingProfile ? <form onSubmit={saveProfile}><fieldset disabled={Boolean(busy)}><Field label="Full name" value={draft.full_name} required maxLength={100} autoFocus autoComplete="name" onChange={event => setDraft({ ...draft, full_name: event.target.value })} /><Field label="Phone number" type="tel" autoComplete="tel" maxLength={30} placeholder="+971 50 000 0000" value={draft.phone} onChange={event => setDraft({ ...draft, phone: event.target.value })} />{hasStore && <Field label="Store name" required maxLength={120} value={draft.shop_name} onChange={event => setDraft({ ...draft, shop_name: event.target.value })} />}<Field label="Login email" value={user?.email || ""} readOnly help="This demo's login email is managed by the project owner." /></fieldset>{errorFor("profile")}<div className="management-actions"><button type="button" className="btn ghost" disabled={Boolean(busy)} onClick={() => { setDraft(storedProfile); setEditingProfile(false); }}>Cancel</button><button className="btn primary" disabled={Boolean(busy) || JSON.stringify(draft) === JSON.stringify(storedProfile)}>{busy === "profile" ? "Saving…" : "Save profile"}</button></div></form> : <><dl><dt>Full name</dt><dd>{profile?.full_name || "Not set"}</dd><dt>Email</dt><dd>{user?.email}</dd><dt>Phone</dt><dd>{profile?.phone || "Not set"}</dd><dt>Store</dt><dd>{retailerProfile?.shop_name || "No store yet"}</dd></dl><button className="btn primary" onClick={() => setEditingProfile(true)}>Edit profile</button></>}
        </section>
        <section className="management-card" aria-labelledby="location-title"><h2 id="location-title">Store location</h2><p className="management-help">Set an address and optional map coordinates for local stock exchanges.</p>
          {!hasStore ? <p>Create a store to add a location.</p> : locationLoading ? <p role="status">Loading location…</p> : editingLocation ? <form onSubmit={saveLocation}><fieldset disabled={Boolean(busy)}><Field label="Location name or address" value={locationForm.location_label} required maxLength={160} autoFocus onChange={event => setLocationForm({ ...locationForm, location_label: event.target.value })} /><div className="management-columns"><Field label="City" value={locationForm.city} maxLength={100} onChange={event => setLocationForm({ ...locationForm, city: event.target.value })} /><Field label="Country" value={locationForm.country} maxLength={100} onChange={event => setLocationForm({ ...locationForm, country: event.target.value })} /></div><div className="management-columns"><Field label="Latitude" type="number" min={-90} max={90} step="any" placeholder="25.2048" value={locationForm.latitude} onChange={event => setLocationForm({ ...locationForm, latitude: event.target.value })} /><Field label="Longitude" type="number" min={-180} max={180} step="any" placeholder="55.2708" value={locationForm.longitude} onChange={event => setLocationForm({ ...locationForm, longitude: event.target.value })} /></div><button type="button" className="btn ghost" onClick={locate}>Use device location</button><p className="management-help">Your browser asks permission first. You can enter coordinates manually instead.</p></fieldset>{errorFor("location")}<div className="management-actions"><button className="btn ghost" type="button" disabled={Boolean(busy)} onClick={() => { setLocationForm(locationDraft(location)); setEditingLocation(false); }}>Cancel</button><button className="btn primary" disabled={Boolean(busy)}>{busy === "location" ? "Saving…" : busy === "locating" ? "Locating…" : "Save location"}</button></div></form> : <>{location ? <><dl><dt>Address</dt><dd>{location.location_label}</dd><dt>City / country</dt><dd>{[location.city, location.country].filter(Boolean).join(", ") || "Not set"}</dd><dt>Coordinates</dt><dd>{location.latitude == null ? "Not set" : `${location.latitude}, ${location.longitude}`}</dd></dl>{location.map_link && <a href={location.map_link} target="_blank" rel="noreferrer">View on map ↗</a>}</> : <p className="management-help">No location set yet. Add one to help retailers find your store.</p>}{errorFor("location")}<div className="management-actions">{location && <button className="btn ghost" onClick={() => { setDialogError(""); setDialog({ type: "location" }); }}>Remove location</button>}<button className="btn primary" onClick={() => setEditingLocation(true)}>{location ? "Edit location" : "Set location"}</button></div></>}
        </section>
        <section className="management-card"><h2>Security</h2><p className="management-help">Change your password using your current password to verify it's you.</p>{passwordOpen ? <form onSubmit={savePassword}><fieldset disabled={Boolean(busy)}><Field label="Current password" type={showPasswords ? "text" : "password"} autoComplete="current-password" value={password.current} required onChange={event => setPassword({ ...password, current: event.target.value })} /><Field label="New password" type={showPasswords ? "text" : "password"} autoComplete="new-password" value={password.next} required minLength={10} maxLength={128} help="Use at least 10 characters. A unique passphrase is easier to remember." onChange={event => setPassword({ ...password, next: event.target.value })} /><Field label="Confirm new password" type={showPasswords ? "text" : "password"} autoComplete="new-password" value={password.confirm} required onChange={event => setPassword({ ...password, confirm: event.target.value })} /><label className="management-check"><input type="checkbox" checked={showPasswords} onChange={event => setShowPasswords(event.target.checked)} />Show passwords</label></fieldset>{errorFor("password")}<div className="management-actions"><button type="button" className="btn ghost" disabled={Boolean(busy)} onClick={() => { setPassword({ current: "", next: "", confirm: "" }); setPasswordOpen(false); }}>Cancel</button><button className="btn primary" disabled={Boolean(busy)}>{busy === "password" ? "Updating…" : "Update password"}</button></div></form> : <button className="btn ghost" onClick={() => setPasswordOpen(true)}>Change password</button>}</section>
        <section className="management-card"><h2>Notifications & dashboard</h2><p className="management-help">Choose what appears when you review your inventory.</p>{hasStore ? [ ["low_stock_notifications", "Low-stock alerts"], ["oos_notifications", "Out-of-stock alerts"], ["show_top_products_widget", "Top sellers on dashboard"] ].map(([column, label]) => <label className="management-check" key={column}><input type="checkbox" checked={Boolean(retailerProfile[column])} disabled={Boolean(busy)} onChange={event => { const checked = event.target.checked; run("preferences", async () => { const { error } = await supabase.from("retailer_profiles").update({ [column]: checked }).eq("id", user.id); if (error) throw error; await refreshProfile(); }, "Preferences saved."); }} />{label}</label>) : <p>Create a store to configure preferences.</p>}{errorFor("preferences")}</section>
        {!hasStore ? <section className="management-card management-wide"><h2>Create your store</h2><p className="management-help">Your account is ready. Create a store to manage products and inventory.</p><form onSubmit={event => { event.preventDefault(); run("store", async () => { await rpc("create_my_store", { shop_name: storeName.trim() }); setStoreName(""); await refreshProfile(); }, "Store created. You can now add a location and products."); }}><Field label="New store name" value={storeName} required maxLength={120} onChange={event => setStoreName(event.target.value)} />{errorFor("store")}<button className="btn primary" disabled={Boolean(busy)}>{busy === "store" ? "Creating…" : "Create store"}</button></form></section> : <section className="management-card management-wide management-danger-zone"><h2>Delete store</h2><p className="management-help">Permanently remove this store, its products, inventory, orders, listings, location and generated recommendations. Pending exchange requests will be cancelled. Your personal profile and login account remain available.</p><button className="btn management-danger" disabled={Boolean(busy)} onClick={() => { setDialogError(""); setDialog({ type: "store" }); }}>Delete store…</button></section>}
        <section className="management-card management-wide"><h2>Recent account activity</h2>{activity.length ? <ul className="management-activity">{activity.map(item => <li key={item.id}>{item.action.replaceAll("_", " ")} · <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></li>)}</ul> : <p className="management-help">Your saved profile, location and inventory changes will appear here.</p>}</section>
      </div>
    </main>
    {dialog && <ConfirmDialog title={dialog.type === "store" ? "Permanently delete this store?" : dialog.type === "location" ? "Remove store location?" : "Discard unsaved changes?"} match={dialog.type === "store" ? retailerProfile.shop_name : undefined} action={dialog.type === "store" ? "Delete store permanently" : dialog.type === "location" ? "Remove location" : "Discard and continue"} busy={busy === "delete"} error={dialogError} onClose={() => setDialog(null)} onConfirm={confirm}>{dialog.type === "store" ? <p>This cannot be undone. All store records will be removed. Your account will stay active.</p> : dialog.type === "location" ? <p>Your saved address and coordinates will be removed. Your inventory will remain.</p> : <p>Your edits have not been saved. Leave this page and discard them?</p>}</ConfirmDialog>}
  </div>;
}
