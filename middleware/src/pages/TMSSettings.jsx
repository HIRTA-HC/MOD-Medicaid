import React, { useState, useEffect, useRef } from 'react';
import { AlertTriangle, CheckCircle, ShieldAlert } from 'lucide-react';
import { useAuthFetch } from '../auth/useAuthFetch';

const TIMEZONES = [
  { value: 'Pacific/Honolulu',     label: 'Pacific/Honolulu (HT, UTC−10)' },
  { value: 'America/Anchorage',    label: 'America/Anchorage (AKT, UTC−9)' },
  { value: 'America/Los_Angeles',  label: 'America/Los Angeles (PT, UTC−8/−7)' },
  { value: 'America/Phoenix',      label: 'America/Phoenix (MST, UTC−7)' },
  { value: 'America/Denver',       label: 'America/Denver (MT, UTC−7/−6)' },
  { value: 'America/Chicago',      label: 'America/Chicago (CT, UTC−6/−5)' },
  { value: 'America/New_York',     label: 'America/New York (ET, UTC−5/−4)' },
  { value: 'America/Puerto_Rico',  label: 'America/Puerto Rico (AST, UTC−4)' },
  { value: 'Pacific/Guam',         label: 'Pacific/Guam (ChST, UTC+10)' },
  { value: 'UTC',                  label: 'UTC (UTC+0)' },
  { value: 'Europe/London',        label: 'Europe/London (GMT/BST, UTC+0/+1)' },
  { value: 'Europe/Paris',         label: 'Europe/Paris (CET/CEST, UTC+1/+2)' },
  { value: 'Europe/Berlin',        label: 'Europe/Berlin (CET/CEST, UTC+1/+2)' },
  { value: 'Europe/Moscow',        label: 'Europe/Moscow (MSK, UTC+3)' },
  { value: 'Asia/Dubai',           label: 'Asia/Dubai (GST, UTC+4)' },
  { value: 'Asia/Kolkata',         label: 'Asia/Kolkata (IST, UTC+5:30)' },
  { value: 'Asia/Bangkok',         label: 'Asia/Bangkok (ICT, UTC+7)' },
  { value: 'Asia/Singapore',       label: 'Asia/Singapore (SGT, UTC+8)' },
  { value: 'Asia/Shanghai',        label: 'Asia/Shanghai (CST, UTC+8)' },
  { value: 'Asia/Tokyo',           label: 'Asia/Tokyo (JST, UTC+9)' },
  { value: 'Australia/Sydney',     label: 'Australia/Sydney (AEST/AEDT, UTC+10/+11)' },
  { value: 'Pacific/Auckland',     label: 'Pacific/Auckland (NZST/NZDT, UTC+12/+13)' },
];

const EMPTY_FORM = {
  tms_provider: '',
  tms_agency_name: '',
  tms_api_base_url: '',
  tms_service_tag: '',
  tms_client_id: '',
  tms_client_secret: '',
  tms_api_key: '',
  tms_token_url: '',
  tms_auto_book: '',
  tms_timezone: '',
  tms_rider_lookup: '',
  tms_webhook_endpoint: '',
};

function isValidHttpsUrl(value) {
  if (!value) return true;
  try {
    const url = new URL(value);
    return url.protocol === 'https:';
  } catch {
    return false;
  }
}

const URL_FIELDS = ['tms_api_base_url', 'tms_token_url', 'tms_webhook_endpoint'];

