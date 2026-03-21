"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { CountryListItem } from "@/lib/types";
import { formatPct, changeColor } from "@/lib/utils";

interface MarketIndicator {
  name: string;
  price: number;
  change_pct: number;
}

interface SectorPerf {
  sector: string;
  ticker: string;
  price: number;
  change_pct: number;
}

function heatColor(pct: number): string {
  if (pct >= 2) return "bg-emerald-600 text-white";
  if (pct >= 1) return "bg-emerald-500/80 text-white";
  if (pct >= 0.3) return "bg-emerald-500/40 text-emerald-700 dark:text-emerald-300";
  if (pct >= -0.3) return "bg-border text-text-secondary";
  if (pct >= -1) return "bg-red-500/40 text-red-700 dark:text-red-300";
  if (pct >= -2) return "bg-red-500/80 text-white";
  return "bg-red-600 text-white";
}

export default function HomePage() {
  const [countries, setCountries] = useState<CountryListItem[]>([]);
  const [indicators, setIndicators] = useState<MarketIndicator[]>([]);
  const [sectorPerf, setSectorPerf] = useState<SectorPerf[]>([]);
  const [activeCountry, setActiveCountry] = useState("US");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getCountries().then(setCountries).catch(console.error),
      api.getMarketIndicators().then(setIndicators).catch(console.error),
      api.getSectorPerformance("US").then(setSectorPerf).catch(console.error),
    ]).finally(() => setLoading(false));
  }, []);

  const loadSectorPerf = (code: string) => {
    setActiveCountry(code);
    api.getSectorPerformance(code).then(setSectorPerf).catch(console.error);
  };

  const flags: Record<string, string> = { US: "🇺🇸", KR: "🇰🇷", JP: "🇯🇵" };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stock Predict</h1>
        <p className="text-text-secondary mt-1">AI-powered market analysis for US, KR, JP</p>
      </div>

      {/* Global Market Indicators */}
      {indicators.length > 0 && (
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
          {indicators.map((ind) => (
            <div key={ind.name} className="card !p-3 text-center">
              <div className="text-xs text-text-secondary mb-1">{ind.name}</div>
              <div className="font-mono text-sm font-bold">{ind.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
              <div className={`text-xs font-medium ${changeColor(ind.change_pct)}`}>{formatPct(ind.change_pct)}</div>
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

      {/* Sector Performance Heatmap */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-lg">Sector Performance</h2>
          <div className="flex gap-1.5">
            {["US", "KR", "JP"].map((code) => (
              <button
                key={code}
                onClick={() => loadSectorPerf(code)}
                className={`px-3 py-1 rounded-lg text-xs transition-colors ${
                  activeCountry === code ? "bg-accent text-white" : "bg-surface border border-border hover:border-accent/50"
                }`}
              >
                {flags[code]} {code}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
          {sectorPerf.map((s) => (
            <div
              key={s.sector}
              className={`rounded-lg p-3 text-center transition-colors ${heatColor(s.change_pct)}`}
            >
              <div className="text-xs font-medium mb-1 truncate">{s.sector}</div>
              <div className="text-sm font-bold">{formatPct(s.change_pct)}</div>
            </div>
          ))}
        </div>
        {sectorPerf.length === 0 && (
          <p className="text-sm text-text-secondary text-center py-6">Loading sector data...</p>
        )}
      </div>
    </div>
  );
}
