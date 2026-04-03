"use client";

import { useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";

import { api, isAuthRequiredError } from "@/lib/api";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import {
  reportErrorOnlyScreen,
  reportHydrationRefetchSuccess,
  reportInitialSsrSuccess,
  reportPanelDegraded,
} from "@/lib/route-observability";
import type { WatchlistItem } from "@/lib/types";

const ROUTE_KEY = "/watchlist";
const WATCHLIST_TIMEOUT_MS = 12_000;

interface UseWatchlistWorkspaceOptions {
  hasSession: boolean;
  authLoading: boolean;
  items: WatchlistItem[];
  loading: boolean;
  loadError: string | null;
  setItems: Dispatch<SetStateAction<WatchlistItem[]>>;
  setLoading: Dispatch<SetStateAction<boolean>>;
  setLoadError: Dispatch<SetStateAction<string | null>>;
  toast: (message: string, tone?: "info" | "success" | "error") => void;
}

export function useWatchlistWorkspace({
  hasSession,
  authLoading,
  items,
  loading,
  loadError,
  setItems,
  setLoading,
  setLoadError,
  toast,
}: UseWatchlistWorkspaceOptions) {
  const reportedPreviewRef = useRef(false);
  const reportedErrorOnlyRef = useRef(false);

  const load = async (showFailureToast = false) => {
    if (!hasSession) {
      setItems([]);
      setLoadError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setItems(await api.getWatchlist({ timeoutMs: WATCHLIST_TIMEOUT_MS }));
      setLoadError(null);
      reportHydrationRefetchSuccess(ROUTE_KEY, "watchlist_items");
    } catch (error) {
      console.error(error);
      if (!isAuthRequiredError(error)) {
        const message = getUserFacingErrorMessage(error, "관심종목 목록을 다시 불러오지 못했습니다.");
        setLoadError(message);
        reportPanelDegraded(ROUTE_KEY, "watchlist_items", message);
        if (showFailureToast) {
          toast(message, "error");
        }
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (authLoading) {
      return;
    }
    void load();
  }, [authLoading, hasSession]);

  useEffect(() => {
    if (!authLoading && !hasSession && !reportedPreviewRef.current) {
      reportInitialSsrSuccess(ROUTE_KEY);
      reportedPreviewRef.current = true;
    }
    if (hasSession) {
      reportedPreviewRef.current = false;
    }
  }, [authLoading, hasSession]);

  useEffect(() => {
    if (!reportedErrorOnlyRef.current && !loading && hasSession && !!loadError && items.length === 0) {
      reportErrorOnlyScreen(ROUTE_KEY, loadError);
      reportedErrorOnlyRef.current = true;
    }
    if (loading || items.length > 0 || !loadError) {
      reportedErrorOnlyRef.current = false;
    }
  }, [hasSession, items.length, loadError, loading]);

  return {
    load,
  };
}
