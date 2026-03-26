"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Session, User } from "@supabase/supabase-js";

import { api, type AccountProfile } from "@/lib/api";
import { extractAccountProfileFromUser } from "@/lib/account";
import { getSupabaseBrowserClient, hasSupabaseBrowserConfig } from "@/lib/supabase-browser";

interface AuthContextValue {
  configured: boolean;
  loading: boolean;
  session: Session | null;
  user: User | null;
  profile: AccountProfile | null;
  profileLoading: boolean;
  refreshProfile: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  configured: false,
  loading: true,
  session: null,
  user: null,
  profile: null,
  profileLoading: false,
  refreshProfile: async () => {},
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
  const [profile, setProfile] = useState<AccountProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  const loadProfileForSession = async (currentSession: Session | null) => {
    if (!configured) {
      setProfile(null);
      return;
    }

    if (!currentSession?.user) {
      setProfile(null);
      return;
    }

    setProfileLoading(true);
    try {
      const nextProfile = await api.getMyAccountProfile();
      setProfile(nextProfile);
    } catch {
      setProfile(extractAccountProfileFromUser(currentSession.user) as AccountProfile | null);
    } finally {
      setProfileLoading(false);
    }
  };

  const refreshProfile = async () => {
    const client = getSupabaseBrowserClient();
    if (!client) {
      setProfile(null);
      return;
    }
    const {
      data: { session: currentSession },
    } = await client.auth.getSession();
    await loadProfileForSession(currentSession);
  };

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
        if (data.session?.user) {
          void loadProfileForSession(data.session);
        } else {
          setProfile(null);
        }
      })
      .catch(() => {
        if (!active) return;
        setSession(null);
        setUser(null);
        setProfile(null);
        setLoading(false);
      });

    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((_event, nextSession) => {
      if (!active) return;
      setSession(nextSession);
      setUser(nextSession?.user ?? null);
      setLoading(false);
      if (nextSession?.user) {
        void loadProfileForSession(nextSession);
      } else {
        setProfile(null);
      }
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
    setProfile(null);
  };

  return (
    <AuthContext.Provider
      value={{
        configured,
        loading,
        session,
        user,
        profile,
        profileLoading,
        refreshProfile,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
