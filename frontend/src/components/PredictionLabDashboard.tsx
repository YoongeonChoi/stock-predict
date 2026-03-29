"use client";

import type { PredictionLabResponse } from "@/lib/api";
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
  const recentFailures = data.recent_records
    .filter((row) => row.direction_hit === false || row.within_range === false)
    .slice(0, 5);

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

      <div className="grid grid-cols-1 xl:grid-cols-[1.15fr_1fr] gap-5">
        <div className="card !p-4 space-y-4">
          <div>
            <h2 className="font-semibold text-base">현재 랩이 보고 있는 것</h2>
            <p className="text-sm text-text-secondary mt-1">실제 저장된 예측과 실현 종가를 바탕으로 자동 생성한 진단 메모입니다.</p>
          </div>
          <div className="space-y-2">
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
        </div>

        <div className="card !p-4 space-y-4">
          <div>
            <h2 className="font-semibold text-base">시장별 신뢰도</h2>
            <p className="text-sm text-text-secondary mt-1">지금 시점에서 어느 시장에서 모델이 더 안정적으로 작동하는지 보여줍니다.</p>
          </div>
          <div className="space-y-2">
            {data.breakdown.by_country.length === 0 ? (
              <div className="text-sm text-text-secondary">검증 표본이 아직 충분히 쌓이지 않았습니다.</div>
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
        </div>

        <div className="card !p-4 space-y-3">
          <div>
            <h2 className="font-semibold text-base">모델 버전 추적</h2>
            <p className="text-sm text-text-secondary mt-1">새 버전이 실제로 성능을 개선하는지 비교할 수 있게 했습니다.</p>
          </div>
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
        </div>
      </div>

      <div className="card !p-4">
        <div>
          <h2 className="font-semibold text-base">최근 예측 로그</h2>
          <p className="text-sm text-text-secondary mt-1">예상 종가와 실제 종가를 빠르게 대조할 수 있는 검증 로그입니다.</p>
        </div>
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
      </div>
    </div>
  );
}
