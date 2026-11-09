import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { publicDemo, supabase } from "../supaBase/Client.js";
const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [retailerProfile, setRetailerProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const activeId = useRef(null);
  const generation = useRef(0);
  const refreshProfile = useCallback(async () => {
    const attempt = generation.current;
    const { data, error } = await supabase.auth.getUser();
    if (error || !data?.user) throw new Error("Your session expired. Please sign in again.");
    const uid = data.user.id;
    const [shared, store] = await Promise.all([
      supabase.from("profiles").select("*").eq("id", uid).single(),
      supabase.from("retailer_profiles").select("*").eq("id", uid).maybeSingle(),
    ]);
    if (shared.error || store.error) throw shared.error || store.error;
    if (shared.data?.role !== "retailer") throw new Error("Retailer account required.");
    if (attempt !== generation.current) return;
    setUser(data.user); setProfile(shared.data); setRetailerProfile(store.data);
  }, []);
  useEffect(() => {
    if (publicDemo) { setLoading(false); return; }
    let disposed = false;
    let timer;
    const load = async () => {
      const attempt = ++generation.current;
      const { data } = await supabase.auth.getSession();
      const current = data?.session?.user;
      if (disposed || attempt !== generation.current) return;
      if (!current) { activeId.current = null; setUser(null); setProfile(null); setRetailerProfile(null); setLoading(false); return; }
      try { await refreshProfile(); activeId.current = current.id; }
      catch { setUser(null); setProfile(null); setRetailerProfile(null); }
      finally { if (!disposed && attempt === generation.current) setLoading(false); }
    };
    load();
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      // Reauthentication of the same account must not unmount forms in progress.
      if (session?.user?.id !== activeId.current) setLoading(true);
      clearTimeout(timer); timer = setTimeout(load, 0);
    });
    return () => { disposed = true; ++generation.current; clearTimeout(timer); listener.subscription.unsubscribe(); };
  }, [refreshProfile]);
  const signOut = async () => {
    ++generation.current;
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
    activeId.current = null; setUser(null); setProfile(null); setRetailerProfile(null);
  };
  return <AuthContext.Provider value={{ user, profile, retailerProfile, refreshProfile, loading, signOut }}>{children}</AuthContext.Provider>;
}
export const useAuth = () => useContext(AuthContext);
