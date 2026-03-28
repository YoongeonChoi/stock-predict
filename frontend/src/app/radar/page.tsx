"use client";

import { useEffect, useState } from "react";

import MarketRegimeCard from "@/components/MarketRegimeCard";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import PageHeader from "@/components/PageHeader";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { api } from "@/lib/api";
import { getUserFacingErrorMessage } from "@/lib/request-state";
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
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.getMarketOpportunities(market, 12, { timeoutMs: 22_000 })
      .then(setData)
      .catch((caught) => setError(toError(caught)))
      .finally(() => setLoading(false));
  }, [market, reloadToken]);

  const retryLoad = () => setReloadToken((value) => value + 1);

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
            {data ? <span className="info-chip">1차 스캔 {data.total_scanned}개</span> : null}
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

      {error && data ? (
        <WorkspaceStateCard
          eyebrow="다시 확인 필요"
          title="최신 레이더 계산이 잠시 지연되고 있습니다"
          message={getUserFacingErrorMessage(error, "이전 계산 결과를 먼저 보여주고 있습니다. 잠시 후 다시 시도해 주세요.")}
          tone="warning"
          actionLabel="레이더 다시 불러오기"
          onAction={retryLoad}
        />
      ) : null}

      {loading ? (
        <div className="space-y-4">
          <WorkspaceLoadingCard
            title="시장 국면을 다시 읽고 있습니다"
            message="대표 흐름과 실행 후보를 먼저 정리한 뒤 레이더 보드를 채웁니다."
            className="min-h-[180px]"
          />
          <WorkspaceLoadingCard
            title="실행 후보를 스캔하고 있습니다"
            message="1차 시세 스캔과 정밀 점수 계산이 끝나는 순서대로 후보를 다시 배열합니다."
            className="min-h-[320px]"
          />
        </div>
      ) : data ? (
        <>
          <MarketRegimeCard regime={data.market_regime} title={`${market} 시장 국면`} />
          <OpportunityRadarBoard data={data} />
        </>
      ) : (
        <WorkspaceStateCard
          eyebrow="레이더 지연"
          title="기회 레이더를 아직 불러오지 못했습니다"
          message={getUserFacingErrorMessage(error, "레이다 계산이 길어지면 잠시 빈 상태로 남을 수 있습니다. 잠시 후 다시 시도해 주세요.")}
          tone="warning"
          actionLabel="레이더 다시 불러오기"
          onAction={retryLoad}
        />
      )}
    </div>
  );
}
