"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { HeatmapData, MarketMovers, SystemDiagnostics } from "@/lib/api";
import type { CountryListItem, OpportunityRadarResponse } from "@/lib/types";
import { formatPct, changeColor } from "@/lib/utils";
import StockHeatmap from "@/components/charts/StockHeatmap";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import SystemStatusCard from "@/components/SystemStatusCard";

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
  const [activeCountry, setActiveCountry] = useState("US");
  const [movers, setMovers] = useState<MarketMovers | null>(null);
  const [diagnostics, setDiagnostics] = useState<SystemDiagnostics | null>(null);
  const [radarData, setRadarData] = useState<OpportunityRadarResponse | null>(null);
  const [radarCountry, setRadarCountry] = useState("US");
  const [radarLoading, setRadarLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getCountries().then(setCountries).catch(console.error),
      api.getMarketIndicators().then(setIndicators).catch(console.error),
      api.getDiagnostics().then(setDiagnostics).catch(console.error),
    ]).finally(() => setLoading(false));
    api.getMarketMovers("US").then(setMovers).catch(console.error);
    setLastUpdated(new Date().toLocaleTimeString());
    loadHeatmap("US");
    loadRadar("US");
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
    "Gold": "$", "Oil (WTI)": "$", "Bitcoin": "$",
    "US 10Y": "%",
  };

  const fmtIndicator = (ind: MarketIndicator) => {
    const unit = indicatorUnit[ind.name];
    const v = (ind.price ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
    if (unit === "$") return `$${v}`;
    if (unit === "%") return `${v}%`;
    return v;
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stock Predict</h1>
        {lastUpdated && <span className="text-xs text-text-secondary ml-2">Last updated: {lastUpdated}</span>}
        <p className="text-text-secondary mt-1">AI-powered market analysis for US, KR, JP</p>
      </div>

      {diagnostics ? <SystemStatusCard diagnostics={diagnostics} /> : null}

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-lg">Best Setups Right Now</h2>
            <p className="text-sm text-text-secondary mt-1">Opportunity radar surfaces the strongest short-horizon setups across each market.</p>
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

      {/* Global Market Indicators */}
      {indicators.length > 0 && (
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
          {indicators.map((ind) => (
            <div key={ind.name} className="card !p-3 text-center">
              <div className="text-xs text-text-secondary mb-1">{ind.name}</div>
              <div className="font-mono text-sm font-bold">
                {fmtIndicator(ind)}
              </div>
              <div className={`text-xs font-medium ${changeColor(ind.change_pct ?? 0)}`}>
                {formatPct(ind.change_pct ?? 0)}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Country Cards */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[1, 2, 3].map((i) => <div key={i} className="card animate-pulse h-48" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {countries.map((c) => (
            <Link
              key={c.code}
              href={`/country/${c.code}`}
              className="card hover:border-accent/50 transition-colors group"
            >
              <div className="flex items-center gap-3 mb-4">
                <span className="text-3xl">{flags[c.code]}</span>
                <div>
                  <h2 className="font-semibold text-lg group-hover:text-accent transition-colors">{c.name_local}</h2>
                  <span className="text-xs text-text-secondary">{c.name}</span>
                </div>
              </div>
              <div className="space-y-2">
                {c.indices.map((idx) => (
                  <div key={idx.ticker} className="flex justify-between items-baseline">
                    <span className="text-sm text-text-secondary">{idx.name}</span>
                    <div className="text-right">
                      <span className="font-mono text-sm">{(idx.price ?? 0).toLocaleString()}</span>
                      <span className={`ml-2 text-sm font-medium ${changeColor(idx.change_pct ?? 0)}`}>
                        {formatPct(idx.change_pct ?? 0)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Stock Market Heatmap */}
      <div className="card !p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-lg">Market Heatmap</h2>
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
          <span>Size = Market Cap</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#b91c1c]" /> -3%+</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#ef4444]" /> -1~-2%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#86efac]" /> 0~+0.5%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#22c55e]" /> +1~+2%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#15803d]" /> +3%+</span>
        </div>
      </div>

      {/* Top Movers */}
      {movers && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="card !p-4">
            <h3 className="font-semibold text-sm mb-3 text-positive">Top Gainers</h3>
            <div className="space-y-2">
              {movers.gainers.map((s) => (
                <Link key={s.ticker} href={`/stock/${s.ticker}`} className="flex justify-between items-center text-sm hover:text-accent transition-colors">
                  <div>
                    <span className="font-medium">{s.ticker}</span>
                    <span className="text-text-secondary text-xs ml-2">{s.name}</span>
                  </div>
                  <span className="text-positive font-mono font-medium">+{s.change_pct.toFixed(2)}%</span>
                </Link>
              ))}
            </div>
          </div>
          <div className="card !p-4">
            <h3 className="font-semibold text-sm mb-3 text-negative">Top Losers</h3>
            <div className="space-y-2">
              {movers.losers.map((s) => (
                <Link key={s.ticker} href={`/stock/${s.ticker}`} className="flex justify-between items-center text-sm hover:text-accent transition-colors">
                  <div>
                    <span className="font-medium">{s.ticker}</span>
                    <span className="text-text-secondary text-xs ml-2">{s.name}</span>
                  </div>
                  <span className="text-negative font-mono font-medium">{s.change_pct.toFixed(2)}%</span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
