import PageHeader from "@/components/PageHeader";
import PredictionLabDashboard from "@/components/PredictionLabDashboard";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import WorkspaceStateCard from "@/components/WorkspaceStateCard";
import { getPublicPredictionAccuracy, getPublicPredictionLab } from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";

export const revalidate = 0;

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "아직 없음";
  }
  return new Date(value).toLocaleString("ko-KR");
}

export default async function LabPage() {
  const data = await timeboxServerPromise(() => getPublicPredictionLab(40, false), 6500, null);
  const accuracySnapshot = data
    ? null
    : await timeboxServerPromise(() => getPublicPredictionAccuracy(), 2500, null);
  const pipelineHealth = data?.pipeline_health;
  const pipelineAlerts = data?.pipeline_alerts ?? [];
  const coverageRows = data?.coverage_breakdown.by_prediction_type ?? [];
  const fusionSummary = data?.fusion_status_summary;

  return (
    <div className="page-shell">
      <PageHeader
        variant="compact"
        eyebrow="예측 검증 워크스페이스"
        title="예측 연구실"
        description={
          data
            ? `표본 저장 ${pipelineHealth?.stored_predictions.toLocaleString("ko-KR") ?? 0}건 / 평가 완료 ${pipelineHealth?.evaluated_predictions.toLocaleString("ko-KR") ?? 0}건 / 실측 대기 ${pipelineHealth?.pending_predictions.toLocaleString("ko-KR") ?? 0}건 / 모델 ${fusionSummary?.active_model_version ?? "dist-studentt-v3.3-lfgraph"}`
            : "표본 저장, 실측 평가, calibration 상태를 한 화면에서 묶어 보고 어떤 horizon이 비어 있는지 먼저 확인합니다."
        }
        meta={
          <>
            <span className="info-chip">표본 수집 퍼널</span>
            <span className="info-chip">Calibration 추적</span>
          </>
        }
      />

      {data ? (
        <>
          <section className="card !p-5 space-y-5">
            <div className="section-heading gap-4">
              <div>
                <h2 className="section-title">표본 수집 퍼널</h2>
                <p className="section-copy">
                  연구실이 비어 보이면 성과 카드보다 먼저 저장 경로와 평가 지연 여부를 확인합니다.
                </p>
              </div>
              <PublicAuditStrip
                meta={{ generated_at: data.generated_at, partial: data.partial, fallback_reason: data.fallback_reason }}
                staleLabel="연구실 집계 기준"
              />
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="metric-card">
                <div className="text-xs text-text-secondary">저장된 표본</div>
                <div className="mt-2 text-2xl font-semibold text-text">
                  {pipelineHealth?.stored_predictions.toLocaleString("ko-KR") ?? "0"}
                </div>
                <div className="mt-1 text-xs text-text-secondary">
                  최근 backfill 복구 {pipelineHealth?.backfill_captured_predictions.toLocaleString("ko-KR") ?? "0"}건
                </div>
              </div>
              <div className="metric-card">
                <div className="text-xs text-text-secondary">평가 완료</div>
                <div className="mt-2 text-2xl font-semibold text-text">
                  {pipelineHealth?.evaluated_predictions.toLocaleString("ko-KR") ?? "0"}
                </div>
                <div className="mt-1 text-xs text-text-secondary">
                  마지막 평가 {formatDateTime(pipelineHealth?.last_evaluated_at)}
                </div>
              </div>
              <div className="metric-card">
                <div className="text-xs text-text-secondary">실측 대기</div>
                <div className="mt-2 text-2xl font-semibold text-text">
                  {pipelineHealth?.pending_predictions.toLocaleString("ko-KR") ?? "0"}
                </div>
                <div className="mt-1 text-xs text-text-secondary">
                  지연 표본 {pipelineHealth?.stale_pending_predictions.toLocaleString("ko-KR") ?? "0"}건
                </div>
              </div>
              <div className="metric-card">
                <div className="text-xs text-text-secondary">최근 저장</div>
                <div className="mt-2 text-sm font-semibold text-text">
                  {formatDateTime(pipelineHealth?.last_saved_at)}
                </div>
                <div className="mt-1 text-xs text-text-secondary">
                  마지막 점검 {formatDateTime(pipelineHealth?.last_checked_at)}
                </div>
              </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="section-slab-subtle !p-4">
                <div className="text-sm font-semibold text-text">Horizon 커버리지</div>
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  {coverageRows.map((row) => (
                    <div key={row.label} className="metric-strip">
                      <div className="text-xs text-text-secondary">{row.label}</div>
                      <div className="mt-2 text-lg font-semibold text-text">
                        {row.stored_predictions.toLocaleString("ko-KR")}건
                      </div>
                      <div className="mt-1 text-xs text-text-secondary">
                        평가 {row.evaluated_predictions.toLocaleString("ko-KR")} / 대기 {row.pending_predictions.toLocaleString("ko-KR")}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="section-slab-subtle !p-4">
                <div className="text-sm font-semibold text-text">지금 막히는 지점</div>
                <div className="mt-3 space-y-2">
                  {pipelineAlerts.length > 0 ? (
                    pipelineAlerts.map((alert) => (
                      <div key={alert.key} className="section-slab-muted !px-3 !py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-medium text-text">{alert.title}</div>
                            <div className="mt-1 text-sm text-text-secondary">{alert.detail}</div>
                          </div>
                          <span className="status-token">{alert.severity}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="section-slab-muted !px-3 !py-3 text-sm text-text-secondary">
                      현재 공개 연구실 기준으로는 즉시 조치가 필요한 수집 경고가 크지 않습니다. 아래 검증 섹션에서 horizon별 성과와 review queue를 이어서 확인해 주세요.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>

          <PredictionLabDashboard data={data} />
        </>
      ) : accuracySnapshot ? (
        <section className="card !p-5 space-y-4">
          <div className="section-heading gap-4">
            <div>
              <h2 className="section-title">공개 검증 요약</h2>
              <p className="section-copy">
                세부 연구실 집계가 지연될 때는 저장 표본과 방향 정확도 요약만 먼저 보여줍니다.
              </p>
            </div>
            <PublicAuditStrip meta={accuracySnapshot} staleLabel="예측 로그 기준" />
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <div className="metric-card">
              <div className="text-xs text-text-secondary">저장된 표본</div>
              <div className="mt-2 text-2xl font-semibold text-text">
                {accuracySnapshot.stored_predictions.toLocaleString("ko-KR")}
              </div>
              <div className="mt-1 text-xs text-text-secondary">
                실측 대기 {accuracySnapshot.pending_predictions.toLocaleString("ko-KR")}건
              </div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">평가 완료</div>
              <div className="mt-2 text-2xl font-semibold text-text">
                {accuracySnapshot.total_predictions.toLocaleString("ko-KR")}
              </div>
              <div className="mt-1 text-xs text-text-secondary">실제 종가 기준 검증</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">방향 정확도</div>
              <div className="mt-2 text-2xl font-semibold text-text">{pct(accuracySnapshot.direction_accuracy)}</div>
              <div className="mt-1 text-xs text-text-secondary">상세 horizon은 잠시 후 다시 확인해 주세요.</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">밴드 적중률</div>
              <div className="mt-2 text-2xl font-semibold text-text">{pct(accuracySnapshot.within_range_rate)}</div>
              <div className="mt-1 text-xs text-text-secondary">분포형 예측 기준</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">평균 오차</div>
              <div className="mt-2 text-2xl font-semibold text-text">{accuracySnapshot.avg_error_pct.toFixed(2)}%</div>
              <div className="mt-1 text-xs text-text-secondary">평균 confidence {accuracySnapshot.avg_confidence.toFixed(1)}</div>
            </div>
          </div>
        </section>
      ) : (
        <WorkspaceStateCard
          kind="blocking"
          eyebrow="예측 검증 지연"
          title="예측 연구실 데이터를 아직 불러오지 못했습니다"
          message="표본 저장과 실측 평가 집계가 준비되면 1D, 5D, 20D 성과와 calibration 상태를 같은 화면에서 바로 확인할 수 있습니다."
        />
      )}
    </div>
  );
}
