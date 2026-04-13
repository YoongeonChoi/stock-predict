"use client";

import { useEffect, useRef, useState } from "react";

import { ApiError, ApiTimeoutError, api } from "@/lib/api";
import type {
  DailyBriefingResponse,
  HeatmapData,
  MarketMovers,
} from "@/lib/api";
import { formatAuditTime, type PublicAuditFields } from "@/lib/public-audit";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import {
  reportErrorOnlyScreen,
  reportHydrationRefetchSuccess,
  reportInitialSsrSuccess,
  reportPanelDegraded,
} from "@/lib/route-observability";
import type { CountryListItem, CountryReport, OpportunityRadarResponse } from "@/lib/types";

const BRIEFING_TIMEOUT_MS = 9_000;
const WORKSPACE_TIMEOUT_MS = 22_000;
const HOME_RADAR_LIMIT = 12;

export interface HomeDashboardInitialData {
  initialCountries?: CountryListItem[];
  initialIndicators?: { name: string; price: number; change_pct: number }[];
  initialBriefing?: DailyBriefingResponse | null;
  initialHeatmap?: (HeatmapData & PublicAuditFields) | null;
  initialMovers?: (MarketMovers & PublicAuditFields) | null;
  initialRadar?: (OpportunityRadarResponse & PublicAuditFields) | null;
  initialCountryReport?: (CountryReport & PublicAuditFields) | null;
  initialSectorPerformance?: { sector: string; ticker: string; price: number; change_pct: number; breadth: number; leader_name: string }[] | null;
}

function describeLoadError(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.errorCode === "SP-5018") {
    return "요청이 길어져 이번 섹션은 잠시 비워 두었습니다. 잠시 뒤 다시 시도해 주세요.";
  }
  if (error instanceof ApiTimeoutError) {
    return fallback;
  }
  return getUserFacingErrorMessage(error, fallback, { timeoutMessage: fallback });
}

function toInitialClock(value?: string | null) {
  return formatAuditTime(value) || "";
}

