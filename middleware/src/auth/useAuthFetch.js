import { useContext, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from './AuthContext';

export function useAuthFetch() {
  const { user, refreshTokens } = useContext(AuthContext);
  const navigate = useNavigate();

  return useCallback(async (url, options = {}) => {
    const withAuth = (token) => fetch(url, {
      ...options,
      headers: { ...options.headers, Authorization: `Bearer ${token}` },
    });

    let res = await withAuth(user?.idToken);
    if (res.status === 401) {
      const refreshed = await refreshTokens();
      if (!refreshed) {
        navigate('/login', { replace: true });
        throw new Error('Session expired. Please log in again.');
      }
      res = await withAuth(refreshed.idToken);
    }
    return res;
  }, [user, refreshTokens, navigate]);
}
