"use client";

import { useEffect, useRef, useState } from "react";

import MarketRegimeCard from "@/components/MarketRegimeCard";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import PageHeader from "@/components/PageHeader";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import RadarNextDayFocusCard from "@/components/RadarNextDayFocusCard";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { api } from "@/lib/api";
import { buildPublicAuditSummary, type PublicAuditFields } from "@/lib/public-audit";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import {
  reportErrorOnlyScreen,
  reportHydrationRefetchSuccess,
  reportInitialSsrSuccess,
  reportPanelDegraded,
} from "@/lib/route-observability";
import type { OpportunityRadarResponse } from "@/lib/types";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "알 수 없는 오류가 발생했습니다.");
}

const MARKETS = ["KR"] as const;
export const RADAR_AUTO_RETRY_DELAYS_MS = [4_000, 10_000] as const;

export type RadarSnapshot = OpportunityRadarResponse & PublicAuditFields;

export function isUsableRadarSnapshot(snapshot?: RadarSnapshot | null) {
  if (!snapshot) {
    return false;
  }
  if (!snapshot.partial) {
    return true;
  }
  return Number(snapshot.quote_available_count ?? 0) > 0 && snapshot.opportunities.length > 0;
}

export function isPlaceholderRadarSnapshot(snapshot?: RadarSnapshot | null) {
  return Boolean(snapshot?.partial) && !isUsableRadarSnapshot(snapshot);
}

export function shouldAutoRetryRadarSnapshot(snapshot: RadarSnapshot | null, loading: boolean, attempt: number) {
  return isPlaceholderRadarSnapshot(snapshot) && !loading && attempt < RADAR_AUTO_RETRY_DELAYS_MS.length;
}

interface RadarPageClientProps {
  initialData?: RadarSnapshot | null;
}

