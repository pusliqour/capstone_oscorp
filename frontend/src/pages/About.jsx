import Icon from "../components/Icon";
// src/pages/About.jsx
import React from "react";
import { Link } from "react-router-dom";
import "/src/styles/About.css";

import logo from "/src/styles/Logo.png";

// Member images (only import the files you actually have)
import yaasirImg from "/src/assets/team/yaasir.jpg";
import hamdanImg from "/src/assets/team/hamdan.jpg";
import asmaaImg from "/src/assets/team/asmaa.jpg";
import daniaImg from "/src/assets/team/dania.jpg";
import youssefImg from "/src/assets/team/youssef.jpg";
import mohsinImg from "/src/assets/team/mohsin.jpg";

const team = [
    {
        name: "Yaasir Bin Muneer",
        role: "Project Lead & Full-Stack Development",
        blurb:
            "Led the project’s overall direction while overseeing backend architecture and frontend system design, ensuring seamless integration and technical execution.",
        studentId: "8309644",
        img: yaasirImg,
        linkedin: "https://www.linkedin.com/in/yaasir-bin-muneer-b48231368/",
        email: "ybm744@uowmail.edu.au",
    },
    {
        name: "Youssef Mansi",
        role: "Frontend Engineering Lead",
        blurb:
            "Led the implementation and refinement of the frontend, translating system requirements into a functional and user-friendly interface while simultaneously managing full-stack compatibility.",
        studentId: "8221376",
        img: youssefImg,
        linkedin: "https://www.linkedin.com/in/youssef-mansi-78735b2bb/",
        email: "ysgm087@uowmail.edu",
    },
    {
        name: "Hamdan Khan",
        role: "Backend Systems Engineer",
        blurb:
            "Supported backend development and system logic implementation while assisting in integrating the machine learning components.",
        studentId: "8329163",
        img: hamdanImg,
        linkedin: "https://ae.linkedin.com/in/hamdan-k-419004201",
        email: "hark382@uowmail.edu.au",
    },
    {
        name: "Muhammad Mohsin",
        role: "Machine Learning Engineer",
        blurb:
            "Handled model selection, training, validation, and optimization to ensure accurate and efficient machine learning performance.",
        studentId: "8703164",
        img: mohsinImg, // set to mohsinImg when you add it
        linkedin: "https://www.linkedin.com/in/muhammad-mohsin-0a8879317/",
        email: "mam721@uowmail.edu.au",
    },
    {
        name: "Dania Nadeem",
        role: "Marketing & Strategy Lead",
        blurb:
            "Developed the project’s market positioning, branding strategy, and presentation narrative while supporting documentation review.",
        studentId: "8417283",
        img: daniaImg,
        linkedin: "https://www.linkedin.com/in/danianadeem/",
        email: "dn150@uowmail.edu.au",
    },
    {
        name: "Asmaa Fatima",
        role: "Documentation & Communications",
        blurb:
            "Managed formal documentation, structured reports, recorded meeting minutes, and coordinated submission materials.",
        studentId: "8219552",
        img: asmaaImg,
        linkedin: "",
        email: "af054@uowmail.edu.au",
    },
];

function initials(name) {
    return name
        .split(" ")
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0].toUpperCase())
        .join("");
}

function TeamAvatar({ img, name }) {
    const [failed, setFailed] = React.useState(false);

    if (!img || failed) {
        return <div className="about-avatar-fallback">{initials(name)}</div>;
    }

    return (
        <img
            className="about-team-photo"
            src={img}
            alt={`${name} portrait`}
            loading="lazy"
            onError={() => setFailed(true)}
        />
    );
}

