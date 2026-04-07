"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import { WarningBanner } from "@/components/ErrorBanner";
import ForecastDeltaCard from "@/components/ForecastDeltaCard";
import HistoricalPatternCard from "@/components/HistoricalPatternCard";
import MarketRegimeCard from "@/components/MarketRegimeCard";
import MetricValueCard from "@/components/MetricValueCard";
import PageHeader from "@/components/PageHeader";
import PivotLevelsCard from "@/components/PivotLevelsCard";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import SetupBacktestCard from "@/components/SetupBacktestCard";
import TradePlanCard from "@/components/TradePlanCard";
import AnalystConsensus from "@/components/charts/AnalystConsensus";
import CandlestickChart from "@/components/charts/CandlestickChart";
import FreeKrForecastCard from "@/components/charts/FreeKrForecastCard";
import EarningsSurprise from "@/components/charts/EarningsSurprise";
import NextDayForecastCard from "@/components/charts/NextDayForecastCard";
import PriceChart from "@/components/charts/PriceChart";
import ScoreBreakdown from "@/components/charts/ScoreBreakdown";
import ScoreRadial from "@/components/charts/ScoreRadial";
import TechnicalSummary from "@/components/charts/TechnicalSummary";
import { useToast } from "@/components/Toast";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { api } from "@/lib/api";
import { buildPublicAuditSummary } from "@/lib/public-audit";
import type { StockDetail, WatchlistItem } from "@/lib/types";
import { changeColor, formatMarketCap, formatPct, formatPrice } from "@/lib/utils";
import { useStockDetailFlow } from "@/components/pages/useStockDetailFlow";

const WATCHLIST_STATUS_TIMEOUT_MS = 6_000;

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "종목 상세를 불러오지 못했습니다.");
}

function SummaryBulletList({ items }: { items: string[] }) {
  return (
    <div className="space-y-2 text-sm text-text-secondary">
      {items.map((item) => (
        <div key={item} className="flex gap-2">
          <span className="mt-1 h-1.5 w-1.5 rounded-full bg-accent/80 shrink-0" />
          <span>{item}</span>
        </div>
      ))}
    </div>
  );
}

interface StockPageClientProps {
  initialTicker: string;
  initialData?: StockDetail | null;
}

