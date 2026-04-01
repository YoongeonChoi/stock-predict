"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import StockHeatmap from "@/components/charts/StockHeatmap";
import { ApiError, ApiTimeoutError, api } from "@/lib/api";
import { buildPublicAuditSummary, type PublicAuditFields } from "@/lib/public-audit";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import {
  reportErrorOnlyScreen,
  reportHydrationRefetchSuccess,
  reportInitialSsrSuccess,
  reportPanelDegraded,
} from "@/lib/route-observability";
import type {
  DailyBriefingEvent,
  DailyBriefingFocusCard,
  DailyBriefingResponse,
  HeatmapData,
  MarketMovers,
} from "@/lib/api";
import type { CountryListItem, CountryReport, MacroClaim, OpportunityRadarResponse } from "@/lib/types";
import { changeColor, formatPct } from "@/lib/utils";

const COUNTRY_FLAGS: Record<string, string> = { KR: "🇰🇷" };
const BRIEFING_TIMEOUT_MS = 9_000;
const WORKSPACE_TIMEOUT_MS = 22_000;
const HOME_RADAR_LIMIT = 12;

type FocusSlot =
  | { kind: "focus"; key: string; item: DailyBriefingFocusCard }
  | { kind: "event"; key: string; item: DailyBriefingEvent }
  | { kind: "reason"; key: string; title: string; summary: string };

interface MarketIndicator {
  name: string;
  price: number;
  change_pct: number;
}

function statusTone(stance?: string) {
  if (stance === "risk_on") return "bg-emerald-500/12 text-emerald-500";
  if (stance === "risk_off") return "bg-rose-500/12 text-rose-500";
  return "bg-border/60 text-text-secondary";
}

function impactTone(impact?: string) {
  if (impact === "high") return "text-negative bg-negative/10";
  if (impact === "medium") return "text-warning bg-warning/10";
  return "text-text-secondary bg-border/40";
}

function indicatorLabel(indicator: MarketIndicator) {
  const value = (indicator.price ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (indicator.name === "USD/KRW") return `₩${value}`;
  if (["Gold", "Oil (WTI)", "Bitcoin"].includes(indicator.name)) return `$${value}`;
  return value;
}

function macroClaimTone(direction: MacroClaim["direction"]) {
  if (direction === "up") return "text-emerald-500";
  if (direction === "down") return "text-rose-500";
  return "text-text";
}

function formatMacroClaimValue(claim: MacroClaim) {
  const showSigned =
    claim.metric.includes("등락률")
    || claim.metric.includes("증가율")
    || claim.metric.includes("성장률");
  const prefix = showSigned && claim.value > 0 ? "+" : "";
  const decimals = Math.abs(claim.value) >= 100 ? 0 : 2;
  return `${prefix}${claim.value.toLocaleString("ko-KR", { maximumFractionDigits: decimals })}${claim.unit}`;
}

function formatMacroClaimDate(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("ko-KR");
}

function describeLoadError(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.errorCode === "SP-5018") {
    return "요청이 길어져 이번 섹션은 잠시 비워 두었습니다. 잠시 후 다시 시도해 주세요.";
  }
  if (error instanceof ApiTimeoutError) {
    return fallback;
  }
  return getUserFacingErrorMessage(error, fallback, { timeoutMessage: fallback });
}

function toInitialClock(value?: string | null) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString("ko-KR");
}

interface HomeDashboardClientProps {
  initialCountries?: CountryListItem[];
  initialIndicators?: MarketIndicator[];
  initialBriefing?: DailyBriefingResponse | null;
  initialHeatmap?: (HeatmapData & PublicAuditFields) | null;
  initialMovers?: (MarketMovers & PublicAuditFields) | null;
  initialRadar?: (OpportunityRadarResponse & PublicAuditFields) | null;
  initialCountryReport?: (CountryReport & PublicAuditFields) | null;
}

