"use client";

import { useEffect, useState } from "react";

import ErrorBanner from "@/components/ErrorBanner";
import MarketRegimeCard from "@/components/MarketRegimeCard";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import { api } from "@/lib/api";
import type { OpportunityRadarResponse } from "@/lib/types";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "Unknown error");
}

const MARKETS = ["US", "KR", "JP"] as const;

export default function RadarPage() {
  const [market, setMarket] = useState<typeof MARKETS[number]>("US");
  const [data, setData] = useState<OpportunityRadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.getMarketOpportunities(market, 12)
      .then(setData)
      .catch((err) => setError(toError(err)))
      .finally(() => setLoading(false));
  }, [market]);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Radar</h1>
          <p className="text-text-secondary mt-1">
            Market regime and top actionable setups across the major supported markets.
          </p>
        </div>
        <div className="flex gap-2">
          {MARKETS.map((code) => (
            <button
              key={code}
              onClick={() => setMarket(code)}
              className={`px-3 py-2 rounded-lg text-sm transition-colors ${
                market === code ? "bg-accent text-white" : "bg-surface border border-border hover:border-accent/50"
              }`}
            >
              {code}
            </button>
          ))}
        </div>
      </div>

      {error ? <ErrorBanner error={error} onRetry={() => window.location.reload()} /> : null}

      {loading ? (
        <div className="space-y-4">
          <div className="card animate-pulse h-64" />
          <div className="card animate-pulse h-96" />
        </div>
      ) : data ? (
        <>
          <MarketRegimeCard regime={data.market_regime} title={`${market} Regime`} />
          <OpportunityRadarBoard data={data} />
        </>
      ) : null}
    </div>
  );
}
