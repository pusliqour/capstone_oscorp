// src/pages/Landing.jsx
import { useEffect, useRef, useState } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import "/src/styles/Landing.css";
import { publicDemo } from "../supaBase/Client";
import { useAuth } from "../context/AuthContext";

import logo from "/src/styles/Logo.png";

export default function Landing() {
  const { user, signOut } = useAuth(); // Destructure what you need
  const navigate = useNavigate();
  const [active, setActive] = useState("home");
  const location = useLocation();

  const homeRef = useRef(null);
  const problemRef = useRef(null);
  const solutionRef = useRef(null);
  const featuresRef = useRef(null);
  const architectureRef = useRef(null);
  const competitorsRef = useRef(null);
  const socialRef = useRef(null);

  const sections = [
    { id: "home", ref: homeRef },
    { id: "problem", ref: problemRef },
    { id: "solution", ref: solutionRef },
    { id: "features", ref: featuresRef },
    { id: "architecture", ref: architectureRef },
    { id: "competitors", ref: competitorsRef },
    { id: "connect", ref: socialRef },
  ];

  const scrollTo = (id) => {
    const s = sections.find((x) => x.id === id);
    if (!s?.ref?.current) return;

    const top = s.ref.current.getBoundingClientRect().top + window.scrollY;
    const navOffset = 86; // navbar height + breathing room
    window.scrollTo({ top: Math.max(0, top - navOffset), behavior: "smooth" });
  };

  const handleLogout = async () => {
    await signOut();
    navigate("/"); // Redirect to landing or login after logout
  };
  useEffect(() => {
    const onScroll = () => {
      const navOffset = 120;
      const y = window.scrollY + navOffset;

      let current = "home";
      for (const s of sections) {
        const el = s.ref.current;
        if (!el) continue;
        const top = el.offsetTop;
        if (y >= top) current = s.id;
      }
      setActive(current);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (location.hash === "#connect") {
      scrollTo("connect");
    }
  }, [location]);


  return (
    <div className="landing-bg">
      {/* ===== NAVBAR ===== */}
      <nav className="navbar" aria-label="Primary">
        <button
          className="nav-brand"
          type="button"
          onClick={() => scrollTo("home")}
          aria-label="Go to Home"
        >
          <img src={logo} alt="Jiran Logo" className="nav-logo" />
          <div className="brand-text">
            <h1>Jiran</h1>
          </div>
        </button>

        <div className="nav-mid" role="navigation" aria-label="Sections">
          <button
            className={`nav-link ${active === "home" ? "active" : ""}`}
            onClick={() => scrollTo("home")}
          >
            Home
          </button>
          <button
            className={`nav-link ${active === "problem" ? "active" : ""}`}
            onClick={() => scrollTo("problem")}
          >
            Problem
          </button>
          <button
            className={`nav-link ${active === "solution" ? "active" : ""}`}
            onClick={() => scrollTo("solution")}
          >
            Solution
          </button>
          <button
            className={`nav-link ${active === "features" ? "active" : ""}`}
            onClick={() => scrollTo("features")}
          >
            Features
          </button>
          <button
            className={`nav-link ${active === "architecture" ? "active" : ""}`}
            onClick={() => scrollTo("architecture")}
          >
            How it works
          </button>
          <button
            className={`nav-link ${active === "competitors" ? "active" : ""}`}
            onClick={() => scrollTo("competitors")}
          >
            Competitors
          </button>
        </div>

        <div className="nav-right">
          {user ? (
            <>
              <Link to="/retailer-dashboard" className="nav-btn primary">
                Dashboard
              </Link>

              <Link to="/Login" className="nav-btn" onClick={handleLogout}>
                Log Out
              </Link>

              <Link to="/about" className="nav-btn">
                About
              </Link>
            </>
          ) : (
            <>
              <Link to="/Signup" className="nav-btn primary">
                Sign Up
              </Link>
              <Link to="/Login" className="nav-btn">
                Log In
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* ===== HERO / HOME ===== */}
      <section className="section hero" ref={homeRef} id="home">
        <div className="container">
          <div className="hero-card">
            <div className="badge">
              {publicDemo ? "Public architecture preview" : "Local recovery build"}
            </div>

            <h1 className="hero-title">
              Jiran
              <span className="hero-accent">.</span>
            </h1>

            <p className="hero-sub">
              A resource-allocation layer that consolidates operational data
              and supports inventory decisions without hiding evidence gaps.
            </p>

            <div className="hero-actions">
              <button
                className="btn primary"
                type="button"
                onClick={() => scrollTo("features")}
              >
                Explore Features →
              </button>
              <button
                className="btn ghost"
                type="button"
                onClick={() => scrollTo("architecture")}
              >
                View Architecture
              </button>
            </div>

            <div className="hero-stats">
              <div className="stat">
                <div className="stat-num">LOCAL</div>
                <div className="stat-label">Self-hosted data plane</div>
              </div>
              <div className="stat">
                <div className="stat-num">OPEN</div>
                <div className="stat-label">Source-neutral imports</div>
              </div>
              <div className="stat">
                <div className="stat-num">NULL</div>
                <div className="stat-label">AI until validated</div>
              </div>

            </div>
          </div>
        </div>
      </section>

      {/* ===== PROBLEM ===== */}
      <section className="section" ref={problemRef} id="problem">
        <div className="container">
          <div className="section-head">
            <div className="pill">The Challenge</div>
            <h2>
              Your POS shows what happened. Jiran shows you what to do next
            </h2>
            <p className="muted">
              Your store already collects valuable sales data.
              <br />
              But without the right insights, you're still guessing what to
              reorder, what to discount, and what to stop buying.
            </p>
          </div>

          <div className="grid cards-2">
            <div className="card">
              <div className="icon amber">💸</div>
              <h3>Slow-moving stock traps cash</h3>
              <p>
                Every item that doesn’t move is money stuck on a shelf. That
                affects your cash flow more than you realize.
              </p>
            </div>

            <div className="card">
              <div className="icon purple">🔁</div>
              <h3>Reordering based on instinct</h3>
              <p>
                “How much did we sell last time?” “Let’s order the same again.”
                But demand changes. Seasons change. Customers change.
              </p>
            </div>

            <div className="card">
              <div className="icon red">📉</div>
              <h3>No clear way to trade excess stock</h3>
              <p>
                You might have extra inventory. Another store might need it. But
                there’s no simple way to connect and trade locally.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== SOLUTION ===== */}
      <section className="section soft" ref={solutionRef} id="solution">
        <div className="container two-col">
          <div>
            <div className="pill">Our Solution</div>
            <h2>We turn POS data into clear, confident decisions.</h2>
            <p className="muted">
              No new system to learn. We connect to your existing POS and
              transform your sales data into smart, actionable insights.
            </p>

            <ul className="checklist">
              <li>Connect your POS securely with zero disruption</li>
              <li>
                Understand what’s selling, what’s slow, and what’s critical
              </li>
              <li>
                Act immediately: reorder smarter, adjust pricing, and trade
                locally
              </li>
              <li>Turn weekly guesswork into clear daily decisions</li>
            </ul>
          </div>

          <div className="mini-grid">
            <div className="mini-card">
              <div className="mini-icon">🔌</div>
              <div className="mini-title">POS</div>
              <div className="mini-sub">
                Your existing sales + inventory data.
              </div>
            </div>

            <div className="mini-card">
              <div className="mini-icon">🧠</div>
              <div className="mini-title">Jiran</div>
              <div className="mini-sub">
                Classification, insights, and recommendations.
              </div>
            </div>

            <div className="mini-card">
              <div className="mini-icon">⚡</div>
              <div className="mini-title">Action</div>
              <div className="mini-sub">
                Restock, discount, and trade with confidence.
              </div>
            </div>

            <div className="mini-card">
              <div className="mini-icon">→</div>
              <div className="mini-title">Flow</div>
              <div className="mini-sub">POS → Jiran → Action</div>
            </div>
          </div>

          <div className="cta-strip">
            <div className="cta-left">
              <div className="cta-title">POS → Jiran → Action</div>
              <div className="cta-sub muted">Connect. Analyze. Act.</div>
            </div>
            <Link to="/Signup" className="btn light">
              Get Started
            </Link>
          </div>
        </div>
      </section>

      {/* ===== FEATURES ===== */}
      <section className="section" ref={featuresRef} id="features">
        <div className="container">
          <div className="section-head center">
            <div className="pill">Capabilities</div>
            <h2>Everything You Need to Optimize Your Store.</h2>
            <p className="muted">
              Divide features into Intelligence, Action, and Connection.
            </p>
          </div>

          <div className="grid cards-3">
            <div className="card">
              <div className="icon blue">📊</div>
              <h3>INTELLIGENCE</h3>
              <p style={{ marginTop: 8 }}>
                <b>Real-Time Inventory Intelligence</b>
                <br />
                <span className="muted">
                  Instantly see what's selling, what's slowing down, and what
                  needs attention
                </span>
                <br />
                <b>
                  <br />
                  Demand Signals
                  <br />
                </b>
                <span className="muted">
                  See demand changes early and stay one step ahead
                </span>
              </p>
            </div>

            <div className="card">
              <div className="icon teal">🔄</div>
              <h3>ACTION</h3>
              <p style={{ marginTop: 8 }}>
                <b>Smarter Reordering</b>
                <br />
                <span className="muted">
                  Stop guessing. Get clear guidance on what to reorder, how much
                  to buy, and when to act
                </span>
                <br />
                <b>
                  <br />
                  Automatic Stock Classification
                  <br />
                </b>
                <span className="muted">
                  Automatically categorize products into fast, slow, and
                  critical.
                </span>
              </p>
            </div>

            <div className="card">
              <div className="icon purple">🤝</div>
              <h3>CONNECTION</h3>
              <p style={{ marginTop: 8 }}>
                <b>B2B Inventory Exchange</b>
                <br />
                <span className="muted">
                  Have extra stock? Another store might need it. Trade surplus
                  inventory instead of writing it off.
                </span>
                <br />
                <b>
                  <br />
                  Secure Access &amp; Data Privacy
                  <br />
                </b>
                <span className="muted">
                  Your data stays yours. Every connection is permission-based,
                  secure, and transparent
                </span>
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== ARCHITECTURE ===== */}
      <section className="section soft" ref={architectureRef} id="architecture">
        <div className="container">
          <div className="section-head center">
            <div className="pill">Technical</div>
            <h2>Platform Architecture</h2>
            <p className="muted">
              A modern setup designed for real-time inventory intelligence.
            </p>
          </div>

          <div className="stack">
            <div className="stack-row">
              <div className="stack-box tint-blue">
                <div className="stack-title">Frontend Applications</div>
                <div className="stack-tags">
                  <span className="tag">Retail Dashboard</span>
                  <span className="tag">Admin Tools</span>
                </div>
              </div>
              <div className="stack-connector">↓</div>
            </div>

            <div className="stack-row">
              <div className="stack-box tint-slate">
                <div className="stack-title">Backend Services</div>
                <div className="stack-tags">
                  <span className="tag">Auth</span>
                  <span className="tag">Inventory</span>
                  <span className="tag">Exchange</span>
                  <span className="tag">Notifications</span>
                </div>
              </div>
              <div className="stack-connector">↓</div>
            </div>

            <div className="stack-row">
              <div className="stack-box tint-purple">
                <div className="stack-title">AI &amp; Analytics Layer</div>
                <div className="stack-tags">
                  <span className="tag">Demand</span>
                  <span className="tag">Rebalancing</span>
                  <span className="tag">Pricing</span>
                  <span className="tag">Anomaly</span>
                </div>
              </div>
              <div className="stack-connector">↓</div>
            </div>

            <div className="stack-row">
              <div className="stack-box tint-teal">
                <div className="stack-title">Data Sources</div>
                <div className="stack-tags">
                  <span className="tag">POS</span>
                  <span className="tag">ERP</span>
                  <span className="tag">Sales</span>
                  <span className="tag">Market Data</span>
                </div>
              </div>
            </div>

            <div className="stack-foot">
              <span className="tiny-pill">Real-time sync</span>
              <span className="tiny-pill">Secure APIs</span>
              <span className="tiny-pill">Auto-scaling</span>
              <span className="tiny-pill">High uptime</span>
            </div>
          </div>
        </div>
      </section>

      {/* ===== COMPETITORS ===== */}
      <section className="section" ref={competitorsRef} id="competitors">
        <div className="container">
          <div className="section-head center">
            <div className="pill">Comparison</div>
            <h2>Why Jiran Wins</h2>
            <p className="muted">
              How we compare against traditional tools and generic marketplaces.
            </p>
          </div>

          <div className="compare">
            <div className="compare-head">
              <div className="compare-title">Features</div>
              <div className="compare-tabs">
                <span className="tab active">Jiran</span>
                <span className="tab">Traditional Systems</span>
                <span className="tab">Marketplaces</span>
              </div>
            </div>

            <div
              className="compare-table"
              role="table"
              aria-label="Competitor comparison"
            >
              {[
                "Hyperlocal optimization",
                "Real-time data sync",
                "Evidence-gated AI (validation pending)",
                "Retailer-first design",
                "Cross-store rebalancing",
                "B2B inventory exchange",
              ].map((row) => (
                <div className="compare-row" key={row}>
                  <div className="compare-cell feature">{row}</div>
                  <div className="compare-cell ok">✓</div>
                  <div className="compare-cell bad">✕</div>
                  <div className="compare-cell warn">—</div>
                </div>
              ))}
            </div>

            <div className="compare-cards">
              <div className="compare-card primary">
                <div className="cc-title">Jiran</div>
                <div className="cc-sub">
                  Designed for auditable resource decisions with optional,
                  evidence-gated intelligence.
                </div>
              </div>
              <div className="compare-card">
                <div className="cc-title">Traditional Systems</div>
                <div className="cc-sub">
                  Legacy tools that struggle with real-time cross-store
                  decisions.
                </div>
              </div>
              <div className="compare-card">
                <div className="cc-title">Marketplaces</div>
                <div className="cc-sub">
                  Not designed for internal inventory optimization or
                  rebalancing.
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== SOCIAL / CONNECT ===== */}
      <section className="section soft" ref={socialRef} id="connect">
        <div className="container">
          <div className="section-head center">
            <div className="pill">Connect</div>
            <h2>Follow our build</h2>
            <p className="muted">
              We share progress, updates, and demos as we ship.
            </p>
          </div>

          <div className="social-grid">
            <a
              className="social-card"
              href="https://instagram.com/jiran.ae"
              target="_blank"
              rel="noreferrer"
            >
              <div className="social-icon ig">📷</div>
              <div className="social-text">
                <div className="social-title">Instagram</div>
                <div className="social-handle">jiran.ae</div>
              </div>
              <div className="social-go">→</div>
            </a>

            <a
              className="social-card"
              href="https://www.linkedin.com/company/jiran-ae"
              target="_blank"
              rel="noreferrer"
            >
              <div className="social-icon in">in</div>
              <div className="social-text">
                <div className="social-title">LinkedIn</div>
                <div className="social-handle">Jiran</div>
              </div>
              <div className="social-go">→</div>
            </a>
          </div>
        </div>
      </section>

      {/* ✅ Footer removed completely */}
    </div>
  );
}
