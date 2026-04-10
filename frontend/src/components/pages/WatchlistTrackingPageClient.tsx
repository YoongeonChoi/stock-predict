"use client";

import Link from "next/link";

import { useAuth } from "@/components/AuthProvider";
import ForecastDeltaCard from "@/components/ForecastDeltaCard";
import PageHeader from "@/components/PageHeader";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import { useToast } from "@/components/Toast";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { useWatchlistTrackingDetail } from "@/components/pages/useWatchlistTrackingDetail";
import type { WatchlistTrackingDetailResponse } from "@/lib/api";
import { buildPublicAuditSummary } from "@/lib/public-audit";
import type { StockDetail } from "@/lib/types";
import { formatPct, formatPrice } from "@/lib/utils";

interface WatchlistTrackingPageClientProps {
  initialTicker: string;
  initialData?: StockDetail | null;
}

function buildForecastDeltaPayload(detail: WatchlistTrackingDetailResponse) {
  return {
    generated_at: detail.latest_snapshot.generated_at || new Date().toISOString(),
    ticker: detail.watchlist_meta.ticker,
    summary: detail.prediction_change_summary,
    history: detail.prediction_history,
  };
}

function formatPredictionAt(value?: string | null) {
  if (!value) {
    return "기록 축적 중";
  }
  return new Date(value).toLocaleString("ko-KR");
}

