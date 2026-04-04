"use client";

import { useEffect, useRef, useState } from "react";

import { api, isAuthRequiredError, type WatchlistTrackingDetailResponse } from "@/lib/api";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import {
  reportErrorOnlyScreen,
  reportHydrationRefetchSuccess,
  reportInitialSsrSuccess,
  reportPanelDegraded,
} from "@/lib/route-observability";

const ROUTE_KEY = "/watchlist/[ticker]";
const WATCHLIST_TRACKING_TIMEOUT_MS = 12_000;

interface UseWatchlistTrackingDetailOptions {
  ticker: string;
  countryCode?: string;
  hasSession: boolean;
  authLoading: boolean;
  toast: (message: string, tone?: "info" | "success" | "error") => void;
}

export function useWatchlistTrackingDetail({
  ticker,
  countryCode = "KR",
  hasSession,
  authLoading,
  toast,
}: UseWatchlistTrackingDetailOptions) {
  const [detail, setDetail] = useState<WatchlistTrackingDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const reportedInitialRef = useRef(false);
  const reportedErrorOnlyRef = useRef(false);

  const load = async (showFailureToast = false) => {
    if (!hasSession) {
      setDetail(null);
      setLoadError(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const payload = await api.getWatchlistTrackingDetail(ticker, countryCode, {
        timeoutMs: WATCHLIST_TRACKING_TIMEOUT_MS,
      });
      setDetail(payload);
      setLoadError(null);
      reportHydrationRefetchSuccess(ROUTE_KEY, "watchlist_tracking_detail");
    } catch (error) {
      if (!isAuthRequiredError(error)) {
        const message = getUserFacingErrorMessage(
          error,
          "심화 추적 정보를 아직 불러오지 못했습니다.",
        );
        setLoadError(message);
        reportPanelDegraded(ROUTE_KEY, "watchlist_tracking_detail", message);
        if (showFailureToast) {
          toast(message, "error");
        }
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!reportedInitialRef.current) {
      reportInitialSsrSuccess(ROUTE_KEY, ticker);
      reportedInitialRef.current = true;
    }
  }, [ticker]);

  useEffect(() => {
    if (authLoading) {
      return;
    }
    void load();
  }, [authLoading, hasSession, ticker, countryCode]);

  useEffect(() => {
    if (!reportedErrorOnlyRef.current && !loading && hasSession && !!loadError && !detail) {
      reportErrorOnlyScreen(ROUTE_KEY, loadError);
      reportedErrorOnlyRef.current = true;
    }
    if (loading || detail || !loadError) {
      reportedErrorOnlyRef.current = false;
    }
  }, [detail, hasSession, loadError, loading]);

  const toggleTracking = async (enabled: boolean) => {
    try {
      if (enabled) {
        await api.enableWatchlistTracking(ticker, countryCode);
        toast("심화 추적을 시작했습니다.", "success");
      } else {
        await api.disableWatchlistTracking(ticker, countryCode);
        toast("심화 추적을 중지했습니다.", "success");
      }
      await load(false);
    } catch (error) {
      console.error(error);
      toast(
        enabled ? "심화 추적 시작에 실패했습니다." : "심화 추적 중지에 실패했습니다.",
        "error",
      );
    }
  };

  return {
    detail,
    loading,
    loadError,
    reload: load,
    toggleTracking,
  };
}
