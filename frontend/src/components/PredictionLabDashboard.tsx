"use client";

import Link from "next/link";
import type { PredictionLabRadarSummary, PredictionLabResponse } from "@/lib/api";
import { changeColor } from "@/lib/utils";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props {
  data: PredictionLabResponse;
}

function pct(value: number, scaled = true) {
  const resolved = scaled ? value * 100 : value;
  return `${resolved.toFixed(1)}%`;
}

function scopeLabel(label: string) {
  if (label === "country") return "국가";
  if (label === "sector") return "섹터";
  if (label === "stock") return "종목";
  return label;
}

function directionLabel(direction: string) {
  if (direction === "up") return "상승";
  if (direction === "down") return "하락";
  if (direction === "flat") return "보합";
  return direction;
}

function methodLabel(method: string) {
  if (method === "learned_blended_graph") return "학습형 fusion + graph";
  if (method === "learned_blended") return "학습형 fusion";
  if (method === "prior_only") return "prior backbone";
  return method;
}

function fusionStatusLabel(status: string) {
  if (status === "active") return "활성";
  if (status === "bootstrapping") return "표본 축적 중";
  return status;
}

function realizedDirectionLabel(actualClose?: number | null, referencePrice?: number) {
  if (actualClose == null || referencePrice == null) {
    return "대기";
  }
  if (actualClose > referencePrice) return "상승";
  if (actualClose < referencePrice) return "하락";
  return "보합";
}

function severityLabel(severity: string) {
  if (severity === "high") return "우선";
  if (severity === "medium") return "주의";
  return "정보";
}

function severityTone(severity: string) {
  if (severity === "high") return "bg-rose-50 text-rose-600 border-rose-200";
  if (severity === "medium") return "bg-amber-50 text-amber-700 border-amber-200";
  return "bg-sky-50 text-sky-700 border-sky-200";
}

function reviewKindLabel(kind: string) {
  if (kind === "miss") return "미스 복기";
  if (kind === "reversal-miss") return "중기 반전 미스";
  if (kind === "early-hit") return "초기 반응 적중";
  if (kind === "direction-hit") return "밴드 점검";
  if (kind === "clean-hit") return "정상 적중";
  return "평가 대기";
}

const EMPTY_RADAR_SUMMARY: PredictionLabRadarSummary = {
  stored_snapshots: 0,
  capture_days: 0,
  latest_reference_date: null,
  last_evaluated_at: null,
  direction_accuracy_1d: 0,
  direction_accuracy_5d: 0,
  direction_accuracy_20d: 0,
  band_hit_rate_20d: 0,
  avg_return_pct_5d: 0,
  avg_return_pct_20d: 0,
  pending_20d: 0,
  tag_breakdown: [],
  recent_cohorts: [],
  review_queue: [],
  profile: {
    status: "cold-start",
    sample_count: 0,
    top_positive: [],
    top_negative: [],
  },
};

