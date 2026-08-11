import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function BrokerSettings() {
  return (
    <section className="dashboard-view">
      <div className="warning-banner">
        <AlertTriangle size={20} className="warning-banner-icon" />
        <span>
          <strong>Demo mode:</strong> Values entered here are stored in your browser only and are used to populate the trip ingestion simulation. No real API calls are made in this demo.
        </span>
      </div>

      <div className="table-card" style={{ padding: '24px' }}>
        <div className="form-title-bar" style={{ borderBottom: '1px solid #e2e8f0', paddingBottom: '16px', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: '700' }}>Medicaid Broker Integration</h2>
          <span className="card-header-status">
            <span className="status-dot-gray"></span> Not saved
          </span>
        </div>

        <form onSubmit={(e) => e.preventDefault()} className="form-grid-2col">
          {/* SECTION 1: BROKER IDENTITY */}
          <div className="form-section-divider">Broker Identity</div>

          <div className="form-group">
            <label className="form-label">Broker Name</label>
            <input type="text" className="form-input-text" placeholder="e.g. Access2Care" />
            <span className="form-group-caption">Display name for this Medicaid broker</span>
          </div>

          <div className="form-group">
            <label className="form-label">Program / State</label>
            <input type="text" className="form-input-text" placeholder="e.g. Iowa Medicaid NEMT" />
          </div>

          <div className="form-group">
            <label className="form-label">Broker Type</label>
            <select className="form-select-box" defaultValue="">
              <option value="" disabled>Select broker type</option>
              <option value="Lyft TAPI (Access2Care)">Lyft TAPI (Access2Care)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">API Base URL</label>
            <input type="text" className="form-input-text" placeholder="e.g. https://api.lyft.com" />
          </div>

          {/* SECTION 2: OAUTH2 CREDENTIALS */}
          <div className="form-section-divider">OAuth2 Credentials</div>

          <div className="form-group">
            <label className="form-label">Client ID</label>
            <input type="text" className="form-input-text" placeholder="your-client-id" />
          </div>

          <div className="form-group">
            <label className="form-label">Client Secret</label>
            <input type="password" className="form-input-text" placeholder="••••••••••••••••" />
          </div>

          <div className="form-group">
            <label className="form-label">Token URL</label>
            <input type="text" className="form-input-text" placeholder="e.g. https://api.lyft.com/oauth/token" />
          </div>

          <div className="form-group">
            <label className="form-label">OAuth Scope</label>
            <input type="text" className="form-input-text" placeholder="e.g. tapi.atms" />
          </div>

          {/* SECTION 3: PROGRAM SETTINGS */}
          <div className="form-section-divider">Program Settings</div>

          <div className="form-group">
            <label className="form-label">Program ID</label>
            <input type="text" className="form-input-text" placeholder="e.g. lyft-program-iowa-001" />
            <span className="form-group-caption">Assigned by broker for your agency</span>
          </div>

          <div className="form-group">
            <label className="form-label">Webhook / Callback URL</label>
            <input type="text" className="form-input-text" placeholder="e.g. https://api.hirtahealthconnector.org/prod/via_webhook" />
            <span className="form-group-caption">URL where broker will send status updates back</span>
          </div>

          <div className="form-group">
            <label className="form-label">Report-back Events</label>
            <div className="events-badges-row">
              <span className="event-badge">scheduled</span>
              <span className="event-badge">dispatched</span>
              <span className="event-badge">picked_up</span>
              <span className="event-badge">dropped_off</span>
              <span className="event-badge">canceled</span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Rider Email Domain</label>
            <input type="text" className="form-input-text" placeholder="e.g. hirta.us" />
            <span className="form-group-caption">Synthesized rider emails: firstname.lastname@(domain)</span>
          </div>

          <div className="form-actions-left">
            <button type="button" className="btn-run-ingestion" style={{ backgroundColor: 'var(--color-primary)' }}>
              Save Broker Settings
            </button>
            <button type="button" className="btn-reset-form">
              Test Connection
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
