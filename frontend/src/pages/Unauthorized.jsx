import Icon from "../components/Icon";
// src/pages/Unauthorized.jsx
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function Unauthorized() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate("/login");
    }, 3000); // Redirect after 3 seconds
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div style={{ textAlign: "center", marginTop: "50px" }}>
      <h1><Icon name="ban" /> Access Denied</h1>
      <p>You do not have permission to access this page.</p>
      <p>Redirecting to login...</p>
    </div>
  );
}
