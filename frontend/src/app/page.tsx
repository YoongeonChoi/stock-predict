"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import StockHeatmap from "@/components/charts/StockHeatmap";
import { api } from "@/lib/api";
import type { DailyBriefingResponse, HeatmapData, MarketMovers } from "@/lib/api";
import type { CountryListItem, CountryReport, OpportunityRadarResponse } from "@/lib/types";
import { changeColor, formatPct } from "@/lib/utils";

const COUNTRY_FLAGS: Record<string, string> = { KR: "🇰🇷" };

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

export default function HomePage() {
  const initializedRef = useRef(false);
  const [countries, setCountries] = useState<CountryListItem[]>([]);
  const [indicators, setIndicators] = useState<MarketIndicator[]>([]);
  const [briefing, setBriefing] = useState<DailyBriefingResponse | null>(null);
  const [selectedCountry, setSelectedCountry] = useState("KR");
  const [heatmapData, setHeatmapData] = useState<HeatmapData | null>(null);
  const [movers, setMovers] = useState<MarketMovers | null>(null);
  const [radarData, setRadarData] = useState<OpportunityRadarResponse | null>(null);
  const [countryReport, setCountryReport] = useState<CountryReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [moversLoading, setMoversLoading] = useState(true);
  const [radarLoading, setRadarLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState("");

  const loadCountryWorkspace = async (code: string) => {
    setSelectedCountry(code);
    setHeatmapLoading(true);
    setMoversLoading(true);
    setRadarLoading(true);
    setReportLoading(true);

    const [heatmapResult, moversResult, radarResult, reportResult] = await Promise.allSettled([
      api.getHeatmap(code),
      api.getMarketMovers(code),
      api.getMarketOpportunities(code, 8),
      api.getCountryReport(code),
    ]);

    setHeatmapData(heatmapResult.status === "fulfilled" ? heatmapResult.value : null);
    setMovers(moversResult.status === "fulfilled" ? moversResult.value : null);
    setRadarData(radarResult.status === "fulfilled" ? radarResult.value : null);
    setCountryReport(reportResult.status === "fulfilled" ? reportResult.value : null);

    if (heatmapResult.status === "rejected") console.error(heatmapResult.reason);
    if (moversResult.status === "rejected") console.error(moversResult.reason);
    if (radarResult.status === "rejected") console.error(radarResult.reason);
    if (reportResult.status === "rejected") console.error(reportResult.reason);

    setHeatmapLoading(false);
    setMoversLoading(false);
    setRadarLoading(false);
    setReportLoading(false);
    setLastUpdated(new Date().toLocaleTimeString("ko-KR"));
  };

  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const bootstrap = async () => {
      setLoading(true);
      const [countryResult, indicatorResult, briefingResult] = await Promise.allSettled([
        api.getCountries(),
        api.getMarketIndicators(),
        api.getDailyBriefing(),
      ]);

      if (countryResult.status === "fulfilled") setCountries(countryResult.value);
      else console.error(countryResult.reason);

      if (indicatorResult.status === "fulfilled") setIndicators(indicatorResult.value);
      else console.error(indicatorResult.reason);

      if (briefingResult.status === "fulfilled") setBriefing(briefingResult.value);
      else console.error(briefingResult.reason);

      await loadCountryWorkspace("KR");
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

        <div className="flex flex-wrap gap-2">
          {countries.map((country) => (
              <button
                key={country.code}
                onClick={() => loadCountryWorkspace(country.code)}
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

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.24fr)_minmax(320px,0.76fr)]">
          <div className="rounded-[22px] border border-border/70 bg-surface/55 px-5 py-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-text">
                  {selectedCountryItem ? `${COUNTRY_FLAGS[selectedCountry]} ${selectedCountryItem.name_local}` : selectedCountry}
                </div>
                <div className="mt-1 text-sm leading-6 text-text-secondary">
                  {countryReport?.market_summary || marketView?.summary || "선택한 시장의 상태를 불러오는 중입니다."}
                </div>
              </div>
              {marketView ? (
                <span className={`rounded-full px-3 py-1.5 text-xs font-medium ${statusTone(marketView.stance)}`}>
                  {marketView.label}
                </span>
              ) : null}
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
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
              <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
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
            <div className="mt-4 space-y-3">
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
          </div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.24fr)_minmax(320px,0.76fr)]">
        <div className="card !p-4">
          <div className="section-heading gap-4">
            <div>
              <h2 className="section-title">시장 히트맵</h2>
              <p className="section-copy">크기는 시가총액, 색은 등락률입니다.</p>
            </div>
            <span className="info-chip">{selectedCountry} 히트맵</span>
          </div>
          <div className="mt-4">
            <StockHeatmap data={heatmapData} loading={heatmapLoading} />
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
          ) : null}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.08fr)_minmax(340px,0.92fr)]">
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
            ) : null}
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
              {!reportLoading && topNews.length === 0 ? <div className="text-sm text-text-secondary">표시할 뉴스가 아직 없습니다.</div> : null}
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
              {!reportLoading && topStocks.length === 0 ? <div className="text-sm text-text-secondary">상위 종목 데이터가 아직 없습니다.</div> : null}
            </div>
          </div>
        </div>
      </section>

      {loading ? <div className="card h-24 animate-pulse" /> : null}
    </div>
  );
}
