"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { HeatmapData, MarketMovers } from "@/lib/api";
import type { CountryListItem, OpportunityRadarResponse } from "@/lib/types";
import { formatPct, changeColor } from "@/lib/utils";
import StockHeatmap from "@/components/charts/StockHeatmap";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";

interface MarketIndicator {
  name: string;
  price: number;
  change_pct: number;
}

export default function HomePage() {
  const [countries, setCountries] = useState<CountryListItem[]>([]);
  const [indicators, setIndicators] = useState<MarketIndicator[]>([]);
  const [heatmapData, setHeatmapData] = useState<HeatmapData | null>(null);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [activeCountry, setActiveCountry] = useState("KR");
  const [movers, setMovers] = useState<MarketMovers | null>(null);
  const [radarData, setRadarData] = useState<OpportunityRadarResponse | null>(null);
  const [radarCountry, setRadarCountry] = useState("KR");
  const [radarLoading, setRadarLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getCountries().then(setCountries).catch(console.error),
      api.getMarketIndicators().then(setIndicators).catch(console.error),
    ]).finally(() => setLoading(false));
    api.getMarketMovers("KR").then(setMovers).catch(console.error);
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
    Gold: "$", "Oil (WTI)": "$", Bitcoin: "$",
    "US 10Y": "%",
  };

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
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stock Predict</h1>
        <div className="flex flex-wrap items-center gap-3 mt-1">
          {lastUpdated ? <span className="text-xs text-text-secondary">마지막 갱신: {lastUpdated}</span> : null}
          <Link href="/settings" className="text-xs text-accent hover:underline">
            설정 및 시스템 보기
          </Link>
        </div>
        <p className="text-text-secondary mt-1">한국 시장을 중심으로 미국·일본까지 함께 읽는 AI 주식 분석 워크스테이션</p>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-lg">지금 가장 강한 셋업</h2>
            <p className="text-sm text-text-secondary mt-1">기본값은 한국 시장이며, 단기 기대수익과 시장 체제를 함께 반영해 핵심 기회를 추립니다.</p>
          </div>
          <div className="flex gap-1.5">
            {["US", "KR", "JP"].map((code) => (
              <button
                key={code}
                onClick={() => loadRadar(code)}
                className={`px-3 py-1 rounded-lg text-xs transition-colors ${
                  radarCountry === code ? "bg-accent text-white" : "bg-surface border border-border hover:border-accent/50"
                }`}
              >
                {flags[code]} {code}
              </button>
            ))}
          </div>
        </div>
        {radarLoading ? <div className="card animate-pulse h-72" /> : radarData ? <OpportunityRadarBoard data={radarData} compact /> : null}
      </div>

      {indicators.length > 0 && (
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
          {indicators.map((indicator) => (
            <div key={indicator.name} className="card !p-3 text-center">
              <div className="text-xs text-text-secondary mb-1">{indicator.name}</div>
              <div className="font-mono text-sm font-bold">{fmtIndicator(indicator)}</div>
              <div className={`text-xs font-medium ${changeColor(indicator.change_pct ?? 0)}`}>
                {formatPct(indicator.change_pct ?? 0)}
              </div>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[1, 2, 3].map((i) => <div key={i} className="card animate-pulse h-48" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {orderedCountries.map((country) => (
            <Link
              key={country.code}
              href={`/country/${country.code}`}
              className="card hover:border-accent/50 transition-colors group"
            >
              <div className="flex items-center gap-3 mb-4">
                <span className="text-3xl">{flags[country.code]}</span>
                <div>
                  <h2 className="font-semibold text-lg group-hover:text-accent transition-colors">{country.name_local}</h2>
                  <span className="text-xs text-text-secondary">{country.name}</span>
                </div>
              </div>
              <div className="space-y-2">
                {country.indices.map((index) => (
                  <div key={index.ticker} className="flex justify-between items-baseline">
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

      <div className="card !p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-lg">시장 히트맵</h2>
          <div className="flex gap-1.5">
            {["US", "KR", "JP"].map((code) => (
              <button
                key={code}
                onClick={() => loadHeatmap(code)}
                className={`px-3 py-1 rounded-lg text-xs transition-colors ${
                  activeCountry === code ? "bg-accent text-white" : "bg-surface border border-border hover:border-accent/50"
                }`}
              >
                {flags[code]} {code}
              </button>
            ))}
          </div>
        </div>
        <StockHeatmap data={heatmapData} loading={heatmapLoading} />
        <div className="flex items-center gap-4 mt-3 text-[10px] text-text-secondary">
          <span>크기 = 시가총액</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#b91c1c]" /> -3% 이상</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#ef4444]" /> -1~-2%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#86efac]" /> 0~+0.5%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#22c55e]" /> +1~+2%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#15803d]" /> +3% 이상</span>
        </div>
      </div>

      {movers && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="card !p-4">
            <h3 className="font-semibold text-sm mb-3 text-positive">한국 시장 상승 상위</h3>
            <div className="space-y-2">
              {movers.gainers.map((stock) => (
                <Link key={stock.ticker} href={`/stock/${stock.ticker}`} className="flex justify-between items-center text-sm hover:text-accent transition-colors">
                  <div>
                    <span className="font-medium">{stock.ticker}</span>
                    <span className="text-text-secondary text-xs ml-2">{stock.name}</span>
                  </div>
                  <span className="text-positive font-mono font-medium">+{stock.change_pct.toFixed(2)}%</span>
                </Link>
              ))}
            </div>
          </div>
          <div className="card !p-4">
            <h3 className="font-semibold text-sm mb-3 text-negative">한국 시장 하락 상위</h3>
            <div className="space-y-2">
              {movers.losers.map((stock) => (
                <Link key={stock.ticker} href={`/stock/${stock.ticker}`} className="flex justify-between items-center text-sm hover:text-accent transition-colors">
                  <div>
                    <span className="font-medium">{stock.ticker}</span>
                    <span className="text-text-secondary text-xs ml-2">{stock.name}</span>
                  </div>
                  <span className="text-negative font-mono font-medium">{stock.change_pct.toFixed(2)}%</span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

