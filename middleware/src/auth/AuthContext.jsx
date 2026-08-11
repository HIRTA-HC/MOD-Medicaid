import React, { createContext, useContext, useState, useEffect } from 'react';

const REGION      = import.meta.env.VITE_AWS_REGION           || 'ap-south-1';
const CLIENT_ID   = import.meta.env.VITE_USER_POOL_CLIENT_ID  || '';
const COGNITO_URL = `https://cognito-idp.${REGION}.amazonaws.com/`;
const SESSION_KEY = 'hc_auth_user';

export const AuthContext = createContext(null);

async function cognitoPost(target, body) {
  const res = await fetch(COGNITO_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': `AWSCognitoIdentityProviderService.${target}`,
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || data.__type || 'Authentication failed');
  return data;
}

export function AuthProvider({ children }) {
  const [user, setUser]        = useState(null);
  const [initialized, setInit] = useState(false);

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(SESSION_KEY);
      if (stored) setUser(JSON.parse(stored));
    } catch {
      sessionStorage.removeItem(SESSION_KEY);
    } finally {
      setInit(true);
    }
  }, []);

  async function login(email, password) {
    try {
      const data = await cognitoPost('InitiateAuth', {
        AuthFlow: 'USER_PASSWORD_AUTH',
        AuthParameters: { USERNAME: email, PASSWORD: password },
        ClientId: CLIENT_ID,
      });
      if (data.ChallengeName === 'NEW_PASSWORD_REQUIRED') {
        return { challenge: 'NEW_PASSWORD_REQUIRED', session: data.Session };
      }
      const u = {
        email,
        idToken:      data.AuthenticationResult.IdToken,
        accessToken:  data.AuthenticationResult.AccessToken,
        refreshToken: data.AuthenticationResult.RefreshToken,
      };
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(u));
      setUser(u);
      return { ok: true };
    } catch (err) {
      return { error: err.message };
    }
  }

  async function forceChangePassword(email, newPassword, session) {
    try {
      const data = await cognitoPost('RespondToAuthChallenge', {
        ChallengeName: 'NEW_PASSWORD_REQUIRED',
        ClientId: CLIENT_ID,
        ChallengeResponses: { USERNAME: email, NEW_PASSWORD: newPassword },
        Session: session,
      });
      const u = {
        email,
        idToken:      data.AuthenticationResult.IdToken,
        accessToken:  data.AuthenticationResult.AccessToken,
        refreshToken: data.AuthenticationResult.RefreshToken,
      };
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(u));
      setUser(u);
      return { ok: true };
    } catch (err) {
      return { error: err.message };
    }
  }

  function logout() {
    sessionStorage.removeItem(SESSION_KEY);
    setUser(null);
  }

  async function refreshTokens() {
    if (!user?.refreshToken) { logout(); return null; }
    try {
      const data = await cognitoPost('InitiateAuth', {
        AuthFlow: 'REFRESH_TOKEN_AUTH',
        AuthParameters: { REFRESH_TOKEN: user.refreshToken },
        ClientId: CLIENT_ID,
      });
      const u = {
        ...user,
        idToken:     data.AuthenticationResult.IdToken,
        accessToken: data.AuthenticationResult.AccessToken,
      };
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(u));
      setUser(u);
      return u;
    } catch {
      logout();
      return null;
    }
  }

  return (
    <AuthContext.Provider value={{ user, initialized, login, logout, forceChangePassword, refreshTokens }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
