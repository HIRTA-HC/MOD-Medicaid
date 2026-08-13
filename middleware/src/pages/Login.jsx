import React, { useState, useContext } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../auth/AuthContext';

export default function Login() {
  const { login, forceChangePassword } = useContext(AuthContext);
  const navigate = useNavigate();

  const [step, setStep]                   = useState('login'); // 'login' | 'change_password'
  const [email, setEmail]                 = useState('');
  const [password, setPassword]           = useState('');
  const [newPassword, setNewPassword]     = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword]   = useState(false);
  const [showNew, setShowNew]             = useState(false);
  const [session, setSession]             = useState(null);
  const [error, setError]                 = useState('');
  const [loading, setLoading]             = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    if (!email || !password) { setError('Please enter your email and password.'); return; }
    setError('');
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (result.ok) {
      navigate('/');
    } else if (result.challenge === 'NEW_PASSWORD_REQUIRED') {
      setSession(result.session);
      setStep('change_password');
    } else {
      setError(result.error || 'Login failed. Please check your credentials.');
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    if (!newPassword) { setError('Please enter a new password.'); return; }
    if (newPassword !== confirmPassword) { setError('Passwords do not match.'); return; }
    setError('');
    setLoading(true);
    const result = await forceChangePassword(email, newPassword, session);
    setLoading(false);
    if (result.ok) {
      navigate('/');
    } else {
      setError(result.error || 'Password change failed. Please try again.');
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">

        {/* Left — Brand panel */}
        <div className="login-brand">
          <div className="login-brand-tag">Transit Agency Demo</div>
          <h1 className="login-brand-title">Health Connector</h1>
          <p className="login-brand-subtitle">Medicaid Ride Middleware</p>
          <p className="login-brand-desc">
            Secure middleware for coordinating Medicaid non-emergency medical
            transportation across broker and TMS platforms.
          </p>
        </div>

        {/* Right — Form panel */}
        <div className="login-form-panel">
          {step === 'login' ? (
            <>
              <div className="login-form-header">
                <h2>Login to your Account</h2>
                <p>Enter your credentials to continue</p>
              </div>

              <form className="login-form" onSubmit={handleLogin} noValidate>
                <div className="form-group">
                  <label className="form-label">Email</label>
                  <input
                    type="email"
                    className="form-input-text"
                    placeholder="Email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    autoComplete="username"
                    autoFocus
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Password</label>
                  <div className="login-password-wrapper">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      className="form-input-text"
                      placeholder="Password"
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      className="login-password-toggle"
                      onClick={() => setShowPassword(v => !v)}
                      tabIndex={-1}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>

                {error && <p className="login-error">{error}</p>}

                <button type="submit" className="login-submit-btn" disabled={loading}>
                  {loading && <span className="btn-spinner" />}
                  {loading ? 'Logging in...' : 'Login'}
                </button>
              </form>
            </>
          ) : (
            <>
              <div className="login-form-header">
                <h2>Set New Password</h2>
                <p>Your account requires a password change before you can continue.</p>
              </div>

              <form className="login-form" onSubmit={handleChangePassword} noValidate>
                <div className="form-group">
                  <label className="form-label">New Password</label>
                  <div className="login-password-wrapper">
                    <input
                      type={showNew ? 'text' : 'password'}
                      className="form-input-text"
                      placeholder="New password"
                      value={newPassword}
                      onChange={e => setNewPassword(e.target.value)}
                      autoComplete="new-password"
                      autoFocus
                    />
                    <button
                      type="button"
                      className="login-password-toggle"
                      onClick={() => setShowNew(v => !v)}
                      tabIndex={-1}
                      aria-label={showNew ? 'Hide password' : 'Show password'}
                    >
                      {showNew ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Confirm Password</label>
                  <input
                    type="password"
                    className="form-input-text"
                    placeholder="Confirm new password"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                </div>

                {error && <p className="login-error">{error}</p>}

                <button type="submit" className="login-submit-btn" disabled={loading}>
                  {loading && <span className="btn-spinner" />}
                  {loading ? 'Updating...' : 'Set Password & Continue'}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