export default function RadarPageClient({ initialData = null }: RadarPageClientProps) {
  const routeKey = "/radar";
  const reportedInitialRef = useRef(false);
  const reportedErrorOnlyRef = useRef(false);
  const reportedHydrationRef = useRef(false);
  const reportedDegradedRef = useRef(false);
  const [market, setMarket] = useState<typeof MARKETS[number]>("KR");
  const [data, setData] = useState<RadarSnapshot | null>(initialData);
  const [lastUsableSnapshot, setLastUsableSnapshot] = useState<RadarSnapshot | null>(
    isUsableRadarSnapshot(initialData) ? initialData : null,
  );
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState<Error | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [autoRetryAttempt, setAutoRetryAttempt] = useState(0);

  useEffect(() => {
    if (isUsableRadarSnapshot(data)) {
      setLastUsableSnapshot(data);
      setAutoRetryAttempt(0);
    }
  }, [data]);

  useEffect(() => {
    setAutoRetryAttempt(0);
  }, [market]);

  useEffect(() => {
    if (!shouldAutoRetryRadarSnapshot(data, loading, autoRetryAttempt)) {
      return undefined;
    }
    const delayMs = RADAR_AUTO_RETRY_DELAYS_MS[autoRetryAttempt];
    const handle = window.setTimeout(() => {
      setAutoRetryAttempt((value) => value + 1);
      setReloadToken((value) => value + 1);
    }, delayMs);
    return () => window.clearTimeout(handle);
  }, [autoRetryAttempt, data, loading]);

  useEffect(() => {
    if (reportedInitialRef.current) {
      return;
    }
    if (initialData || data) {
      reportedInitialRef.current = true;
      reportInitialSsrSuccess(routeKey, "radar_shell");
    }
  }, [data, initialData, routeKey]);

  useEffect(() => {
    if (reloadToken === 0 && market === "KR" && isUsableRadarSnapshot(initialData)) {
      return;
    }
    setLoading(true);
    setError(null);
    api.getMarketOpportunities(market, 12, { timeoutMs: 28_000 })
      .then((next) => {
        setData(next);
        if (isUsableRadarSnapshot(next)) {
          setLastUsableSnapshot(next);
        }
      })
      .catch((caught) => setError(toError(caught)))
      .finally(() => setLoading(false));
  }, [initialData, market, reloadToken]);

  useEffect(() => {
    if (!reportedHydrationRef.current && !loading && data) {
      reportedHydrationRef.current = true;
      reportHydrationRefetchSuccess(routeKey, isUsableRadarSnapshot(data) ? "radar_quick" : "radar_placeholder");
    }
    if (!reportedDegradedRef.current && !loading && error) {
      reportedDegradedRef.current = true;
      reportPanelDegraded(routeKey, "radar_board", error.message);
    }
  }, [data, error, loading, routeKey]);

  useEffect(() => {
    if (reportedErrorOnlyRef.current) {
      return;
    }
    if (!loading && !data && !lastUsableSnapshot && !isPlaceholderRadarSnapshot(data) && error) {
      reportedErrorOnlyRef.current = true;
      reportErrorOnlyScreen(routeKey, "radar");
    }
  }, [data, error, lastUsableSnapshot, loading, routeKey]);

  const retryLoad = () => setReloadToken((value) => value + 1);
  const visibleData = isUsableRadarSnapshot(data) ? data : lastUsableSnapshot;
  const placeholderData = isPlaceholderRadarSnapshot(data) ? data : null;
  const activeAuditMeta = data || visibleData;
  const auditSummary = buildPublicAuditSummary(activeAuditMeta, {
    defaultSummary: "시장 국면, 스캔 수, 표시 후보 수를 기준으로 현재 레이더 상태를 표시합니다.",
  });
  const nextDayFocus = visibleData?.next_day_focus ?? null;
  const placeholderUniverseSize = placeholderData?.universe_size ?? 0;
  const radarHeaderDescription = visibleData
    ? "대표 유니버스, 다음 거래일 포커스, 20거래일 후보를 분리해 표시합니다."
    : "한국장 후보를 시장 국면, 차트 점수, 실행 액션 기준으로 필터링합니다.";

  return (
    <div className="page-shell">
      <PageHeader
        variant="compact"
        eyebrow="시장 탐색"
        title="기회 레이더"
        description={radarHeaderDescription}
        meta={
          <>
            <span className="info-chip">실행 후보 우선</span>
            {visibleData ? <span className="info-chip">대표 {visibleData.universe_size.toLocaleString("ko-KR")}개</span> : null}
            {visibleData ? <span className="info-chip">1차 스캔 {visibleData.total_scanned}개</span> : null}
            {nextDayFocus ? (
              <span className="info-chip">1일 포커스 {nextDayFocus.name}</span>
            ) : null}
          </>
        }
        actions={MARKETS.length > 1 ? (
          <div className="flex flex-wrap gap-2">
            {MARKETS.map((code) => (
              <button
                key={code}
                onClick={() => setMarket(code)}
                className={market === code ? "action-chip-primary" : "action-chip-secondary"}
              >
                {code}
              </button>
            ))}
          </div>
        ) : undefined}
      />

      {visibleData && nextDayFocus ? (
        <RadarNextDayFocusCard focus={nextDayFocus} />
      ) : visibleData ? (
        <WorkspaceStateCard
          kind="partial"
          eyebrow="다음 거래일 포커스 준비 중"
          title="단기 추천 계산 중"
          message="레이더 후보 보드는 표시됐고, 다음 거래일 전용 매수·목표·손절 기준은 정밀 후보 재평가가 끝나면 채워집니다."
          actionLabel="레이더 다시 불러오기"
          onAction={retryLoad}
        />
      ) : null}

      {visibleData ? (
        <section className="card !p-5 space-y-4">
          <div className="section-heading gap-4">
            <div>
              <h2 className="section-title">레이더 상태</h2>
              <p className="section-copy">{auditSummary}</p>
            </div>
            <PublicAuditStrip meta={activeAuditMeta} />
          </div>
          <div className="workspace-metric-grid">
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
                시장 국면은 계산됐지만 이번 요청에서는 후보 스냅샷을 만들지 못했습니다. 0 / 0 / 0 지표 대신 실패 원인을 표시합니다.
              </p>
            </div>
            <PublicAuditStrip meta={placeholderData} />
          </div>
          <div className="workspace-grid-balanced">
            <div className="ui-panel-warning !px-4 !py-4 text-sm leading-6">
              최신 레이더는 이번 요청에서 바로 쓸 수 있는 후보 스냅샷을 만들지 못했습니다. 자동 장기 스캔이 계속 도는 상태를 기다리는 것이 아니라, 다시 불러오기 때 fresh quick 스냅샷과 캐시 재사용을 새로 시도하는 구조입니다.
            </div>
            <div className="section-slab-subtle !px-4 !py-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">현재 상태</div>
              <div className="mt-3 space-y-3 text-sm text-text-secondary">
                <div>
                  <div className="text-xs text-text-secondary">준비 중인 유니버스</div>
                  <div className="mt-1 text-lg font-semibold text-text">
                    {placeholderUniverseSize > 0 ? `${placeholderUniverseSize.toLocaleString("ko-KR")}개 후보군` : "기본 후보군 준비 중"}
                  </div>
                </div>
                <div className="section-slab-muted !px-3 !py-3">
                  <div className="text-xs text-text-secondary">다음 동작</div>
                  <div className="mt-2 leading-6">
                    같은 화면을 열어 두면 짧게 자동 재조회하고, 다시 불러오기를 누르면 즉시 fresh quick 스냅샷과 캐시 재사용을 새로 확인합니다. usable 후보가 생기면 그 즉시 후보 보드로 바뀝니다.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {placeholderData && visibleData ? (
        <WorkspaceStateCard
          kind="partial"
          eyebrow="레이더 partial"
          title="최신 레이더가 아직 완전히 올라오지 않아 마지막 사용 가능 스냅샷을 유지합니다"
          message="대표 스냅샷과 audit 정보는 최신 상태로 갱신하고, 실제 후보 보드는 마지막으로 확인된 사용 가능 스냅샷으로 유지합니다."
          actionLabel="레이더 다시 불러오기"
          onAction={retryLoad}
        />
      ) : null}

      {error && visibleData ? (
        <WorkspaceStateCard
          kind="partial"
          eyebrow="다시 확인 필요"
          title="최신 레이더 계산이 잠시 지연되고 있습니다"
          message={getUserFacingErrorMessage(error, "이전 계산 결과를 표시합니다. 잠시 후 다시 시도해 주세요.")}
          actionLabel="레이더 다시 불러오기"
          onAction={retryLoad}
        />
      ) : null}

      {loading && !visibleData && !placeholderData ? (
        <div className="space-y-4">
          <WorkspaceLoadingCard
            title="시장 국면을 다시 읽고 있습니다"
            message="대표 흐름과 실행 후보 계산이 끝나면 레이더 보드를 채웁니다."
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
          kind="blocking"
          eyebrow="레이더 지연"
          title="기회 레이더를 아직 불러오지 못했습니다"
          message={getUserFacingErrorMessage(error, "레이더 계산이 길어지면 시장 국면만 표시될 수 있습니다. 잠시 후 다시 시도해 주세요.")}
          actionLabel="레이더 다시 불러오기"
          onAction={retryLoad}
        />
      )}
    </div>
  );
}
