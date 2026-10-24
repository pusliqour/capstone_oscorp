// src/pages/auth/Signup.jsx
import { useEffect, useState } from "react";
import { publicDemo, supabase } from "../../supaBase/Client";
import { Link, useNavigate } from "react-router-dom";
import "/src/styles/Login.css";
import logo from "/src/styles/Logo.png";

const allowedDomains = new Set([
  "gmail.com",
  "yahoo.com",
  "yahoo.co.uk",
  "hotmail.com",
  "outlook.com",
  "live.com",
  "icloud.com",
  "me.com",
  "aol.com",
  "proton.me",
  "protonmail.com",
]);

function isValidEmailFormat(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.trim());
}

function isAllowedEmailProvider(email) {
  const domain = email.trim().toLowerCase().split("@")[1];
  if (!domain) return false;
  return allowedDomains.has(domain);
}

function isStrongPassword(password) {
  return (
    password.length >= 10 &&
    /[A-Z]/.test(password) && // 1 uppercase
    /\d/.test(password) && // 1 number
    /[^A-Za-z0-9]/.test(password) // 1 special char
  );
}

function safeUUID() {
  try {
    if (crypto?.randomUUID) return crypto.randomUUID();
  } catch (_) {}
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/* ===============================
  Nominatim helpers
================================ */
async function searchPlaces(query) {
  const q = query.trim();
  if (!q) return [];

  const url = `https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(
    q,
  )}`;

  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) return [];

  return res.json();
}

