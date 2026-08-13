import React, { useState, useEffect, useRef } from 'react';
import { Info, CheckCircle, ShieldAlert } from 'lucide-react';
import CustomDateTimePicker from '../components/CustomDateTimePicker';
import { useAuthFetch } from '../auth/useAuthFetch';

// ── Constants ────────────────────────────────────────────────────────────────

const EMPTY_FORM = {
  brokerTripId: '',
  pickupTime: '',
  pickupAddress: '',
  dropoffAddress: '',
  riderFirstName: '',
  riderLastName: '',
  riderPhone: '',
  vehicleType: '',
  additionalRiders: '',
  appointmentTime: '',
};

const SAMPLE_DATA = {
  form: {
    brokerTripId: 'TAPI-2024-08847',
    pickupTime: '07-25-2024, 09:30 AM',
    pickupAddress: '600-614 Grove St, Perry, IA 50220, USA',
    dropoffAddress: '610 10th St, Perry, IA 50220, United States',
    riderFirstName: 'John',
    riderLastName: 'Smith',
    riderPhone: '+12122223333',
    vehicleType: 'SEDAN',
    additionalRiders: '0',
    appointmentTime: '07-25-2024, 10:00 AM',
  },
  pickupCoords: {
    lat: 41.5547, lng: -93.7144,
    addressLine1: '5229 Fawnway Dr', city: 'Des Moines', state: 'IA', zip: '50321',
  },
  dropoffCoords: {
    lat: 41.5868, lng: -93.6250,
    addressLine1: '1200 Pleasant St', city: 'Des Moines', state: 'IA', zip: '50309',
  },
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function parseDateTime(str) {
  if (!str) return '';
  const [datePart, timePart] = str.split(', ');
  if (!datePart || !timePart) return '';
  const [mm, dd, yyyy] = datePart.split('-');
  const [time, ampm] = timePart.split(' ');
  let [h, min] = time.split(':').map(Number);
  if (ampm === 'PM' && h !== 12) h += 12;
  if (ampm === 'AM' && h === 12) h = 0;
  return `${yyyy}-${mm}-${dd}T${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}:00`;
}

function isValidPhone(phone) {
  const cleaned = phone.replace(/[\s\-().]/g, '');
  return /^\+?1?\d{10}$/.test(cleaned);
}

function parseApiError(data, httpStatus) {
  if (data?.response && typeof data.response === 'string') {
    try {
      const jsonPart = data.response.replace(/^[^{]+/, '');
      const parsed = JSON.parse(jsonPart);
      return parsed.info || parsed.message || data.response;
    } catch {
      return data.response;
    }
  }
  return data?.error || `HTTP ${httpStatus}`;
}

function JsonHighlight({ data }) {
  const json = JSON.stringify(data, null, 2);
  const TOKEN_RE = /("(?:\\u[0-9a-fA-F]{4}|\\[^u]|[^\\"])*"(?:\s*:)?|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g;
  const COLORS = { key: '#9cdcfe', string: '#ce9178', number: '#b5cea8', boolean: '#569cd6', null: '#569cd6', plain: '#d4d4d4' };

  const parts = [];
  let last = 0, m;
  while ((m = TOKEN_RE.exec(json)) !== null) {
    if (m.index > last) parts.push({ t: 'plain', v: json.slice(last, m.index) });
    const v = m[0];
    const t = /^"/.test(v) ? (/:$/.test(v) ? 'key' : 'string')
            : /true|false/.test(v) ? 'boolean'
            : /null/.test(v) ? 'null' : 'number';
    parts.push({ t, v });
    last = TOKEN_RE.lastIndex;
  }
  if (last < json.length) parts.push({ t: 'plain', v: json.slice(last) });

  return (
    <pre className="preview-json">
      {parts.map((p, i) => <span key={i} style={{ color: COLORS[p.t] }}>{p.v}</span>)}
    </pre>
  );
}

function extractAddressComponents(place) {
  let addressLine1 = '';
  let city = '';
  let state = '';
  let zip = '';
  let streetNumber = '';
  let route = '';

  for (const component of place.address_components || []) {
    const types = component.types;
    if (types.includes('street_number')) streetNumber = component.long_name;
    else if (types.includes('route')) route = component.short_name;
    else if (types.includes('locality')) city = component.long_name;
    else if (types.includes('administrative_area_level_1')) state = component.short_name;
    else if (types.includes('postal_code')) zip = component.long_name;
  }
  addressLine1 = streetNumber ? `${streetNumber} ${route}` : route;
  return { addressLine1, city, state, zip };
}

// ── Component ────────────────────────────────────────────────────────────────

export default function TripIngestion() {
  const authFetch = useAuthFetch();
  const [googleMapsLoaded, setGoogleMapsLoaded] = useState(false);
  const pickupInputRef  = useRef(null);
  const dropoffInputRef = useRef(null);

  const [form, setForm]                     = useState(EMPTY_FORM);
  const [pickupCoords, setPickupCoords]     = useState(null);
  const [dropoffCoords, setDropoffCoords]   = useState(null);
  const [activeTab, setActiveTab]           = useState('broker');
  const [payloads, setPayloads]             = useState({ broker: null, via: null, response: null });
  const [loading, setLoading]               = useState(false);
  const [errors, setErrors]                 = useState({});
  const [toast, setToast]                   = useState(null);
  const toastTimerRef                       = useRef(null);

  function showToast(type, message) {
    clearTimeout(toastTimerRef.current);
    setToast({ type, message });
    toastTimerRef.current = setTimeout(() => setToast(null), 4000);
  }

  function setField(name, value) {
    setForm(f => ({ ...f, [name]: value }));
  }

  // ── Google Maps loader ──────────────────────────────────────────────────

  useEffect(() => {
    const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || window.GOOGLE_MAPS_API_KEY || 'YOUR_GOOGLE_MAPS_API_KEY';
    if (!API_KEY || API_KEY === 'YOUR_GOOGLE_MAPS_API_KEY') {
      console.warn('Google Maps Places Autocomplete is disabled: set VITE_GOOGLE_MAPS_API_KEY.');
      return;
    }
    if (window.google && window.google.maps) { setGoogleMapsLoaded(true); return; }
    const existingScript = document.getElementById('google-maps-script');
    if (existingScript) { existingScript.addEventListener('load', () => setGoogleMapsLoaded(true)); return; }
    const script = document.createElement('script');
    script.id = 'google-maps-script';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${API_KEY}&libraries=places`;
    script.async = true;
    script.defer = true;
    script.addEventListener('load', () => setGoogleMapsLoaded(true));
    document.head.appendChild(script);
  }, []);

  // ── Autocomplete setup ──────────────────────────────────────────────────

  useEffect(() => {
    if (!googleMapsLoaded) return;
    let pickupAC, dropoffAC;
    const pickupEl  = pickupInputRef.current;
    const dropoffEl = dropoffInputRef.current;

    if (pickupEl) {
      pickupAC = new window.google.maps.places.Autocomplete(pickupEl, {
        types: ['address'], componentRestrictions: { country: 'us' },
      });
      pickupAC.addListener('place_changed', () => {
        const place = pickupAC.getPlace();
        if (!place.geometry) return;
        const addr = extractAddressComponents(place);
        setForm(f => ({ ...f, pickupAddress: place.formatted_address || pickupEl.value }));
        setPickupCoords({ lat: place.geometry.location.lat(), lng: place.geometry.location.lng(), ...addr });
      });
    }

    if (dropoffEl) {
      dropoffAC = new window.google.maps.places.Autocomplete(dropoffEl, {
        types: ['address'], componentRestrictions: { country: 'us' },
      });
      dropoffAC.addListener('place_changed', () => {
        const place = dropoffAC.getPlace();
        if (!place.geometry) return;
        const addr = extractAddressComponents(place);
        setForm(f => ({ ...f, dropoffAddress: place.formatted_address || dropoffEl.value }));
        setDropoffCoords({ lat: place.geometry.location.lat(), lng: place.geometry.location.lng(), ...addr });
      });
    }

    return () => {
      if (window.google?.maps?.event) {
        if (pickupAC  && pickupEl)  window.google.maps.event.clearInstanceListeners(pickupEl);
        if (dropoffAC && dropoffEl) window.google.maps.event.clearInstanceListeners(dropoffEl);
      }
    };
  }, [googleMapsLoaded]);

  // ── Handlers ────────────────────────────────────────────────────────────

  function handleReset() {
    setForm(EMPTY_FORM);
    setPickupCoords(null);
    setDropoffCoords(null);
    if (pickupInputRef.current)  pickupInputRef.current.value  = '';
    if (dropoffInputRef.current) dropoffInputRef.current.value = '';
    setPayloads({ broker: null, via: null, response: null });
    setErrors({});
    setToast(null);
    clearTimeout(toastTimerRef.current);
  }

  function handleLoadSample() {
    setForm(SAMPLE_DATA.form);
    setPickupCoords(SAMPLE_DATA.pickupCoords);
    setDropoffCoords(SAMPLE_DATA.dropoffCoords);
    if (pickupInputRef.current)  pickupInputRef.current.value  = SAMPLE_DATA.form.pickupAddress;
    if (dropoffInputRef.current) dropoffInputRef.current.value = SAMPLE_DATA.form.dropoffAddress;
    setPayloads({ broker: null, via: null, response: null });
    setErrors({});
  }

  function validate() {
    const e = {};
    if (!form.brokerTripId.trim())                      e.brokerTripId   = 'Required';
    if (!form.pickupTime)                               e.pickupTime     = 'Required';
    if (!form.pickupAddress.trim() || !pickupCoords)    e.pickupAddress  = 'Select an address from autocomplete';
    if (!form.dropoffAddress.trim() || !dropoffCoords)  e.dropoffAddress = 'Select an address from autocomplete';
    if (!form.riderFirstName.trim())                    e.riderFirstName = 'Required';
    if (!form.riderLastName.trim())                     e.riderLastName  = 'Required';
    if (!form.riderPhone.trim())                        e.riderPhone     = 'Required';
    else if (!isValidPhone(form.riderPhone))            e.riderPhone     = 'Use format +15155559821';
    if (!form.vehicleType)                              e.vehicleType    = 'Required';
    return e;
  }

  async function handleRun() {
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setErrors({});
    setLoading(true);

    const lyftRequest = {
      tapi_trip_id: form.brokerTripId,
      pickup_time:  parseDateTime(form.pickupTime),
      origin: {
        lat: pickupCoords.lat,
        lng: pickupCoords.lng,
        address: {
          address_line1: pickupCoords.addressLine1,
          city:          pickupCoords.city,
          state:         pickupCoords.state,
          zip:           pickupCoords.zip,
        },
      },
      destination: {
        lat: dropoffCoords.lat,
        lng: dropoffCoords.lng,
        address: {
          address_line1: dropoffCoords.addressLine1,
          city:          dropoffCoords.city,
          state:         dropoffCoords.state,
          zip:           dropoffCoords.zip,
        },
      },
      rider: {
        first_name: form.riderFirstName,
        last_name:  form.riderLastName,
        phone:      form.riderPhone,
      },
      trip_source_name: { broker_trip_id: form.brokerTripId },
      appointment_time: parseDateTime(form.appointmentTime),
      demand_additional_info: {
        additional_riders: Array(parseInt(form.additionalRiders, 10) || 0).fill({}),
        vehicle_type: form.vehicleType,
      },
    };

    try {
      const res  = await authFetch('/demo_ingestion', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(lyftRequest),
      });
      const data = await res.json();
      setPayloads({ broker: data.broker_request, via: data.via_payload, response: data.response });
      if (!res.ok) {
        setActiveTab('response');
        showToast('error', parseApiError(data, res.status));
      } else {
        setActiveTab('broker');
        showToast('success', 'Trip Ingestion was successful.');
      }
    } catch (err) {
      const msg = err.name === 'TypeError'
        ? `Network error — ensure you are using the CloudFront URL, not localhost. (${err.message})`
        : err.message;
      showToast('error', msg);
    } finally {
      setLoading(false);
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────

  const TAB_MAP = { broker: 'broker', via: 'via', response: 'response' };
  const activePayload = payloads[activeTab];

  return (
    <section className="dashboard-view">

      <div className="info-banner">
        <Info size={20} className="info-banner-icon" />
        <span>
          This demo simulates receiving a trip request from the Medicaid broker (Access2Care / Lyft TAPI format), translating it to Via API format, and booking it in the TMS. Configure your broker and TMS credentials first.
        </span>
      </div>

      <div className="ingestion-grid">
        {/* Left Column: Form */}
        <div className="table-card" style={{ padding: '24px' }}>
          <div className="form-title-bar">
            <h2 style={{ fontSize: '16px', fontWeight: '700' }}>Simulate Incoming Trip Request</h2>
            <span className="form-subtitle-broker">From Medicaid Broker</span>
          </div>

          <form onSubmit={e => e.preventDefault()} className="form-grid-2col">

            <div className="form-group">
              <label className="form-label">Broker Trip ID</label>
              <input
                type="text"
                className="form-input-text"
                placeholder="e.g. TAPI-2024-08847"
                value={form.brokerTripId}
                onChange={e => setField('brokerTripId', e.target.value)}
                style={errors.brokerTripId ? { borderColor: '#dc2626' } : {}}
              />
              {errors.brokerTripId && <span className="form-group-caption" style={{ color: 'var(--color-danger)' }}>{errors.brokerTripId}</span>}
            </div>

            <div className="form-group">
              <label className="form-label">Pickup Time</label>
              <CustomDateTimePicker
                placeholder="MM-DD-YYYY, HH:MM AM/PM"
                value={form.pickupTime}
                onChange={v => setField('pickupTime', v)}
              />
              {errors.pickupTime && <span className="form-group-caption" style={{ color: 'var(--color-danger)' }}>{errors.pickupTime}</span>}
            </div>

            <div className="form-group full-width">
              <label className="form-label">Pickup Address</label>
              <input
                type="text"
                className="form-input-text"
                placeholder="Enter pickup address (autocomplete)"
                ref={pickupInputRef}
                onChange={e => setField('pickupAddress', e.target.value)}
                style={errors.pickupAddress ? { borderColor: '#dc2626' } : {}}
              />
              {errors.pickupAddress && <span className="form-group-caption" style={{ color: 'var(--color-danger)' }}>{errors.pickupAddress}</span>}
            </div>

            <div className="form-group full-width">
              <label className="form-label">Drop-off Address</label>
              <input
                type="text"
                className="form-input-text"
                placeholder="Enter drop-off address (autocomplete)"
                ref={dropoffInputRef}
                onChange={e => setField('dropoffAddress', e.target.value)}
                style={errors.dropoffAddress ? { borderColor: '#dc2626' } : {}}
              />
              {errors.dropoffAddress && <span className="form-group-caption" style={{ color: 'var(--color-danger)' }}>{errors.dropoffAddress}</span>}
            </div>

            <div className="form-group">
              <label className="form-label">Rider First Name</label>
              <input
                type="text"
                className="form-input-text"
                placeholder="Enter first name"
                value={form.riderFirstName}
                onChange={e => setField('riderFirstName', e.target.value)}
                style={errors.riderFirstName ? { borderColor: '#dc2626' } : {}}
              />
              {errors.riderFirstName && <span className="form-group-caption" style={{ color: 'var(--color-danger)' }}>{errors.riderFirstName}</span>}
            </div>

            <div className="form-group">
              <label className="form-label">Rider Last Name</label>
              <input
                type="text"
                className="form-input-text"
                placeholder="Enter last name"
                value={form.riderLastName}
                onChange={e => setField('riderLastName', e.target.value)}
                style={errors.riderLastName ? { borderColor: '#dc2626' } : {}}
              />
              {errors.riderLastName && <span className="form-group-caption" style={{ color: 'var(--color-danger)' }}>{errors.riderLastName}</span>}
            </div>

            <div className="form-group">
              <label className="form-label">Rider Phone</label>
              <input
                type="text"
                className="form-input-text"
                placeholder="e.g. +15155559821"
                value={form.riderPhone}
                onChange={e => setField('riderPhone', e.target.value)}
                style={errors.riderPhone ? { borderColor: '#dc2626' } : {}}
              />
              {errors.riderPhone && <span className="form-group-caption" style={{ color: 'var(--color-danger)' }}>{errors.riderPhone}</span>}
            </div>

            <div className="form-group">
              <label className="form-label">Vehicle Type</label>
              <select
                className="form-select-box"
                value={form.vehicleType}
                onChange={e => setField('vehicleType', e.target.value)}
                style={errors.vehicleType ? { borderColor: '#dc2626' } : {}}
              >
                <option value="" disabled>Select vehicle type</option>
                <option value="SEDAN">SEDAN</option>
                <option value="WAV">WAV (Wheelchair Accessible)</option>
                <option value="SUV">SUV</option>
              </select>
              {errors.vehicleType && <span className="form-group-caption" style={{ color: 'var(--color-danger)' }}>{errors.vehicleType}</span>}
            </div>

            <div className="form-group">
              <label className="form-label">Additional Riders</label>
              <input
                type="number"
                className="form-input-text"
                placeholder="0"
                min="0"
                value={form.additionalRiders}
                onChange={e => setField('additionalRiders', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Appointment Time</label>
              <CustomDateTimePicker
                placeholder="MM-DD-YYYY, HH:MM AM/PM"
                value={form.appointmentTime}
                onChange={v => setField('appointmentTime', v)}
              />
            </div>

            <div className="form-actions full-width">
              <button
                type="button"
                className="btn-run-ingestion"
                onClick={handleRun}
                disabled={loading}
              >
                {loading
                  ? <span className="btn-spinner" />
                  : <span style={{ fontSize: '10px' }}>▶</span>
                }
                Run Trip Ingestion
              </button>
              <button type="button" className="btn-reset-form" onClick={handleReset}>
                Reset
              </button>
              <button type="button" className="btn-load-sample" onClick={handleLoadSample}>
                Load Sample
              </button>
            </div>

          </form>
        </div>

        {/* Right Column: Payload Preview */}
        <div className="preview-card">
          <div className="preview-header">
            <span className="preview-title">Payload Preview</span>
            <div className="preview-tabs">
              <button
                type="button"
                className={`preview-tab${activeTab === 'broker' ? ' active' : ''}`}
                onClick={() => setActiveTab('broker')}
              >
                Broker Request
              </button>
              <button
                type="button"
                className={`preview-tab${activeTab === 'via' ? ' active' : ''}`}
                onClick={() => setActiveTab('via')}
              >
                → Via Payload
              </button>
              <button
                type="button"
                className={`preview-tab${activeTab === 'response' ? ' active' : ''}`}
                onClick={() => setActiveTab('response')}
              >
                ← Response
              </button>
            </div>
          </div>
          {activePayload
            ? <JsonHighlight data={activePayload} />
            : <div className="preview-body-blank" />
          }
        </div>
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
