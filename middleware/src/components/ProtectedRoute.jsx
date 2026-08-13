import React, { useContext } from 'react';
import { Navigate } from 'react-router-dom';
import { AuthContext } from '../auth/AuthContext';

export default function ProtectedRoute({ children }) {
  const { user, initialized } = useContext(AuthContext);
  if (!initialized) return null;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
