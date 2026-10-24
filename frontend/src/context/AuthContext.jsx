import { createContext, useContext, useEffect, useState } from "react";
import { publicDemo, supabase } from "../supaBase/Client.js";
import { getMyProfile } from "../supaBase/Profiles.js";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);

  // shared profile row from public.profiles
  const [profile, setProfile] = useState(null);

  // retailer-specific row from retailer_profiles
  const [retailerProfile, setRetailerProfile] = useState(null);

  const [loading, setLoading] = useState(true);

  /**
   * Fetch retailer profile ONLY
   * (no customers, no fallback roles)
   */
  const fetchRetailerProfile = async (uid) => {
    const { data, error } = await supabase
      .from("retailer_profiles")
      .select("id, shop_name, document_url, store_id, created_at")
      .eq("id", uid)
      .single();

    if (error) return null;
    return data;
  };

  useEffect(() => {
    if (publicDemo) {
      setLoading(false);
      return;
    }

    const loadUser = async () => {
      setLoading(true);

      const { data } = await supabase.auth.getUser();

      // No active session
      if (!data?.user) {
        setUser(null);
        setProfile(null);
        setRetailerProfile(null);
        setLoading(false);
        return;
      }

      const u = data.user;
      setUser(u);

      /**
       * 1) Load shared profile (public.profiles)
       * This MUST exist and MUST be retailer
       */
      const { data: profileData, error: profileError } = await getMyProfile(u.id);

      if (profileError || !profileData || profileData.role !== "retailer") {
        // Invalid or incomplete setup → force logout
        await supabase.auth.signOut();
        setUser(null);
        setProfile(null);
        setRetailerProfile(null);
        setLoading(false);
        return;
      }

      setProfile(profileData);

      /**
       * 2) Load retailer-specific profile
       */
      const retailerData = await fetchRetailerProfile(u.id);
      setRetailerProfile(retailerData);

      setLoading(false);
    };

    loadUser();

    const { data: authListener } = supabase.auth.onAuthStateChange(() => {
      loadUser();
    });

    return () => {
      authListener?.subscription?.unsubscribe();
    };
  }, []);

  const signOut = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setProfile(null);
    setRetailerProfile(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        retailerProfile,
        loading,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
