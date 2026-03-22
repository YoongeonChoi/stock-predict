"use client";

import { useEffect, useState } from "react";

import ErrorBanner from "@/components/ErrorBanner";
import MarketRegimeCard from "@/components/MarketRegimeCard";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import { api } from "@/lib/api";
import type { OpportunityRadarResponse } from "@/lib/types";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "알 수 없는 오류가 발생했습니다.");
}

const MARKETS = ["US", "KR", "JP"] as const;

export default function RadarPage() {
  const [market, setMarket] = useState<typeof MARKETS[number]>("KR");
  const [data, setData] = useState<OpportunityRadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.getMarketOpportunities(market, 12)
      .then(setData)
      .catch((caught) => setError(toError(caught)))
      .finally(() => setLoading(false));
  }, [market]);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">기회 레이더</h1>
          <p className="text-text-secondary mt-1">한국을 기본으로 미국과 일본까지 훑으면서 지금 당장 체크할 만한 셋업을 추려줍니다.</p>
        </div>
        <div className="flex gap-2">
          {MARKETS.map((code) => (
            <button key={code} onClick={() => setMarket(code)} className={`px-3 py-2 rounded-lg text-sm transition-colors ${market === code ? "bg-accent text-white" : "bg-surface border border-border hover:border-accent/50"}`}>
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
          <MarketRegimeCard regime={data.market_regime} title={`${market} 시장 국면`} />
          <OpportunityRadarBoard data={data} />
        </>
      ) : null}
    </div>
  );
}