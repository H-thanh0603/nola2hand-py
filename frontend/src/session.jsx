import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { store } from './api';

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const [user, setUserState] = useState(() => store.user);
  const [token, setTokenState] = useState(() => store.token);

  const setUser = useCallback((next) => {
    store.user = next;
    setUserState(next);
  }, []);

  const signIn = useCallback((nextToken, nextUser) => {
    store.token = nextToken;
    store.user = nextUser;
    setTokenState(nextToken);
    setUserState(nextUser);
  }, []);

  const clearSession = useCallback(() => {
    store.token = null;
    store.user = null;
    setTokenState(null);
    setUserState(null);
    window._banks = [];
  }, []);

  const hasRole = useCallback(
    (...roles) => (user?.roles || []).some((role) => roles.includes(role)),
    [user],
  );

  const value = useMemo(
    () => ({
      user,
      token,
      setUser,
      signIn,
      clearSession,
      hasRole,
      loggedIn: Boolean(token),
    }),
    [user, token, setUser, signIn, clearSession, hasRole],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export const useSession = () => useContext(SessionContext);