async function geocodePlace(query) {
  const q = query.trim();
  if (!q) return null;

  const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(
    q,
  )}`;

  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) return null;

  const data = await res.json();
  if (!data?.length) return null;

  return { lat: Number(data[0].lat), lng: Number(data[0].lon) };
}

// -----------------------------
// Reverse geocode to get human-readable name
// -----------------------------
async function reverseGeocode(lat, lng) {
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`;
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) return null;
    const data = await res.json();
    return (
      data?.display_name ??
      `Current Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`
    );
  } catch {
    return `Current Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
  }
}

// -----------------------------
// Parse Google Maps link to coordinates
// -----------------------------
function parseMapLink(link) {
  try {
    const url = new URL(link);
    // format: google.com/maps?q=lat,lng OR /@lat,lng
    let coords = null;

    if (url.searchParams.has("q")) {
      const [lat, lng] = url.searchParams.get("q").split(",");
      coords = { lat: Number(lat), lng: Number(lng) };
    } else {
      const match = url.pathname.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
      if (match) coords = { lat: Number(match[1]), lng: Number(match[2]) };
    }

    return coords;
  } catch {
    return null;
  }
}

export default function Signup() {
  const [step, setStep] = useState(1);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Step 1
  const [shopName, setShopName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Step 2
  const [locationLabel, setLocationLabel] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [mapLink, setMapLink] = useState(""); // <-- ADD THIS
  const [selectedCoords, setSelectedCoords] = useState({
    lat: null,
    lng: null,
  }); // <-- selected coords

  const [proofFile, setProofFile] = useState(null);

  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [country, setCountry] = useState("");

  const navigate = useNavigate();

  const phoneRegex = /^\+9715[0-2,4-6,8]\d{7}$/;

  const validateStep1 = () => {
    if (!shopName.trim()) return "Please enter your shop name.";
    if (!fullName.trim()) return "Please enter your full name.";
    if (!email.trim()) return "Please enter your email.";

    if (!isValidEmailFormat(email))
      return "Please enter a valid email address (example: name@gmail.com).";

    if (!isAllowedEmailProvider(email))
      return "Please use a valid email provider (Gmail, Yahoo, Outlook, iCloud, etc.).";

    if (!phone.trim()) return "Please enter your phone number.";
    if (!phoneRegex.test(phone.replace(/\s+/g, "")))
      return "Enter a valid UAE phone number (example: +971501234567).";

    if (!password) return "Please enter a password.";
    if (!isStrongPassword(password))
      return "Password must be at least 10 characters and include 1 uppercase letter, 1 number, and 1 special character.";

    if (!confirmPassword) return "Please confirm your password.";
    if (confirmPassword !== password)
      return "Passwords do not match. Please try again.";

    return null;
  };

  const validateAll = () => {
    const step1Err = validateStep1();
    if (step1Err) return step1Err;

    if (!locationLabel.trim())
      return "Please enter your location (try: 'Dubai Sports City' or 'Motor City Dubai').";

    if (!proofFile) return "Please upload proof that you are a retailer.";

    const name = (proofFile?.name || "").toLowerCase();
    const isPdfByType = proofFile?.type === "application/pdf";
    const isPdfByExt = name.endsWith(".pdf");
    if (!isPdfByType && !isPdfByExt)
      return "Proof document must be a PDF file only.";

    return null;
  };

  // Autocomplete effect
  useEffect(() => {
    let active = true;

    const q = locationLabel.trim();
    if (q.length < 3) {
      setSuggestions([]);
      return;
    }

    searchPlaces(q).then((results) => {
      if (!active) return;
      setSuggestions(results);
    });

    return () => {
      active = false;
    };
  }, [locationLabel]);

  const selectLocation = (place) => {
    setLocationLabel(place.display_name);
    setShowSuggestions(false);

    // Set coordinates
    setSelectedCoords({ lat: Number(place.lat), lng: Number(place.lon) });

    // Auto-generate Google Maps link
    setMapLink(`https://www.google.com/maps?q=${place.lat},${place.lon}`);

    // Extract city, state, country
    const addr = place.address || {};
    setCity(addr.city || addr.town || addr.village || "");
    setState(addr.state || "");
    setCountry(addr.country || "");
  };

  const goNext = () => {
    const err = validateStep1();
    if (err) {
      setMessage(err);
      return;
    }
    setMessage("");
    setStep(2);
  };

  const goBack = () => {
    setMessage("");
    setStep(1);
  };

  const handleSignup = async (e) => {
    e.preventDefault();

    if (publicDemo) {
      setMessage("This GitHub Pages build is a public preview. Account creation runs only in the local recovered environment.");
      return;
    }

    const validationError = validateAll();
    if (validationError) {
      setMessage(validationError);
      return;
    }

    setLoading(true);
    setMessage("");

    try {
      const { data, error } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: {
            full_name: fullName.trim(),
            role: "retailer",
            phone: phone.trim(),
          },
        },
      });

      if (error) throw error;

      if (!data?.session) {
        setMessage(
          "Account created. Please check your email to confirm, then log in.",
        );
        return;
      }

      const userId = data?.user?.id;
      if (!userId) throw new Error("Signup succeeded but user id is missing.");

      // Upload PDF
      const filePath = `${userId}/${safeUUID()}.pdf`;

      const { error: uploadError } = await supabase.storage
        .from("retailer-docs")
        .upload(filePath, proofFile, {
          upsert: false,
          contentType: "application/pdf",
        });

      if (uploadError) throw uploadError;

      // Signed URL
      const { data: signed, error: signedErr } = await supabase.storage
        .from("retailer-docs")
        .createSignedUrl(filePath, 60 * 60 * 24 * 7);

      if (signedErr) throw signedErr;

      // Insert retailer profile
      const { error: retailerInsertError } = await supabase
        .from("retailer_profiles")
        .insert({
          id: userId,
          shop_name: shopName.trim(),
          document_url: signed?.signedUrl,
        });

      if (retailerInsertError) throw retailerInsertError;

      // Insert location
      // Use selectedCoords if available, else fallback to geocode
      let coords = selectedCoords;
      if (!coords.lat || !coords.lng) {
        coords = await geocodePlace(locationLabel);
      }

      // Fallback map link if user didn’t provide
      const finalMapLink =
        mapLink ||
        (coords?.lat && coords?.lng
          ? `https://www.google.com/maps?q=${coords.lat},${coords.lng}`
          : null);

      const { error: locationInsertError } = await supabase
        .from("retailer_locations")
        .insert({
          retailer_id: userId,
          location_label: locationLabel.trim() || finalMapLink,
          latitude: coords?.lat ?? null,
          longitude: coords?.lng ?? null,
          map_link: finalMapLink,
          city,
          state,
          country,
          is_primary: true,
        });

      if (locationInsertError) throw locationInsertError;

      if (!coords) {
        setMessage(
          "Signup successful, but we couldn't find coordinates for that location. Please enter a more specific location in Settings.",
        );
        setTimeout(() => navigate("/retailer-dashboard"), 900);
        return;
      }

      setMessage("Signup successful! Redirecting...");
      setTimeout(() => navigate("/retailer-dashboard"), 600);
    } catch (err) {
      console.log("SIGNUP ERROR RAW:", err);
      const msg = (err?.message || "").toLowerCase();

      if (
        msg.includes("already registered") ||
        msg.includes("already in use")
      ) {
        setMessage("This email already exists. Try logging in instead.");
      } else if (msg.includes("invalid login credentials")) {
        setMessage("Invalid email or password.");
      } else if (msg.includes("password")) {
        setMessage(
          "Password must be at least 10 characters and include 1 uppercase letter, 1 number, and 1 special character.",
        );
      } else {
        setMessage(err?.message || "Signup failed.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-bg">
      <nav className="navbar">
        <div className="nav-left">
          <Link to="/" className="nav-brand" aria-label="Go to landing page">
            <img src={logo} alt="Jiran Logo" className="nav-logo" />
            <span className="nav-title">Jiran</span>
          </Link>
        </div>

        <div className="nav-right">
          <Link to="/" className="nav-btn">
            Home
          </Link>
          <Link to="/Login" className="nav-btn primary">
            Log In
          </Link>
        </div>
      </nav>

      <main className="auth-main">
        <div className="auth-container signup-container">
          <h2>Create Retailer Account</h2>

          <div className="auth-step-pill">
            {step === 1 ? "Step 1 of 2" : "Step 2 of 2"}
          </div>

          <form onSubmit={handleSignup}>
            {step === 1 && (
              <>
                <div className="auth-section">
                  <label className="auth-section-title" htmlFor="shopName">
                    Shop Name
                  </label>
                  <input
                    id="shopName"
                    type="text"
                    placeholder="e.g. Al Noor Minimart"
                    value={shopName}
                    onChange={(e) => setShopName(e.target.value)}
                    autoComplete="organization"
                  />
                </div>

                <div className="auth-section">
                  <label className="auth-section-title" htmlFor="fullName">
                    Owner Full Name
                  </label>
                  <input
                    id="fullName"
                    type="text"
                    placeholder="e.g. Sami Mansi"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    autoComplete="name"
                  />

                  <label className="auth-section-title" htmlFor="email">
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    placeholder="e.g. name@gmail.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                  />

                  <label className="auth-section-title" htmlFor="phone">
                    Phone Number
                  </label>
                  <input
                    id="phone"
                    type="tel"
                    placeholder="e.g. +971501234567"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    autoComplete="tel"
                  />
                </div>
                <div className="auth-section">
                  <label className="auth-section-title" htmlFor="password">
                    Password
                  </label>
                  <div className="password-field">
                    <input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      placeholder="Min 10 chars, incl. 1 uppercase + 1 number + 1 special"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      className="password-toggle"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={
                        showPassword ? "Hide password" : "Show password"
                      }
                    >
                      {showPassword ? "🙈" : "👁️"}
                    </button>
                  </div>

                  <label
                    className="auth-section-title"
                    htmlFor="confirmPassword"
                    style={{ marginTop: 10 }}
                  >
                    Confirm Password
                  </label>
                  <div className="password-field">
                    <input
                      id="confirmPassword"
                      type={showConfirmPassword ? "text" : "password"}
                      placeholder="Re-type your password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      className="password-toggle"
                      onClick={() => setShowConfirmPassword((v) => !v)}
                      aria-label={
                        showConfirmPassword ? "Hide password" : "Show password"
                      }
                    >
                      {showConfirmPassword ? "🙈" : "👁️"}
                    </button>
                  </div>
                </div>

                {/* ✅ IMPORTANT: only disable while loading so errors can show */}
                <button type="button" onClick={goNext} disabled={loading}>
                  Next
                </button>
              </>
            )}

            {step === 2 && (
              <>
                {/* =========================
     STEP 2: Location + Map Link
========================= */}
                <div className="auth-section location-section">
                  <label className="auth-section-title" htmlFor="location">
                    Shop Location
                  </label>

                  {/* Current Location Button */}
                  <button
                    type="button"
                    className="current-location-btn"
                    onClick={() => {
                      if (!navigator.geolocation)
                        return alert("Geolocation not supported");

                      navigator.geolocation.getCurrentPosition(
                        async (pos) => {
                          const { latitude, longitude } = pos.coords;
                          setSelectedCoords({ lat: latitude, lng: longitude });

                          // Fixed your string template error here (was using {lat} instead of ${lat})
                          setMapLink(
                            `https://www.google.com/maps?q=${latitude},${longitude}`,
                          );

                          try {
                            const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`;
                            const res = await fetch(url, {
                              headers: { "Accept-Language": "en" },
                            }); // Force English
                            const data = await res.json();
                            const addr = data.address || {};

                            // 1. Set the Label
                            setLocationLabel(
                              data.display_name || "Custom Location",
                            );

                            // 2. Robust City Logic (Checks multiple possible keys)
                            const detectedCity =
                              addr.city ||
                              addr.town ||
                              addr.village ||
                              addr.suburb ||
                              addr.city_district ||
                              "";
                            setCity(detectedCity);

                            // 3. State/Province Logic
                            setState(
                              addr.state || addr.province || addr.region || "",
                            );

                            // 4. Country
                            setCountry(addr.country || "");
                          } catch (err) {
                            console.error("Reverse geocode failed", err);
                          }
                        },
                        (err) =>
                          alert("Location access denied or unavailable."),
                      );
                    }}
                  >
                    📍 Use Current Location
                  </button>

                  <div className="location-or-separator">or</div>

                  {/* Location Input */}
                  <input
                    id="location"
                    type="text"
                    placeholder="Enter location (e.g., Dubai Sports City)"
                    value={locationLabel}
                    onChange={(e) => setLocationLabel(e.target.value)}
                  />

                  {/* Google Maps Link Input */}
                  <input
                    type="text"
                    placeholder="Or paste Google Maps link"
                    value={mapLink}
                    onChange={(e) => {
                      setMapLink(e.target.value);
                      const coords = parseMapLink(e.target.value);
                      if (coords) setSelectedCoords(coords);

                      // Do NOT fill city/state/country automatically
                      // They remain as is unless user selects from autocomplete
                    }}
                  />

                  {/* Autocomplete suggestions */}
                  {showSuggestions && suggestions.length > 0 && (
                    <ul className="location-suggestions">
                      {suggestions.map((place, idx) => (
                        <li key={idx} onClick={() => selectLocation(place)}>
                          {place.display_name}
                        </li>
                      ))}
                    </ul>
                  )}

                  <small className="auth-help-text">
                    You can use your current location 📍, type your location, or
                    paste a Google Maps link.
                  </small>

                  <div className="location-fields-row">
                    <div className="field-group">
                      <label htmlFor="city">City</label>
                      <input
                        id="city"
                        type="text"
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                      />
                    </div>
                    <div className="field-group">
                      <label htmlFor="state">State</label>
                      <input
                        id="state"
                        type="text"
                        value={state}
                        onChange={(e) => setState(e.target.value)}
                      />
                    </div>
                    <div className="field-group">
                      <label htmlFor="country">Country</label>
                      <input
                        id="country"
                        type="text"
                        value={country}
                        onChange={(e) => setCountry(e.target.value)}
                      />
                    </div>
                  </div>
                </div>

                <div className="auth-section">
                  <label className="auth-section-title" htmlFor="proofDoc">
                    Shop License Document
                  </label>

                  <input
                    id="proofDoc"
                    type="file"
                    accept="application/pdf,.pdf"
                    onChange={(e) => setProofFile(e.target.files?.[0] || null)}
                  />

                  <small className="auth-help-text">
                    Example: Trade license or retailer proof document (PDF only)
                  </small>
                </div>

                <div className="auth-row-buttons">
                  <button
                    type="button"
                    onClick={goBack}
                    className="auth-btn-secondary"
                    disabled={loading}
                  >
                    Back
                  </button>

                  <button type="submit" disabled={loading}>
                    {loading ? "Signing up..." : "Sign up"}
                  </button>
                </div>
              </>
            )}
          </form>

          {message && <p className="auth-error">{message}</p>}
        </div>
      </main>
    </div>
  );
}