export default function TMSSettings() {
  const authFetch = useAuthFetch();
  const [form, setForm]           = useState(EMPTY_FORM);
  const [savedForm, setSavedForm] = useState(null);
  const [urlErrors, setUrlErrors] = useState({});
  const [status, setStatus]       = useState('loading');
  const [errorMsg, setErrorMsg]   = useState('');
  const [toast, setToast]         = useState(null);
  const toastTimerRef             = useRef(null);

  function showToast(type, message) {
    clearTimeout(toastTimerRef.current);
    setToast({ type, message });
    toastTimerRef.current = setTimeout(() => setToast(null), 4000);
  }

  useEffect(() => {
    authFetch('/tms_settings')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        const merged = { ...EMPTY_FORM, ...data };
        setForm(merged);
        setSavedForm(merged);
        setStatus('idle');
      })
      .catch(err => {
        setErrorMsg(`Failed to load settings: ${err.message}`);
        setStatus('error');
      });
  }, []);

  function setField(key, value) {
    setForm(f => ({ ...f, [key]: value }));
    if (urlErrors[key] && isValidHttpsUrl(value)) {
      setUrlErrors(e => ({ ...e, [key]: false }));
    }
  }

  function handleBlur(key, value) {
    if (URL_FIELDS.includes(key)) {
      setUrlErrors(e => ({ ...e, [key]: value.length > 0 && !isValidHttpsUrl(value) }));
    }
  }

  async function handleSave() {
    const hasUrlError = URL_FIELDS.some(k => urlErrors[k]);
    if (hasUrlError) return;
    setStatus('saving');
    setErrorMsg('');
    try {
      const res = await authFetch('/tms_settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSavedForm({ ...form });
      setStatus('idle');
      showToast('success', 'Settings saved successfully.');
    } catch (err) {
      setErrorMsg(`Save failed: ${err.message}`);
      setStatus('error');
    }
  }

  function urlStyle(key) {
    return urlErrors[key] ? { borderColor: '#dc2626', boxShadow: '0 0 0 3px rgba(220,38,38,0.12)' } : {};
  }

  const isBusy = status === 'loading' || status === 'saving';

  return (
    <section className="dashboard-view">
      <div className="warning-banner">
        <AlertTriangle size={20} className="warning-banner-icon" />
        <span>
          <strong>Demo mode:</strong> Values entered here are stored securely in AWS Secrets Manager and drive the simulated trip ingestion flow.
        </span>
      </div>

      <div className="table-card" style={{ padding: '24px' }}>
        {status === 'loading' ? (
          <div className="page-loader">
            <div className="page-spinner" />
            <span>Loading settings…</span>
          </div>
        ) : (<>
          <div
            className="form-title-bar"
            style={{ borderBottom: '1px solid #e2e8f0', paddingBottom: '16px', marginBottom: '24px' }}
          >
          <h2 style={{ fontSize: '16px', fontWeight: '700' }}>Transportation Management System (TMS)</h2>
          <span className="card-header-status">
            {status === 'loading' || status === 'saving'
              ? <span className="status-dot-gray" />
              : savedForm !== null && JSON.stringify(form) === JSON.stringify(savedForm)
              ? <><CheckCircle size={13} style={{ marginRight: 4, color: '#16a34a' }} /><span style={{ color: '#16a34a' }}>Saved</span></>
              : <><span className="status-dot-gray"></span> Not saved</>
            }
          </span>
        </div>

        {status === 'error' && errorMsg && (
          <p style={{ color: 'var(--color-danger)', fontSize: '13px', marginBottom: '16px' }}>{errorMsg}</p>
        )}

        <form onSubmit={e => e.preventDefault()} className="form-grid-2col">

          {/* ── TMS IDENTITY ─────────────────────────────────────────── */}
          <div className="form-section-divider">TMS Identity</div>

          <div className="form-group">
            <label className="form-label">TMS Provider</label>
            <input
              type="text"
              className="form-input-text"
              placeholder="e.g. Via Transportation"
              value={form.tms_provider}
              onChange={e => setField('tms_provider', e.target.value)}
              disabled={isBusy}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Agency / Operator Name</label>
            <input
              type="text"
              className="form-input-text"
              placeholder="e.g. HIRTA"
              value={form.tms_agency_name}
              onChange={e => setField('tms_agency_name', e.target.value)}
              disabled={isBusy}
            />
          </div>

          <div className="form-group">
            <label className="form-label">API Base URL</label>
            <input
              type="text"
              className="form-input-text"
              style={urlStyle('tms_api_base_url')}
              placeholder="e.g. https://us-east-1.trip-api.ridewithvia.com"
              value={form.tms_api_base_url}
              onChange={e => setField('tms_api_base_url', e.target.value)}
              onBlur={e => handleBlur('tms_api_base_url', e.target.value)}
              disabled={isBusy}
            />
            {urlErrors.tms_api_base_url && (
              <span className="form-group-caption" style={{ color: 'var(--color-danger)' }}>
                Must be a valid HTTPS URL (e.g. https://…)
              </span>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">Service Tag / Sub-Service</label>
            <input
              type="text"
              className="form-input-text"
              placeholder="e.g. Health_Connector"
              value={form.tms_service_tag}
              onChange={e => setField('tms_service_tag', e.target.value)}
              disabled={isBusy}
            />
            <span className="form-group-caption">Tag applied to all trips for filtering in TMS</span>
          </div>

          {/* ── OAUTH2 / API KEY CREDENTIALS ─────────────────────────── */}
          <div className="form-section-divider">OAuth2 / API Key Credentials</div>

          <div className="form-group">
            <label className="form-label">Client ID</label>
            <input
              type="text"
              className="form-input-text"
              placeholder="via-client-id"
              value={form.tms_client_id}
              onChange={e => setField('tms_client_id', e.target.value)}
              disabled={isBusy}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Client Secret</label>
            <input
              type="password"
              className="form-input-text"
              placeholder="••••••••••••••"
              autoComplete="new-password"
              value={form.tms_client_secret}
              onChange={e => setField('tms_client_secret', e.target.value)}
              disabled={isBusy}
            />
          </div>

          <div className="form-group">
            <label className="form-label">API Key</label>
            <input
              type="text"
              className="form-input-text"
              placeholder="x-api-key value"
              value={form.tms_api_key}
              onChange={e => setField('tms_api_key', e.target.value)}
              disabled={isBusy}
            />
            <span className="form-group-caption">Sent as x-api-key header on all requests</span>
          </div>

          <div className="form-group">
            <label className="form-label">Token URL</label>
            <input
              type="text"
              className="form-input-text"
              style={urlStyle('tms_token_url')}
              placeholder="e.g. https://auth.us-east-1.amazoncognito.com/oauth2/token"
              value={form.tms_token_url}
              onChange={e => setField('tms_token_url', e.target.value)}
              onBlur={e => handleBlur('tms_token_url', e.target.value)}
              disabled={isBusy}
            />
            {urlErrors.tms_token_url && (
              <span className="form-group-caption" style={{ color: 'var(--color-danger)' }}>
                Must be a valid HTTPS URL (e.g. https://…)
              </span>
            )}
          </div>

          {/* ── TRIP BOOKING SETTINGS ─────────────────────────────────── */}
          <div className="form-section-divider">Trip Booking Settings</div>

          <div className="form-group">
            <label className="form-label">Auto-Book on Request</label>
            <select
              className="form-select-box"
              value={form.tms_auto_book}
              onChange={e => setField('tms_auto_book', e.target.value)}
              disabled={isBusy}
            >
              <option value="">Select booking mode</option>
              <option value="yes_one_call">Yes — request + book in one call</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Timezone</label>
            <select
              className="form-select-box"
              value={form.tms_timezone}
              onChange={e => setField('tms_timezone', e.target.value)}
              disabled={isBusy}
            >
              <option value="">Select timezone</option>
              {TIMEZONES.map((tz) => (
                <option key={tz.value} value={tz.value}>{tz.label}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Rider Lookup Strategy</label>
            <select
              className="form-select-box"
              value={form.tms_rider_lookup}
              onChange={e => setField('tms_rider_lookup', e.target.value)}
              disabled={isBusy}
            >
              <option value="">Select strategy</option>
              <option value="email_synthesized">Email (synthesized)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Webhook Endpoint (from Via)</label>
            <input
              type="text"
              className="form-input-text"
              style={urlStyle('tms_webhook_endpoint')}
              placeholder="e.g. https://api.hirtahealthconnector.org/prod/via_webhook"
              value={form.tms_webhook_endpoint}
              onChange={e => setField('tms_webhook_endpoint', e.target.value)}
              onBlur={e => handleBlur('tms_webhook_endpoint', e.target.value)}
              disabled={isBusy}
            />
            <span className="form-group-caption" style={urlErrors.tms_webhook_endpoint ? { color: 'var(--color-danger)' } : {}}>
              {urlErrors.tms_webhook_endpoint
                ? 'Must be a valid HTTPS URL (e.g. https://…)'
                : 'Register this in Via dashboard to receive status updates'}
            </span>
          </div>

          <div className="form-actions-left">
            <button
              type="button"
              className="btn-run-ingestion"
              style={{ backgroundColor: 'var(--color-primary)' }}
              onClick={handleSave}
              disabled={isBusy}
            >
              {status === 'saving' ? 'Saving…' : 'Save TMS Settings'}
            </button>
            <button type="button" className="btn-reset-form" disabled={isBusy}>
              Test Connection
            </button>
          </div>

        </form>
        </>)}
      </div>

      {toast && (
        <div className={`toast toast-${toast.type}`}>
          <span className="toast-icon">
            {toast.type === 'success'
              ? <CheckCircle size={30} strokeWidth={2} />
              : <ShieldAlert  size={30} strokeWidth={2} />
            }
          </span>
          <div className="toast-body">
            <span className="toast-title">{toast.type === 'success' ? 'Success!' : 'Error!'}</span>
            <span className="toast-message">{toast.message}</span>
          </div>
          <button type="button" className="toast-close" onClick={() => setToast(null)}>✕</button>
        </div>
      )}
    </section>
  );
}