export default function PredictionLabDashboard({ data }: Props) {
  const accuracy = data.accuracy;
  const trendData = data.recent_trend.map((row) => ({
    ...row,
    direction_accuracy_pct: row.direction_accuracy * 100,
    within_range_rate_pct: row.within_range_rate * 100,
  }));
  const horizonRows = data.horizon_accuracy ?? [];
  const empiricalRows = data.empirical_calibration ?? [];
  const empiricalByType = new Map(empiricalRows.map((row) => [row.prediction_type, row]));
  const fusionProfiles = data.fusion_profiles ?? [];
  const fusionProfileByType = new Map(fusionProfiles.map((row) => [row.prediction_type, row]));
  const graphSummary = data.graph_context_summary;
  const fusionStatus = data.fusion_status_summary;
  const actionQueue = data.action_queue ?? [];
  const failurePatterns = data.failure_patterns ?? [];
  const reviewQueue = data.review_queue ?? [];
  const radarSummary = data.radar_cohorts ?? EMPTY_RADAR_SUMMARY;
  const radarCohorts = radarSummary?.recent_cohorts ?? [];
  const radarReviewQueue = radarSummary?.review_queue ?? [];
  const radarProfile = radarSummary?.profile;
  const recentFailures = data.recent_records
    .filter((row) => row.direction_hit === false || row.within_range === false)
    .slice(0, 5);
  const hasValidationSamples = accuracy.total_predictions > 0;
  const hasTrendData =
    trendData.length > 1
    && trendData.some((row) => row.direction_accuracy_pct > 0 || row.within_range_rate_pct > 0 || row.avg_error_pct > 0);
  const hasCountryBreakdown = data.breakdown.by_country.some((row) => row.total > 0);
  const hasScopeBreakdown = data.breakdown.by_scope.some((row) => row.total > 0);
  const hasModelBreakdown = data.breakdown.by_model.some((row) => row.total > 0);
  const hasRecentRecords = data.recent_records.length > 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 xl:grid-cols-5 gap-4">
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">저장된 예측</div>
          <div className="text-2xl font-bold mt-3">{accuracy.stored_predictions}</div>
          <div className="text-[11px] text-text-secondary mt-1">평가 대기 {accuracy.pending_predictions}</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">검증 완료 표본</div>
          <div className="text-2xl font-bold mt-3">{accuracy.total_predictions}</div>
          <div className="text-[11px] text-text-secondary mt-1">실제 종가까지 확인된 건수</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">방향 적중률</div>
          <div className="text-2xl font-bold mt-3">{pct(accuracy.direction_accuracy)}</div>
          <div className="text-[11px] text-text-secondary mt-1">상승/하락 방향 일치율</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">밴드 적중률</div>
          <div className="text-2xl font-bold mt-3">{pct(accuracy.within_range_rate)}</div>
          <div className="text-[11px] text-text-secondary mt-1">실제 종가가 예상 범위 안에 들어온 비율</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">평균 오차</div>
          <div className="text-2xl font-bold mt-3">{accuracy.avg_error_pct.toFixed(2)}%</div>
          <div className="text-[11px] text-text-secondary mt-1">평균 신뢰도 {accuracy.avg_confidence.toFixed(1)}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_0.9fr] gap-5">
        <div className="card !p-4 space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="font-semibold text-base">기회 레이더 상위 10 추적</h2>
              <p className="text-sm text-text-secondary mt-1">
                매일 레이더 상위 후보를 저장한 뒤 1일, 1주, 20거래일 실제 흐름으로 다시 채점합니다.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
              <span className="info-chip">저장 {radarSummary.stored_snapshots}건</span>
              <span className="info-chip">기준일 {radarSummary.capture_days}일</span>
              <span className="info-chip">20D 대기 {radarSummary.pending_20d}건</span>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-border/70 bg-surface/70 px-4 py-3">
              <div className="text-xs text-text-secondary">1D 방향 적중</div>
              <div className="mt-2 text-2xl font-semibold">{pct(radarSummary.direction_accuracy_1d)}</div>
              <div className="mt-1 text-[11px] text-text-secondary">초기 반응 정합도</div>
            </div>
            <div className="rounded-2xl border border-border/70 bg-surface/70 px-4 py-3">
              <div className="text-xs text-text-secondary">5D 방향 적중</div>
              <div className="mt-2 text-2xl font-semibold">{pct(radarSummary.direction_accuracy_5d)}</div>
              <div className="mt-1 text-[11px] text-text-secondary">1주 유지력</div>
            </div>
            <div className="rounded-2xl border border-border/70 bg-surface/70 px-4 py-3">
              <div className="text-xs text-text-secondary">20D 방향 적중</div>
              <div className="mt-2 text-2xl font-semibold">{pct(radarSummary.direction_accuracy_20d)}</div>
              <div className="mt-1 text-[11px] text-text-secondary">중기 방향 유지력</div>
            </div>
            <div className="rounded-2xl border border-border/70 bg-surface/70 px-4 py-3">
              <div className="text-xs text-text-secondary">20D 밴드 적중</div>
              <div className="mt-2 text-2xl font-semibold">{pct(radarSummary.band_hit_rate_20d)}</div>
              <div className="mt-1 text-[11px] text-text-secondary">평균 수익률 {radarSummary.avg_return_pct_20d.toFixed(2)}%</div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-2xl border border-border/70 bg-surface/60 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold">최근 cohort 복기</div>
                <div className="text-xs text-text-secondary">
                  최신 기준일 {radarSummary.latest_reference_date ?? "대기"}
                </div>
              </div>
              <div className="mt-3 space-y-3">
                {radarCohorts.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-border/80 px-3 py-3 text-sm text-text-secondary">
                    아직 저장된 레이더 cohort가 없습니다. 다음 갱신부터 상위 10개 추적이 자동으로 쌓입니다.
                  </div>
                ) : (
                  radarCohorts.map((cohort) => (
                    <div key={cohort.reference_date} className="rounded-xl border border-border/70 bg-white/70 px-3 py-3">
                      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                        <div>
                          <div className="text-sm font-semibold">{cohort.reference_date}</div>
                          <div className="mt-1 text-xs text-text-secondary">
                            저장 {cohort.capture_count} · 평가 완료 {cohort.evaluated_count} · 대기 {cohort.pending_count}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
                          {cohort.top_symbols.map((symbol) => (
                            <span key={symbol} className="info-chip">{symbol}</span>
                          ))}
                        </div>
                      </div>
                      <div className="mt-3 grid gap-2 sm:grid-cols-4 text-xs">
                        <div>
                          <div className="text-text-secondary">1D</div>
                          <div className="mt-1 font-semibold">{pct(cohort.direction_accuracy_1d)}</div>
                        </div>
                        <div>
                          <div className="text-text-secondary">5D</div>
                          <div className="mt-1 font-semibold">{pct(cohort.direction_accuracy_5d)}</div>
                        </div>
                        <div>
                          <div className="text-text-secondary">20D</div>
                          <div className="mt-1 font-semibold">{pct(cohort.direction_accuracy_20d)}</div>
                        </div>
                        <div>
                          <div className="text-text-secondary">밴드 / 수익률</div>
                          <div className="mt-1 font-semibold">{pct(cohort.band_hit_rate_20d)} / {cohort.avg_return_pct_20d.toFixed(2)}%</div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-2xl border border-border/70 bg-surface/60 p-4">
                <div className="text-sm font-semibold">가중 보정 프로필</div>
                <div className="mt-1 text-xs text-text-secondary">
                  상태 {fusionStatusLabel(radarProfile?.status ?? "insufficient")} · 표본 {radarProfile?.sample_count ?? 0}
                </div>
                <div className="mt-3 space-y-2">
                  {(radarProfile?.top_positive ?? []).slice(0, 3).map((item) => (
                    <div key={`positive-${item.key}`} className="flex items-center justify-between gap-3 rounded-xl bg-emerald-50 px-3 py-2 text-sm">
                      <span>{item.label}</span>
                      <span className="font-semibold text-emerald-700">+{(item.delta * 100).toFixed(1)}bp</span>
                    </div>
                  ))}
                  {(radarProfile?.top_negative ?? []).slice(0, 3).map((item) => (
                    <div key={`negative-${item.key}`} className="flex items-center justify-between gap-3 rounded-xl bg-rose-50 px-3 py-2 text-sm">
                      <span>{item.label}</span>
                      <span className="font-semibold text-rose-700">{(item.delta * 100).toFixed(1)}bp</span>
                    </div>
                  ))}
                  {!(radarProfile?.top_positive?.length || radarProfile?.top_negative?.length) ? (
                    <div className="rounded-xl border border-dashed border-border/80 px-3 py-3 text-sm text-text-secondary">
                      아직 cohort 실측이 부족해 보정 가중은 고정하지 않고 있습니다.
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="rounded-2xl border border-border/70 bg-surface/60 p-4">
                <div className="text-sm font-semibold">자주 걸린 태그</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {radarSummary.tag_breakdown.length === 0 ? (
                    <span className="text-sm text-text-secondary">태그 집계 대기 중</span>
                  ) : (
                    radarSummary.tag_breakdown.map((tag) => (
                      <span key={tag.label} className="action-chip-muted">
                        {tag.label} {tag.count}건
                      </span>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="card !p-4 space-y-4">
          <div>
            <h2 className="font-semibold text-base">레이더 복기 큐</h2>
            <p className="text-sm text-text-secondary mt-1">
              미스와 반전 사례를 우선 위로 올려, 다음 점수 보정이 어느 신호에서 시작되는지 보여줍니다.
            </p>
          </div>
          <div className="space-y-3">
            {radarReviewQueue.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border/80 px-3 py-3 text-sm text-text-secondary">
                20거래일 평가가 닫히면 이곳에 상위 cohort 복기 메모가 자동으로 쌓입니다.
              </div>
            ) : (
              radarReviewQueue.map((item) => (
                <div key={`${item.reference_date}-${item.symbol}-${item.rank}`} className="rounded-xl border border-border/70 bg-surface/60 px-3 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold">#{item.rank} {item.symbol}</span>
                        <span className="action-chip-neutral">{reviewKindLabel(item.kind)}</span>
                      </div>
                      <div className="mt-1 text-sm">{item.summary}</div>
                    </div>
                    <div className={`text-sm font-semibold ${changeColor(item.return_pct_20d)}`}>
                      {item.return_pct_20d > 0 ? "+" : ""}{item.return_pct_20d.toFixed(2)}%
                    </div>
                  </div>
                  <div className="mt-2 text-xs leading-6 text-text-secondary">{item.detail}</div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-text-secondary">
                    <span className="info-chip">기준일 {item.reference_date}</span>
                    <span className="info-chip">방향 {item.direction_hit_20d ? "적중" : item.direction_hit_20d === false ? "미스" : "대기"}</span>
                    <span className="info-chip">밴드 {item.within_band_20d ? "적중" : item.within_band_20d === false ? "이탈" : "대기"}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.15fr_1fr] gap-5">
        <div className="card !p-4 space-y-4">
          <div>
            <h2 className="font-semibold text-base">현재 랩이 보고 있는 것</h2>
            <p className="text-sm text-text-secondary mt-1">실제 저장된 예측과 실현 종가를 바탕으로 자동 생성한 진단 메모입니다.</p>
          </div>
          <div className="space-y-2">
            {actionQueue.length === 0 ? (
              <div className="rounded-xl border border-border/70 bg-surface/60 px-3 py-3 text-sm text-text-secondary">
                아직 우선순위를 매길 만큼 충분한 검증 신호가 쌓이지 않았습니다. 아래 진단 메모와 horizon별 지표를 함께 보면서 표본이 더 쌓이기를 기다려 주세요.
              </div>
            ) : (
              actionQueue.map((item) => (
                <div key={item.key} className="rounded-xl border border-border/70 bg-surface/60 px-3 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">{item.title}</div>
                      <div className="mt-1 text-sm text-text-secondary">{item.detail}</div>
                    </div>
                    <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${severityTone(item.severity)}`}>
                      {severityLabel(item.severity)}
                    </span>
                  </div>
                  {item.metric_label && item.metric_value ? (
                    <div className="mt-2 text-xs text-text-secondary">
                      {item.metric_label} · {item.metric_value}
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
          <div className="border-t border-border/70 pt-4 space-y-2">
            <div className="text-xs font-semibold text-text-secondary">자동 진단 메모</div>
            {data.insights.map((insight) => (
              <div key={insight} className="rounded-xl border border-border/70 bg-surface/60 px-3 py-2 text-sm">
                {insight}
              </div>
            ))}
          </div>
        </div>

        <div className="card !p-4">
          <div>
            <h2 className="font-semibold text-base">신뢰도 보정 상태</h2>
            <p className="text-sm text-text-secondary mt-1">신뢰도가 높을수록 실제 방향 적중률도 함께 올라가는지 확인합니다.</p>
          </div>
          {hasValidationSamples ? (
            <div className="h-[320px] mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.calibration}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={(value) => `${value}%`} tick={{ fontSize: 12 }} width={44} />
                  <Tooltip formatter={(value: number) => `${Number(value).toFixed(1)}%`} />
                  <Bar dataKey="direction_accuracy" name="방향 적중률" fill="#7C6AE6" radius={[6, 6, 0, 0]} />
                  <Bar dataKey="avg_confidence" name="평균 신뢰도" fill="#f59e0b" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="workspace-empty-frame mt-4 min-h-[260px] space-y-3">
              <div className="text-sm font-semibold text-text">보정 차트는 표본이 쌓이면 자동으로 채워집니다</div>
              <div className="text-sm leading-6 text-text-secondary">
                지금은 실측 종가 기준 검증 표본이 충분하지 않아 캘리브레이션 막대를 그리지 않고, 현재 모델 상태와 표본 축적 단계를 먼저 보여줍니다.
              </div>
              <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
                <span className="info-chip">검증 완료 {accuracy.total_predictions}건</span>
                <span className="info-chip">표본 축적 중</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.15fr_1fr] gap-5">
        <div className="card !p-4 space-y-3">
          <div>
            <h2 className="font-semibold text-base">Learned Fusion 상태</h2>
            <p className="text-sm text-text-secondary mt-1">
              prior backbone 위에 학습형 fusion이 어느 horizon에서 실제로 활성화됐는지, prior 대비 Brier가 얼마나 줄었는지 먼저 보여줍니다.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {fusionProfiles.map((profile) => (
              <div key={profile.prediction_type} className="rounded-xl border border-border/70 px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">{profile.label}</div>
                    <div className="text-xs text-text-secondary mt-1">
                      {fusionStatusLabel(profile.status)} · {methodLabel(profile.method)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold">{profile.sample_count.toLocaleString("ko-KR")}건</div>
                    <div className="text-xs text-text-secondary mt-1">
                      delta {profile.prior_brier_delta != null ? profile.prior_brier_delta.toFixed(4) : "대기"}
                    </div>
                  </div>
                </div>
                <div className="mt-3 space-y-1 text-xs text-text-secondary">
                  <div>
                    Brier {profile.brier_score != null ? profile.brier_score.toFixed(4) : "대기"} / prior{" "}
                    {profile.prior_brier_score != null ? profile.prior_brier_score.toFixed(4) : "대기"}
                  </div>
                  <div>positive rate {profile.positive_rate.toFixed(1)}% · bucket {profile.profile_bucket ?? "default"}</div>
                  <div>최근 갱신 {profile.fitted_at ? new Date(profile.fitted_at).toLocaleString("ko-KR") : "아직 없음"}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-xl border border-border/70 bg-surface/50 px-3 py-3 text-sm text-text-secondary">
            현재 모델 {fusionStatus.active_model_version} · 평균 blend weight {(fusionStatus.avg_blend_weight * 100).toFixed(1)}% · 마지막 프로필 갱신{" "}
            {fusionStatus.last_refresh_time ? new Date(fusionStatus.last_refresh_time).toLocaleString("ko-KR") : "아직 없음"}
          </div>
        </div>

        <div className="card !p-4 space-y-3">
          <div>
            <h2 className="font-semibold text-base">Graph Context 활용도</h2>
            <p className="text-sm text-text-secondary mt-1">
              피어·섹터·상관관계 기반 경량 graph context가 최근 실측 로그에서 어느 정도 coverage로 들어가는지 같은 기준으로 봅니다.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-border/70 px-3 py-3">
              <div className="text-xs text-text-secondary">활용 비율</div>
              <div className="mt-2 text-2xl font-semibold">{pct(graphSummary.used_rate)}</div>
              <div className="mt-1 text-xs text-text-secondary">검증 로그 {graphSummary.records.toLocaleString("ko-KR")}건 기준</div>
            </div>
            <div className="rounded-xl border border-border/70 px-3 py-3">
              <div className="text-xs text-text-secondary">평균 coverage</div>
              <div className="mt-2 text-2xl font-semibold">{(graphSummary.avg_coverage * 100).toFixed(1)}%</div>
              <div className="mt-1 text-xs text-text-secondary">평균 peer 수 {graphSummary.avg_peer_count.toFixed(1)}</div>
            </div>
          </div>
          <div className="space-y-2">
            {graphSummary.by_horizon.map((row) => (
              <div key={row.prediction_type} className="rounded-xl border border-border/70 px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">{row.label}</div>
                    <div className="text-xs text-text-secondary mt-1">
                      활용 {pct(row.used_rate)} · 평균 coverage {(row.avg_coverage * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="text-right text-xs text-text-secondary">
                    <div>graph score {row.avg_score.toFixed(2)}</div>
                    <div className="mt-1">표본 {row.records.toLocaleString("ko-KR")}건</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[0.95fr_1.05fr] gap-5">
        <div className="card !p-4 space-y-3">
          <div>
            <h2 className="font-semibold text-base">Horizon별 실측 성과</h2>
            <p className="text-sm text-text-secondary mt-1">1D, 5D, 20D 예측을 적중률뿐 아니라 현재 fusion 상태와 graph 활용도까지 같이 봅니다.</p>
          </div>
          <div className="space-y-2">
            {horizonRows.map((row) => (
              <div key={row.prediction_type} className="rounded-xl border border-border/70 px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">{row.label}</div>
                    <div className="text-xs text-text-secondary mt-1">
                      저장 {row.stored_predictions}건 · 평가 완료 {row.total_predictions}건 · 대기 {row.pending_predictions}건
                    </div>
                    <div className="text-xs text-text-secondary mt-1">
                      {methodLabel(row.current_method)} · profile {row.fusion_profile_sample_count.toLocaleString("ko-KR")}건 · {fusionStatusLabel(row.fusion_status)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold">{pct(row.direction_accuracy)}</div>
                    <div className="text-xs text-text-secondary mt-1">평균 오차 {row.avg_error_pct.toFixed(2)}%</div>
                    <div className="text-xs text-text-secondary mt-1">
                      Brier {empiricalByType.get(row.prediction_type)?.brier_score?.toFixed(4) ?? "대기"}
                    </div>
                    <div className="text-xs text-text-secondary mt-1">
                      Gap {empiricalByType.get(row.prediction_type)?.max_reliability_gap?.toFixed(1) ?? "대기"}%
                    </div>
                    <div className="text-xs text-text-secondary mt-1">
                      blend {(row.avg_blend_weight * 100).toFixed(1)}% · graph {(row.graph_coverage * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2 text-xs text-text-secondary">
                  <div>prior 대비 Brier delta {row.prior_brier_delta != null ? row.prior_brier_delta.toFixed(4) : "대기"}</div>
                  <div>graph 활용률 {pct(row.graph_context_used_rate)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card !p-4 space-y-3">
          <div>
            <h2 className="font-semibold text-base">Empirical calibrator 상태</h2>
            <p className="text-sm text-text-secondary mt-1">실측 로그가 쌓일수록 bootstrap prior에서 벗어나 horizon별 sigmoid가 다시 맞춰집니다.</p>
          </div>
          <div className="space-y-2">
            {empiricalRows.length === 0 ? (
              <div className="rounded-xl border border-border/70 px-3 py-3 text-sm text-text-secondary">
                아직 충분한 실측 로그가 쌓이지 않아 empirical calibrator가 bootstrap prior 위주로 동작하고 있습니다.
              </div>
            ) : (
              empiricalRows.map((row) => {
                const fusionProfile = fusionProfileByType.get(row.prediction_type);
                return (
                  <div key={row.prediction_type} className="rounded-xl border border-border/70 px-3 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium">{row.label}</div>
                        <div className="text-xs text-text-secondary mt-1">
                          {row.method} · 표본 {row.sample_count}건 · positive rate {row.positive_rate.toFixed(1)}%
                        </div>
                        <div className="text-xs text-text-secondary mt-1">
                          fusion {methodLabel(fusionProfile?.method ?? "prior_only")}
                          {fusionProfile?.prior_brier_delta != null
                            ? ` · prior delta ${fusionProfile.prior_brier_delta.toFixed(4)}`
                            : ""}
                        </div>
                        <div className="text-xs text-text-secondary mt-1">
                          reliability bin {row.reliability_bins.length}개 · 최대 gap {row.max_reliability_gap.toFixed(1)}%
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-semibold">{row.brier_score.toFixed(4)}</div>
                        <div className="text-xs text-text-secondary mt-1">prior {row.prior_brier_score.toFixed(4)}</div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-5">
        <div className="card !p-4">
          <div>
            <h2 className="font-semibold text-base">최근 검증 추세</h2>
            <p className="text-sm text-text-secondary mt-1">최근 타깃 날짜 기준으로 방향 적중률과 평균 오차 흐름을 함께 봅니다.</p>
          </div>
          {hasTrendData ? (
            <div className="h-[320px] mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="target_date" tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="left" tickFormatter={(value) => `${value}%`} tick={{ fontSize: 12 }} width={44} />
                  <YAxis yAxisId="right" orientation="right" tickFormatter={(value) => `${value}%`} tick={{ fontSize: 12 }} width={44} />
                  <Tooltip
                    formatter={(value: number, name: string) =>
                      name === "방향 적중률"
                        ? `${Number(value).toFixed(1)}%`
                        : `${Number(value).toFixed(2)}%`
                    }
                  />
                  <Line yAxisId="left" type="monotone" dataKey="direction_accuracy_pct" name="방향 적중률" stroke="#7C6AE6" strokeWidth={2} dot={false} />
                  <Line yAxisId="right" type="monotone" dataKey="avg_error_pct" name="평균 오차" stroke="#ef4444" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="workspace-empty-frame mt-4 min-h-[260px] space-y-3">
              <div className="text-sm font-semibold text-text">추세 차트는 아직 공개할 만큼 쌓이지 않았습니다</div>
              <div className="text-sm leading-6 text-text-secondary">
                날짜별 적중률과 평균 오차는 검증 완료 표본이 일정 수준을 넘으면 자동으로 그려집니다. 지금은 horizon별 표본 상태와 fusion/graph 진단을 먼저 읽는 단계입니다.
              </div>
            </div>
          )}
        </div>

        <div className="card !p-4 space-y-4">
          <div>
            <h2 className="font-semibold text-base">시장별 신뢰도</h2>
            <p className="text-sm text-text-secondary mt-1">지금 시점에서 어느 시장에서 모델이 더 안정적으로 작동하는지 보여줍니다.</p>
          </div>
          <div className="space-y-2">
            {!hasCountryBreakdown ? (
              <div className="workspace-empty-frame min-h-[220px] text-sm leading-6 text-text-secondary">
                시장별 비교는 같은 시점의 검증 표본이 더 쌓이면 채워집니다. 지금은 모델이 어느 시장에서 안정적인지 결론을 내리기보다, 전체 표본을 먼저 축적하는 단계입니다.
              </div>
            ) : (
              data.breakdown.by_country.map((row) => (
                <div key={row.label} className="rounded-xl border border-border/70 px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium">{row.label}</div>
                      <div className="text-xs text-text-secondary mt-1">검증 표본 {row.total}건</div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold">{pct(row.direction_accuracy)}</div>
                      <div className="text-xs text-text-secondary mt-1">평균 오차 {row.avg_error_pct.toFixed(2)}%</div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[0.92fr_1.08fr] gap-5">
        <div className="card !p-4 space-y-3">
          <div>
            <h2 className="font-semibold text-base">반복되는 실패 패턴</h2>
            <p className="text-sm text-text-secondary mt-1">최근 미스 기록을 묶어서 어디에서 자주 흔들리는지 먼저 보여줍니다.</p>
          </div>
          {failurePatterns.length === 0 ? (
            <div className="rounded-xl border border-border/70 px-3 py-3 text-sm text-text-secondary">
              아직 반복 패턴으로 묶일 만큼 최근 실패 표본이 충분하지 않습니다. 새 검증 로그가 더 쌓이면 이 영역이 자동으로 채워집니다.
            </div>
          ) : (
            <div className="space-y-2">
              {failurePatterns.map((pattern) => (
                <div key={pattern.key} className="rounded-xl border border-border/70 px-3 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">{pattern.title}</div>
                      <div className="mt-1 text-sm text-text-secondary">{pattern.detail}</div>
                    </div>
                    <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${severityTone(pattern.severity)}`}>
                      {severityLabel(pattern.severity)}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-3 text-xs text-text-secondary">
                    <div>발생 {pattern.count}건</div>
                    <div>평균 오차 {pattern.avg_error_pct.toFixed(2)}%</div>
                    <div>평균 신뢰도 {pattern.avg_confidence.toFixed(1)}</div>
                  </div>
                  {pattern.example_symbol ? (
                    <div className="mt-2 text-xs text-text-secondary">예시 심볼 · {pattern.example_symbol}</div>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card !p-4 space-y-3">
          <div>
            <h2 className="font-semibold text-base">리뷰 큐</h2>
            <p className="text-sm text-text-secondary mt-1">바로 복기할 예측을 우선순위대로 정리해 상세 화면으로 이어서 볼 수 있게 했습니다.</p>
          </div>
          {reviewQueue.length === 0 ? (
            <div className="rounded-xl border border-border/70 px-3 py-3 text-sm text-text-secondary">
              아직 우선 복기할 최근 예측이 충분하지 않습니다. 새 실측 로그가 들어오면 여기서 바로 추적할 수 있습니다.
            </div>
          ) : (
            <div className="space-y-2">
              {reviewQueue.map((item) => (
                <div key={`review-${item.id}`} className="rounded-xl border border-border/70 px-3 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{item.symbol}</span>
                        <span className="text-xs text-text-secondary">{item.prediction_label}</span>
                        <span className="rounded-full border border-border/70 px-2 py-0.5 text-[11px] text-text-secondary">
                          {reviewKindLabel(item.review_kind)}
                        </span>
                      </div>
                      <div className="mt-1 text-sm text-text-secondary">{item.review_summary}</div>
                    </div>
                    {item.stock_path ? (
                      <Link href={item.stock_path} className="ui-button-secondary px-4 text-xs">
                        상세 보기
                      </Link>
                    ) : null}
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-4 text-xs text-text-secondary">
                    <div>
                      목표일 · {item.target_date}
                      {item.country_code ? ` · ${item.country_code}` : ""}
                    </div>
                    <div>신뢰도 · {item.confidence.toFixed(1)}</div>
                    <div>Fusion · {methodLabel(item.fusion_method)}</div>
                    <div>
                      Graph · {item.graph_context_used ? `${(Number(item.graph_coverage ?? 0) * 100).toFixed(0)}%` : "미사용"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card !p-4 space-y-3">
        <div>
          <h2 className="font-semibold text-base">최근 실패 사례</h2>
          <p className="text-sm text-text-secondary mt-1">방향 미스나 밴드 이탈이 있었던 최근 사례를 먼저 공개해 검증 흐름이 좋은 결과만 보여주지 않도록 유지합니다.</p>
        </div>
        {recentFailures.length === 0 ? (
          <div className="rounded-xl border border-border/70 px-3 py-3 text-sm text-text-secondary">
            최근 표본에서는 공개할 실패 사례가 아직 없습니다. 새 실측 로그가 들어오면 이 영역이 자동으로 채워집니다.
          </div>
        ) : (
          <div className="grid gap-3 xl:grid-cols-2">
            {recentFailures.map((row) => (
              <div key={`failure-${row.id}`} className="rounded-xl border border-border/70 px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">{row.symbol}</div>
                    <div className="text-xs text-text-secondary mt-1">
                      {scopeLabel(row.scope)} · {row.target_date}
                      {row.country_code ? ` · ${row.country_code}` : ""}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-text-secondary">예측</div>
                    <div className="font-semibold">{directionLabel(row.direction)}</div>
                    <div className="text-[11px] text-text-secondary mt-1">
                      {methodLabel(row.fusion_method ?? "prior_only")}
                    </div>
                  </div>
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  <div>
                    <div className="text-[11px] text-text-secondary">실현 결과</div>
                    <div className="font-semibold">{realizedDirectionLabel(row.actual_close, row.reference_price)}</div>
                  </div>
                  <div>
                    <div className="text-[11px] text-text-secondary">오차</div>
                    <div className={row.abs_error_pct != null ? changeColor(-Math.abs(row.abs_error_pct)) : "text-text-secondary"}>
                      {row.abs_error_pct != null ? `${row.abs_error_pct.toFixed(2)}%` : "대기"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] text-text-secondary">신뢰도</div>
                    <div className="font-semibold">{row.confidence.toFixed(1)}</div>
                  </div>
                  <div>
                    <div className="text-[11px] text-text-secondary">밴드</div>
                    <div className={row.within_range ? "text-positive" : "text-negative"}>
                      {row.within_range == null ? "대기" : row.within_range ? "밴드 안" : "밴드 밖"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] text-text-secondary">Graph</div>
                    <div className="font-semibold">
                      {row.graph_context_used ? `${(Number(row.graph_coverage ?? 0) * 100).toFixed(0)}%` : "미사용"}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className="card !p-4 space-y-3">
          <div>
            <h2 className="font-semibold text-base">스코프별 안정성</h2>
            <p className="text-sm text-text-secondary mt-1">국가, 종목, 섹터 예측을 분리해서 어느 층이 더 강한지 추적합니다.</p>
          </div>
          {hasScopeBreakdown ? (
            <div className="space-y-2">
              {data.breakdown.by_scope.map((row) => (
                <div key={row.label} className="rounded-xl border border-border/70 px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium">{scopeLabel(row.label)}</div>
                      <div className="text-xs text-text-secondary mt-1">표본 {row.total}건</div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold">{pct(row.direction_accuracy)}</div>
                      <div className="text-xs text-text-secondary mt-1">밴드 적중 {pct(row.within_range_rate)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="workspace-empty-frame min-h-[200px] text-sm leading-6 text-text-secondary">
              국가, 섹터, 종목 스코프를 분리한 안정성 비교는 아직 충분한 공개 표본이 없습니다. 표본이 쌓이면 어느 층이 더 일관적인지 자동으로 채워집니다.
            </div>
          )}
        </div>

        <div className="card !p-4 space-y-3">
          <div>
            <h2 className="font-semibold text-base">모델 버전 추적</h2>
            <p className="text-sm text-text-secondary mt-1">새 버전이 실제로 성능을 개선하는지 비교할 수 있게 했습니다.</p>
          </div>
          {hasModelBreakdown ? (
            <div className="space-y-2">
              {data.breakdown.by_model.map((row) => (
                <div key={row.label} className="rounded-xl border border-border/70 px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium">{row.label}</div>
                      <div className="text-xs text-text-secondary mt-1">표본 {row.total}건</div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold">{pct(row.direction_accuracy)}</div>
                      <div className="text-xs text-text-secondary mt-1">평균 신뢰도 {row.avg_confidence.toFixed(1)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="workspace-empty-frame min-h-[200px] text-sm leading-6 text-text-secondary">
              모델 버전 비교는 아직 버전별 검증 표본이 분리될 만큼 충분하지 않습니다. 현재는 상단의 active model과 fusion 상태를 기준으로 먼저 읽도록 유지합니다.
            </div>
          )}
        </div>
      </div>

      <div className="card !p-4">
        <div>
          <h2 className="font-semibold text-base">최근 예측 로그</h2>
          <p className="text-sm text-text-secondary mt-1">예상 종가와 실제 종가를 빠르게 대조할 수 있는 검증 로그입니다.</p>
        </div>
        {hasRecentRecords ? (
          <div className="overflow-x-auto mt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-text-secondary">
                  <th className="pb-2">심볼</th>
                  <th className="pb-2">구분</th>
                  <th className="pb-2">Fusion</th>
                  <th className="pb-2 text-right">예상 종가</th>
                  <th className="pb-2 text-right">실제 종가</th>
                  <th className="pb-2 text-right">오차</th>
                  <th className="pb-2 text-right">신뢰도</th>
                  <th className="pb-2 text-right">상태</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_records.map((row) => (
                  <tr key={row.id} className="border-b border-border/40">
                    <td className="py-2">
                      <div className="font-medium">{row.symbol}</div>
                      <div className="text-[11px] text-text-secondary">
                        {row.target_date}
                        {row.country_code ? ` • ${row.country_code}` : ""}
                      </div>
                    </td>
                    <td className="py-2">{scopeLabel(row.scope)}</td>
                    <td className="py-2">
                      <div className="font-medium">{methodLabel(row.fusion_method ?? "prior_only")}</div>
                      <div className="text-[11px] text-text-secondary">
                        blend {((row.fusion_blend_weight ?? 0) * 100).toFixed(0)}% · graph{" "}
                        {row.graph_context_used ? `${((row.graph_coverage ?? 0) * 100).toFixed(0)}%` : "미사용"}
                      </div>
                    </td>
                    <td className="py-2 text-right font-mono">{row.predicted_close.toFixed(2)}</td>
                    <td className="py-2 text-right font-mono">{row.actual_close != null ? row.actual_close.toFixed(2) : "대기"}</td>
                    <td className="py-2 text-right font-mono">{row.abs_error_pct != null ? `${row.abs_error_pct.toFixed(2)}%` : "-"}</td>
                    <td className="py-2 text-right">{row.confidence.toFixed(1)}</td>
                    <td
                      className={`py-2 text-right font-medium ${
                        row.direction_hit == null
                          ? "text-text-secondary"
                          : row.direction_hit
                            ? "text-emerald-500"
                            : "text-red-500"
                      }`}
                    >
                      {row.direction_hit == null ? "대기" : row.direction_hit ? "적중" : "미스"}
                      {row.within_range != null ? (
                        <span className={`ml-2 text-[11px] ${changeColor(row.within_range ? 1 : -1)}`}>
                          {row.within_range ? "밴드 안" : "밴드 밖"}
                        </span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="workspace-empty-frame mt-4 min-h-[220px] space-y-3">
            <div className="text-sm font-semibold text-text">최근 예측 로그는 아직 축적 중입니다</div>
            <div className="text-sm leading-6 text-text-secondary">
              지금은 저장된 예측이 많지 않아 표 형식 로그를 크게 비워 두지 않고, 위 카드에서 표본 상태와 fusion/graph 준비 단계를 먼저 읽도록 유지합니다.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
