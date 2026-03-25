"use client";

import { useEffect, useState } from "react";

import ErrorBanner from "@/components/ErrorBanner";
import MarketRegimeCard from "@/components/MarketRegimeCard";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import type { OpportunityRadarResponse } from "@/lib/types";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "알 수 없는 오류가 발생했습니다.");
}

const MARKETS = ["KR"] as const;

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
    <div className="page-shell">
      <PageHeader
        eyebrow="Opportunity Radar"
        title="기회 레이더"
        description="한국장에서 지금 당장 체크할 만한 셋업과 실행 액션을 더 정돈된 흐름으로 보여줍니다."
        meta={
          <>
            <span className="info-chip">실행 후보 우선</span>
            <span className="info-chip">시장 국면 반영</span>
            {data ? <span className="info-chip">스캔 {data.total_scanned}개</span> : null}
          </>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            {MARKETS.map((code) => (
              <button
                key={code}
                onClick={() => setMarket(code)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                  market === code ? "bg-accent text-white" : "border border-border bg-surface/60 text-text-secondary hover:border-accent/40 hover:text-text"
                }`}
              >
                {code}
              </button>
            ))}
          </div>
        }
      />

      {error ? <ErrorBanner error={error} onRetry={() => window.location.reload()} /> : null}

      {loading ? (
        <div className="space-y-4">
          <div className="card h-64 animate-pulse" />
          <div className="card h-96 animate-pulse" />
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