export default function WatchlistTrackingPageClient({
  initialTicker,
  initialData = null,
}: WatchlistTrackingPageClientProps) {
  const { session, loading: authLoading } = useAuth();
  const { toast } = useToast();
  const { detail, loading, loadError, reload, toggleTracking } = useWatchlistTrackingDetail({
    ticker: initialTicker,
    hasSession: Boolean(session),
    authLoading,
    toast,
  });

  const displayName = detail?.watchlist_meta.name || initialData?.name || initialTicker;
  const countryCode = detail?.watchlist_meta.country_code || initialData?.country_code || "KR";
  const priceKey = countryCode;
  const publicAuditSummary = initialData ? buildPublicAuditSummary(initialData) : null;
  const activeSnapshot = detail?.latest_snapshot;
  const accuracy = detail?.realized_accuracy_summary;
  const contextSummary = detail?.current_context_summary;
  const isInactive = detail?.tracking_state === "inactive";

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="Watchlist"
        title={`${displayName} 심화 추적`}
        description="최근 예측 변화, 현재 판단 근거, 적중 기록을 한 화면에 모아 두고 필요할 때 종목 상세로 바로 이어집니다."
        meta={
          <>
            <span className="info-chip">{initialTicker}</span>
            <span className="info-chip">{countryCode}</span>
            <span className="info-chip">{detail?.tracking_state === "active" ? "추적 중" : "추적 준비"}</span>
          </>
        }
        actions={
          <div className="ui-inline-actions">
            <Link href={`/stock/${encodeURIComponent(initialTicker)}`} className="action-chip-secondary">
              종목 상세 보기
            </Link>
            {session && detail ? (
              <button
                onClick={() => void toggleTracking(detail.tracking_state !== "active")}
                className={detail.tracking_state === "active" ? "action-chip-primary" : "action-chip-secondary"}
              >
                {detail.tracking_state === "active" ? "심화 추적 중지" : "심화 추적 시작"}
              </button>
            ) : null}
          </div>
        }
      />

      {initialData ? (
        <section className="card !p-4 space-y-3">
          <PublicAuditStrip meta={initialData} />
          {publicAuditSummary ? (
            <p className="text-sm leading-relaxed text-text-secondary">{publicAuditSummary}</p>
          ) : null}
        </section>
      ) : null}

      <section className="workspace-grid-balanced">
        <div className="card !p-5 space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="section-title">최신 예측 스냅샷</h2>
              <p className="section-copy">현재 저장된 최신 예측값과 최근 판단 근거를 먼저 보여드립니다.</p>
            </div>
            <span className="info-chip self-start">
              최근 기록 {formatPredictionAt(activeSnapshot?.last_prediction_at || detail?.watchlist_meta.last_prediction_at)}
            </span>
          </div>

          {activeSnapshot?.available ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div className="metric-card">
                  <div className="text-xs text-text-secondary">현재가</div>
                  <div className="mt-2 font-mono text-text">{formatPrice(activeSnapshot.current_price, priceKey)}</div>
                </div>
                <div className="metric-card">
                  <div className="text-xs text-text-secondary">대표 예측값</div>
                  <div className="mt-2 font-mono text-text">{formatPrice(activeSnapshot.predicted_close, priceKey)}</div>
                </div>
                <div className="metric-card">
                  <div className="text-xs text-text-secondary">상승 확률</div>
                  <div className="mt-2 font-mono text-text">
                    {activeSnapshot.up_probability != null ? `${activeSnapshot.up_probability.toFixed(1)}%` : "없음"}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="text-xs text-text-secondary">신뢰도</div>
                  <div className="mt-2 font-mono text-text">
                    {activeSnapshot.confidence != null ? activeSnapshot.confidence.toFixed(1) : "없음"}
                  </div>
                </div>
              </div>

              <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-4 text-sm leading-6 text-text-secondary">
                <div className="font-medium text-text">{activeSnapshot.direction_label}</div>
                <div className="mt-2">
                  {activeSnapshot.summary || activeSnapshot.confidence_note || "현재 스냅샷을 기준으로 심화 추적을 이어가고 있습니다."}
                </div>
                {activeSnapshot.target_date ? (
                  <div className="mt-2 text-xs">목표일 {activeSnapshot.target_date}</div>
                ) : null}
              </div>
            </>
          ) : (
            <WorkspaceStateCard
              eyebrow="스냅샷 준비"
              title="현재 스냅샷을 아직 준비하지 못했습니다"
              message="과거 기록은 유지한 채로, 최신 예측 요약이 준비되면 이 영역부터 먼저 채워집니다."
              tone="warning"
              actionLabel="다시 불러오기"
              onAction={() => void reload(true)}
            />
          )}
        </div>

        <div className="card !p-5 space-y-4">
          {!session ? (
            <WorkspaceStateCard
              eyebrow="로그인 필요"
              title="로그인 후 심화 추적 데이터를 이어서 볼 수 있습니다"
              message="이 화면은 공개 shell을 먼저 보여드리고, 로그인 후에는 관심종목 기준의 최근 예측 변화와 적중 기록을 이어서 불러옵니다."
              aside={
                <Link href={`/auth?next=${encodeURIComponent(`/watchlist/${initialTicker}`)}`} className="action-chip-primary">
                  로그인하기
                </Link>
              }
            />
          ) : authLoading || (loading && !detail) ? (
            <WorkspaceLoadingCard
              title="심화 추적 정보를 불러오고 있습니다"
              message="관심종목 여부, 최근 예측 변화, 적중 기록을 한 화면에 맞게 정리하고 있습니다."
              className="min-h-[220px]"
            />
          ) : loadError && !detail ? (
            <WorkspaceStateCard
              eyebrow="심화 추적 지연"
              title="심화 추적 정보를 아직 불러오지 못했습니다"
              message={loadError}
              tone="warning"
              actionLabel="다시 불러오기"
              onAction={() => void reload(true)}
            />
          ) : isInactive ? (
            <WorkspaceStateCard
              eyebrow="추적 준비"
              title="심화 추적을 시작하면 예측 변화 기록이 이어집니다"
              message="관심종목에는 이미 들어 있고, 여기서 추적만 켜면 최신 예측 변화와 적중 기록을 계속 쌓아 확인할 수 있습니다."
              actionLabel="심화 추적 시작"
              onAction={() => void toggleTracking(true)}
            />
          ) : (
            <WorkspaceStateCard
              eyebrow="추적 상태"
              title="심화 추적이 활성화되어 있습니다"
              message="최근 예측 변화, 적중 기록, 현재 판단 근거를 이 화면에서 계속 이어서 확인할 수 있습니다."
              aside={<span className="info-chip">추적 중</span>}
              actionLabel="심화 추적 중지"
              onAction={() => void toggleTracking(false)}
            />
          )}

          {accuracy ? (
            <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-4">
              <div className="text-sm font-semibold text-text">최근 적중·오차 요약</div>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border border-border/60 bg-surface/65 px-3 py-3">
                  <div className="text-[11px] text-text-secondary">평가 가능 기록</div>
                  <div className="mt-2 font-mono text-text">{accuracy.evaluated_count}/{accuracy.sample_count}</div>
                </div>
                <div className="rounded-2xl border border-border/60 bg-surface/65 px-3 py-3">
                  <div className="text-[11px] text-text-secondary">방향 적중률</div>
                  <div className="mt-2 font-mono text-text">
                    {accuracy.direction_hit_rate != null ? `${accuracy.direction_hit_rate.toFixed(1)}%` : "기록 축적 중"}
                  </div>
                </div>
                <div className="rounded-2xl border border-border/60 bg-surface/65 px-3 py-3">
                  <div className="text-[11px] text-text-secondary">평균 오차</div>
                  <div className="mt-2 font-mono text-text">
                    {accuracy.average_absolute_error_pct != null ? formatPct(accuracy.average_absolute_error_pct) : "기록 축적 중"}
                  </div>
                </div>
              </div>
              <div className="mt-3 text-sm leading-6 text-text-secondary">{accuracy.message}</div>
            </div>
          ) : null}
        </div>
      </section>

      {detail ? <ForecastDeltaCard data={buildForecastDeltaPayload(detail)} /> : null}

      <section className="card !p-5 space-y-4">
        <div>
          <h2 className="section-title">현재 판단 근거</h2>
          <p className="section-copy">종목 상세에서 이미 계산한 현재 판단 근거를 심화 추적 흐름에 맞게 다시 모아 보여드립니다.</p>
        </div>

        {contextSummary?.available ? (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-border/60 bg-surface/60 px-4 py-3">
                <div className="text-[11px] text-text-secondary">세팅</div>
                <div className="mt-2 text-sm font-medium text-text">{contextSummary.setup_label || "없음"}</div>
              </div>
              <div className="rounded-2xl border border-border/60 bg-surface/60 px-4 py-3">
                <div className="text-[11px] text-text-secondary">현재 액션</div>
                <div className="mt-2 text-sm font-medium text-text">{contextSummary.action || "없음"}</div>
              </div>
              <div className="rounded-2xl border border-border/60 bg-surface/60 px-4 py-3">
                <div className="text-[11px] text-text-secondary">시장 국면</div>
                <div className="mt-2 text-sm font-medium text-text">{contextSummary.market_regime_label || "없음"}</div>
              </div>
            </div>

            <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-4 text-sm leading-7 text-text-secondary">
              {contextSummary.summary}
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-4">
                <div className="text-sm font-semibold text-text">주요 리스크</div>
                <div className="mt-3 space-y-2 text-sm text-text-secondary">
                  {(contextSummary.key_risks.length > 0
                    ? contextSummary.key_risks
                    : ["현재 공개 리스크 요약을 정리 중입니다."]).map((item) => (
                    <div key={item}>• {item}</div>
                  ))}
                </div>
              </div>

              <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-4">
                <div className="text-sm font-semibold text-text">주요 근거</div>
                <div className="mt-3 space-y-2 text-sm text-text-secondary">
                  {(contextSummary.key_catalysts.length > 0
                    ? contextSummary.key_catalysts
                    : ["현재 핵심 근거를 정리 중입니다."]).map((item) => (
                    <div key={item}>• {item}</div>
                  ))}
                </div>
              </div>
            </div>
          </>
        ) : (
          <WorkspaceStateCard
            eyebrow="근거 준비"
            title="현재 판단 근거를 아직 정리하지 못했습니다"
            message="빠른 스냅샷은 유지한 채로, 현재 해석 포인트와 리스크는 이어서 채워집니다."
            tone="warning"
          />
        )}
      </section>
    </div>
  );
}
