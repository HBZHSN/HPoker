import React, { useState, useEffect } from 'react';
import LoginModal from './components/LoginModal';
import {
  getStoredToken,
  getStoredUser,
  setStoredAuth,
  clearAuthStorage,
  clearLegacyAuthStorage,
} from './utils/authStorage';

const AuthenticatedApp = React.lazy(() => import('./AuthenticatedApp'));

export default function App() {
  const [token, setToken] = useState(getStoredToken);
  const [currentUser, setCurrentUser] = useState(getStoredUser);
  const [isCheckingAuth, setIsCheckingAuth] = useState(() => Boolean(getStoredToken()));

  // Verify stored token on startup
  useEffect(() => {
    if (!token) {
      setIsCheckingAuth(false);
      return;
    }

    let isMounted = true;
    fetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (res.status === 401) {
          throw new Error('Token expired');
        }
        if (!res.ok) {
          return null;
        }
        return res.json();
      })
      .then((data) => {
        if (!isMounted) return;
        if (data && data.user) {
          setCurrentUser(data.user);
          setStoredAuth(data.user, token, true);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        if (err.message === 'Token expired') {
          setToken('');
          setCurrentUser(null);
          clearAuthStorage();
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsCheckingAuth(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [token]);

  const handleLoginSuccess = (user, authToken, remember = true) => {
    setCurrentUser(user);
    setToken(authToken);
    setStoredAuth(user, authToken, remember);
  };

  const handleLogout = () => {
    clearAuthStorage(currentUser?.user_id);
    setToken('');
    setCurrentUser(null);
  };

  const handleUpdateUser = (updatedUser) => {
    setCurrentUser(updatedUser);
    if (token) {
      setStoredAuth(updatedUser, token, true);
    }
  };

  // While validating stored credentials on initial load, show minimal neutral spinner
  if (isCheckingAuth) {
    return (
      <div className="w-full h-full min-h-screen bg-[#080b11] flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-slate-700 border-t-amber-400 animate-spin" />
      </div>
    );
  }

  // If not authenticated, render pure neutral login modal (no poker components or network calls)
  if (!token || !currentUser) {
    return (
      <div className="w-full h-full min-h-screen bg-[#080b11] text-slate-100 flex flex-col font-sans">
        <LoginModal onLoginSuccess={handleLoginSuccess} />
      </div>
    );
  }

  // Authenticated: dynamically load and mount the full poker app bundle
  return (
    <React.Suspense
      fallback={
        <div className="w-full h-full min-h-screen bg-[#080b11] flex items-center justify-center">
          <div className="w-8 h-8 rounded-full border-2 border-slate-700 border-t-amber-400 animate-spin" />
        </div>
      }
    >
      <AuthenticatedApp
        currentUser={currentUser}
        token={token}
        onLogout={handleLogout}
        onUpdateUser={handleUpdateUser}
      />
    </React.Suspense>
  );
}
