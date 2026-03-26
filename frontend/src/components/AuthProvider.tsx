"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Session, User } from "@supabase/supabase-js";

import { getSupabaseBrowserClient, hasSupabaseBrowserConfig } from "@/lib/supabase-browser";

interface AuthContextValue {
  configured: boolean;
  loading: boolean;
  session: Session | null;
  user: User | null;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  configured: false,
  loading: true,
  session: null,
  user: null,
  signOut: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const configured = hasSupabaseBrowserConfig();
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const client = getSupabaseBrowserClient();
    if (!client) {
      setLoading(false);
      return;
    }

    let active = true;

    client.auth
      .getSession()
      .then(({ data }) => {
        if (!active) return;
        setSession(data.session);
        setUser(data.session?.user ?? null);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setSession(null);
        setUser(null);
        setLoading(false);
      });

    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((_event, nextSession) => {
      if (!active) return;
      setSession(nextSession);
      setUser(nextSession?.user ?? null);
      setLoading(false);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  const signOut = async () => {
    const client = getSupabaseBrowserClient();
    if (!client) {
      return;
    }
    await client.auth.signOut();
  };

  return (
    <AuthContext.Provider
      value={{
        configured,
        loading,
        session,
        user,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
