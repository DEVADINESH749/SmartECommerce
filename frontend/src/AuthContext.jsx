import { createContext, useContext, useEffect, useRef, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { apiRequest } from "./api";

const AuthContext = createContext(null);
const SESSION_KEY = "smart-ecommerce-session";

function readSession() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null");
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const {
    isAuthenticated: auth0Authenticated,
    isLoading: auth0Loading,
    getIdTokenClaims,
    loginWithRedirect,
    logout: auth0Logout
  } = useAuth0();
  const [session, setSession] = useState(readSession);
  const [exchangeLoading, setExchangeLoading] = useState(false);
  const [auth0Error, setAuth0Error] = useState("");
  const exchangePromise = useRef(null);

  const storeSession = (data, authProvider = "local") => {
    const nextSession = {
      accessToken: data.access_token,
      user: {
        id: data.user_id,
        name: data.name,
        email: data.email,
        role: data.role,
        authProvider
      }
    };
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
    setSession(nextSession);
    return nextSession;
  };

  useEffect(() => {
    if (!auth0Authenticated || auth0Loading) return undefined;
    let active = true;

    async function exchangeIdentity() {
      setExchangeLoading(true);
      setAuth0Error("");
      try {
        if (!exchangePromise.current) {
          exchangePromise.current = getIdTokenClaims().then((idTokenClaims) => apiRequest("/auth0-exchange", {
            method: "POST",
            body: { id_token: idTokenClaims?.__raw || "" }
          }));
        }
        const data = await exchangePromise.current;
        if (active) storeSession(data, "Auth0");
      } catch (error) {
        exchangePromise.current = null;
        if (active) setAuth0Error(error.message || "Social sign-in could not be completed.");
      } finally {
        if (active) setExchangeLoading(false);
      }
    }

    exchangeIdentity();
    return () => { active = false; };
  }, [auth0Authenticated, auth0Loading, getIdTokenClaims]);

  const signIn = async (email, password) => {
    const data = await apiRequest("/login", {
      method: "POST",
      body: { email, password }
    });
    setAuth0Error("");
    return storeSession(data);
  };

  const register = async ({ name, email, password }) => {
    await apiRequest("/register", {
      method: "POST",
      body: { name, email, password }
    });
    return signIn(email, password);
  };

  const signInWithProvider = (connection) => loginWithRedirect({
    authorizationParams: {
      connection,
      scope: "openid profile email"
    }
  });

  const signOut = () => {
    sessionStorage.removeItem(SESSION_KEY);
    setSession(null);
    if (auth0Authenticated) {
      auth0Logout({ logoutParams: { returnTo: window.location.origin } });
    }
  };

  return (
    <AuthContext.Provider value={{
      accessToken: session?.accessToken || "",
      user: session?.user || null,
      isAuthenticated: Boolean(session?.accessToken),
      isLoading: auth0Loading || exchangeLoading,
      auth0Error,
      signIn,
      register,
      signInWithProvider,
      signOut
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useSession() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useSession must be used within AuthProvider");
  return context;
}
