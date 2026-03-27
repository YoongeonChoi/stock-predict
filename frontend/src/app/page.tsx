"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import StockHeatmap from "@/components/charts/StockHeatmap";
import { ApiError, ApiTimeoutError, api } from "@/lib/api";
import type { DailyBriefingResponse, HeatmapData, MarketMovers } from "@/lib/api";
import type { CountryListItem, CountryReport, OpportunityRadarResponse } from "@/lib/types";
import { changeColor, formatPct } from "@/lib/utils";

const COUNTRY_FLAGS: Record<string, string> = { KR: "🇰🇷" };
const BRIEFING_TIMEOUT_MS = 9_000;
const WORKSPACE_TIMEOUT_MS = 22_000;

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

function describeLoadError(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    if (error.errorCode === "SP-5018") {
      return "요청이 길어져 이번 섹션은 잠시 비워 두었습니다. 잠시 후 다시 시도해 주세요.";
    }
    return `${error.errorCode} · ${error.message}`;
  }
  if (error instanceof ApiTimeoutError) {
    return fallback;
  }
  if (error instanceof Error && error.message) {
    return `${fallback} (${error.message})`;
  }
  return fallback;
}

function SectionFallback({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-5 text-sm text-text-secondary">
      <div>{message}</div>
      {onRetry ? (
        <button
          onClick={onRetry}
          className="mt-3 inline-flex rounded-full border border-accent/25 px-3 py-1.5 text-xs font-medium text-accent transition-colors hover:border-accent/45 hover:bg-accent/10"
        >
          다시 시도
        </button>
      ) : null}
    </div>
  );
}

