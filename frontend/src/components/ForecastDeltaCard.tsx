import type { ForecastDeltaResponse } from "@/lib/api";
import { changeColor, formatPct } from "@/lib/utils";

interface ForecastDeltaCardProps {
  data: ForecastDeltaResponse;
}

export default function ForecastDeltaCard({ data }: ForecastDeltaCardProps) {
  const summary = data.summary;

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