export function useHomeDashboardViewModel({
  initialCountries = [],
  initialIndicators = [],
  initialBriefing = null,
  initialHeatmap = null,
  initialMovers = null,
  initialRadar = null,
  initialCountryReport = null,
}: HomeDashboardInitialData) {
  const routeKey = "/";
  const initializedRef = useRef(false);
  const workspaceRequestIdRef = useRef(0);
  const reportedInitialRef = useRef(false);
  const reportedErrorOnlyRef = useRef(false);
  const reportedSuccessRef = useRef<Record<string, boolean>>({});
  const reportedDegradedRef = useRef<Record<string, boolean>>({});
  const [countries, setCountries] = useState<CountryListItem[]>(initialCountries);
  const [indicators, setIndicators] = useState(initialIndicators);
  const [briefing, setBriefing] = useState<DailyBriefingResponse | null>(initialBriefing);
  const [selectedCountry, setSelectedCountry] = useState("KR");
  const [heatmapData, setHeatmapData] = useState<(HeatmapData & PublicAuditFields) | null>(initialHeatmap);
  const [movers, setMovers] = useState<(MarketMovers & PublicAuditFields) | null>(initialMovers);
  const [radarData, setRadarData] = useState<(OpportunityRadarResponse & PublicAuditFields) | null>(initialRadar);
  const [countryReport, setCountryReport] = useState<(CountryReport & PublicAuditFields) | null>(initialCountryReport);
  const [loading, setLoading] = useState(initialCountries.length === 0 && initialIndicators.length === 0);
  const [briefingLoading, setBriefingLoading] = useState(!initialBriefing);
  const [heatmapLoading, setHeatmapLoading] = useState(!initialHeatmap);
  const [moversLoading, setMoversLoading] = useState(!initialMovers);
  const [radarLoading, setRadarLoading] = useState(!initialRadar);
  const [reportLoading, setReportLoading] = useState(!initialCountryReport);
  const [briefingError, setBriefingError] = useState<string | null>(null);
  const [heatmapError, setHeatmapError] = useState<string | null>(null);
  const [moversError, setMoversError] = useState<string | null>(null);
  const [radarError, setRadarError] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState(
    toInitialClock(initialCountryReport?.generated_at || initialRadar?.generated_at || initialBriefing?.generated_at),
  );

  const loadBriefing = async () => {
    setBriefingLoading(true);
    setBriefingError(null);
    try {
      const result = await api.getDailyBriefing({ timeoutMs: BRIEFING_TIMEOUT_MS });
      setBriefing(result);
    } catch (error) {
      console.warn(error);
      setBriefing(null);
      setBriefingError(describeLoadError(error, "브리핑 계산이 길어져 오늘의 요약을 아직 표시하지 못했습니다."));
    } finally {
      setBriefingLoading(false);
    }
  };

  const loadCountryWorkspace = async (code: string) => {
    const requestId = workspaceRequestIdRef.current + 1;
    workspaceRequestIdRef.current = requestId;

    const syncIfCurrent = (callback: () => void) => {
      if (workspaceRequestIdRef.current === requestId) {
        callback();
      }
    };

    setSelectedCountry(code);
    setHeatmapLoading(true);
    setMoversLoading(true);
    setRadarLoading(true);
    setReportLoading(true);
    setHeatmapError(null);
    setMoversError(null);
    setRadarError(null);
    setReportError(null);

    const heatmapTask = (async () => {
      try {
        const result = await api.getHeatmap(code, { timeoutMs: WORKSPACE_TIMEOUT_MS });
        syncIfCurrent(() => {
          setHeatmapData(result);
          setHeatmapError(null);
        });
      } catch (error) {
        console.warn(error);
        syncIfCurrent(() => {
          setHeatmapData(null);
          setHeatmapError(describeLoadError(error, "히트맵 계산이 지연되고 있습니다. 잠시 뒤 다시 시도해 주세요."));
        });
      } finally {
        syncIfCurrent(() => setHeatmapLoading(false));
      }
    })();

    const moversTask = (async () => {
      try {
        const result = await api.getMarketMovers(code, { timeoutMs: WORKSPACE_TIMEOUT_MS });
        syncIfCurrent(() => {
          setMovers(result);
          setMoversError(null);
        });
      } catch (error) {
        console.warn(error);
        syncIfCurrent(() => {
          setMovers(null);
          setMoversError(describeLoadError(error, "상승률·하락률 상위 집계가 지연되고 있습니다. 잠시 뒤 다시 시도해 주세요."));
        });
      } finally {
        syncIfCurrent(() => setMoversLoading(false));
      }
    })();

    const radarTask = (async () => {
      try {
        const result = await api.getMarketOpportunities(code, HOME_RADAR_LIMIT, { timeoutMs: WORKSPACE_TIMEOUT_MS });
        syncIfCurrent(() => {
          setRadarData(result);
          setRadarError(null);
        });
      } catch (error) {
        console.warn(error);
        syncIfCurrent(() => {
          setRadarData(null);
          setRadarError(describeLoadError(error, "강한 셋업 계산이 길어져 이번에는 목록을 비워 두었습니다."));
        });
      } finally {
        syncIfCurrent(() => setRadarLoading(false));
      }
    })();

    const reportTask = (async () => {
      try {
        const result = await api.getCountryReport(code, { timeoutMs: WORKSPACE_TIMEOUT_MS });
        syncIfCurrent(() => {
          setCountryReport(result);
          setReportError(null);
        });
      } catch (error) {
        console.warn(error);
        syncIfCurrent(() => {
          setCountryReport(null);
          setReportError(describeLoadError(error, "시장 요약 리포트 계산이 길어져 이번에는 요약만 표시합니다."));
        });
      } finally {
        syncIfCurrent(() => setReportLoading(false));
      }
    })();

    await Promise.allSettled([heatmapTask, moversTask, radarTask, reportTask]);
    syncIfCurrent(() => setLastUpdated(formatAuditTime(new Date().toISOString()) || ""));
  };

  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const bootstrap = async () => {
      setLoading(true);
      if (initialCountries.length === 0 || initialIndicators.length === 0) {
        const [countryResult, indicatorResult] = await Promise.allSettled([
          api.getCountries(),
          api.getMarketIndicators(),
        ]);

        if (countryResult.status === "fulfilled") setCountries(countryResult.value);
        else console.warn(countryResult.reason);

        if (indicatorResult.status === "fulfilled") setIndicators(indicatorResult.value);
        else console.warn(indicatorResult.reason);
      }

      if (!initialBriefing) {
        void loadBriefing();
      } else {
        setBriefingLoading(false);
      }
      if (!initialHeatmap || !initialMovers || !initialRadar || !initialCountryReport) {
        void loadCountryWorkspace("KR");
      } else {
        setHeatmapLoading(false);
        setMoversLoading(false);
        setRadarLoading(false);
        setReportLoading(false);
      }
      setLoading(false);
    };

    void bootstrap();
  }, [
    initialBriefing,
    initialCountries.length,
    initialCountryReport,
    initialHeatmap,
    initialIndicators.length,
    initialMovers,
    initialRadar,
  ]);

  useEffect(() => {
    if (reportedInitialRef.current) {
      return;
    }
    if (countries.length > 0 || indicators.length > 0 || briefing || heatmapData || movers || radarData || countryReport) {
      reportedInitialRef.current = true;
      reportInitialSsrSuccess(routeKey, "home_shell");
    }
  }, [briefing, countries.length, countryReport, heatmapData, indicators.length, movers, radarData, routeKey]);

  useEffect(() => {
    if (briefing && !briefingLoading && !reportedSuccessRef.current.briefing) {
      reportedSuccessRef.current.briefing = true;
      reportHydrationRefetchSuccess(routeKey, "briefing");
    }
    if (briefingError && !briefingLoading && !reportedDegradedRef.current.briefing) {
      reportedDegradedRef.current.briefing = true;
      reportPanelDegraded(routeKey, "briefing", briefingError);
    }
  }, [briefing, briefingError, briefingLoading, routeKey]);

  useEffect(() => {
    if (heatmapData && !heatmapLoading && !reportedSuccessRef.current.heatmap) {
      reportedSuccessRef.current.heatmap = true;
      reportHydrationRefetchSuccess(routeKey, "heatmap");
    }
    if (heatmapError && !heatmapLoading && !reportedDegradedRef.current.heatmap) {
      reportedDegradedRef.current.heatmap = true;
      reportPanelDegraded(routeKey, "heatmap", heatmapError);
    }
  }, [heatmapData, heatmapError, heatmapLoading, routeKey]);

  useEffect(() => {
    if (movers && !moversLoading && !reportedSuccessRef.current.movers) {
      reportedSuccessRef.current.movers = true;
      reportHydrationRefetchSuccess(routeKey, "movers");
    }
    if (moversError && !moversLoading && !reportedDegradedRef.current.movers) {
      reportedDegradedRef.current.movers = true;
      reportPanelDegraded(routeKey, "movers", moversError);
    }
  }, [movers, moversError, moversLoading, routeKey]);

  useEffect(() => {
    if (radarData && !radarLoading && !reportedSuccessRef.current.radar) {
      reportedSuccessRef.current.radar = true;
      reportHydrationRefetchSuccess(routeKey, "radar");
    }
    if (radarError && !radarLoading && !reportedDegradedRef.current.radar) {
      reportedDegradedRef.current.radar = true;
      reportPanelDegraded(routeKey, "radar", radarError);
    }
  }, [radarData, radarError, radarLoading, routeKey]);

  useEffect(() => {
    if (countryReport && !reportLoading && !reportedSuccessRef.current.report) {
      reportedSuccessRef.current.report = true;
      reportHydrationRefetchSuccess(routeKey, "country_report");
    }
    if (reportError && !reportLoading && !reportedDegradedRef.current.report) {
      reportedDegradedRef.current.report = true;
      reportPanelDegraded(routeKey, "country_report", reportError);
    }
  }, [countryReport, reportError, reportLoading, routeKey]);

  useEffect(() => {
    if (reportedErrorOnlyRef.current) {
      return;
    }
    const hasVisiblePanels = Boolean(briefing || heatmapData || movers || radarData || countryReport);
    const hasOnlyErrors = Boolean(briefingError || heatmapError || moversError || radarError || reportError);
    if (!loading && !hasVisiblePanels && hasOnlyErrors) {
      reportedErrorOnlyRef.current = true;
      reportErrorOnlyScreen(routeKey, "home_workspace");
    }
  }, [
    briefing,
    briefingError,
    countryReport,
    heatmapData,
    heatmapError,
    loading,
    movers,
    moversError,
    radarData,
    radarError,
    reportError,
    routeKey,
  ]);

  return {
    countries,
    indicators,
    briefing,
    selectedCountry,
    heatmapData,
    movers,
    radarData,
    countryReport,
    loading,
    briefingLoading,
    heatmapLoading,
    moversLoading,
    radarLoading,
    reportLoading,
    briefingError,
    heatmapError,
    moversError,
    radarError,
    reportError,
    lastUpdated,
    loadBriefing,
    loadCountryWorkspace,
  };
}