export default function About() {
    return (
        <div className="about-bg">
            {/* ===== NAVBAR ===== */}
            <nav className="navbar" aria-label="Primary">
                <Link className="nav-brand" to="/" aria-label="Go to Home">
                    <img src={logo} alt="Jiran Logo" className="nav-logo" />
                    <div className="brand-text">
                        <h1>Jiran</h1>
                    </div>
                </Link>

                <div className="nav-mid">
                    <Link to="/" className="nav-link">
                        Home
                    </Link>
                    <a href="#story" className="nav-link">
                        Overview
                    </a>
                    <a href="#team" className="nav-link">
                        Team
                    </a>
                    <Link to="/#connect" className="nav-link">
                        Contact
                    </Link>
                </div>

                <div className="nav-right">
                    <Link to="/retailer-dashboard" className="nav-btn primary">
                        Dashboard
                    </Link>


                    <Link to="/Login" className="nav-btn">
                        Log Out
                    </Link>
                </div>
            </nav>

            {/* ===== HERO ===== */}
            <section className="section hero" id="about">
                <div className="container">
                    <div className="hero-card">

                        <h1 className="hero-title">
                            About <span className="hero-accent">Jiran</span>
                            <span className="hero-accent">.</span>
                        </h1>

                        <p className="hero-sub">
                            Jiran is a retail-industry technology platform built to help
                            general-store retailers overcome one of their biggest challenges:{" "}
                            <strong>inventory inefficiency</strong>.
                        </p>

                        <p className="hero-sub" style={{ marginTop: 10 }}>
                            Many small stores operate independently, which makes it difficult
                            to track product availability, manage fluctuating stock levels,
                            and prevent losses from <strong>overstocking</strong>,{" "}
                            <strong>understocking</strong>, and{" "}
                            <strong>dead stock</strong>. This disconnect also impacts
                            consumers, who often have no simple way to see which nearby stores
                            carry what they need.
                        </p>

                        <div className="hero-actions">
                            <a className="btn primary" href="#story">
                                What is Jiran? <Icon name="arrowRight" size={16} />
                            </a>
                            <a className="btn ghost" href="#team">
                                Meet the Team
                            </a>
                            <Link to="/#connect" className="btn ghost">
                                Contact
                            </Link>
                        </div>

                        <div className="hero-stats" aria-label="Project quick stats">
                            <div className="stat">
                                <div className="stat-num">6</div>
                                <div className="stat-label">Team members</div>
                            </div>
                            <div className="stat">
                                <div className="stat-num">B2B</div>
                                <div className="stat-label">Marketplace</div>
                            </div>
                            <div className="stat">
                                <div className="stat-num">POS</div>
                                <div className="stat-label">Integrated</div>
                            </div>
                            <div className="stat">
                                <div className="stat-num">ML</div>
                                <div className="stat-label">Stock insights</div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* ===== STORY / PLATFORM ===== */}
            <section className="section soft" id="story">
                <div className="container">
                    <div className="section-head center">
                        <div className="pill">Platform Overview</div>
                        <h2>One network for retailers and consumers</h2>
                        <p className="muted">
                            Built for fast setup, relevant results, and real-world general
                            stores.
                        </p>
                    </div>

                    <div className="hero-card" style={{ textAlign: "left" }}>
                        <h3
                            style={{
                                margin: "0 0 10px",
                                fontSize: "1.25rem",
                                fontWeight: 900,
                                letterSpacing: "-0.3px",
                            }}
                        >
                            Centralized B2B marketplace + smart inventory management
                        </h3>

                        <p style={{ marginTop: 0 }}>
                            Jiran combines a centralized <strong>B2B marketplace</strong> with
                            a smart <strong>inventory management</strong> system. Retailers can
                            buy and sell excess stock inside a trusted network of nearby
                            stores—helping them rebalance inventory quickly instead of losing
                            money.
                        </p>

                        <p style={{ marginTop: 10 }}>
                            At the same time, consumers can search for products, check{" "}
                            <strong>real-time availability</strong>, and locate stores that
                            carry specific items—bringing transparency and convenience to
                            everyday shopping.
                        </p>

                        <div className="hero-stats" style={{ marginTop: 16 }}>
                            <div className="stat">
                                <div className="stat-num">Rebalance</div>
                                <div className="stat-label">Buy/sell excess stock</div>
                            </div>
                            <div className="stat">
                                <div className="stat-num">Locate</div>
                                <div className="stat-label">Find items nearby</div>
                            </div>
                            <div className="stat">
                                <div className="stat-num">Transparency</div>
                                <div className="stat-label">Real-time availability</div>
                            </div>
                            <div className="stat">
                                <div className="stat-num">Trusted</div>
                                <div className="stat-label">Local retailer network</div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* ===== ML / INSIGHTS ===== */}
            <section className="section" id="insights">
                <div className="container">
                    <div className="section-head center">
                        <div className="pill">Smart Insights</div>
                        <h2>Machine-learning features that stay simple</h2>
                        <p className="muted">Retailers get decisions, not technical complexity.</p>
                    </div>

                    <div className="hero-card" style={{ textAlign: "left" }}>
                        <p style={{ marginTop: 0 }}>
                            Jiran includes machine-learning-based inventory features designed
                            to support retailers without overwhelming them with technical
                            details.
                        </p>

                        <p style={{ marginTop: 10 }}>
                            These include <strong>dead stock detection</strong>,{" "}
                            <strong>demand forecasting</strong>, and{" "}
                            <strong>sales-based inventory classification</strong>. Together,
                            they help stores understand what to stock, what to clear, and how
                            to plan ahead—making the entire retail ecosystem more efficient
                            and profitable.
                        </p>

                        <div className="hero-stats" style={{ marginTop: 16 }}>
                            <div className="stat">
                                <div className="stat-num">Dead stock</div>
                                <div className="stat-label">Identify slow movers</div>
                            </div>
                            <div className="stat">
                                <div className="stat-num">Forecast</div>
                                <div className="stat-label">Plan ahead</div>
                            </div>
                            <div className="stat">
                                <div className="stat-num">Classify</div>
                                <div className="stat-label">Stock priority</div>
                            </div>
                            <div className="stat">
                                <div className="stat-num">Actionable</div>
                                <div className="stat-label">Simple outputs</div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* ===== DIFFERENTIATORS + VISION ===== */}
            <section className="section soft" id="vision">
                <div className="container">
                    <div className="section-head center">
                        <div className="pill">What Sets Us Apart</div>
                        <h2>Built specifically for general stores</h2>
                        <p className="muted">Modern retail advantages — without the complexity.</p>
                    </div>

                    <div className="hero-card" style={{ textAlign: "left" }}>
                        <p style={{ marginTop: 0 }}>
                            What sets Jiran apart is its focus on{" "}
                            <strong>small store relevance</strong>,{" "}
                            <strong>fast transactions</strong>, <strong>ease of setup</strong>,
                            and modern stock-optimization tools designed specifically for
                            general stores.
                        </p>

                        <p style={{ marginTop: 10 }}>
                            Jiran creates an interconnected network that gives retailers the
                            advantages of modern retail technology while keeping the
                            experience clean, simple, and practical.
                        </p>

                        <div
                            style={{
                                marginTop: 14,
                                padding: "14px 14px",
                                borderRadius: 18,
                                border: "1px solid rgba(15, 23, 42, 0.08)",
                                background: "rgba(248, 250, 252, 0.70)",
                            }}
                        >
                            <div style={{ fontWeight: 950, letterSpacing: "-0.2px" }}>
                                Vision <span style={{ color: "#2563eb" }}>(Jiran)</span>
                            </div>
                            <div
                                style={{
                                    marginTop: 6,
                                    color: "#475569",
                                    lineHeight: 1.65,
                                    fontWeight: 650,
                                }}
                            >
                                To unify general-store retailers into one intelligent inventory
                                network and help them optimize their stores.
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* ===== TEAM ===== */}
            <section className="section" id="team">
                <div className="container">
                    <div className="section-head center">
                        <div className="pill">Our Team</div>
                        <h2>The six people behind Jiran</h2>
                    </div>

                    <div className="team-row" aria-label="Team members row">
                        {team.map((m) => (
                            <article
                                className="team-card team-card--compact"
                                key={m.studentId}
                                aria-label={`${m.name} team card`}
                            >
                                <div className="team-top">
                                    <div className="team-avatar-wrap" aria-hidden="true">
                                        <TeamAvatar img={m.img} name={m.name} />
                                    </div>

                                    <div className="team-meta">
                                        <div className="team-name">{m.name}</div>
                                        <div className="team-role-clean">{m.role}</div>
                                        <div className="team-id-clean">ID: {m.studentId}</div>
                                    </div>
                                </div>

                                <div className="team-desc" title={m.blurb}>
                                    {m.blurb}
                                </div>

                                <div className="team-actions">
                                    {m.linkedin ? (
                                        <a
                                            className="team-chip link"
                                            href={m.linkedin}
                                            target="_blank"
                                            rel="noreferrer"
                                        >
                                            LinkedIn
                                        </a>
                                    ) : (
                                        <span className="team-chip disabled" aria-disabled="true">
                                            LinkedIn
                                        </span>
                                    )}

                                    {m.email ? (
                                        <a className="team-chip link" href={`mailto:${m.email}`}>
                                            Email
                                        </a>
                                    ) : (
                                        <span className="team-chip disabled" aria-disabled="true">
                                            Email
                                        </span>
                                    )}
                                </div>
                            </article>
                        ))}
                    </div>
                </div>
            </section>

            {/* ===== CONTACT STRIP ===== */}
            <section className="section soft" id="contact">
                <div className="container">
                    <div className="cta-strip">
                        <div className="cta-left">
                            <div className="cta-title">Want to contact us?</div>
                            <div className="cta-sub muted">
                                Use the Contact page and we’ll get back fast.
                            </div>
                        </div>
                        <Link to="/#connect" className="btn light">
                            Contact <Icon name="arrowRight" size={16} />
                        </Link>
                    </div>
                </div>
            </section>

            {/* ===== FOOTER ===== */}
            <footer className="footer" aria-label="Footer">
                <div className="footer-content">
                    <p>© {new Date().getFullYear()} Jiran. All rights reserved.</p>
                    <div className="footer-links">
                        <Link to="/about">About</Link>
                        <Link to="/#connect">Contact</Link>
                        <Link to="/privacy">Privacy Policy</Link>
                    </div>
                </div>
            </footer>
        </div>
    );
}