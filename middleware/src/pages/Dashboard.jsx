import React, { useState, useEffect, useMemo } from 'react';
import { Search, RefreshCw, CheckSquare, AlertTriangle, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAuthFetch } from '../auth/useAuthFetch';

const PAGE_SIZE = 10;

function JsonPanel({ label, data }) {
  const text = JSON.stringify(data, null, 2);
  return (
    <div>
      <h4 className="drawer-section-title">{label}</h4>
      <div className="json-payload-card">
        <pre className="json-pre">{text}</pre>
      </div>
    </div>
  );
}

function StatTrend({ delta, suffix, zeroLabel }) {
  if (delta === 0) return <span className="stat-trend down">{zeroLabel || 'No change'}</span>;
  const cls  = delta > 0 ? 'stat-trend up' : 'stat-trend negative';
  const arrow = delta > 0 ? '↑' : '↓';
  return <span className={cls}>{arrow} {Math.abs(delta)}{suffix}</span>;
}

export default function Dashboard() {
  const authFetch = useAuthFetch();

  const [trips,  setTrips]  = useState([]);
  const [stats,  setStats]  = useState(null);
  const [status, setStatus] = useState('loading');
  const [errorMsg, setErrorMsg] = useState('');

  const [searchQuery,  setSearchQuery]  = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [page,         setPage]         = useState(0);

  const [selectedTrip,  setSelectedTrip]  = useState(null);
  const [isDrawerOpen,  setIsDrawerOpen]  = useState(false);

  useEffect(() => {
    authFetch('/dashboard')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        if (data.error) throw new Error(data.error);
        setTrips(data.trips  || []);
        setStats(data.stats  || null);
        setStatus('idle');
      })
      .catch(err => {
        setErrorMsg(err.message);
        setStatus('error');
      });
  }, []);

  const filteredTrips = useMemo(() => {
    return trips.filter(trip => {
      if (statusFilter !== 'All' && trip.status !== statusFilter.toLowerCase()) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          (trip.rider          || '').toLowerCase().includes(q) ||
          (trip.broker_trip_id || '').toLowerCase().includes(q) ||
          (trip.internal_id    || '').toLowerCase().includes(q) ||
          (trip.via_trip_id    || '').toLowerCase().includes(q) ||
          (trip.pickup         || '').toLowerCase().includes(q) ||
          (trip.destination    || '').toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [trips, searchQuery, statusFilter]);

  const totalPages  = Math.max(1, Math.ceil(filteredTrips.length / PAGE_SIZE));
  const safePage    = Math.min(page, totalPages - 1);
  const pagedTrips  = filteredTrips.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);
  const showStart   = filteredTrips.length === 0 ? 0 : safePage * PAGE_SIZE + 1;
  const showEnd     = Math.min((safePage + 1) * PAGE_SIZE, filteredTrips.length);

  const handleSearch = (val) => { setSearchQuery(val); setPage(0); };
  const handleFilter = (val) => { setStatusFilter(val); setPage(0); };

  const handleOpenDrawer  = (trip) => { setSelectedTrip(trip); setIsDrawerOpen(true); };
  const handleCloseDrawer = ()     => { setIsDrawerOpen(false); };

  // ── Stat card helpers ──────────────────────────────────────────────────────

  function tripsYesterdayDelta() {
    if (!stats) return 0;
    return stats.trips_today - stats.trips_yesterday;
  }

  function bookedMonthDelta() {
    if (!stats || stats.booked_last_month === 0) return stats?.booked_this_month > 0 ? 100 : 0;
    return Math.round(((stats.booked_this_month - stats.booked_last_month) / stats.booked_last_month) * 100);
  }

  function cancelRate() {
    if (!stats || stats.total_trips === 0) return '0.0';
    return ((stats.canceled_total / stats.total_trips) * 100).toFixed(1);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <>
      <section className="dashboard-view">

        {/* ── Stat cards ────────────────────────────────────────────────── */}
        <div className="stats-grid">

          {/* Trips Today */}
          <div className="stat-card">
            <div className="stat-left">
              <span className="stat-label">Trips Today</span>
              <span className="stat-value">{stats ? stats.trips_today : '—'}</span>
              {stats && (
                <StatTrend
                  delta={tripsYesterdayDelta()}
                  suffix=" from yesterday"
                  zeroLabel="Same as yesterday"
                />
              )}
            </div>
            <div className="stat-icon-wrapper trips">
              <RefreshCw size={24} />
            </div>
          </div>

          {/* Booked (all time non-canceled) */}
          <div className="stat-card">
            <div className="stat-left">
              <span className="stat-label">Booked (All Time)</span>
              <span className="stat-value">{stats ? stats.booked_total : '—'}</span>
              {stats && (
                <StatTrend
                  delta={bookedMonthDelta()}
                  suffix="% this month"
                  zeroLabel="Flat vs last month"
                />
              )}
            </div>
            <div className="stat-icon-wrapper booked">
              <CheckSquare size={24} />
            </div>
          </div>

          {/* Cancellations */}
          <div className="stat-card">
            <div className="stat-left">
              <span className="stat-label">Cancellations</span>
              <span className="stat-value">{stats ? stats.canceled_total : '—'}</span>
              {stats && (
                <span className="stat-trend down">{cancelRate()}% cancel rate</span>
              )}
            </div>
            <div className="stat-icon-wrapper cancellations">
              <AlertTriangle size={24} />
            </div>
          </div>
        </div>

        {/* ── Trips table ───────────────────────────────────────────────── */}
        <div className="table-card">
          <div className="table-header-section">
            <div className="table-title-area">
              <h2>All Trip Exchanges</h2>
              <p>All trips ingested through Health Connector middleware</p>
            </div>

            <div className="table-controls">
              <div className="search-input-wrapper">
                <Search size={18} className="search-icon" />
                <input
                  type="text"
                  placeholder="Search trips..."
                  className="search-input"
                  value={searchQuery}
                  onChange={e => handleSearch(e.target.value)}
                />
              </div>

              <select
                className="filter-select"
                value={statusFilter}
                onChange={e => handleFilter(e.target.value)}
              >
                <option value="All">All Statuses</option>
                <option value="Completed">Completed</option>
                <option value="Booked">Booked</option>
                <option value="Dispatched">Dispatched</option>
                <option value="Canceled">Canceled</option>
              </select>
            </div>
          </div>

          {/* Loading state */}
          {status === 'loading' && (
            <div className="page-loader">
              <div className="page-spinner" />
              <span>Loading trips…</span>
            </div>
          )}

          {/* Error state */}
          {status === 'error' && (
            <div className="page-loader">
              <AlertTriangle size={32} style={{ color: 'var(--color-danger)' }} />
              <span style={{ color: 'var(--color-danger)', textAlign: 'center', maxWidth: 420 }}>
                Failed to load dashboard data: {errorMsg}
              </span>
            </div>
          )}

          {/* Table */}
          {status === 'idle' && (
            <>
              <div className="table-wrapper">
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Broker Trip ID</th>
                      <th>Internal ID</th>
                      <th>Via Trip ID</th>
                      <th>Rider</th>
                      <th>Pickup</th>
                      <th>Destination</th>
                      <th>Status</th>
                      <th>Booked At</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagedTrips.length > 0 ? (
                      pagedTrips.map((trip, i) => (
                        <tr key={trip.internal_id || i}>
                          <td className="mono-cell">{trip.broker_trip_id || '—'}</td>
                          <td className="mono-cell">{trip.internal_id    || '—'}</td>
                          <td className="mono-cell">{trip.via_trip_id    || '—'}</td>
                          <td className="rider-cell">{trip.rider || '—'}</td>
                          <td className="address-cell" title={trip.pickup}>{trip.pickup || '—'}</td>
                          <td className="address-cell" title={trip.destination}>{trip.destination || '—'}</td>
                          <td>
                            <span className={`status-badge-inline ${trip.status}`}>
                              {trip.status}
                            </span>
                          </td>
                          <td>{trip.booked_at || '—'}</td>
                          <td style={{ textAlign: 'right' }}>
                            <button
                              className="btn-details"
                              onClick={() => handleOpenDrawer(trip)}
                            >
                              Details
                            </button>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="9" style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-secondary)' }}>
                          {trips.length === 0
                            ? 'No trips found in the database.'
                            : 'No trips match the current filters.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {filteredTrips.length > 0 && (
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '12px 24px', borderTop: '1px solid var(--border-card)',
                  fontSize: '13px', color: 'var(--text-secondary)',
                }}>
                  <span>Showing {showStart}–{showEnd} of {filteredTrips.length} trips</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button
                      className="btn-details"
                      onClick={() => setPage(p => Math.max(0, p - 1))}
                      disabled={safePage === 0}
                      style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                    >
                      <ChevronLeft size={14} /> Previous
                    </button>
                    <span style={{ padding: '0 8px' }}>Page {safePage + 1} of {totalPages}</span>
                    <button
                      className="btn-details"
                      onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                      disabled={safePage >= totalPages - 1}
                      style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                    >
                      Next <ChevronRight size={14} />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {/* ── Details drawer ────────────────────────────────────────────────── */}
      <div
        className={`drawer-backdrop ${isDrawerOpen ? 'open' : ''}`}
        onClick={handleCloseDrawer}
      />
      <div className={`drawer ${isDrawerOpen ? 'open' : ''}`}>
        <div className="drawer-header">
          <h3>Trip Details</h3>
          <button className="btn-close" onClick={handleCloseDrawer}>
            <X size={20} />
          </button>
        </div>

        {selectedTrip && (
          <div className="drawer-content">
            <div>
              <h4 className="drawer-section-title">Overview</h4>
              <div className="details-grid">
                <div className="detail-item">
                  <span className="detail-label">Rider</span>
                  <span className="detail-value">{selectedTrip.rider || '—'}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Status</span>
                  <span className="detail-value">{(selectedTrip.status || '').toUpperCase()}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Broker Trip ID</span>
                  <span className="detail-value">{selectedTrip.broker_trip_id || '—'}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Booked At</span>
                  <span className="detail-value">{selectedTrip.booked_at || '—'}</span>
                </div>
              </div>
            </div>
            {selectedTrip.payload?.lyft && (
              <JsonPanel label="Lyft Request Payload" data={selectedTrip.payload.lyft} />
            )}
            {selectedTrip.payload?.via && (
              <JsonPanel label="Via Response Payload" data={selectedTrip.payload.via} />
            )}
          </div>
        )}
      </div>
    </>
  );
}
