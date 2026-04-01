"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { Session, User } from "@supabase/supabase-js";

import { AUTH_REQUIRED_EVENT, api, isAuthRequiredError, type AccountProfile, type AuthRequiredEventDetail } from "@/lib/api";
import { extractAccountProfileFromUser } from "@/lib/account";
import { reportSessionRecoveryAttempt, reportSessionRecoveryFailed } from "@/lib/route-observability";
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
  signOutEverywhere: () => Promise<void>;
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
  signOutEverywhere: async () => {},
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
  const authRecoveryRef = useRef<Promise<void> | null>(null);

  const clearAuthState = () => {
    setSession(null);
    setUser(null);
    setProfile(null);
    setProfileLoading(false);
    setLoading(false);
  };

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
    } catch (error) {
      if (isAuthRequiredError(error)) {
        setProfile(null);
        return;
      }
      setProfile(extractAccountProfileFromUser(currentSession.user) as AccountProfile | null);
    } finally {
      setProfileLoading(false);
    }
  };

  const reconcileSession = async () => {
    const client = getSupabaseBrowserClient();
    const currentRoute = typeof window !== "undefined" ? window.location.pathname : "/unknown";
    if (!client) {
      reportSessionRecoveryFailed(currentRoute, "Supabase 브라우저 클라이언트를 찾지 못했습니다.");
      clearAuthState();
      return;
    }

    if (authRecoveryRef.current) {
      await authRecoveryRef.current;
      return;
    }

    authRecoveryRef.current = (async () => {
      reportSessionRecoveryAttempt(currentRoute);
      try {
        const {
          data: { session: currentSession },
          error: sessionError,
        } = await client.auth.getSession();

        if (sessionError || !currentSession?.refresh_token) {
          reportSessionRecoveryFailed(currentRoute, sessionError?.message || "refresh_token이 없습니다.");
          clearAuthState();
          return;
        }

        const {
          data: refreshedData,
          error: refreshError,
        } = await client.auth.refreshSession();

        if (refreshError || !refreshedData.session?.user) {
          reportSessionRecoveryFailed(currentRoute, refreshError?.message || "세션 갱신에 실패했습니다.");
          clearAuthState();
          return;
        }

        setSession(refreshedData.session);
        setUser(refreshedData.session.user);
        setLoading(false);
        await loadProfileForSession(refreshedData.session);
      } catch (error) {
        reportSessionRecoveryFailed(
          currentRoute,
          error instanceof Error ? error.message : "세션 재검증 중 예외가 발생했습니다.",
        );
        clearAuthState();
      } finally {
        authRecoveryRef.current = null;
      }
    })();

    await authRecoveryRef.current;
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

  useEffect(() => {
    const handleAuthRequired = (event: Event) => {
      const customEvent = event as CustomEvent<AuthRequiredEventDetail>;
      if (customEvent.detail?.status === 401 || customEvent.detail?.errorCode === "SP-6014") {
        void reconcileSession();
      }
    };

    window.addEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired as EventListener);
    return () => {
      window.removeEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired as EventListener);
    };
  }, [configured]);

  const signOut = async () => {
    const client = getSupabaseBrowserClient();
    if (!client) {
      return;
    }
    await client.auth.signOut({ scope: "local" });
    clearAuthState();
  };

  const signOutEverywhere = async () => {
    const client = getSupabaseBrowserClient();
    if (!client) {
      return;
    }
    await client.auth.signOut({ scope: "global" });
    clearAuthState();
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
        signOutEverywhere,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