export default function StockPageClient({ initialTicker, initialData = null }: StockPageClientProps) {
  const router = useRouter();
  const [chartType, setChartType] = useState<"line" | "candle">("line");
  const [watchlistEntry, setWatchlistEntry] = useState<WatchlistItem | null>(null);
  const [watchlistSyncing, setWatchlistSyncing] = useState(false);
  const { toast } = useToast();
  const { session } = useAuth();
  const {
    stock,
    loading,
    error,
    techSummary,
    pivotPoints,
    forecastDelta,
    chartPeriod,
    chartData,
    changeChartPeriod,
    composite,
  } = useStockDetailFlow({
    initialTicker,
    initialData,
  });

  const refreshWatchlistEntry = async (tickerValue: string) => {
    if (!session) {
      setWatchlistEntry(null);
      return;
    }

    setWatchlistSyncing(true);
    try {
      const entries = await api.getWatchlist({ timeoutMs: WATCHLIST_STATUS_TIMEOUT_MS });
      setWatchlistEntry(
        entries.find((item) => item.ticker.toUpperCase() === tickerValue.toUpperCase()) ?? null,
      );
    } catch (error) {
      console.error(error);
      setWatchlistEntry(null);
    } finally {
      setWatchlistSyncing(false);
    }
  };

  useEffect(() => {
    if (!stock?.ticker || !session) {
      setWatchlistEntry(null);
      setWatchlistSyncing(false);
      return;
    }
    void refreshWatchlistEntry(stock.ticker);
  }, [session, stock?.ticker]);

  const addToWatchlist = async () => {
    if (!stock) {
      return;
    }
    if (!session) {
      toast("워치리스트는 로그인 후 사용할 수 있습니다.", "info");
      router.push(`/auth?next=${encodeURIComponent(`/stock/${stock.ticker}`)}`);
      return;
    }
    try {
      await api.addWatchlist(stock.ticker, stock.country_code);
      await refreshWatchlistEntry(stock.ticker);
      toast(`${stock.ticker} 종목을 워치리스트에 추가했습니다.`, "success");
    } catch (error) {
      console.error(error);
      toast("워치리스트 추가에 실패했습니다.", "error");
    }
  };

  const handleTrackingAction = async () => {
    if (!stock) {
      return;
    }

    if (!session) {
      toast("관심종목과 심화 추적은 로그인 후 사용할 수 있습니다.", "info");
      router.push(`/auth?next=${encodeURIComponent(`/stock/${stock.ticker}`)}`);
      return;
    }

    if (!watchlistEntry) {
      await addToWatchlist();
      return;
    }

    if (watchlistEntry.tracking_enabled) {
      router.push(`/watchlist/${encodeURIComponent(stock.ticker)}`);
      return;
    }

    try {
      setWatchlistSyncing(true);
      await api.enableWatchlistTracking(stock.ticker, stock.country_code);
      toast(`${stock.ticker} 심화 추적을 시작했습니다.`, "success");
      await refreshWatchlistEntry(stock.ticker);
      router.push(`/watchlist/${encodeURIComponent(stock.ticker)}`);
    } catch (error) {
      console.error(error);
      toast("심화 추적 시작에 실패했습니다.", "error");
      setWatchlistSyncing(false);
    }
  };

  const week52Progress = useMemo(() => {
    if (!stock?.week52_low || !stock?.week52_high || stock.week52_high <= stock.week52_low) return null;
    return ((stock.current_price - stock.week52_low) / (stock.week52_high - stock.week52_low)) * 100;
  }, [stock]);

  if (loading) {
    return (
      <div className="page-shell space-y-4">
        <PageHeader
          variant="compact"
          eyebrow="종목 상세"
          title={initialTicker.toUpperCase()}
          description="가격 흐름, 기술 신호, 공개 판단 요약을 먼저 정리하고 세부 분석을 이어서 불러옵니다."
        />
        <WorkspaceLoadingCard
          title="종목 핵심 수치를 불러오고 있습니다"
          message="현재가와 공개 판단 요약, 관심종목 상태를 먼저 확인할 수 있도록 준비하고 있습니다."
          className="min-h-[180px]"
        />
        <WorkspaceLoadingCard
          title="차트와 세부 분석을 이어서 준비하고 있습니다"
          message="기술 요약, 예측 차트, 매수·매도 가이드가 순서대로 이어집니다."
          className="min-h-[260px]"
        />
      </div>
    );
  }

  if (!stock && error) {
    return (
      <div className="page-shell space-y-4">
        <PageHeader
          variant="compact"
          eyebrow="종목 상세"
          title={initialTicker.toUpperCase()}
          description="종목 상세 응답이 아직 도착하지 않아, 다시 불러오기로 최신 스냅샷을 재요청합니다."
          actions={
            <Link href="/" className="action-chip-secondary">
              홈으로
            </Link>
          }
        />
        <WorkspaceStateCard
          kind="blocking"
          eyebrow="응답 지연"
          title="종목 상세를 아직 불러오지 못했습니다"
          message={error.message}
          actionLabel="다시 시도"
          onAction={() => window.location.reload()}
        />
      </div>
    );
  }

  if (!stock) {
    return (
      <div className="page-shell">
        <WorkspaceStateCard
          kind="blocking"
          eyebrow="종목 없음"
          title="종목 정보를 찾을 수 없습니다"
          message="티커를 다시 확인한 뒤 검색 또는 홈 화면에서 다른 종목으로 이동해 주세요."
          actionLabel="홈으로"
          onAction={() => router.push("/")}
        />
      </div>
    );
  }

  const priceKey = stock.country_code;
  const bsg = stock.buy_sell_guide;
  const displayedData = chartData.length > 0 ? chartData : stock.price_history;
  const ma20 = chartData.length === 0 ? stock.technical?.ma_20 : undefined;
  const ma60 = chartData.length === 0 ? stock.technical?.ma_60 : undefined;
  const scoreCategories = [
    { label: "기초체력", data: stock.score.fundamental },
    { label: "밸류에이션", data: stock.score.valuation },
    { label: "성장과 모멘텀", data: stock.score.growth_momentum },
    { label: "애널리스트", data: stock.score.analyst },
    { label: "리스크", data: stock.score.risk },
  ];
  const compositeCategories = composite
    ? [
        { label: "기초체력", data: composite.fundamental, color: "bg-blue-500" },
        { label: "밸류에이션", data: composite.valuation, color: "bg-indigo-500" },
        { label: "성장과 모멘텀", data: composite.growth_momentum, color: "bg-emerald-500" },
        { label: "애널리스트", data: composite.analyst, color: "bg-amber-500" },
        { label: "리스크", data: composite.risk, color: "bg-rose-500" },
        { label: "기술 지표", data: composite.technical, color: "bg-cyan-500" },
      ]
    : [];
  const overviewMetrics = [
    { label: "시가총액", value: formatMarketCap(stock.market_cap, priceKey) },
    { label: "P/E", value: stock.pe_ratio?.toFixed(2) ?? "없음" },
    { label: "P/B", value: stock.pb_ratio?.toFixed(2) ?? "없음" },
    { label: "EV/EBITDA", value: stock.ev_ebitda?.toFixed(2) ?? "없음" },
  ];
  const guideLevels = [
    { label: "매수 하단", value: formatPrice(bsg.buy_zone_low, priceKey), toneClass: "bg-blue-500/10", valueClassName: "font-bold text-blue-500" },
    { label: "매수 상단", value: formatPrice(bsg.buy_zone_high, priceKey), toneClass: "bg-blue-500/10", valueClassName: "font-bold text-blue-500" },
    { label: "적정가", value: formatPrice(bsg.fair_value, priceKey), toneClass: "bg-emerald-500/10", valueClassName: "font-bold text-emerald-500" },
    { label: "매도 하단", value: formatPrice(bsg.sell_zone_low, priceKey), toneClass: "bg-red-500/10", valueClassName: "font-bold text-red-500" },
    { label: "매도 상단", value: formatPrice(bsg.sell_zone_high, priceKey), toneClass: "bg-red-500/10", valueClassName: "font-bold text-red-500" },
  ];
  const financialMetrics = [
    { label: "PEG", value: stock.peg_ratio?.toFixed(2) ?? "없음" },
    { label: "배당수익률", value: stock.dividend.dividend_yield != null ? `${(stock.dividend.dividend_yield * 100).toFixed(2)}%` : "없음" },
    { label: "배당성향", value: stock.dividend.payout_ratio != null ? `${(stock.dividend.payout_ratio * 100).toFixed(2)}%` : "없음" },
    { label: "최근 분기 수", value: String(stock.financials.length) },
  ];
  const publicSummaryCards = stock.public_summary ? [
    { title: "근거", items: stock.public_summary.evidence_for },
    { title: "반대 근거", items: stock.public_summary.evidence_against },
    { title: "지금 바로 사지 않는 이유", items: stock.public_summary.why_not_buy_now },
    { title: "무효화 조건", items: stock.public_summary.thesis_breakers },
  ].filter((section) => section.items.length > 0) : [];
  const stockAuditSummary = buildPublicAuditSummary(stock, {
    defaultSummary: "종목 상세는 최신 스냅샷과 공개 판단 요약을 기준으로 먼저 정리합니다.",
  });
  const watchlistActionLabel = watchlistSyncing
    ? "관심종목 확인 중"
    : watchlistEntry?.tracking_enabled
      ? "심화 추적 보기"
      : watchlistEntry
        ? "심화 추적 시작"
        : "관심종목 추가";

  return (
    <div className="page-shell">
      <PageHeader
        variant="compact"
        eyebrow="종목 상세"
        title={stock.name}
        description={`${stock.ticker} · ${stock.sector} · ${stock.industry}`}
        meta={
          <>
            <span className="info-chip">{formatPrice(stock.current_price, priceKey)}</span>
            <span className={`info-chip ${changeColor(stock.change_pct)}`}>{formatPct(stock.change_pct)}</span>
            <span className="info-chip">시가총액 {formatMarketCap(stock.market_cap, priceKey)}</span>
          </>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Link href="/" className="action-chip-secondary">
              홈으로
            </Link>
            <button
              onClick={handleTrackingAction}
              disabled={watchlistSyncing}
              className="action-chip-primary disabled:cursor-wait disabled:opacity-60"
            >
              {watchlistActionLabel}
            </button>
          </div>
        }
      />
      {(stock.generated_at || stock.partial || stock.fallback_reason || (stock.errors && stock.errors.length > 0)) ? (
        <div className="card !p-4 space-y-3">
          <PublicAuditStrip meta={stock} />
          {stockAuditSummary ? (
            <p className="text-sm leading-relaxed text-text-secondary">{stockAuditSummary}</p>
          ) : null}
          {stock.errors && stock.errors.length > 0 ? <WarningBanner codes={stock.errors} /> : null}
        </div>
      ) : null}

      <div className="card !p-4 space-y-3">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-semibold">관심종목 · 심화 추적</h2>
            <p className="mt-1 text-sm leading-6 text-text-secondary">
              종목을 먼저 관심종목에 저장하고, 필요한 경우 심화 추적으로 올려 최근 예측 변화와 적중 기록을 이어서 볼 수 있습니다.
            </p>
          </div>
          <button
            onClick={handleTrackingAction}
            disabled={watchlistSyncing}
            className="action-chip-primary disabled:cursor-wait disabled:opacity-60"
          >
            {watchlistActionLabel}
          </button>
        </div>
        <div className="text-sm text-text-secondary">
          {!session
            ? "로그인 후 관심종목과 심화 추적을 계정별로 저장할 수 있습니다."
            : watchlistEntry?.tracking_enabled
              ? "이미 심화 추적 중인 종목입니다. 추적 화면에서 최근 예측 변화와 현재 판단 근거를 이어서 확인할 수 있습니다."
              : watchlistEntry
                ? "이미 관심종목에 들어 있습니다. 심화 추적을 시작하면 최근 예측 변화와 적중 기록이 추가됩니다."
                : "아직 관심종목에 없는 종목입니다. 먼저 저장한 뒤 심화 추적으로 이어갈 수 있습니다."}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {overviewMetrics.map((item) => (
          <div key={item.label} className="card !p-4">
            <div className="text-xs text-text-secondary">{item.label}</div>
            <div className="font-bold mt-2">{item.value}</div>
          </div>
        ))}
      </div>

      {stock.public_summary ? (
        <div className="card space-y-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="space-y-1">
              <h2 className="font-semibold">판단 요약</h2>
              <p className="text-sm text-text-secondary">
                공개 요약은 상승 근거보다 반대 조건과 실패 시그널을 먼저 읽도록 정리했습니다.
              </p>
            </div>
            <div className="min-w-[260px] max-w-[360px] rounded-xl border border-border bg-accent/5 px-4 py-3">
              <div className="text-xs text-text-secondary">신뢰 메모</div>
              <p className="mt-2 text-sm leading-relaxed text-text">{stock.public_summary.confidence_note}</p>
            </div>
          </div>

          <p className="text-sm leading-relaxed whitespace-pre-line">{stock.public_summary.summary}</p>

          {publicSummaryCards.length > 0 ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              {publicSummaryCards.map((section) => (
                <div key={section.title} className="rounded-xl border border-border px-4 py-4">
                  <h3 className="text-sm font-semibold mb-3">{section.title}</h3>
                  <SummaryBulletList items={section.items} />
                </div>
              ))}
            </div>
          ) : null}

          <div className="rounded-xl border border-border bg-border/20 px-4 py-4">
            <div className="text-xs text-text-secondary">데이터 품질</div>
            <p className="mt-2 text-sm leading-relaxed text-text">{stock.public_summary.data_quality}</p>
          </div>
        </div>
      ) : null}

      {stock.analysis_summary ? (
        <div className="card">
          <h2 className="font-semibold mb-3">상세 분석</h2>
          <p className="text-sm leading-relaxed whitespace-pre-line">{stock.analysis_summary}</p>
        </div>
      ) : null}

      <div className="card">
        <div className="flex items-center justify-between mb-3 gap-4 flex-wrap">
          <h2 className="font-semibold">가격 차트</h2>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex gap-1">
              {[{ label: "1M", value: "1mo" }, { label: "3M", value: "3mo" }, { label: "6M", value: "6mo" }, { label: "1Y", value: "1y" }].map((period) => (
                <button key={period.value} onClick={() => changeChartPeriod(period.value)} className={`px-2 py-0.5 text-xs rounded ${chartPeriod === period.value ? "bg-accent text-white" : "bg-border text-text-secondary hover:text-text"}`}>{period.label}</button>
              ))}
            </div>
            <div className="flex gap-1 ml-2 border-l border-border pl-2">
              <button onClick={() => setChartType("line")} className={`px-2 py-0.5 text-xs rounded ${chartType === "line" ? "bg-accent text-white" : "bg-border text-text-secondary hover:text-text"}`}>라인</button>
              <button onClick={() => setChartType("candle")} className={`px-2 py-0.5 text-xs rounded ${chartType === "candle" ? "bg-accent text-white" : "bg-border text-text-secondary hover:text-text"}`}>캔들</button>
            </div>
          </div>
        </div>

        {chartType === "candle" ? (
          <CandlestickChart data={displayedData} />
        ) : (
          <PriceChart
            data={displayedData}
            ma20={ma20}
            ma60={ma60}
            buyZone={{ low: bsg.buy_zone_low, high: bsg.buy_zone_high }}
            sellZone={{ low: bsg.sell_zone_low, high: bsg.sell_zone_high }}
            fairValue={bsg.fair_value}
            nextDayForecast={stock.next_day_forecast}
            historicalPatternForecast={stock.historical_pattern_forecast}
          />
        )}

        <div className="flex gap-4 mt-2 text-xs text-text-secondary flex-wrap">
          <span><span className="inline-block w-3 h-0.5 bg-accent mr-1" /> 종가</span>
          <span><span className="inline-block w-3 h-0.5 bg-yellow-500 mr-1" /> MA20</span>
          <span><span className="inline-block w-3 h-0.5 bg-purple-500 mr-1" /> MA60</span>
          <span><span className="inline-block w-3 h-0.5 bg-emerald-500 mr-1" /> 매수 구간</span>
          <span><span className="inline-block w-3 h-0.5 bg-sky-500 mr-1" /> 과거 유사 국면 경로</span>
        </div>
      </div>

      {stock.next_day_forecast ? <NextDayForecastCard forecast={stock.next_day_forecast} assetLabel={stock.name} priceKey={priceKey} /> : null}
      {stock.free_kr_forecast ? <FreeKrForecastCard forecast={stock.free_kr_forecast} assetLabel={stock.name} priceKey={priceKey} /> : null}
      {forecastDelta ? <ForecastDeltaCard data={forecastDelta} /> : null}

      {stock.historical_pattern_warning ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-600">
          과거 유사 국면 예측을 계산하는 중 일부 입력이 부족했습니다. 기본 예측은 계속 표시되며, 상세 경고는 다음과 같습니다: {stock.historical_pattern_warning}
        </div>
      ) : null}

      {(stock.historical_pattern_forecast || stock.setup_backtest) ? (
        <div className="grid grid-cols-1 gap-6">
          {stock.historical_pattern_forecast ? (
            <HistoricalPatternCard forecast={stock.historical_pattern_forecast} priceKey={priceKey} />
          ) : null}
          {stock.setup_backtest ? <SetupBacktestCard backtest={stock.setup_backtest} /> : null}
        </div>
      ) : null}

      {(stock.market_regime || stock.trade_plan) ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {stock.market_regime ? <MarketRegimeCard regime={stock.market_regime} title="시장 국면" /> : null}
          {stock.trade_plan ? <TradePlanCard plan={stock.trade_plan} priceKey={priceKey} /> : null}
        </div>
      ) : null}

      <div className="card">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div>
            <h2 className="font-semibold">매수 / 매도 가이드</h2>
            <p className="text-sm text-text-secondary mt-1">{bsg.summary}</p>
          </div>
          <span className={`text-sm px-3 py-1 rounded-full font-medium ${bsg.confidence_grade === "A" ? "bg-emerald-500/20 text-emerald-500" : bsg.confidence_grade === "B" ? "bg-yellow-500/20 text-yellow-500" : "bg-red-500/20 text-red-500"}`}>신뢰 등급 {bsg.confidence_grade}</span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
          {guideLevels.map((item) => (
            <MetricValueCard
              key={item.label}
              label={item.label}
              value={item.value}
              toneClass={item.toneClass}
              valueClassName={item.valueClassName}
            />
          ))}
        </div>

        <div className="text-sm text-text-secondary">손익비: <strong>{bsg.risk_reward_ratio.toFixed(2)}</strong></div>
        {bsg.methodology.length > 0 ? (
          <div className="mt-3 text-xs text-text-secondary space-y-1">
            {bsg.methodology.map((method, index) => (
              <div key={index}>• {method.name}: {formatPrice(method.value, priceKey)} (가중치 {(method.weight * 100).toFixed(0)}%) - {method.details}</div>
            ))}
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {techSummary ? (
          <div className="card">
            <h2 className="font-semibold mb-3">기술적 요약</h2>
            <TechnicalSummary data={techSummary} />
          </div>
        ) : null}

        {pivotPoints ? (
          <div className="card">
            <h2 className="font-semibold mb-3">피벗 포인트</h2>
            <div className="grid grid-cols-2 gap-4">
              <PivotLevelsCard title="클래식" levels={pivotPoints.classic} />
              <PivotLevelsCard title="피보나치" levels={pivotPoints.fibonacci} />
            </div>
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {(stock.analyst_ratings.buy + stock.analyst_ratings.hold + stock.analyst_ratings.sell) > 0 ? (
          <div className="card">
            <h2 className="font-semibold mb-3">애널리스트 의견</h2>
            <AnalystConsensus
              buy={stock.analyst_ratings.buy}
              hold={stock.analyst_ratings.hold}
              sell={stock.analyst_ratings.sell}
              targetLow={stock.analyst_ratings.target_low ?? null}
              targetMean={stock.analyst_ratings.target_mean ?? null}
              targetHigh={stock.analyst_ratings.target_high ?? null}
              currentPrice={stock.current_price}
            />
          </div>
        ) : null}

        {stock.earnings_history.length > 0 ? (
          <div className="card">
            <h2 className="font-semibold mb-3">실적 서프라이즈</h2>
            <EarningsSurprise data={stock.earnings_history.map((item) => ({ date: item.date, eps_estimate: item.eps_estimate ?? null, eps_actual: item.eps_actual ?? null, surprise_pct: item.surprise_pct ?? null }))} />
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="font-semibold mb-3">52주 범위</h2>
          {stock.week52_low != null && stock.week52_high != null ? (
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span>{formatPrice(stock.week52_low, priceKey)}</span>
                <span>{formatPrice(stock.week52_high, priceKey)}</span>
              </div>
              <div className="h-2 rounded-full bg-border relative overflow-hidden">
                <div className="absolute inset-y-0 left-0 bg-accent rounded-full" style={{ width: `${Math.min(100, Math.max(0, week52Progress ?? 0))}%` }} />
              </div>
              <div className="text-sm text-text-secondary">현재가 {formatPrice(stock.current_price, priceKey)} · 범위 내 위치 {week52Progress != null ? `${week52Progress.toFixed(1)}%` : "없음"}</div>
            </div>
          ) : (
            <div className="text-sm text-text-secondary">52주 범위를 계산할 데이터가 부족합니다.</div>
          )}
        </div>

        <div className="card">
          <h2 className="font-semibold mb-3">재무와 배당</h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            {financialMetrics.map((item) => (
              <MetricValueCard key={item.label} label={item.label} value={item.value} />
            ))}
          </div>
        </div>
      </div>

      {stock.financials.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-3">최근 재무 스냅샷</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead>
                <tr className="text-left text-text-secondary border-b border-border">
                  <th className="pb-2 pr-4">기간</th>
                  <th className="pb-2 pr-4 text-right">매출</th>
                  <th className="pb-2 pr-4 text-right">영업이익</th>
                  <th className="pb-2 pr-4 text-right">순이익</th>
                  <th className="pb-2 pr-4 text-right">EBITDA</th>
                  <th className="pb-2 pr-4 text-right">FCF</th>
                </tr>
              </thead>
              <tbody>
                {stock.financials.slice(0, 4).map((row) => (
                  <tr key={row.period} className="border-b border-border/30">
                    <td className="py-2 pr-4 font-medium">{row.period}</td>
                    <td className="py-2 pr-4 text-right">{row.revenue?.toLocaleString() ?? "없음"}</td>
                    <td className="py-2 pr-4 text-right">{row.operating_income?.toLocaleString() ?? "없음"}</td>
                    <td className="py-2 pr-4 text-right">{row.net_income?.toLocaleString() ?? "없음"}</td>
                    <td className="py-2 pr-4 text-right">{row.ebitda?.toLocaleString() ?? "없음"}</td>
                    <td className="py-2 pr-4 text-right">{row.free_cash_flow?.toLocaleString() ?? "없음"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {stock.peer_comparisons.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-3">피어 비교</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            {stock.peer_comparisons.map((item) => (
              <div key={item.metric} className="rounded-lg border border-border px-3 py-3">
                <div className="text-xs text-text-secondary">{item.metric}</div>
                <div className="font-semibold mt-1">우리 종목 {item.company_value?.toFixed(2) ?? "없음"}</div>
                <div className="text-sm text-text-secondary mt-1">피어 평균 {item.peer_avg?.toFixed(2) ?? "없음"}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {(stock.key_catalysts?.length || stock.key_risks?.length) ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {stock.key_catalysts && stock.key_catalysts.length > 0 ? (
            <div className="card">
              <h2 className="font-semibold mb-3">상승 촉매</h2>
              <div className="space-y-2 text-sm text-text-secondary">{stock.key_catalysts.map((item) => <div key={item}>• {item}</div>)}</div>
            </div>
          ) : null}
          {stock.key_risks && stock.key_risks.length > 0 ? (
            <div className="card">
              <h2 className="font-semibold mb-3">핵심 리스크</h2>
              <div className="space-y-2 text-sm text-text-secondary">{stock.key_risks.map((item) => <div key={item}>• {item}</div>)}</div>
            </div>
          ) : null}
        </div>
      ) : null}

      {composite ? (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">복합 점수</h2>
            <div className="flex items-center gap-3">
              <div className={`text-3xl font-bold ${composite.total >= 70 ? "text-positive" : composite.total >= 50 ? "text-warning" : "text-negative"}`}>{composite.total.toFixed(1)}</div>
              <span className="text-xs text-text-secondary">/ 100</span>
            </div>
          </div>

          <div className="space-y-3 mb-5">
            {compositeCategories.map((category) => (
              <div key={category.label}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium">{category.label}</span>
                  <span className="text-text-secondary">{category.data.total}/{category.data.max_score}</span>
                </div>
                <div className="h-2 bg-border rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${category.color}`} style={{ width: `${(category.data.total / category.data.max_score) * 100}%` }} />
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1">
                  {category.data.items.map((item) => (
                    <div key={item.name} className="flex items-center gap-1 text-[10px] text-text-secondary">
                      <span>{item.name}</span>
                      <span className="font-mono font-medium">{item.score.toFixed(1)}/{item.max_score}</span>
                      <span className="opacity-60">({item.description})</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="text-[10px] text-text-secondary border-t border-border pt-2">Raw {composite.total_raw}/{composite.max_raw}를 100점 기준으로 정규화한 점수입니다.</div>
        </div>
      ) : null}

      <div className="card">
        <h2 className="font-semibold mb-4">세부 점수</h2>
        <div className="flex items-center gap-6 mb-5 flex-wrap">
          <ScoreRadial score={stock.score.total || 0} label="종합" />
          <div className="flex gap-3 flex-wrap">
            {scoreCategories.map((category) => (
              <ScoreRadial key={category.label} score={category.data.total} max={category.data.max_score} size={84} label={category.label} />
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {scoreCategories.map((category) => (
            <div key={category.label} className="rounded-xl border border-border px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <div className="font-medium">{category.label}</div>
                <div className="text-xs text-text-secondary">{category.data.total}/{category.data.max_score}</div>
              </div>
              <ScoreBreakdown items={category.data.items} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
