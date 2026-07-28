import React, { useState, useContext } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Sidebar from './components/Sidebar';
import ProtectedRoute from './components/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import TripIngestion from './pages/TripIngestion';
import BrokerSettings from './pages/BrokerSettings';
import TMSSettings from './pages/TMSSettings';
import Login from './pages/Login';
import { AuthProvider, AuthContext } from './auth/AuthContext';

function AppContent() {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, logout } = useContext(AuthContext);

  // Login page renders full-screen without the app shell
  if (location.pathname === '/login') {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
      </Routes>
    );
  }

  let title = 'Dashboard';
  let subtitle = 'Overview of trip exchange activity';

  if (location.pathname === '/ingestion') {
    title = 'Trip Ingestion';
    subtitle = 'Simulate a broker trip request flowing through Health Connector';
  } else if (location.pathname === '/broker-settings') {
    title = 'Broker Settings';
    subtitle = 'Configure Medicaid broker API credentials';
  } else if (location.pathname === '/tms-settings') {
    title = 'TMS Settings';
    subtitle = 'Configure Transportation Management System connection';
  }

  return (
    <div className="app-container">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        user={user}
        onLogout={logout}
      />

      <main className="main-content">
        <header className="top-bar">
          <div className="header-left">
            <button className="hamburger-btn" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
              <Menu size={22} />
            </button>
            <div className="header-title-group">
              <h1>{title}</h1>
              <p className="header-subtitle">{subtitle}</p>
            </div>
          </div>

          <div className="header-right">
            <span className="status-badge online">System Online</span>
            <span className="status-badge broker">Broker: Access2Care</span>
            <span className="status-badge tms">TMS: Via</span>
          </div>
        </header>

        <Routes>
          <Route path="/"                element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/ingestion"       element={<ProtectedRoute><TripIngestion /></ProtectedRoute>} />
          <Route path="/broker-settings" element={<ProtectedRoute><BrokerSettings /></ProtectedRoute>} />
          <Route path="/tms-settings"    element={<ProtectedRoute><TMSSettings /></ProtectedRoute>} />
          <Route path="/login"           element={<Login />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  );
}
