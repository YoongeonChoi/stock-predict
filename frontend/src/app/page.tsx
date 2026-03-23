"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Archive, ArrowRight, BriefcaseBusiness, Crosshair, FlaskConical } from "lucide-react";

import DailyIdealPortfolioPanel from "@/components/DailyIdealPortfolioPanel";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import PageHeader from "@/components/PageHeader";
import StockHeatmap from "@/components/charts/StockHeatmap";
import { api } from "@/lib/api";
import type { DailyIdealPortfolio, HeatmapData, MarketMovers } from "@/lib/api";
import type { CountryListItem, OpportunityRadarResponse } from "@/lib/types";
import { changeColor, formatPct } from "@/lib/utils";

interface MarketIndicator {
  name: string;
  price: number;
  change_pct: number;
}

export default function HomePage() {
  const initializedRef = useRef(false);
  const [countries, setCountries] = useState<CountryListItem[]>([]);
  const [indicators, setIndicators] = useState<MarketIndicator[]>([]);
  const [heatmapData, setHeatmapData] = useState<HeatmapData | null>(null);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [activeCountry, setActiveCountry] = useState("KR");
  const [movers, setMovers] = useState<MarketMovers | null>(null);
  const [radarData, setRadarData] = useState<OpportunityRadarResponse | null>(null);
  const [radarCountry, setRadarCountry] = useState("KR");
  const [radarLoading, setRadarLoading] = useState(true);
  const [idealPortfolio, setIdealPortfolio] = useState<DailyIdealPortfolio | null>(null);
  const [idealLoading, setIdealLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    Promise.all([
      api.getCountries().then(setCountries).catch(console.error),
      api.getMarketIndicators().then(setIndicators).catch(console.error),
    ]).finally(() => setLoading(false));

    api.getMarketMovers("KR").then(setMovers).catch(console.error);
    api.getDailyIdealPortfolio(false, 8).then(setIdealPortfolio).catch(console.error).finally(() => setIdealLoading(false));
    setLastUpdated(new Date().toLocaleTimeString("ko-KR"));
    loadHeatmap("KR");
    loadRadar("KR");
  }, []);

  const loadHeatmap = (code: string) => {
    setActiveCountry(code);
    setHeatmapLoading(true);
    api.getHeatmap(code)
      .then(setHeatmapData)
      .catch(console.error)
      .finally(() => setHeatmapLoading(false));
  };

  const loadRadar = (code: string) => {
    setRadarCountry(code);
    setRadarLoading(true);
    api.getMarketOpportunities(code, 6)
      .then(setRadarData)
      .catch(console.error)
      .finally(() => setRadarLoading(false));
  };

  const flags: Record<string, string> = { US: "🇺🇸", KR: "🇰🇷", JP: "🇯🇵" };
  const indicatorUnit: Record<string, string> = {
    Gold: "$",
    "Oil (WTI)": "$",
    Bitcoin: "$",
    "US 10Y": "%",
  };
  const quickLinks = [
    { href: "/portfolio", label: "포트폴리오", description: "보유 종목과 모델 비중 관리", icon: BriefcaseBusiness },
    { href: "/radar", label: "기회 레이더", description: "강한 셋업과 액션 우선순위 확인", icon: Crosshair },
    { href: "/lab", label: "예측 연구실", description: "적중률과 calibration 점검", icon: FlaskConical },
    { href: "/archive", label: "아카이브", description: "과거 리포트와 예측 기록 보기", icon: Archive },
  ];

  const orderedCountries = [...countries].sort((a, b) => {
    const priority: Record<string, number> = { KR: 0, US: 1, JP: 2 };
    return (priority[a.code] ?? 9) - (priority[b.code] ?? 9);
  });

  const fmtIndicator = (indicator: MarketIndicator) => {
    const unit = indicatorUnit[indicator.name];
    const value = (indicator.price ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
    if (unit === "$") return `$${value}`;
    if (unit === "%") return `${value}%`;
    return value;
  };

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="AI 투자 워크스테이션"
        title="Stock Predict"
        description="한국 시장을 중심으로 미국·일본까지 함께 읽으면서, 내일의 추천 포트폴리오와 당장 확인할 셋업을 한 흐름으로 정리합니다."
        meta={
          <>
            <span className="info-chip">KR 기본 탐색</span>
            <span className="info-chip">US · JP 동시 스캔</span>
            <span className="info-chip">일일 추천 포트폴리오 추적</span>
            {lastUpdated ? <span className="info-chip">마지막 갱신 {lastUpdated}</span> : null}
          </>
        }
        actions={
          <>
            <Link href="/portfolio" className="action-chip-primary">
              포트폴리오 열기
            </Link>
            <Link href="/settings" className="action-chip-secondary">
              설정 및 시스템
            </Link>
          </>
        }
      />

      <section className="grid gap-6 xl:grid-cols-[1.25fr_0.95fr]">
        <div className="min-w-0 space-y-4">
          <div>
            <h2 className="section-title">내일 바로 볼 추천 포트폴리오</h2>
            <p className="section-copy">다음 거래일 기준으로 가장 이상적인 종목 조합을 만들고, 이전 추천안 성과까지 같이 추적합니다.</p>
          </div>
          {idealLoading ? <div className="card h-80 animate-pulse" /> : idealPortfolio ? <DailyIdealPortfolioPanel data={idealPortfolio} compact /> : null}
        </div>

        <div className="min-w-0 space-y-4">
          <div className="section-heading">
            <div>
              <h2 className="section-title">지금 가장 강한 셋업</h2>
              <p className="section-copy">단기 기대수익과 시장 체제를 함께 반영해 지금 당장 볼 만한 기회를 추립니다.</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {["US", "KR", "JP"].map((code) => (
                <button
                  key={code}
                  onClick={() => loadRadar(code)}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                    radarCountry === code ? "bg-accent text-white" : "border border-border bg-surface/60 text-text-secondary hover:border-accent/40 hover:text-text"
                  }`}
                >
                  {flags[code]} {code}
                </button>
              ))}
            </div>
          </div>
          {radarLoading ? <div className="card h-72 animate-pulse" /> : radarData ? <OpportunityRadarBoard data={radarData} compact /> : null}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.12fr_0.88fr]">
        <div className="card !p-5">
          <div>
            <h2 className="section-title">시장 스냅샷</h2>
            <p className="section-copy">핵심 지표와 국가별 대표 지수를 같은 리듬으로 정리해 한 번에 읽기 쉽게 맞췄습니다.</p>
          </div>

          {indicators.length > 0 ? (
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {indicators.map((indicator) => (
                <div key={indicator.name} className="metric-card">
                  <div className="text-xs text-text-secondary">{indicator.name}</div>
                  <div className="mt-3 font-mono text-lg font-semibold">{fmtIndicator(indicator)}</div>
                  <div className={`mt-1 text-xs font-medium ${changeColor(indicator.change_pct ?? 0)}`}>
                    {formatPct(indicator.change_pct ?? 0)}
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {loading ? (
            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
              {[1, 2, 3].map((i) => <div key={i} className="metric-card h-44 animate-pulse" />)}
            </div>
          ) : (
            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
              {orderedCountries.map((country) => (
                <Link
                  key={country.code}
                  href={`/country/${country.code}`}
                  className="metric-card group transition-colors hover:border-accent/35"
                >
                  <div className="mb-4 flex items-center gap-3">
                    <span className="text-3xl">{flags[country.code]}</span>
                    <div className="min-w-0">
                      <h2 className="truncate text-lg font-semibold transition-colors group-hover:text-accent">{country.name_local}</h2>
                      <span className="text-xs text-text-secondary">{country.name}</span>
                    </div>
                  </div>
                  <div className="space-y-2.5">
                    {country.indices.map((index) => (
                      <div key={index.ticker} className="flex items-baseline justify-between gap-3">
                        <span className="text-sm text-text-secondary">{index.name}</span>
                        <div className="text-right">
                          <span className="font-mono text-sm">{(index.price ?? 0).toLocaleString()}</span>
                          <span className={`ml-2 text-sm font-medium ${changeColor(index.change_pct ?? 0)}`}>
                            {formatPct(index.change_pct ?? 0)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="card !p-5">
          <div>
            <h2 className="section-title">빠른 이동</h2>
            <p className="section-copy">지금 하는 일에 맞춰 자주 쓰는 화면만 먼저 묶어두었습니다.</p>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {quickLinks.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="metric-card group flex items-start gap-3 transition-colors hover:border-accent/35"
                >
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
                    <Icon size={20} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-medium text-text">{item.label}</span>
                      <ArrowRight size={15} className="text-text-secondary transition-transform group-hover:translate-x-0.5" />
                    </span>
                    <span className="mt-2 block text-xs leading-5 text-text-secondary">{item.description}</span>
                  </span>
                </Link>
              );
            })}
          </div>

          <div className="mt-5 rounded-[22px] border border-border px-4 py-4 surface-muted">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary">정리 포인트</div>
            <div className="mt-3 space-y-2 text-sm text-text-secondary">
              <div>레이더는 “지금 강한 후보”, 포트폴리오는 “실제로 들고 갈 비중”, 연구실은 “사후 검증” 역할로 분리했습니다.</div>
              <div>아카이브는 과거 리포트와 PDF/CSV 관리 허브로 남겨서 메뉴 동선이 덜 산만하게 읽히도록 정리했습니다.</div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.26fr_0.74fr]">
        <div className="card !p-4">
          <div className="section-heading">
            <div>
              <h2 className="section-title">시장 히트맵</h2>
              <p className="section-copy">시가총액과 등락률을 함께 보면서 어느 섹터와 종목군에 자금이 붙는지 빠르게 확인합니다.</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {["US", "KR", "JP"].map((code) => (
                <button
                  key={code}
                  onClick={() => loadHeatmap(code)}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                    activeCountry === code ? "bg-accent text-white" : "border border-border bg-surface/60 text-text-secondary hover:border-accent/40 hover:text-text"
                  }`}
                >
                  {flags[code]} {code}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-4">
            <StockHeatmap data={heatmapData} loading={heatmapLoading} />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-4 text-[10px] text-text-secondary">
            <span>크기 = 시가총액</span>
            <span className="flex items-center gap-1"><span className="h-3 w-3 rounded bg-[#b91c1c]" /> -3% 이상</span>
            <span className="flex items-center gap-1"><span className="h-3 w-3 rounded bg-[#ef4444]" /> -1~-2%</span>
            <span className="flex items-center gap-1"><span className="h-3 w-3 rounded bg-[#86efac]" /> 0~+0.5%</span>
            <span className="flex items-center gap-1"><span className="h-3 w-3 rounded bg-[#22c55e]" /> +1~+2%</span>
            <span className="flex items-center gap-1"><span className="h-3 w-3 rounded bg-[#15803d]" /> +3% 이상</span>
          </div>
        </div>

        {movers ? (
          <div className="card !p-5">
            <div>
              <h2 className="section-title">한국 시장 모멘텀</h2>
              <p className="section-copy">상승 상위와 하락 상위를 한 카드에 묶어 시장 강도 변화를 더 빠르게 읽습니다.</p>
            </div>
            <div className="mt-5 grid gap-5 sm:grid-cols-2 xl:grid-cols-1">
              <div>
                <h3 className="text-sm font-semibold text-positive">상승 상위</h3>
                <div className="mt-3 space-y-2">
                  {movers.gainers.map((stock) => (
                    <Link key={stock.ticker} href={`/stock/${stock.ticker}`} className="metric-card flex items-center justify-between gap-3 py-3 transition-colors hover:border-accent/35">
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
                  {movers.losers.map((stock) => (
                    <Link key={stock.ticker} href={`/stock/${stock.ticker}`} className="metric-card flex items-center justify-between gap-3 py-3 transition-colors hover:border-accent/35">
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
          </div>
        ) : null}
      </section>
    </div>
  );
}