export default function HomePage() {
  const initializedRef = useRef(false);
  const workspaceRequestIdRef = useRef(0);
  const [countries, setCountries] = useState<CountryListItem[]>([]);
  const [indicators, setIndicators] = useState<MarketIndicator[]>([]);
  const [briefing, setBriefing] = useState<DailyBriefingResponse | null>(null);
  const [selectedCountry, setSelectedCountry] = useState("KR");
  const [heatmapData, setHeatmapData] = useState<HeatmapData | null>(null);
  const [movers, setMovers] = useState<MarketMovers | null>(null);
  const [radarData, setRadarData] = useState<OpportunityRadarResponse | null>(null);
  const [countryReport, setCountryReport] = useState<CountryReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [briefingLoading, setBriefingLoading] = useState(true);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [moversLoading, setMoversLoading] = useState(true);
  const [radarLoading, setRadarLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(true);
  const [briefingError, setBriefingError] = useState<string | null>(null);
  const [heatmapError, setHeatmapError] = useState<string | null>(null);
  const [moversError, setMoversError] = useState<string | null>(null);
  const [radarError, setRadarError] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState("");

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
        const result = await api.getMarketOpportunities(code, 8, { timeoutMs: WORKSPACE_TIMEOUT_MS });
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
      const [countryResult, indicatorResult] = await Promise.allSettled([
        api.getCountries(),
        api.getMarketIndicators(),
      ]);

      if (countryResult.status === "fulfilled") setCountries(countryResult.value);
      else console.error(countryResult.reason);

      if (indicatorResult.status === "fulfilled") setIndicators(indicatorResult.value);
      else console.error(indicatorResult.reason);

      void loadBriefing();
      void loadCountryWorkspace("KR");
      setLoading(false);
    };

    bootstrap();
  }, []);

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

  const topNews = countryReport?.key_news.slice(0, 4) ?? [];
  const topStocks = countryReport?.top_stocks.slice(0, 5) ?? [];
  const retryCurrentWorkspace = () => {
    void loadCountryWorkspace(selectedCountry);
  };
  const marketSummaryText =
    countryReport?.market_summary ||
    marketView?.summary ||
    (reportLoading
      ? "선택한 시장의 상태를 불러오는 중입니다."
      : reportError || (briefingLoading ? "브리핑을 불러오는 중입니다." : briefingError || "선택한 시장 요약이 아직 없습니다."));

  return (
    <div className="page-shell">
      <section className="card !p-5 space-y-5">
        <div className="section-heading gap-4">
          <div>
            <h1 className="section-title text-2xl">대시보드</h1>
            <p className="section-copy">선택한 시장의 지수, 뉴스, 히트맵, 강한 셋업을 한 흐름으로 봅니다.</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
            {lastUpdated ? <span className="info-chip">최근 갱신 {lastUpdated}</span> : null}
            {countryReport?.generated_at ? <span className="info-chip">리포트 {new Date(countryReport.generated_at).toLocaleString("ko-KR")}</span> : null}
          </div>
        </div>

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

        <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.24fr)_minmax(320px,0.76fr)]">
          <div className="rounded-[22px] border border-border/70 bg-surface/55 px-5 py-5">
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

          <div className="rounded-[22px] border border-border/70 bg-surface/55 px-5 py-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-text">오늘의 포커스</div>
                <div className="mt-1 text-sm text-text-secondary">선택 시장에서 바로 볼 종목과 일정만 추렸습니다.</div>
              </div>
              {briefing?.research_archive ? <span className="info-chip">리서치 {briefing.research_archive.todays_reports}건</span> : null}
            </div>
            <div className="mt-4">
              {briefingLoading ? (
                <div className="h-64 rounded-[22px] bg-border/20 animate-pulse" />
              ) : focusCards.length > 0 || events.length > 0 ? (
                <div className="space-y-3">
                  {focusCards.map((item) => (
                    <Link key={`${item.country_code}-${item.ticker}`} href={`/stock/${encodeURIComponent(item.ticker)}`} className="block rounded-2xl border border-border/70 bg-surface/50 px-4 py-3 transition-colors hover:border-accent/35">
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
                  ))}
                  {events.map((event) => (
                    <div key={`${event.country_code}-${event.date}-${event.title}`} className="rounded-2xl border border-border/70 bg-surface/45 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-medium text-text">{event.title}</div>
                        <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${impactTone(event.impact)}`}>{event.date}</span>
                      </div>
                      <div className="mt-1 text-xs text-text-secondary">{event.summary}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <SectionFallback
                  message={briefingError || "오늘의 포커스 데이터가 아직 없습니다."}
                  onRetry={() => void loadBriefing()}
                />
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-5 2xl:grid-cols-[minmax(0,1.24fr)_minmax(320px,0.76fr)]">
        <div className="card !p-4">
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
              <SectionFallback
                message={heatmapError || "히트맵 데이터가 아직 없습니다."}
                onRetry={retryCurrentWorkspace}
              />
            )}
          </div>
        </div>

        <div className="card !p-5">
          <div>
            <h2 className="section-title">상승·하락 상위</h2>
            <p className="section-copy">선택 시장에서 강도가 강한 종목과 약한 종목을 같이 봅니다.</p>
          </div>
          {moversLoading ? (
            <div className="mt-5 h-64 rounded-[22px] bg-border/20 animate-pulse" />
          ) : movers ? (
            <div className="mt-5 grid gap-5 sm:grid-cols-2 2xl:grid-cols-1">
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
              <SectionFallback
                message={moversError || "상승·하락 상위 데이터가 아직 없습니다."}
                onRetry={retryCurrentWorkspace}
              />
            </div>
          )}
        </div>
      </section>

      <section className="grid gap-5 2xl:grid-cols-[minmax(0,1.08fr)_minmax(340px,0.92fr)]">
        <div className="card !p-0 overflow-hidden">
          <div className="border-b border-border px-5 py-4">
            <h2 className="section-title">강한 셋업</h2>
            <p className="section-copy">선택 시장에서 점수와 실행력이 높은 후보를 먼저 봅니다.</p>
          </div>
          <div className="px-5 py-5">
            {radarLoading ? (
              <div className="h-80 rounded-[22px] bg-border/20 animate-pulse" />
            ) : radarData ? (
              <OpportunityRadarBoard data={radarData} compact embedded />
            ) : (
              <SectionFallback
                message={radarError || "강한 셋업 데이터가 아직 없습니다."}
                onRetry={retryCurrentWorkspace}
              />
            )}
          </div>
        </div>

        <div className="space-y-5">
          <div className="card !p-5">
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
                <SectionFallback
                  message={reportError || "표시할 뉴스가 아직 없습니다."}
                  onRetry={retryCurrentWorkspace}
                />
              ) : null}
            </div>
          </div>

          <div className="card !p-5">
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
                <SectionFallback
                  message={reportError || "상위 종목 데이터가 아직 없습니다."}
                  onRetry={retryCurrentWorkspace}
                />
              ) : null}
            </div>
          </div>
        </div>
      </section>

      {loading ? <div className="card h-24 animate-pulse" /> : null}
    </div>
  );
}
