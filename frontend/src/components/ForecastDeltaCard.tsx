import type { ForecastDeltaResponse } from "@/lib/api";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

interface ForecastDeltaCardProps {
  data: ForecastDeltaResponse;
  priceKey?: string;
}

function touchLabel(value: boolean | null | undefined, readyLabel: string) {
  if (value == null) return "평가 대기";
  return value ? readyLabel : "미접촉";
}

export default function ForecastDeltaCard({ data, priceKey = "KR" }: ForecastDeltaCardProps) {
  const summary = data.summary;
  const weeklyPlan = data.weekly_plan;

  return (
    <div className="card !p-0 overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <h2 className="section-title">예측 변화 추적</h2>
        <p className="section-copy">직전 저장값과 비교해 상방 확률, 신뢰도, 방향이 얼마나 흔들렸는지 확인합니다.</p>
      </div>
      <div className="px-5 py-5">
        {!summary.available ? (
          <div className="rounded-2xl border border-border/70 bg-surface/45 px-4 py-4 text-sm text-text-secondary">{summary.message}</div>
        ) : (
          <>
            <div className="grid gap-3 md:grid-cols-4">
              <div className="metric-card">
                <div className="text-xs text-text-secondary">현재 방향</div>
                <div className="mt-2 font-semibold text-text">{summary.current_direction_label}</div>
              </div>
              <div className="metric-card">
                <div className="text-xs text-text-secondary">상방 확률 변화</div>
                <div className={`mt-2 font-mono ${changeColor(summary.up_probability_delta ?? 0)}`}>{formatPct(summary.up_probability_delta ?? 0)}</div>
              </div>
              <div className="metric-card">
                <div className="text-xs text-text-secondary">예측 종가 변화</div>
                <div className={`mt-2 font-mono ${changeColor(summary.predicted_close_delta_pct ?? 0)}`}>{formatPct(summary.predicted_close_delta_pct ?? 0)}</div>
              </div>
              <div className="metric-card">
                <div className="text-xs text-text-secondary">최근 적중률</div>
                <div className="mt-2 font-mono text-text">{summary.hit_rate != null ? `${summary.hit_rate.toFixed(1)}%` : "없음"}</div>
              </div>
            </div>

            <div className="mt-4 rounded-2xl border border-border/70 bg-surface/45 px-4 py-4 text-sm text-text-secondary">
              {summary.message}
            </div>

            {weeklyPlan ? (
              <div className="mt-4 rounded-2xl border border-border/70 bg-surface/45 px-4 py-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-text">이번 주 판단 검증</h3>
                    <p className="mt-1 text-sm leading-6 text-text-secondary">{weeklyPlan.message}</p>
                  </div>
                  {weeklyPlan.available ? (
                    <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
                      <span className="rounded-full border border-border/70 px-2 py-1">
                        평가 {weeklyPlan.evaluated_count ?? 0}건
                      </span>
                      <span className="rounded-full border border-border/70 px-2 py-1">
                        목표 {weeklyPlan.target_hit_rate != null ? `${weeklyPlan.target_hit_rate.toFixed(1)}%` : "대기"}
                      </span>
                      <span className="rounded-full border border-border/70 px-2 py-1">
                        손절 {weeklyPlan.stop_hit_rate != null ? `${weeklyPlan.stop_hit_rate.toFixed(1)}%` : "대기"}
                      </span>
                    </div>
                  ) : null}
                </div>
                {weeklyPlan.history.length > 0 ? (
                  <div className="mt-3 space-y-2">
                    {weeklyPlan.history.slice(0, 3).map((item) => (
                      <div key={`${item.target_date}:${item.created_at ?? ""}`} className="rounded-xl border border-border/60 bg-background/40 px-3 py-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-sm font-medium text-text">목표일 {item.target_date} · {item.outcome_label}</span>
                          <span className="text-xs text-text-secondary">신뢰도 {item.confidence.toFixed(1)} · 상방 {item.up_probability.toFixed(1)}%</span>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-secondary">
                          {item.buy_price != null ? <span>매수가 {formatPrice(item.buy_price, priceKey)}</span> : null}
                          {item.sell_price != null ? <span>매도가 {formatPrice(item.sell_price, priceKey)}</span> : null}
                          {item.stop_loss != null ? <span>손절 {formatPrice(item.stop_loss, priceKey)}</span> : null}
                          {item.window_low != null && item.window_high != null ? (
                            <span>실제 범위 {formatPrice(item.window_low, priceKey)} - {formatPrice(item.window_high, priceKey)}</span>
                          ) : null}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-text-secondary">
                          <span className="rounded-full bg-border/40 px-2 py-1">{touchLabel(item.buy_zone_touched, "매수 접촉")}</span>
                          <span className="rounded-full bg-border/40 px-2 py-1">{touchLabel(item.sell_zone_touched, "목표 접촉")}</span>
                          <span className="rounded-full bg-border/40 px-2 py-1">{touchLabel(item.stop_loss_touched, "손절 접촉")}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="mt-4 space-y-2">
              {data.history.slice(0, 5).map((item) => (
                <div key={`${item.target_date}:${item.created_at}`} className="rounded-2xl border border-border/70 bg-surface/50 px-4 py-3">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="text-sm font-medium text-text">목표일 {item.target_date} · {item.direction_label}</div>
                    <div className="text-xs text-text-secondary">신뢰도 {item.confidence.toFixed(1)} · 상방 {item.up_probability.toFixed(1)}%</div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-4 text-xs text-text-secondary">
                    <span>예측 종가 {item.predicted_close.toLocaleString()}</span>
                    {item.actual_close != null ? <span>실제 종가 {Number(item.actual_close).toLocaleString()}</span> : null}
                    <span>{item.direction_hit == null ? "평가 대기" : item.direction_hit ? "방향 적중" : "방향 빗나감"}</span>
                    <span>{item.model_version}</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
