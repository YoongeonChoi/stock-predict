"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { MarketSessionsResponse, ResearchArchiveStatus, SystemDiagnostics } from "@/lib/api";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import {
  reportErrorOnlyScreen,
  reportHydrationRefetchSuccess,
  reportInitialSsrSuccess,
  reportPanelDegraded,
} from "@/lib/route-observability";

const ROUTE_KEY = "/settings";

interface UseSettingsPageLoaderOptions {
  timeoutMs: number;
}

export function useSettingsPageLoader({ timeoutMs }: UseSettingsPageLoaderOptions) {
  const [diagnostics, setDiagnostics] = useState<SystemDiagnostics | null>(null);
  const [marketSessions, setMarketSessions] = useState<MarketSessionsResponse | null>(null);
  const [researchStatus, setResearchStatus] = useState<ResearchArchiveStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [diagnosticsError, setDiagnosticsError] = useState<string | null>(null);
  const [marketSessionsError, setMarketSessionsError] = useState<string | null>(null);
  const [researchError, setResearchError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setDiagnosticsError(null);
    setMarketSessionsError(null);
    setResearchError(null);

    const [diagResult, sessionsResult, researchResult] = await Promise.allSettled([
      api.getDiagnostics({ timeoutMs }),
      api.getMarketSessions({ timeoutMs }),
      api.getResearchArchiveStatus(true, { timeoutMs }),
    ]);

    if (diagResult.status === "fulfilled") {
      setDiagnostics(diagResult.value);
      reportHydrationRefetchSuccess(ROUTE_KEY, "diagnostics");
    } else {
      console.error(diagResult.reason);
      const message = getUserFacingErrorMessage(diagResult.reason, "시스템 진단 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
      setDiagnosticsError(message);
      reportPanelDegraded(ROUTE_KEY, "diagnostics", message);
    }

    if (sessionsResult.status === "fulfilled") {
      setMarketSessions(sessionsResult.value);
      reportHydrationRefetchSuccess(ROUTE_KEY, "market_sessions");
    } else {
      console.error(sessionsResult.reason);
      const message = getUserFacingErrorMessage(sessionsResult.reason, "시장 세션 요약을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
      setMarketSessionsError(message);
      reportPanelDegraded(ROUTE_KEY, "market_sessions", message);
    }

    if (researchResult.status === "fulfilled") {
      setResearchStatus(researchResult.value);
      reportHydrationRefetchSuccess(ROUTE_KEY, "research_archive_status");
    } else {
      console.error(researchResult.reason);
      const message = getUserFacingErrorMessage(researchResult.reason, "기관 리서치 동기화 상태를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
      setResearchError(message);
      reportPanelDegraded(ROUTE_KEY, "research_archive_status", message);
    }

    setLoading(false);
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!loading && (diagnostics || marketSessions || researchStatus)) {
      reportInitialSsrSuccess(ROUTE_KEY);
    }
  }, [diagnostics, loading, marketSessions, researchStatus]);

  useEffect(() => {
    if (!loading && !diagnostics && !marketSessions && !researchStatus && (diagnosticsError || marketSessionsError || researchError)) {
      reportErrorOnlyScreen(ROUTE_KEY, diagnosticsError || marketSessionsError || researchError || "settings error");
    }
  }, [diagnostics, diagnosticsError, loading, marketSessions, marketSessionsError, researchError, researchStatus]);

  const refreshResearchArchive = async () => {
    setRefreshing(true);
    setResearchError(null);
    try {
      await api.refreshResearchArchive();
      const research = await api.getResearchArchiveStatus(true, { timeoutMs });
      setResearchStatus(research);
    } catch (err) {
      console.error(err);
      setResearchError(
        getUserFacingErrorMessage(err, "기관 리서치 상태를 새로고침하지 못했습니다. 잠시 후 다시 시도해 주세요."),
      );
    } finally {
      setRefreshing(false);
    }
  };

  return {
    diagnostics,
    marketSessions,
    researchStatus,
    loading,
    refreshing,
    diagnosticsError,
    marketSessionsError,
    researchError,
    load,
    refreshResearchArchive,
  };
}
