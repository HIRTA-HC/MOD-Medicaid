import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, FileJson, Sliders, Settings, LogOut, User } from 'lucide-react';

export default function Sidebar({ isOpen, onClose, user, onLogout }) {
  return (
    <>
      {isOpen && <div className="sidebar-overlay" onClick={onClose} />}
      <aside className={`sidebar${isOpen ? ' open' : ''}`}>

        <div className="sidebar-header">
          <div className="agency-tag">Transit Agency Demo</div>
          <h2 className="sidebar-title">Health Connector</h2>
          <div className="sidebar-subtitle">Medicaid Ride Middleware</div>
        </div>

        <nav className="sidebar-nav">
          <div>
            <div className="nav-section-title">Overview</div>
            <div className="nav-links">
              <NavLink
                to="/"
                end
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                onClick={onClose}
              >
                <LayoutDashboard size={18} />
                Dashboard
              </NavLink>
              <NavLink
                to="/ingestion"
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                onClick={onClose}
              >
                <FileJson size={18} />
                Trip Ingestion
              </NavLink>
            </div>
          </div>

          <div>
            <div className="nav-section-title">Configuration</div>
            <div className="nav-links">
              <NavLink
                to="/broker-settings"
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                onClick={onClose}
              >
                <Sliders size={18} />
                Broker Settings
              </NavLink>
              <NavLink
                to="/tms-settings"
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                onClick={onClose}
              >
                <Settings size={18} />
                TMS Settings
              </NavLink>
            </div>
          </div>
        </nav>

        <footer className="sidebar-footer">
          {user && (
            <div className="sidebar-user">
              <User size={14} />
              <span className="sidebar-user-email">{user.email}</span>
            </div>
          )}
          <button className="sidebar-logout-btn" onClick={onLogout}>
            <LogOut size={16} />
            Logout
          </button>
          <div className="sidebar-footer-meta">
            <div>Health Connector v1.0</div>
            <div>Middleware · HIRTA Reference</div>
          </div>
        </footer>

      </aside>
    </>
  );
}
