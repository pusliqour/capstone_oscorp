import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext.jsx";

import Signup from "./pages/Auth/Signup.jsx";
import Login from "./pages/Auth/login.jsx";
import Landing from "./pages/Landing.jsx";
import Analytics from "./pages/Analytics.jsx";
import RetailDashboard from "./pages/RetailDashboard.jsx";
import Inventory from "./pages/Inventory.jsx";
import Exchange from "./pages/Exchange.jsx";
import DatasetNotice from "./components/DatasetNotice.jsx";
import DataExplorer from "./pages/DataExplorer.jsx";
import Settings from "./pages/Settings.jsx";
import ProtectedRoute from "./routes/ProtectedRoutes.jsx";
import Unauthorized from "./pages/Unauthorized.jsx";
import Loading from "./pages/Loading.jsx";

//  ADD THIS
import About from "./pages/About.jsx";

function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <AuthProvider>
        <DatasetNotice />
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<Landing />} />

          {/*  ADD THIS */}
          <Route path="/about" element={<About />} />

          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/unauthorized" element={<Unauthorized />} />
          <Route path="/loading" element={<Loading />} />

          {/* Retailer-only routes */}
          <Route path="/data-explorer" element={<ProtectedRoute allowedRoles={["retailer"]}><DataExplorer /></ProtectedRoute>} />
          <Route
            path="/retailer-dashboard"
            element={
              <ProtectedRoute allowedRoles={["retailer"]}>
                <RetailDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/inventory"
            element={
              <ProtectedRoute allowedRoles={["retailer"]}>
                <Inventory />
              </ProtectedRoute>
            }
          />
          <Route
            path="/analytics"
            element={
              <ProtectedRoute allowedRoles={["retailer"]}>
                <Analytics />
              </ProtectedRoute>
            }
          />
          <Route
            path="/exchange"
            element={
              <ProtectedRoute allowedRoles={["retailer"]}>
                <Exchange />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute allowedRoles={["retailer"]}>
                <Settings />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;