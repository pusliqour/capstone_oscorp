// src/pages/auth/Login.jsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "/src/styles/Login.css";
import logo from "/src/styles/Logo.png";
import { publicDemo, supabase } from "../../supaBase/Client";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);

  const handleAuth = async () => {
    if (publicDemo) {
      setMessage("This GitHub Pages build is a public preview. Authentication runs only in the local recovered environment.");
      return;
    }

    if (!email || !password) {
      setMessage("Please enter email and password.");
      return;
    }

    setMessage("");

    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      setMessage("Incorrect email or password.");
      return;
    }

    const user = data?.user;

    if (!user) {
      setMessage("Login failed. Please try again.");
      return;
    }

    const role = user.user_metadata?.role;

    if (!role) {
      setMessage("Account role not found. Please contact support.");
      return;
    }

    if (role === "retailer") {
      navigate("/retailer-dashboard");
    } else {
      setMessage("Unknown account type.");
    }
  };

  return (
    <div className="auth-bg">
      <nav className="navbar">
        <div className="nav-left">
          <div className="nav-brand">
            <img src={logo} alt="MarketMesh Logo" className="nav-logo" />
            <span className="nav-title">Jiran</span>
          </div>
        </div>

        <div className="nav-right">
          <Link to="/" className="nav-btn">
            Home
          </Link>
          <Link to="/signup" className="nav-btn primary">
            Sign Up
          </Link>
        </div>
      </nav>

      <main className="auth-main">
        <div className="auth-container">
          <h2>Log In</h2>

          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <div className="password-field">
            <input
              type={showPassword ? "text" : "password"}
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? "🙈" : "👁️"}
            </button>
          </div>

          <button onClick={handleAuth}>Login</button>

          <p className="text-muted mt-1 auth-toggle" onClick={() => navigate("/signup")}>
            New here? Create an account
          </p>

          {message && <p className="mt-1 auth-error">{message}</p>}
        </div>
      </main>

      <footer className="footer">
        <div className="footer-content">
          <p>&copy; {new Date().getFullYear()} Jiran. All rights reserved.</p>
          <div className="footer-links">
            <Link to="/about">About</Link>
            <Link to="/contact">Contact</Link>
            <Link to="/privacy">Privacy Policy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
