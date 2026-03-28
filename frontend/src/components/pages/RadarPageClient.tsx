"use client";

import { useEffect, useState } from "react";

import MarketRegimeCard from "@/components/MarketRegimeCard";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import PageHeader from "@/components/PageHeader";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { api } from "@/lib/api";
import { buildPublicAuditSummary } from "@/lib/public-audit";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import type { OpportunityRadarResponse } from "@/lib/types";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "알 수 없는 오류가 발생했습니다.");
}

const MARKETS = ["KR"] as const;

interface RadarPageClientProps {
  initialData?: (OpportunityRadarResponse & { partial?: boolean; fallback_reason?: string | null }) | null;
}

export default function RadarPageClient({ initialData = null }: RadarPageClientProps) {
  const [market, setMarket] = useState<typeof MARKETS[number]>("KR");
  const [data, setData] = useState<(OpportunityRadarResponse & { partial?: boolean; fallback_reason?: string | null }) | null>(initialData);
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState<Error | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (reloadToken === 0 && market === "KR" && initialData) {
      return;
    }
    setLoading(true);
    setError(null);
    api.getMarketOpportunities(market, 12, { timeoutMs: 22_000 })
      .then((next) => setData(next))
      .catch((caught) => setError(toError(caught)))
      .finally(() => setLoading(false));
  }, [initialData, market, reloadToken]);

  const retryLoad = () => setReloadToken((value) => value + 1);
  const auditSummary = buildPublicAuditSummary(data, {
    defaultSummary: "시장 국면, 스캔 수, 표시 후보 수를 먼저 보여주고 상세 보드는 뒤이어 갱신합니다.",
  });

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="Opportunity Radar"
        title="기회 레이더"
        description={
          data
            ? `금일 KRX ${data.universe_size.toLocaleString("ko-KR")}종목 기반 / 1차 스캔 ${data.total_scanned.toLocaleString("ko-KR")}종목 / 실시세 확보 ${Number(data.quote_available_count ?? 0).toLocaleString("ko-KR")}종목 / 표시 후보 ${data.opportunities.length.toLocaleString("ko-KR")}개`
            : "한국장에서 지금 바로 확인할 후보를 시장 국면과 실행 액션 기준으로 먼저 정리합니다."
        }
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

      {data ? (
        <section className="card !p-5 space-y-4">
          <div className="section-heading gap-4">
            <div>
              <h2 className="section-title">첫 판단 스레드</h2>
              <p className="section-copy">{auditSummary}</p>
            </div>
            <PublicAuditStrip meta={data} />
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="metric-card">
              <div className="text-xs text-text-secondary">시장 국면</div>
              <div className="mt-2 text-2xl font-semibold text-text">{data.market_regime.label}</div>
              <div className="mt-1 text-xs text-text-secondary">{data.market_regime.summary}</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">전체 스캔</div>
              <div className="mt-2 text-2xl font-semibold text-text">{data.total_scanned.toLocaleString("ko-KR")}</div>
              <div className="mt-1 text-xs text-text-secondary">1차 시세 스캔 완료 기준</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">실제 시세 확보</div>
              <div className="mt-2 text-2xl font-semibold text-text">{Number(data.quote_available_count ?? 0).toLocaleString("ko-KR")}</div>
              <div className="mt-1 text-xs text-text-secondary">정밀 계산에 투입 가능한 종목</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">표시 후보</div>
              <div className="mt-2 text-2xl font-semibold text-text">{data.opportunities.length.toLocaleString("ko-KR")}</div>
              <div className="mt-1 text-xs text-text-secondary">보정 confidence 기준 상위 후보</div>
            </div>
          </div>
        </section>
      ) : null}

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
