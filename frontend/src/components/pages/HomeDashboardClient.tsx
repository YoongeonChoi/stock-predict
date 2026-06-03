"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  ExternalLink,
  LineChart,
  Radar,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import dynamic from "next/dynamic";
import { ApiError, ApiTimeoutError, api } from "@/lib/api";

const StockHeatmap = dynamic(() => import("@/components/charts/StockHeatmap"), { ssr: false });
import MarketSessionBadge from "@/components/MarketSessionBadge";
import SectorRotationBoard from "@/components/SectorRotationBoard";
import {
  buildPublicAuditSummary,
  formatAuditDate,
  formatAuditTime,
  type PublicAuditFields,
} from "@/lib/public-audit";
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
import { type HomeDashboardInitialData, useHomeDashboardViewModel } from "@/components/pages/useHomeDashboardViewModel";

const COUNTRY_FLAGS: Record<string, string> = { KR: "🇰🇷" };
const BRIEFING_TIMEOUT_MS = 16_000;
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

function hasUsableNumericValue(value: number | null | undefined) {
  return Number.isFinite(value) && Math.abs(value ?? 0) > 0.0001;
}

function hasUsableIndicator(indicator: MarketIndicator) {
  return hasUsableNumericValue(indicator.price);
}

function hasUsableIndexValue(index: { price?: number | null; current_price?: number | null }) {
  return hasUsableNumericValue(index.price ?? index.current_price ?? null);
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
  return formatAuditDate(value) || value || "";
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
  return formatAuditTime(value) || "";
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
  initialSectorPerformance = null,
  initialMarketSessions = null,
}: HomeDashboardInitialData) {
  const {
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
  } = useHomeDashboardViewModel({
    initialCountries,
    initialIndicators,
    initialBriefing,
    initialHeatmap,
    initialMovers,
    initialRadar,
    initialCountryReport,
  });

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
  const moversHasItems = (movers?.gainers.length ?? 0) > 0 || (movers?.losers.length ?? 0) > 0;
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
  const usableIndices = useMemo(
    () => selectedCountryItem?.indices.filter((index) => hasUsableIndexValue(index)) ?? [],
    [selectedCountryItem],
  );
  const hasDelayedIndices = (selectedCountryItem?.indices.length ?? 0) > 0 && usableIndices.length === 0;
  const visibleIndicators = useMemo(
    () => indicators.filter((indicator) => hasUsableIndicator(indicator)).slice(0, 4),
    [indicators],
  );
  const hasDelayedIndicators = indicators.length > 0 && visibleIndicators.length === 0;
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
  const reportClock = countryReport?.generated_at ? toInitialClock(countryReport.generated_at) : "";
  const nextDayForecast = countryReport?.next_day_forecast ?? null;
  const radarCount = radarData?.opportunities.length ?? 0;
  const topMover = movers?.gainers?.[0] ?? null;
  const weakestMover = movers?.losers?.[0] ?? null;
  const dashboardStatusLabel = marketView?.label || (reportLoading ? "시장 요약 준비 중" : "선별 관찰");

  return (
    <div className="dashboard-shell">
      <section className="dashboard-hero" aria-labelledby="dashboard-title">
        <div className="dashboard-hero-main">
          <div className="dashboard-kicker">
            <span>대시보드</span>
            <span>{selectedCountryItem ? `${COUNTRY_FLAGS[selectedCountry]} ${selectedCountryItem.name_local}` : selectedCountry}</span>
          </div>
          <h1 id="dashboard-title" className="dashboard-hero-title">
            오늘 시장에서 먼저 볼 것만 정리합니다.
          </h1>
          <p className="dashboard-hero-copy">{marketSummaryText}</p>

          <div className="dashboard-action-row">
            <Link href="/radar" className="ui-button-primary">
              <Radar aria-hidden className="h-4 w-4" />
              레이더 보기
              <ArrowRight aria-hidden className="h-4 w-4" />
            </Link>
            <Link href="/screener" className="ui-button-secondary">
              <BarChart3 aria-hidden className="h-4 w-4" />
              스크리너로 좁히기
            </Link>
            <button type="button" onClick={retryCurrentWorkspace} className="ui-button-ghost">
              <RefreshCw aria-hidden className="h-4 w-4" />
              다시 불러오기
            </button>
          </div>

          <div className="dashboard-meta-row" aria-label="대시보드 상태">
            {lastUpdated ? <span>최근 갱신 {lastUpdated}</span> : null}
            {reportClock ? <span>리포트 {reportClock}</span> : null}
            <span>오늘 포커스 {focusSlots.length}개</span>
            <span>레이더 {radarCount > 0 ? `${Math.min(radarCount, HOME_RADAR_LIMIT)}개` : "대기"}</span>
          </div>

          {countries.length > 1 ? (
            <div className="dashboard-country-row" aria-label="시장 선택">
              {countries.map((country) => (
                <button
                  key={country.code}
                  type="button"
                  onClick={() => void loadCountryWorkspace(country.code)}
                  className={`dashboard-country-button ${
                    selectedCountry === country.code ? "dashboard-country-button-active" : ""
                  }`}
                  aria-pressed={selectedCountry === country.code}
                >
                  {COUNTRY_FLAGS[country.code]} {country.name_local}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <aside className="dashboard-hero-panel" aria-label="현재 시장 핵심 신호">
          <div className="dashboard-hero-panel-top">
            <div>
              <span className="dashboard-panel-label">현재 시장</span>
              <div className="mt-2 text-xl font-semibold text-text">{dashboardStatusLabel}</div>
            </div>
            {marketView ? <span className={`status-token ${statusTone(marketView.stance)}`}>{marketView.label}</span> : null}
          </div>
          <div className="dashboard-session-wrap">
            <MarketSessionBadge sessions={initialMarketSessions} />
          </div>
          <div className="dashboard-stat-grid">
            <div className="dashboard-stat">
              <span className="dashboard-stat-label">다음 상방 확률</span>
              <strong className="dashboard-stat-value">
                {nextDayForecast ? `${nextDayForecast.up_probability.toFixed(1)}%` : "대기"}
              </strong>
              <span className={`dashboard-stat-detail ${nextDayForecast ? changeColor(nextDayForecast.predicted_return_pct) : ""}`}>
                {nextDayForecast ? `기대 ${formatPct(nextDayForecast.predicted_return_pct)}` : "예측 수집 중"}
              </span>
            </div>
            <div className="dashboard-stat">
              <span className="dashboard-stat-label">상승 상위</span>
              <strong className="dashboard-stat-value">{topMover?.ticker ?? "대기"}</strong>
              <span className={`dashboard-stat-detail ${topMover ? "text-positive" : ""}`}>
                {topMover ? `+${topMover.change_pct.toFixed(2)}%` : "등락 집계 중"}
              </span>
            </div>
            <div className="dashboard-stat">
              <span className="dashboard-stat-label">하락 상위</span>
              <strong className="dashboard-stat-value">{weakestMover?.ticker ?? "대기"}</strong>
              <span className={`dashboard-stat-detail ${weakestMover ? "text-negative" : ""}`}>
                {weakestMover ? `${weakestMover.change_pct.toFixed(2)}%` : "등락 집계 중"}
              </span>
            </div>
          </div>
        </aside>
      </section>

      <section className="dashboard-audit-band" aria-label="공개 데이터 상태">
        <PublicAuditStrip meta={dashboardAuditMeta} />
        <p>{dashboardSummary}</p>
      </section>

      {workspaceDelays.length > 0 ? (
        <WorkspaceStateCard
          kind="partial"
          eyebrow="부분 업데이트"
          title="일부 계산이 더 필요합니다"
          message={`${workspaceDelays.join(", ")} 섹션은 계산이 길어져 현재 확보된 데이터부터 먼저 보여주고 있습니다.`}
          actionLabel="현재 시장 다시 불러오기"
          onAction={retryCurrentWorkspace}
        />
      ) : null}

      <section className="dashboard-two-column" aria-labelledby="dashboard-signals-title">
        <div className="dashboard-panel dashboard-panel-main">
          <div className="dashboard-section-header">
            <div>
              <h2 id="dashboard-signals-title" className="dashboard-section-title">시장 신호</h2>
              <p className="dashboard-section-copy">지수, 거시 지표, 다음 거래일 신호를 한 번에 읽습니다.</p>
            </div>
            {marketView ? <span className={`dashboard-soft-token ${statusTone(marketView.stance)}`}>{marketView.label}</span> : null}
          </div>

          {macroClaims.length > 0 ? (
            <div className="dashboard-signal-grid">
              {macroClaims.map((claim) => (
                <div key={`${claim.source}-${claim.metric}`} className="dashboard-signal-tile">
                  <span className="dashboard-tile-label">{claim.metric}</span>
                  <strong className={`dashboard-tile-value ${macroClaimTone(claim.direction)}`}>
                    {formatMacroClaimValue(claim)}
                  </strong>
                  <span className="dashboard-tile-detail">
                    {claim.source}
                    {formatMacroClaimDate(claim.published_at) ? ` · ${formatMacroClaimDate(claim.published_at)}` : ""}
                    {` · 근거 ${Math.round((claim.confidence ?? 0) * 100)}%`}
                  </span>
                </div>
              ))}
            </div>
          ) : null}

          <div className="dashboard-signal-grid">
            {usableIndices.map((index) => (
              <div key={index.ticker} className="dashboard-signal-tile">
                <span className="dashboard-tile-label">{index.name}</span>
                <strong className="dashboard-tile-value">
                  {(index.price ?? index.current_price ?? 0).toLocaleString()}
                </strong>
                <span className={`dashboard-tile-detail ${changeColor(index.change_pct ?? 0)}`}>
                  {formatPct(index.change_pct ?? 0)}
                </span>
              </div>
            ))}
            {nextDayForecast ? (
              <div className="dashboard-signal-tile dashboard-signal-tile-accent">
                <span className="dashboard-tile-label">다음 거래일 시그널</span>
                <strong className="dashboard-tile-value">상방 {nextDayForecast.up_probability.toFixed(1)}%</strong>
                <span className={`dashboard-tile-detail ${changeColor(nextDayForecast.predicted_return_pct)}`}>
                  기대 {formatPct(nextDayForecast.predicted_return_pct)}
                </span>
              </div>
            ) : null}
          </div>

          {hasDelayedIndices ? (
            <p className="dashboard-alert-band">
              대표 지수 실시간 수집이 늦어져 거시 지표와 다음 거래일 시그널을 먼저 보여주고 있습니다.
            </p>
          ) : null}

          {visibleIndicators.length > 0 ? (
            <div className="dashboard-indicator-row" aria-label="보조 지표">
              {visibleIndicators.map((indicator) => (
                <div key={indicator.name}>
                  <span>{indicator.name}</span>
                  <strong>{indicatorLabel(indicator)}</strong>
                  <em className={changeColor(indicator.change_pct ?? 0)}>{formatPct(indicator.change_pct ?? 0)}</em>
                </div>
              ))}
            </div>
          ) : null}
          {hasDelayedIndicators ? (
            <p className="dashboard-alert-band">
              환율·원자재·가상자산 보조 지표는 외부 원본 응답이 늦어지는 동안 숨기고, 확보된 시장 요약만 먼저 유지합니다.
            </p>
          ) : null}
        </div>

        <div className="dashboard-panel">
          <div className="dashboard-section-header">
            <div>
              <h2 className="dashboard-section-title">오늘의 포커스</h2>
              <p className="dashboard-section-copy">바로 볼 종목과 일정만 남겼습니다.</p>
            </div>
            {briefing?.research_archive ? <span className="dashboard-soft-token">리서치 {briefing.research_archive.todays_reports}건</span> : null}
          </div>

          {briefingLoading ? (
            <WorkspaceLoadingCard
              title="오늘의 포커스를 추리고 있습니다"
              message="브리핑, 핵심 종목, 가까운 일정 중 먼저 확인할 항목만 다시 묶는 중입니다."
              className="min-h-[230px]"
            />
          ) : focusSlots.length > 0 ? (
            <div className="dashboard-list">
              {focusSlots.map((slot) => {
                if (slot.kind === "focus") {
                  const item = slot.item;
                  return (
                    <Link key={slot.key} href={`/stock/${encodeURIComponent(item.ticker)}`} className="dashboard-list-link">
                      <span className="dashboard-list-main">
                        <strong>{item.name}</strong>
                        <span>{item.ticker} · {item.sector}</span>
                      </span>
                      <span className="dashboard-list-metric">
                        <strong className={changeColor(item.predicted_return_pct)}>{formatPct(item.predicted_return_pct)}</strong>
                        <span>상방 {item.up_probability.toFixed(1)}%</span>
                      </span>
                    </Link>
                  );
                }

                if (slot.kind === "event") {
                  const event = slot.item;
                  return (
                    <div key={slot.key} className="dashboard-list-row">
                      <span className="dashboard-list-main">
                        <strong>{event.title}</strong>
                        <span>{event.summary}</span>
                      </span>
                      <span className={`dashboard-soft-token ${impactTone(event.impact)}`}>{event.date}</span>
                    </div>
                  );
                }

                return (
                  <div key={slot.key} className="dashboard-list-row">
                    <span className="dashboard-list-main">
                      <strong>{slot.title}</strong>
                      <span>{slot.summary}</span>
                    </span>
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
      </section>

      <section className="dashboard-two-column dashboard-two-column-wide" aria-labelledby="dashboard-map-title">
        <div className="dashboard-panel dashboard-board">
          <div className="dashboard-section-header">
            <div>
              <h2 id="dashboard-map-title" className="dashboard-section-title">시장 히트맵</h2>
              <p className="dashboard-section-copy">크기는 시가총액, 색은 등락률입니다.</p>
            </div>
            <span className="dashboard-soft-token">{selectedCountry} 히트맵</span>
          </div>
          <div className="dashboard-heatmap-frame">
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

        <div className="dashboard-stack">
          {initialSectorPerformance && initialSectorPerformance.length > 0 ? (
            <SectorRotationBoard data={initialSectorPerformance} countryCode={selectedCountry} />
          ) : null}

          <div className="dashboard-panel">
            <div className="dashboard-section-header">
              <div>
                <h2 className="dashboard-section-title">상승·하락 상위</h2>
                <p className="dashboard-section-copy">강한 종목과 약한 종목을 같이 봅니다.</p>
              </div>
            </div>
            {moversLoading ? (
              <WorkspaceLoadingCard
                title="상승·하락 상위를 정리하고 있습니다"
                message="강도가 큰 종목과 약한 종목을 분리해 순위 보드로 묶는 중입니다."
                className="min-h-[240px]"
              />
            ) : movers && moversHasItems ? (
              <div className="dashboard-movers-grid">
                <div>
                  <h3 className="dashboard-group-title text-positive">
                    <TrendingUp aria-hidden className="h-4 w-4" />
                    상승 상위
                  </h3>
                  <div className="dashboard-list dashboard-list-compact">
                    {movers.gainers.slice(0, 5).map((stock) => (
                      <Link key={stock.ticker} href={`/stock/${encodeURIComponent(stock.ticker)}`} className="dashboard-mover-row">
                        <span>
                          <strong>{stock.ticker}</strong>
                          <em>{stock.name}</em>
                        </span>
                        <b className="text-positive">+{stock.change_pct.toFixed(2)}%</b>
                      </Link>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="dashboard-group-title text-negative">
                    <TrendingDown aria-hidden className="h-4 w-4" />
                    하락 상위
                  </h3>
                  <div className="dashboard-list dashboard-list-compact">
                    {movers.losers.slice(0, 5).map((stock) => (
                      <Link key={stock.ticker} href={`/stock/${encodeURIComponent(stock.ticker)}`} className="dashboard-mover-row">
                        <span>
                          <strong>{stock.ticker}</strong>
                          <em>{stock.name}</em>
                        </span>
                        <b className="text-negative">{stock.change_pct.toFixed(2)}%</b>
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <WorkspaceStateCard
                eyebrow="상위 집계 지연"
                title="등락 상위 집계가 아직 준비되지 않았습니다"
                message={moversError || "상승·하락 상위 데이터가 아직 없습니다."}
                onAction={retryCurrentWorkspace}
                tone="warning"
              />
            )}
          </div>
        </div>
      </section>

      <section className="dashboard-two-column" aria-labelledby="dashboard-radar-title">
        <div className="dashboard-panel dashboard-board">
          <div className="dashboard-section-header">
            <div>
              <h2 id="dashboard-radar-title" className="dashboard-section-title">강한 셋업</h2>
              <p className="dashboard-section-copy">점수와 실행력이 높은 후보를 먼저 봅니다.</p>
            </div>
            <Link href="/radar" className="dashboard-inline-link">
              전체 보기
              <ArrowRight aria-hidden className="h-4 w-4" />
            </Link>
          </div>
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

        <div className="dashboard-stack">
          <div className="dashboard-panel">
            <div className="dashboard-section-header">
              <div>
                <h2 className="dashboard-section-title">주요 뉴스</h2>
                <p className="dashboard-section-copy">선택 시장 리포트에서 뽑은 핵심 기사입니다.</p>
              </div>
              {reportLoading ? <span className="dashboard-soft-token">불러오는 중</span> : null}
            </div>
            <div className="dashboard-list">
              {topNews.map((item) => (
                <a key={`${item.source}-${item.url}`} href={item.url} target="_blank" rel="noreferrer" className="dashboard-list-link">
                  <span className="dashboard-list-main">
                    <strong>{item.title}</strong>
                    <span>{item.source} · {item.published}</span>
                  </span>
                  <ExternalLink aria-hidden className="h-4 w-4 shrink-0 text-text-secondary" />
                </a>
              ))}
              {!reportLoading && topNews.length === 0 ? (
                <WorkspaceStateCard
                  eyebrow={reportError ? "뉴스 지연" : "핵심 기사 보강 중"}
                  title={reportError ? "핵심 기사 연결이 늦어지고 있습니다" : "오늘 핵심 기사 목록을 준비하고 있습니다"}
                  message={
                    reportError ||
                    "시장 요약은 먼저 준비됐고, 핵심 기사 연결은 이어서 보강됩니다. 잠시 뒤 다시 열면 기사 목록이 채워질 수 있습니다."
                  }
                  onAction={reportError ? retryCurrentWorkspace : undefined}
                  tone={reportError ? "warning" : "neutral"}
                />
              ) : null}
            </div>
          </div>

          <div className="dashboard-panel">
            <div className="dashboard-section-header">
              <div>
                <h2 className="dashboard-section-title">상위 종목</h2>
                <p className="dashboard-section-copy">선택 국가 리포트에서 상단에 위치한 종목입니다.</p>
              </div>
              <LineChart aria-hidden className="h-5 w-5 text-accent" />
            </div>
            <div className="dashboard-list">
              {topStocks.map((stock) => (
                <Link key={stock.ticker} href={`/stock/${encodeURIComponent(stock.ticker)}`} className="dashboard-list-link">
                  <span className="dashboard-list-main">
                    <strong>{stock.name}</strong>
                    <span>{stock.ticker} · {stock.reason}</span>
                  </span>
                  <span className="dashboard-list-metric">
                    <strong>점수 {stock.score.toFixed(1)}</strong>
                    <span className={changeColor(stock.change_pct)}>{formatPct(stock.change_pct)}</span>
                  </span>
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
