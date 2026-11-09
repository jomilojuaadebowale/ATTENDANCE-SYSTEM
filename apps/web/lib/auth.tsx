"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createApi, type Api } from "@/lib/api";
import { config } from "@/lib/config";
import type { Me } from "@/types/api";

type Status = "loading" | "signed_out" | "signed_in" | "not_provisioned";

interface AuthContextValue {
  status: Status;
  me: Me | null;
  error: string | null;
  api: Api;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const DEV_KEY = "attendance.dev_email";

/** Firebase is loaded only when needed, so dev mode and tests do not pull it in. */
async function firebaseAuth() {
  const [{ initializeApp, getApps }, authMod] = await Promise.all([import("@firebase/app"), import("@firebase/auth")]);
  const app = getApps()[0] ?? initializeApp(config.firebase);
  return { auth: authMod.getAuth(app), mod: authMod };
}

async function getToken(): Promise<string | null> {
  if (config.authMode === "dev") {
    const email = sessionStorage.getItem(DEV_KEY);
    return email ? `dev:${email}` : null;
  }
  const { auth } = await firebaseAuth();
  return auth.currentUser ? auth.currentUser.getIdToken() : null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const api = useMemo(() => createApi(getToken), []);
  const started = useRef(false);

  const loadMe = useCallback(async () => {
    try {
      const profile = await api.request<Me>("/auth/me");
      setMe(profile);
      setStatus("signed_in");
      setError(null);
    } catch (e) {
      const err = e as { code?: string; message?: string };
      setMe(null);
      setError(err.message ?? "Could not load your profile.");
      setStatus(err.code === "account_not_provisioned" ? "not_provisioned" : "signed_out");
    }
  }, [api]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (config.authMode === "dev") {
      // Reading browser-only storage after mount is synchronising with an external system.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (sessionStorage.getItem(DEV_KEY)) void loadMe();
      else setStatus("signed_out");
      return;
    }
    void firebaseAuth().then(({ auth, mod }) =>
      mod.onAuthStateChanged(auth, (user) => {
        if (user) void loadMe();
        else {
          setMe(null);
          setStatus("signed_out");
        }
      }),
    );
  }, [loadMe]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      setError(null);
      if (config.authMode === "dev") {
        sessionStorage.setItem(DEV_KEY, email.trim().toLowerCase());
        await loadMe();
        return;
      }
      const { auth, mod } = await firebaseAuth();
      await mod.signInWithEmailAndPassword(auth, email.trim(), password);
      await loadMe();
    },
    [loadMe],
  );

  const signOut = useCallback(async () => {
    if (config.authMode === "dev") sessionStorage.removeItem(DEV_KEY);
    else {
      const { auth, mod } = await firebaseAuth();
      await mod.signOut(auth);
    }
    setMe(null);
    setStatus("signed_out");
  }, []);

  const value = useMemo(() => ({ status, me, error, api, signIn, signOut }), [status, me, error, api, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