export default function HomeDashboardClient({
  initialCountries = [],
  initialIndicators = [],
  initialBriefing = null,
  initialHeatmap = null,
  initialMovers = null,
  initialRadar = null,
  initialCountryReport = null,
}: HomeDashboardClientProps) {
  const routeKey = "/";
  const initializedRef = useRef(false);
  const workspaceRequestIdRef = useRef(0);
  const reportedInitialRef = useRef(false);
  const reportedErrorOnlyRef = useRef(false);
  const reportedSuccessRef = useRef<Record<string, boolean>>({});
  const reportedDegradedRef = useRef<Record<string, boolean>>({});
  const [countries, setCountries] = useState<CountryListItem[]>(initialCountries);
  const [indicators, setIndicators] = useState<MarketIndicator[]>(initialIndicators);
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
      console.error(error);
      setBriefing(null);
      setBriefingError(
        describeLoadError(error, "브리핑 계산이 길어져 오늘의 포커스를 아직 표시하지 못했습니다."),
      );
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
        console.error(error);
        syncIfCurrent(() => {
          setHeatmapData(null);
          setHeatmapError(
            describeLoadError(error, "히트맵 계산이 지연되고 있습니다. 잠시 후 다시 시도해 주세요."),
          );
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
        console.error(error);
        syncIfCurrent(() => {
          setMovers(null);
          setMoversError(
            describeLoadError(error, "상승·하락 상위 집계가 지연되고 있습니다. 잠시 후 다시 시도해 주세요."),
          );
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
        console.error(error);
        syncIfCurrent(() => {
          setRadarData(null);
          setRadarError(
            describeLoadError(error, "강한 셋업 계산이 길어져 이번에는 목록을 비워 두었습니다."),
          );
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
        console.error(error);
        syncIfCurrent(() => {
          setCountryReport(null);
          setReportError(
            describeLoadError(error, "시장 요약 리포트 계산이 길어져 이번에는 요약만 표시합니다."),
          );
        });
      } finally {
        syncIfCurrent(() => setReportLoading(false));
      }
    })();

    await Promise.allSettled([heatmapTask, moversTask, radarTask, reportTask]);
    syncIfCurrent(() => setLastUpdated(new Date().toLocaleTimeString("ko-KR")));
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
        else console.error(countryResult.reason);

        if (indicatorResult.status === "fulfilled") setIndicators(indicatorResult.value);
        else console.error(indicatorResult.reason);
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

    bootstrap();
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

  const selectedCountryItem = useMemo(
    () => countries.find((country) => country.code === selectedCountry) ?? null,
    [countries, selectedCountry],
  );

  const marketView = useMemo(
    () => briefing?.market_view.find((item) => item.country_code === selectedCountry) ?? null,
    [briefing, selectedCountry],
  );

  const focusCards = useMemo(() => {
    const scoped = briefing?.focus_cards.filter((item) => item.country_code === selectedCountry) ?? [];
    if (scoped.length > 0) return scoped.slice(0, 3);
    return briefing?.focus_cards.slice(0, 3) ?? [];
  }, [briefing, selectedCountry]);

  const events = useMemo(() => {
    const scoped = briefing?.upcoming_events.filter((item) => item.country_code === selectedCountry) ?? [];
    if (scoped.length > 0) return scoped.slice(0, 4);
    return briefing?.upcoming_events.slice(0, 4) ?? [];
  }, [briefing, selectedCountry]);

  const focusSlots = useMemo<FocusSlot[]>(() => {
    const slots: FocusSlot[] = focusCards.map((item) => ({
      kind: "focus",
      key: `focus-${item.country_code}-${item.ticker}`,
      item,
    }));

    for (const event of events) {
      if (slots.length >= 3) {
        break;
      }
      slots.push({
        kind: "event",
        key: `event-${event.country_code}-${event.date}-${event.title}`,
        item: event,
      });
    }

    const reasonQueue = [
      briefingError || reportError
        ? {
            key: "reason-report-sync",
            title: "리포트 동기화 중",
            summary: "브리핑과 시장 요약 계산이 길어져 현재 확보된 신호와 일정부터 먼저 보여주고 있습니다.",
          }
        : null,
      (radarData as PublicAuditFields | null)?.partial
        ? {
            key: "reason-radar-partial",
            title: "후보 부족: 보수 모드 유지",
            summary: "레이더 정밀 계산이 지연돼도 지금은 무리하게 늘리지 않고, 먼저 확보된 후보 기준으로 선별 대응합니다.",
          }
        : null,
      events.length > 0
        ? {
            key: "reason-event-priority",
            title: "오늘은 이벤트 우선",
            summary: "가까운 일정이 있어 종목 후보가 부족한 슬롯은 이벤트 기준 판단 카드로 채웠습니다.",
          }
        : null,
      {
        key: "reason-selective",
        title: "보수 모드 유지",
        summary: "당장 늘릴 이유가 뚜렷하지 않으면 관찰과 일정 확인을 먼저 두고, 다시 열었을 때 후보를 이어받습니다.",
      },
    ].filter((item): item is NonNullable<typeof item> => Boolean(item));

    const usedReasonKeys = new Set<string>();
    for (const reason of reasonQueue) {
      if (slots.length >= 3) {
        break;
      }
      if (usedReasonKeys.has(reason.key)) {
        continue;
      }
      usedReasonKeys.add(reason.key);
      slots.push({
        kind: "reason",
        key: reason.key,
        title: reason.title,
        summary: reason.summary,
      });
    }

    while (slots.length < 3) {
      const order = slots.length + 1;
      slots.push({
        kind: "reason",
        key: `reason-default-${order}`,
        title: "관찰 우선",
        summary: "오늘 바로 늘릴 신호가 적더라도 공개 대시보드는 빈 슬롯 대신 다음 확인 포인트를 이유 카드로 유지합니다.",
      });
    }

    return slots.slice(0, 3);
  }, [briefingError, events, focusCards, radarData, reportError]);

  const topNews = countryReport?.key_news.slice(0, 4) ?? [];
  const topStocks = countryReport?.top_stocks.slice(0, 5) ?? [];
  const radarHasItems = (radarData?.opportunities.length ?? 0) > 0;
  const retryCurrentWorkspace = () => {
    void loadCountryWorkspace(selectedCountry);
  };
  const workspaceDelays = useMemo(() => {
    const pending: string[] = [];
    if (briefingError) pending.push("오늘의 포커스");
    if (reportError) pending.push("시장 요약");
    if (heatmapError) pending.push("히트맵");
    if (moversError) pending.push("상승·하락 상위");
    if (radarError || (!radarLoading && !radarHasItems)) pending.push("강한 셋업");
    return pending;
  }, [briefingError, heatmapError, moversError, radarError, radarHasItems, radarLoading, reportError]);
  const marketSummaryText =
    countryReport?.market_summary ||
    marketView?.summary ||
    (reportLoading
      ? "선택한 시장의 상태를 불러오는 중입니다."
      : reportError || (briefingLoading ? "브리핑을 불러오는 중입니다." : briefingError || "선택한 시장 요약이 아직 없습니다."));
  const macroClaims = countryReport?.macro_claims?.slice(0, 4) ?? [];
  const dashboardAuditMeta = useMemo<PublicAuditFields | null>(() => ({
    snapshot_id: radarData?.snapshot_id || null,
    generated_at: countryReport?.generated_at || radarData?.generated_at || briefing?.generated_at || null,
    partial:
      Boolean((countryReport as PublicAuditFields | null)?.partial)
      || Boolean((radarData as PublicAuditFields | null)?.partial)
      || Boolean((heatmapData as PublicAuditFields | null)?.partial)
      || Boolean((movers as PublicAuditFields | null)?.partial),
    fallback_reason:
      (countryReport as PublicAuditFields | null)?.fallback_reason
      || (radarData as PublicAuditFields | null)?.fallback_reason
      || (heatmapData as PublicAuditFields | null)?.fallback_reason
      || (movers as PublicAuditFields | null)?.fallback_reason
      || null,
    fallback_tier: (radarData as PublicAuditFields | null)?.fallback_tier || null,
  }), [briefing?.generated_at, countryReport, heatmapData, movers, radarData]);
  const dashboardSummary = buildPublicAuditSummary(dashboardAuditMeta, {
    defaultSummary:
      radarData && countryReport
        ? `시장 국면 ${countryReport.market_regime?.label || radarData.market_regime.label} / 오늘의 포커스 ${focusSlots.length}개 / 레이더 상위 ${Math.min(radarData.opportunities.length, 3)}개를 먼저 보여줍니다.`
        : "선택 시장 현황과 핵심 수치를 먼저 보여주고, 아래 카드에서 히트맵과 레이더를 이어서 읽습니다.",
  });

  return (
    <div className="page-shell">
      <section className="card !p-5 space-y-5">
        <div className="section-heading gap-4">
          <div>
            <h1 className="section-title text-2xl">대시보드</h1>
            <p className="section-copy">
              {countryReport && radarData
                ? `선택 시장 현황 / 핵심 수치 / 오늘의 포커스 ${focusSlots.length}개 / 마지막 갱신 ${lastUpdated || "방금"}`
                : "선택한 시장의 지수, 뉴스, 히트맵, 강한 셋업을 한 흐름으로 봅니다."}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
            {lastUpdated ? <span className="info-chip">최근 갱신 {lastUpdated}</span> : null}
            {countryReport?.generated_at ? <span className="info-chip">리포트 {new Date(countryReport.generated_at).toLocaleString("ko-KR")}</span> : null}
          </div>
        </div>
        <PublicAuditStrip meta={dashboardAuditMeta} />
        <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-4 text-sm leading-6 text-text-secondary">
          {dashboardSummary}
        </div>

        {workspaceDelays.length > 0 ? (
          <WorkspaceStateCard
            eyebrow="부분 업데이트"
            title="일부 계산이 더 필요합니다"
            message={`${workspaceDelays.join(", ")} 섹션은 계산이 길어져 현재 확보된 데이터부터 먼저 보여주고 있습니다.`}
            tone="warning"
            actionLabel="현재 시장 다시 불러오기"
            onAction={retryCurrentWorkspace}
          />
        ) : null}

        {countries.length > 1 ? (
          <div className="flex flex-wrap gap-2">
            {countries.map((country) => (
                <button
                  key={country.code}
                  onClick={() => void loadCountryWorkspace(country.code)}
                  className={`rounded-full px-3 py-2 text-sm font-medium transition-colors ${
                    selectedCountry === country.code
                      ? "bg-accent text-white"
                      : "border border-border bg-surface/70 text-text-secondary hover:border-accent/35 hover:text-text"
                  }`}
                >
                  {COUNTRY_FLAGS[country.code]} {country.name_local}
                </button>
              ))}
          </div>
        ) : null}

        <div className="workspace-grid">
          <div className="workspace-panel h-full">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-text">
                  {selectedCountryItem ? `${COUNTRY_FLAGS[selectedCountry]} ${selectedCountryItem.name_local}` : selectedCountry}
                </div>
                <div className="mt-1 text-sm leading-6 text-text-secondary">
                  {marketSummaryText}
                </div>
              </div>
              {marketView ? (
                <span className={`rounded-full px-3 py-1.5 text-xs font-medium ${statusTone(marketView.stance)}`}>
                  {marketView.label}
                </span>
              ) : null}
            </div>

            {macroClaims.length > 0 ? (
              <div className="mt-5 grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
                {macroClaims.map((claim) => (
                  <div key={`${claim.source}-${claim.metric}`} className="rounded-2xl border border-border/60 bg-surface/45 px-3 py-3">
                    <div className="text-[11px] text-text-secondary">{claim.metric}</div>
                    <div className={`mt-2 text-base font-semibold ${macroClaimTone(claim.direction)}`}>
                      {formatMacroClaimValue(claim)}
                    </div>
                    <div className="mt-1 text-[11px] leading-5 text-text-secondary">
                      {claim.source}
                      {formatMacroClaimDate(claim.published_at) ? ` · ${formatMacroClaimDate(claim.published_at)}` : ""}
                      {` · 근거 ${Math.round((claim.confidence ?? 0) * 100)}%`}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="mt-5 grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
              {selectedCountryItem?.indices.map((index) => (
                <div key={index.ticker} className="metric-card">
                  <div className="text-xs text-text-secondary">{index.name}</div>
                  <div className="mt-2 text-lg font-semibold text-text">{(index.price ?? index.current_price ?? 0).toLocaleString()}</div>
                  <div className={`mt-1 text-xs font-medium ${changeColor(index.change_pct ?? 0)}`}>
                    {formatPct(index.change_pct ?? 0)}
                  </div>
                </div>
              ))}
              {countryReport?.next_day_forecast ? (
                <div className="metric-card sm:col-span-2 xl:col-span-1">
                  <div className="text-xs text-text-secondary">다음 거래일 시그널</div>
                  <div className="mt-2 text-lg font-semibold text-text">상방 {countryReport.next_day_forecast.up_probability.toFixed(1)}%</div>
                  <div className={`mt-1 text-xs font-medium ${changeColor(countryReport.next_day_forecast.predicted_return_pct)}`}>
                    기대 {formatPct(countryReport.next_day_forecast.predicted_return_pct)}
                  </div>
                </div>
              ) : null}
            </div>

            {indicators.length > 0 ? (
              <div className="mt-5 grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
                {indicators.slice(0, 4).map((indicator) => (
                  <div key={indicator.name} className="rounded-2xl border border-border/60 bg-surface/45 px-3 py-3">
                    <div className="text-[11px] text-text-secondary">{indicator.name}</div>
                    <div className="mt-2 text-sm font-semibold text-text">{indicatorLabel(indicator)}</div>
                    <div className={`mt-1 text-[11px] ${changeColor(indicator.change_pct ?? 0)}`}>
                      {formatPct(indicator.change_pct ?? 0)}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <div className="workspace-panel h-full">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-text">오늘의 포커스</div>
                <div className="mt-1 text-sm text-text-secondary">선택 시장에서 바로 볼 종목과 일정만 추렸습니다.</div>
              </div>
              {briefing?.research_archive ? <span className="info-chip">리서치 {briefing.research_archive.todays_reports}건</span> : null}
            </div>
            <div className="mt-4">
              {briefingLoading ? (
                <WorkspaceLoadingCard
                  title="오늘의 포커스를 추리고 있습니다"
                  message="브리핑, 핵심 종목, 가까운 일정 중 먼저 확인할 항목만 다시 묶는 중입니다."
                  className="min-h-[230px]"
                />
              ) : focusSlots.length > 0 ? (
                <div className="space-y-3">
                  {focusSlots.map((slot) => {
                    if (slot.kind === "focus") {
                      const item = slot.item;
                      return (
                        <Link key={slot.key} href={`/stock/${encodeURIComponent(item.ticker)}`} className="block rounded-2xl border border-border/70 bg-surface/50 px-4 py-3 transition-colors hover:border-accent/35">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="font-medium text-text">{item.name}</div>
                              <div className="mt-1 text-xs text-text-secondary">{item.ticker} · {item.sector}</div>
                            </div>
                            <div className="text-right">
                              <div className={`text-sm font-semibold ${changeColor(item.predicted_return_pct)}`}>{formatPct(item.predicted_return_pct)}</div>
                              <div className="mt-1 text-[11px] text-text-secondary">상방 {item.up_probability.toFixed(1)}%</div>
                            </div>
                          </div>
                        </Link>
                      );
                    }

                    if (slot.kind === "event") {
                      const event = slot.item;
                      return (
                        <div key={slot.key} className="rounded-2xl border border-border/70 bg-surface/45 px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <div className="font-medium text-text">{event.title}</div>
                            <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${impactTone(event.impact)}`}>{event.date}</span>
                          </div>
                          <div className="mt-1 text-xs text-text-secondary">{event.summary}</div>
                        </div>
                      );
                    }

                    return (
                      <div key={slot.key} className="rounded-2xl border border-border/70 bg-surface/45 px-4 py-3">
                        <div className="font-medium text-text">{slot.title}</div>
                        <div className="mt-1 text-xs leading-6 text-text-secondary">{slot.summary}</div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <WorkspaceStateCard
                  eyebrow="포커스 지연"
                  title="오늘 바로 볼 항목을 아직 정리하지 못했습니다"
                  message={briefingError || "오늘의 포커스 데이터가 아직 없습니다."}
                  onAction={() => void loadBriefing()}
                  tone="warning"
                />
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="workspace-grid">
        <div className="card !p-4 h-full">
          <div className="section-heading gap-4">
            <div>
              <h2 className="section-title">시장 히트맵</h2>
              <p className="section-copy">크기는 시가총액, 색은 등락률입니다.</p>
            </div>
            <span className="info-chip">{selectedCountry} 히트맵</span>
          </div>
          <div className="mt-4">
            {heatmapLoading ? (
              <StockHeatmap data={heatmapData} loading />
            ) : heatmapData ? (
              <StockHeatmap data={heatmapData} loading={false} />
            ) : (
              <WorkspaceStateCard
                eyebrow="히트맵 지연"
                title="시장 분포 계산이 조금 더 필요합니다"
                message={heatmapError || "히트맵 데이터가 아직 없습니다."}
                onAction={retryCurrentWorkspace}
                tone="warning"
              />
            )}
          </div>
        </div>

        <div className="card !p-5 h-full">
          <div>
            <h2 className="section-title">상승·하락 상위</h2>
            <p className="section-copy">선택 시장에서 강도가 강한 종목과 약한 종목을 같이 봅니다.</p>
          </div>
          {moversLoading ? (
            <div className="mt-5">
              <WorkspaceLoadingCard
                title="상승·하락 상위를 정리하고 있습니다"
                message="강도가 큰 종목과 약한 종목을 분리해 순위 보드로 묶는 중입니다."
                className="min-h-[240px]"
              />
            </div>
          ) : movers ? (
            <div className="mt-5 grid gap-5 sm:grid-cols-2 xl:grid-cols-1">
              <div>
                <h3 className="text-sm font-semibold text-positive">상승 상위</h3>
                <div className="mt-3 space-y-2">
                  {movers.gainers.slice(0, 5).map((stock) => (
                    <Link key={stock.ticker} href={`/stock/${encodeURIComponent(stock.ticker)}`} className="metric-card flex items-center justify-between gap-3 py-3 transition-colors hover:border-accent/35">
                      <div className="min-w-0">
                        <div className="font-medium text-text">{stock.ticker}</div>
                        <div className="mt-1 truncate text-xs text-text-secondary">{stock.name}</div>
                      </div>
                      <span className="shrink-0 font-mono text-sm font-medium text-positive">+{stock.change_pct.toFixed(2)}%</span>
                    </Link>
                  ))}
                </div>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-negative">하락 상위</h3>
                <div className="mt-3 space-y-2">
                  {movers.losers.slice(0, 5).map((stock) => (
                    <Link key={stock.ticker} href={`/stock/${encodeURIComponent(stock.ticker)}`} className="metric-card flex items-center justify-between gap-3 py-3 transition-colors hover:border-accent/35">
                      <div className="min-w-0">
                        <div className="font-medium text-text">{stock.ticker}</div>
                        <div className="mt-1 truncate text-xs text-text-secondary">{stock.name}</div>
                      </div>
                      <span className="shrink-0 font-mono text-sm font-medium text-negative">{stock.change_pct.toFixed(2)}%</span>
                    </Link>
                  ))}
                </div>
              </div>
            </div>
            ) : (
              <div className="mt-5">
                <WorkspaceStateCard
                  eyebrow="상위 집계 지연"
                  title="등락 상위 집계가 아직 준비되지 않았습니다"
                  message={moversError || "상승·하락 상위 데이터가 아직 없습니다."}
                  onAction={retryCurrentWorkspace}
                  tone="warning"
                />
              </div>
            )}
        </div>
      </section>

      <section className="workspace-grid-balanced">
        <div className="card !p-0 overflow-hidden h-full">
          <div className="border-b border-border px-5 py-4">
            <h2 className="section-title">강한 셋업</h2>
            <p className="section-copy">선택 시장에서 점수와 실행력이 높은 후보를 먼저 봅니다.</p>
          </div>
          <div className="px-5 py-5">
            {radarLoading ? (
              <WorkspaceLoadingCard
                title="강한 셋업을 다시 계산하고 있습니다"
                message="1차 시세 스캔과 실행 메모를 순서대로 정리해 레이더 후보를 채우는 중입니다."
                className="min-h-[300px]"
              />
            ) : radarData ? (
              <OpportunityRadarBoard data={radarData} compact embedded />
            ) : (
              <WorkspaceStateCard
                eyebrow="레이더 지연"
                title="강한 셋업 후보를 아직 정리하지 못했습니다"
                message={radarError || "강한 셋업 데이터가 아직 없습니다."}
                onAction={retryCurrentWorkspace}
                tone="warning"
              />
            )}
          </div>
        </div>

        <div className="workspace-stack">
          <div className="card !p-5 min-h-[260px]">
            <div className="section-heading gap-3">
              <div>
                <h2 className="section-title">주요 뉴스</h2>
                <p className="section-copy">선택 시장 리포트에서 뽑은 핵심 기사입니다.</p>
              </div>
              {reportLoading ? <span className="info-chip">불러오는 중</span> : null}
            </div>
            <div className="mt-4 space-y-3">
              {topNews.map((item) => (
                <a key={`${item.source}-${item.url}`} href={item.url} target="_blank" rel="noreferrer" className="block rounded-2xl border border-border/70 bg-surface/50 px-4 py-3 transition-colors hover:border-accent/35">
                  <div className="font-medium text-text">{item.title}</div>
                  <div className="mt-2 text-xs text-text-secondary">{item.source} · {item.published}</div>
                </a>
              ))}
              {!reportLoading && topNews.length === 0 ? (
                <WorkspaceStateCard
                  eyebrow={reportError ? "뉴스 지연" : "기사 연결 대기"}
                  title={reportError ? "핵심 기사 연결이 늦어지고 있습니다" : "연결된 기사 목록이 아직 비어 있습니다"}
                  message={
                    reportError ||
                    "시장 요약은 준비됐지만 연결된 핵심 기사 목록은 아직 비어 있습니다. 잠시 뒤 다시 열면 기사 연결이 채워질 수 있습니다."
                  }
                  onAction={reportError ? retryCurrentWorkspace : undefined}
                  tone={reportError ? "warning" : "neutral"}
                />
              ) : null}
            </div>
          </div>

          <div className="card !p-5 min-h-[260px]">
            <div>
              <h2 className="section-title">상위 종목</h2>
              <p className="section-copy">선택 국가 리포트에서 상단에 위치한 종목입니다.</p>
            </div>
            <div className="mt-4 space-y-2">
              {topStocks.map((stock) => (
                <Link key={stock.ticker} href={`/stock/${encodeURIComponent(stock.ticker)}`} className="block rounded-2xl border border-border/70 bg-surface/50 px-4 py-3 transition-colors hover:border-accent/35">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium text-text">{stock.name}</div>
                      <div className="mt-1 text-xs text-text-secondary">{stock.ticker}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-semibold text-text">점수 {stock.score.toFixed(1)}</div>
                      <div className={`mt-1 text-[11px] ${changeColor(stock.change_pct)}`}>{formatPct(stock.change_pct)}</div>
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-text-secondary">{stock.reason}</div>
                </Link>
              ))}
              {!reportLoading && topStocks.length === 0 ? (
                <WorkspaceStateCard
                  eyebrow={reportError ? "상위 종목 지연" : "후보 정리 대기"}
                  title={reportError ? "상위 종목 점수 정리가 늦어지고 있습니다" : "상위 후보 정리가 아직 비어 있습니다"}
                  message={
                    reportError ||
                    "시장 리포트는 준비됐지만 상위 종목 점수 정리가 아직 비어 있습니다. 잠시 뒤 다시 열면 후보가 채워질 수 있습니다."
                  }
                  onAction={reportError ? retryCurrentWorkspace : undefined}
                  tone={reportError ? "warning" : "neutral"}
                />
              ) : null}
            </div>
          </div>
        </div>
      </section>

      {loading ? (
        <WorkspaceLoadingCard
          title="시장 워크스페이스를 준비하고 있습니다"
          message="국가 목록과 대표 지표를 먼저 정리한 뒤 대시보드 패널을 순서대로 채웁니다."
          className="min-h-[120px]"
        />
      ) : null}
    </div>
  );
}
