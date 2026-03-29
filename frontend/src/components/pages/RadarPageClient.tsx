"use client";

import { useEffect, useState } from "react";

import MarketRegimeCard from "@/components/MarketRegimeCard";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import PageHeader from "@/components/PageHeader";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { api } from "@/lib/api";
import { buildPublicAuditSummary, type PublicAuditFields } from "@/lib/public-audit";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import type { OpportunityRadarResponse } from "@/lib/types";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "알 수 없는 오류가 발생했습니다.");
}

const MARKETS = ["KR"] as const;

type RadarSnapshot = OpportunityRadarResponse & PublicAuditFields;

function isUsableRadarSnapshot(snapshot?: RadarSnapshot | null) {
  if (!snapshot) {
    return false;
  }
  if (!snapshot.partial) {
    return true;
  }
  return Number(snapshot.quote_available_count ?? 0) > 0 && snapshot.opportunities.length > 0;
}

function isPlaceholderRadarSnapshot(snapshot?: RadarSnapshot | null) {
  return Boolean(snapshot?.partial) && !isUsableRadarSnapshot(snapshot);
}

interface RadarPageClientProps {
  initialData?: RadarSnapshot | null;
}

export default function RadarPageClient({ initialData = null }: RadarPageClientProps) {
  const [market, setMarket] = useState<typeof MARKETS[number]>("KR");
  const [data, setData] = useState<RadarSnapshot | null>(initialData);
  const [lastUsableSnapshot, setLastUsableSnapshot] = useState<RadarSnapshot | null>(
    isUsableRadarSnapshot(initialData) ? initialData : null,
  );
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState<Error | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (isUsableRadarSnapshot(data)) {
      setLastUsableSnapshot(data);
    }
  }, [data]);

  useEffect(() => {
    if (reloadToken === 0 && market === "KR" && isUsableRadarSnapshot(initialData)) {
      return;
    }
    setLoading(true);
    setError(null);
    api.getMarketOpportunities(market, 12, { timeoutMs: 22_000 })
      .then((next) => {
        setData(next);
        if (isUsableRadarSnapshot(next)) {
          setLastUsableSnapshot(next);
        }
      })
      .catch((caught) => setError(toError(caught)))
      .finally(() => setLoading(false));
  }, [initialData, market, reloadToken]);

  const retryLoad = () => setReloadToken((value) => value + 1);
  const visibleData = isUsableRadarSnapshot(data) ? data : lastUsableSnapshot;
  const placeholderData = isPlaceholderRadarSnapshot(data) ? data : null;
  const activeAuditMeta = data || visibleData;
  const auditSummary = buildPublicAuditSummary(activeAuditMeta, {
    defaultSummary: "시장 국면, 스캔 수, 표시 후보 수를 먼저 보여주고 상세 보드는 뒤이어 갱신합니다.",
  });
  const placeholderUniverseSize = placeholderData?.universe_size ?? 0;

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="Opportunity Radar"
        title="기회 레이더"
        description={
          visibleData
            ? `금일 KRX ${visibleData.universe_size.toLocaleString("ko-KR")}종목 기반 / 1차 스캔 ${visibleData.total_scanned.toLocaleString("ko-KR")}종목 / 실시세 확보 ${Number(visibleData.quote_available_count ?? 0).toLocaleString("ko-KR")}종목 / 표시 후보 ${visibleData.opportunities.length.toLocaleString("ko-KR")}개`
            : "한국장에서 지금 바로 확인할 후보를 시장 국면과 실행 액션 기준으로 먼저 정리합니다."
        }
        meta={
          <>
            <span className="info-chip">실행 후보 우선</span>
            <span className="info-chip">시장 국면 반영</span>
            {visibleData ? <span className="info-chip">1차 스캔 {visibleData.total_scanned}개</span> : null}
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

      {visibleData ? (
        <section className="card !p-5 space-y-4">
          <div className="section-heading gap-4">
            <div>
              <h2 className="section-title">첫 판단 스레드</h2>
              <p className="section-copy">{auditSummary}</p>
            </div>
            <PublicAuditStrip meta={activeAuditMeta} />
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="metric-card">
              <div className="text-xs text-text-secondary">시장 국면</div>
              <div className="mt-2 text-2xl font-semibold text-text">{visibleData.market_regime.label}</div>
              <div className="mt-1 text-xs text-text-secondary">{visibleData.market_regime.summary}</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">전체 스캔</div>
              <div className="mt-2 text-2xl font-semibold text-text">{visibleData.total_scanned.toLocaleString("ko-KR")}</div>
              <div className="mt-1 text-xs text-text-secondary">1차 시세 스캔 완료 기준</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">실제 시세 확보</div>
              <div className="mt-2 text-2xl font-semibold text-text">{Number(visibleData.quote_available_count ?? 0).toLocaleString("ko-KR")}</div>
              <div className="mt-1 text-xs text-text-secondary">정밀 계산에 투입 가능한 종목</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">표시 후보</div>
              <div className="mt-2 text-2xl font-semibold text-text">{visibleData.opportunities.length.toLocaleString("ko-KR")}</div>
              <div className="mt-1 text-xs text-text-secondary">보정 confidence 기준 상위 후보</div>
            </div>
          </div>
        </section>
      ) : placeholderData ? (
        <section className="card !p-5 space-y-5">
          <div className="section-heading gap-4">
            <div>
              <h2 className="section-title">첫 판단 스레드 준비 중</h2>
              <p className="section-copy">
                시장 국면은 먼저 읽었지만, 이번 요청에서는 바로 쓸 후보 스냅샷을 만들지 못했습니다. 지금은 0 / 0 / 0 지표를 크게 보여주기보다 무엇이 실패했는지 먼저 안내합니다.
              </p>
            </div>
            <PublicAuditStrip meta={placeholderData} />
          </div>
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
            <div className="rounded-[22px] border border-amber-500/20 bg-amber-500/5 px-4 py-4 text-sm leading-6 text-amber-700">
              최신 레이더는 이번 요청에서 바로 쓸 수 있는 후보 스냅샷을 만들지 못했습니다. 자동 장기 스캔이 계속 도는 상태를 기다리는 것이 아니라, 다시 불러오기 때 fresh quick 스냅샷과 캐시 재사용을 새로 시도하는 구조입니다.
            </div>
            <div className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">현재 상태</div>
              <div className="mt-3 space-y-3 text-sm text-text-secondary">
                <div>
                  <div className="text-xs text-text-secondary">준비 중인 유니버스</div>
                  <div className="mt-1 text-lg font-semibold text-text">
                    {placeholderUniverseSize > 0 ? `${placeholderUniverseSize.toLocaleString("ko-KR")}개 후보군` : "기본 후보군 준비 중"}
                  </div>
                </div>
                <div className="rounded-xl border border-border/70 bg-surface/70 px-3 py-3">
                  <div className="text-xs text-text-secondary">다음 동작</div>
                  <div className="mt-2 leading-6">
                    다시 불러오기를 누르거나 새로 열면 quick 후보 스냅샷을 새로 만들고, usable 후보가 생기면 그 즉시 후보 보드로 바뀝니다. 계속 같은 화면을 띄워 두는 것만으로 완료되지는 않습니다.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {placeholderData && visibleData ? (
        <WorkspaceStateCard
          eyebrow="레이더 partial"
          title="최신 레이더가 아직 완전히 올라오지 않아 마지막 사용 가능 스냅샷을 유지합니다"
          message="대표 스냅샷과 audit 정보는 최신 상태로 갱신하고, 실제 후보 보드는 마지막으로 확인된 사용 가능 스냅샷으로 먼저 유지합니다."
          tone="warning"
          actionLabel="레이더 다시 불러오기"
          onAction={retryLoad}
        />
      ) : null}

      {error && visibleData ? (
        <WorkspaceStateCard
          eyebrow="다시 확인 필요"
          title="최신 레이더 계산이 잠시 지연되고 있습니다"
          message={getUserFacingErrorMessage(error, "이전 계산 결과를 먼저 보여주고 있습니다. 잠시 후 다시 시도해 주세요.")}
          tone="warning"
          actionLabel="레이더 다시 불러오기"
          onAction={retryLoad}
        />
      ) : null}

      {loading && !visibleData && !placeholderData ? (
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
      ) : visibleData ? (
        <>
          <MarketRegimeCard regime={visibleData.market_regime} title={`${market} 시장 국면`} />
          <OpportunityRadarBoard data={visibleData} />
        </>
      ) : (
        <WorkspaceStateCard
          eyebrow="레이더 지연"
          title="기회 레이더를 아직 불러오지 못했습니다"
          message={getUserFacingErrorMessage(error, "레이더 계산이 길어지면 먼저 시장 국면만 보일 수 있습니다. 잠시 후 다시 시도해 주세요.")}
          tone="warning"
          actionLabel="레이더 다시 불러오기"
          onAction={retryLoad}
        />
      )}
    </div>
  );
}
