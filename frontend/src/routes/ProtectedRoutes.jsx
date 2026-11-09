import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const ProtectedRoute = ({ allowedRoles = ["retailer"], children }) => {
  const { user, profile, loading } = useAuth();
  const location = useLocation();

  // Still loading auth/profile
  if (loading) return <div role="status" style={{padding:40,textAlign:"center"}}>Loading your account…</div>;

  // Not logged in
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  // Logged in but profile not ready yet (wait)
  if (!profile) return null;

  // Retailer-only app: must be retailer
  if (profile.role !== "retailer") {
    return <Navigate to="/unauthorized" replace />;
  }

  // Keep this for future-proofing
  if (allowedRoles.length && !allowedRoles.includes(profile.role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
};

export default ProtectedRoute;