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

export default async function LabPage() {
  const data = await timeboxServerPromise(() => getPublicPredictionLab(40, false), 6500, null);
  const accuracySnapshot = data
    ? null
    : await timeboxServerPromise(() => getPublicPredictionAccuracy(), 2500, null);
  const horizonRows = data?.horizon_accuracy ?? [];
  const empiricalByType = new Map((data?.empirical_calibration ?? []).map((row) => [row.prediction_type, row]));
  const fusionSummary = data?.fusion_status_summary;

  return (
    <div className="page-shell">
      <PageHeader
        variant="compact"
        eyebrow="예측 검증"
        title="예측 연구실"
        description={
          data
            ? `1D / 5D / 20D 실측 검증 ${data.accuracy.total_predictions.toLocaleString("ko-KR")}건 기준 / 방향 적중 ${pct(data.accuracy.direction_accuracy)} / 밴드 적중 ${pct(data.accuracy.within_range_rate)} / 평균 오차 ${data.accuracy.avg_error_pct.toFixed(2)}% / 모델 ${fusionSummary?.active_model_version ?? "dist-studentt-v3.3-lfgraph"}`
            : "예측 방향 적중률, 밴드 적중률, 평균 오차, 보정 상태를 같은 기준으로 묶어 공개 검증 흐름을 먼저 보여줍니다."
        }
        meta={
          <>
            <span className="info-chip">방향 적중률</span>
            <span className="info-chip">Calibration 추적</span>
          </>
        }
      />

      {data ? (
        <>
          <section className="card !p-5 space-y-4">
            <div className="section-heading gap-4">
              <div>
                <h2 className="section-title">공개 검증 스냅샷</h2>
                <p className="section-copy">실측 로그를 기준으로 1D, 5D, 20D 예측이 지금 어떤 성능과 보정 상태를 보이는지 같은 기준으로 먼저 공개합니다.</p>
              </div>
              <PublicAuditStrip meta={{ generated_at: data.generated_at, partial: data.partial, fallback_reason: data.fallback_reason }} staleLabel="실측 로그 기준" />
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {horizonRows.map((row) => {
                const empirical = empiricalByType.get(row.prediction_type);
                return (
                  <div key={row.prediction_type} className="metric-card">
                    <div className="text-xs text-text-secondary">{row.label}</div>
                    <div className="mt-2 text-2xl font-semibold text-text">{pct(row.direction_accuracy)}</div>
                    <div className="mt-1 text-xs text-text-secondary">표본 {row.total_predictions.toLocaleString("ko-KR")}건 · Brier {empirical?.brier_score?.toFixed(4) ?? "대기"}</div>
                    <div className="mt-1 text-xs text-text-secondary">Reliability gap {empirical ? `${empirical.max_reliability_gap.toFixed(1)}%` : "대기"}</div>
                  </div>
                );
              })}
              <div className="metric-card">
                <div className="text-xs text-text-secondary">최근 생성</div>
                <div className="mt-2 text-sm font-semibold text-text">{new Date(data.generated_at).toLocaleString("ko-KR")}</div>
                <div className="mt-1 text-xs text-text-secondary">평가 완료 {data.accuracy.total_predictions.toLocaleString("ko-KR")}건</div>
                <div className="mt-1 text-xs text-text-secondary">평가 대기 {data.accuracy.pending_predictions.toLocaleString("ko-KR")}건</div>
              </div>
              <div className="metric-card">
                <div className="text-xs text-text-secondary">Learned Fusion</div>
                <div className="mt-2 text-sm font-semibold text-text">{fusionSummary?.active_model_version ?? "dist-studentt-v3.3-lfgraph"}</div>
                <div className="mt-1 text-xs text-text-secondary">
                  평균 blend {(Number(fusionSummary?.avg_blend_weight ?? 0) * 100).toFixed(1)}%
                </div>
                <div className="mt-1 text-xs text-text-secondary">
                  graph coverage {Number(data.graph_context_summary?.avg_coverage ?? 0).toFixed(2)}
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
              <h2 className="section-title">공개 검증 스냅샷</h2>
              <p className="section-copy">상세 검증 테이블이 지연돼 핵심 적중률과 평균 오차만 먼저 공개합니다.</p>
            </div>
            <PublicAuditStrip meta={accuracySnapshot} staleLabel="실측 로그 기준" />
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <div className="metric-card">
              <div className="text-xs text-text-secondary">저장된 예측</div>
              <div className="mt-2 text-2xl font-semibold text-text">{accuracySnapshot.stored_predictions.toLocaleString("ko-KR")}</div>
              <div className="mt-1 text-xs text-text-secondary">평가 대기 {accuracySnapshot.pending_predictions.toLocaleString("ko-KR")}건</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">검증 완료 표본</div>
              <div className="mt-2 text-2xl font-semibold text-text">{accuracySnapshot.total_predictions.toLocaleString("ko-KR")}</div>
              <div className="mt-1 text-xs text-text-secondary">실제 종가까지 확인된 건수</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">방향 적중률</div>
              <div className="mt-2 text-2xl font-semibold text-text">{pct(accuracySnapshot.direction_accuracy)}</div>
              <div className="mt-1 text-xs text-text-secondary">상세 horizon 표는 잠시 뒤 다시 확인해 주세요.</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">밴드 적중률</div>
              <div className="mt-2 text-2xl font-semibold text-text">{pct(accuracySnapshot.within_range_rate)}</div>
              <div className="mt-1 text-xs text-text-secondary">분포형 예측 밴드 기준</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">평균 오차</div>
              <div className="mt-2 text-2xl font-semibold text-text">{accuracySnapshot.avg_error_pct.toFixed(2)}%</div>
              <div className="mt-1 text-xs text-text-secondary">평균 신뢰도 {accuracySnapshot.avg_confidence.toFixed(1)}</div>
            </div>
          </div>
        </section>
      ) : (
        <WorkspaceStateCard
          kind="blocking"
          eyebrow="예측 검증 지연"
          title="예측 연구실 데이터를 아직 불러오지 못했습니다"
          message="실측 검증 스냅샷이 준비되면 1D, 5D, 20D 성과와 보정 상태를 같은 화면에서 바로 확인할 수 있습니다."
        />
      )}
    </div>
  );
}
