"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { setAuthTokenProvider } from "@/features/seo/track";
import { ensureApiAuth, getApiToken, setApiToken } from "./apiAuth";
import { isSupabaseConfigured, loadSupabase } from "./supabaseClient";
import { SignInSheet } from "./SignInSheet";

export type AuthStatus = "loading" | "signed-out" | "signed-in";

export type AuthState = {
  status: AuthStatus;
  email: string | null;
  /** False when NEXT_PUBLIC_SUPABASE_URL / _ANON_KEY are not set (mock mode, local dev). */
  configured: boolean;
  openSignIn: () => void;
  signOut: () => Promise<void>;
};

const SIGNED_OUT: AuthState = {
  status: "signed-out",
  email: null,
  configured: false,
  openSignIn: () => {},
  signOut: async () => {},
};

const AuthContext = createContext<AuthState>(SIGNED_OUT);

export function useAuth(): AuthState {
  return useContext(AuthContext);
}

/**
 * Tracks the Supabase session, keeps the API token in sync (`apiAuth`), and hosts the email OTP
 * sheet. Without Supabase configuration it stays signed out and the sheet explains why.
 * Mounted once, in the root layout, so `/feedback/*` and `/events` carry the user on every screen.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const configured = isSupabaseConfigured();
  // Without Supabase there is nothing to wait for: signed out from the first render.
  const [status, setStatus] = useState<AuthStatus>(configured ? "loading" : "signed-out");
  const [email, setEmail] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  useEffect(() => {
    ensureApiAuth();
    // Beta events carry the user too: the API reads the id from the same bearer token.
    setAuthTokenProvider(getApiToken);
    let active = true;
    let unsubscribe = () => {};
    void loadSupabase().then((supabase) => {
      if (!active) return;
      if (!supabase) {
        setApiToken(null);
        return;
      }
      const apply = (
        session: { access_token: string; user?: { email?: string | null } } | null,
      ) => {
        if (!active) return;
        setApiToken(session?.access_token ?? null);
        setEmail(session?.user?.email ?? null);
        setStatus(session ? "signed-in" : "signed-out");
      };
      void supabase.auth.getSession().then(({ data }) => apply(data.session));
      const { data } = supabase.auth.onAuthStateChange((_event, session) => apply(session));
      unsubscribe = () => data.subscription.unsubscribe();
    });
    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  const openSignIn = useCallback(() => setSheetOpen(true), []);
  const signOut = useCallback(async () => {
    const supabase = await loadSupabase();
    setApiToken(null);
    if (supabase) await supabase.auth.signOut();
    setEmail(null);
    setStatus("signed-out");
  }, []);

  const value = useMemo<AuthState>(
    () => ({ status, email, configured, openSignIn, signOut }),
    [status, email, configured, openSignIn, signOut],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
      <SignInSheet
        open={sheetOpen}
        configured={configured}
        onClose={() => setSheetOpen(false)}
        onSignedIn={() => setSheetOpen(false)}
      />
    </AuthContext.Provider>
  );
}
