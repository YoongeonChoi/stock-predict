"use client";

import Link from "next/link";

import type { NextDayFocusRecommendation, ShortTermChartFactor } from "@/lib/types";
import { changeColor, cn, formatPct, formatPrice } from "@/lib/utils";

interface RadarNextDayFocusCardProps {
  focus: NextDayFocusRecommendation;
  embedded?: boolean;
}

function actionMeta(action: string) {
  if (action === "accumulate") return { label: "분할 매수", tone: "bg-positive/10 text-positive" };
  if (action === "breakout_watch") return { label: "돌파 확인", tone: "bg-emerald-500/10 text-emerald-500" };
  if (action === "reduce_risk") return { label: "리스크 축소", tone: "bg-negative/10 text-negative" };
  if (action === "avoid") return { label: "관망", tone: "bg-negative/10 text-negative" };
  return { label: "눌림 대기", tone: "bg-warning/10 text-warning" };
}

function executionBiasMeta(bias?: string | null) {
  if (bias === "press_long") return { label: "추세 우선", tone: "bg-positive/10 text-positive" };
  if (bias === "lean_long") return { label: "상방 우세", tone: "bg-emerald-500/10 text-emerald-500" };
  if (bias === "reduce_risk") return { label: "리스크 관리", tone: "bg-amber-500/10 text-amber-600" };
  if (bias === "capital_preservation") return { label: "방어 우선", tone: "bg-negative/10 text-negative" };
  return { label: "중립 대응", tone: "bg-border/55 text-text-secondary" };
}

function chartSignalMeta(signal: "bullish" | "neutral" | "bearish") {
  if (signal === "bullish") return { label: "차트 우세", tone: "bg-positive/10 text-positive" };
  if (signal === "bearish") return { label: "차트 경계", tone: "bg-negative/10 text-negative" };
  return { label: "차트 중립", tone: "bg-warning/10 text-warning" };
}

function factorTone(signal: "bullish" | "neutral" | "bearish") {
  if (signal === "bullish") return "border-positive/20 bg-positive/5 text-positive";
  if (signal === "bearish") return "border-negative/20 bg-negative/5 text-negative";
  return "border-border/70 bg-surface/70 text-text-secondary";
}

function directionLabel(direction: "up" | "down" | "flat") {
  if (direction === "up") return "상승 우위";
  if (direction === "down") return "하락 우위";
  return "중립";
}

function entryStyleLabel(entryStyle: "pullback" | "breakout" | "balanced" | "stand_aside") {
  if (entryStyle === "pullback") return "눌림 우선";
  if (entryStyle === "breakout") return "돌파 우선";
  if (entryStyle === "stand_aside") return "관망 우선";
  return "유연 대응";
}

function entryRangeText(focus: NextDayFocusRecommendation) {
  const { entry_low, entry_high } = focus.trade_plan;
  if (entry_low != null && entry_high != null) {
    return `${formatPrice(entry_low, focus.country_code)} - ${formatPrice(entry_high, focus.country_code)}`;
  }
  return "미정";
}

function topChartFactors(factors: ShortTermChartFactor[]) {
  return [...factors]
    .sort((left, right) => Math.abs(right.score - 50) - Math.abs(left.score - 50))
    .slice(0, 4);
}

export default function RadarNextDayFocusCard({
  focus,
  embedded = false,
}: RadarNextDayFocusCardProps) {
  const forecast = focus.next_day_forecast;
  const plan = focus.trade_plan;
  const action = actionMeta(plan.action);
  const execution = executionBiasMeta(forecast.execution_bias);
  const chartMeta = chartSignalMeta(focus.chart_analysis.signal);
  const chartFactors = topChartFactors(focus.chart_analysis.factors);

  return (
    <section className={cn(embedded ? "space-y-4" : "card !p-5 space-y-4")}>
      <div className="section-heading gap-4">
        <div>
          <h2 className="section-title">다음 거래일 포커스</h2>
          <p className="section-copy">
            다음 거래일 기준으로 단타 1종목을 다시 고른 추천입니다. 기대수익률만이 아니라
            차트 점수, 손익비, 최근 과열 여부를 함께 반영합니다.
          </p>
        </div>
        <Link
          href={`/stock/${encodeURIComponent(focus.ticker)}`}
          className="action-chip-secondary text-center"
        >
          종목 상세 보기
        </Link>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.16fr)_320px]">
        <div className="workspace-panel space-y-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="rounded-full border border-border/70 bg-surface/70 px-2 py-1 text-text-secondary">
                  {focus.radar_rank != null ? `레이더 #${focus.radar_rank}` : "포커스 추천"}
                </span>
                <span className={`rounded-full px-2 py-1 font-semibold ${action.tone}`}>{action.label}</span>
                <span className={`rounded-full px-2 py-1 ${execution.tone}`}>{execution.label}</span>
                <span className={`rounded-full px-2 py-1 font-semibold ${chartMeta.tone}`}>{chartMeta.label}</span>
              </div>
              <div className="mt-3 flex flex-wrap items-end gap-3">
                <h3 className="text-2xl font-semibold tracking-tight text-text">{focus.name}</h3>
                <span className="text-sm text-text-secondary">{focus.ticker}</span>
                <span className="text-sm text-text-secondary">{focus.sector}</span>
              </div>
              <div className="mt-2 text-sm leading-6 text-text-secondary">{focus.selection_summary}</div>
            </div>
            <div className="rounded-2xl border border-border/70 bg-surface/70 px-4 py-3 text-right">
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
                {forecast.target_date}
              </div>
              <div
                className={`mt-2 text-lg font-semibold ${
                  forecast.direction === "up"
                    ? "text-positive"
                    : forecast.direction === "down"
                      ? "text-negative"
                      : "text-warning"
                }`}
              >
                {directionLabel(forecast.direction)}
              </div>
              <div className="mt-1 text-xs text-text-secondary">확신도 {forecast.confidence.toFixed(0)} / 100</div>
            </div>
          </div>

          <div className="workspace-metric-grid">
            <div className="metric-card">
              <div className="text-[11px] text-text-secondary">기준가</div>
              <div className="mt-2 text-xl font-semibold text-text">
                {formatPrice(focus.current_price, focus.country_code)}
              </div>
              <div className="mt-1 text-[11px] text-text-secondary">조회 시점 기준</div>
            </div>
            <div className="metric-card">
              <div className="text-[11px] text-text-secondary">예상 종가</div>
              <div className="mt-2 text-xl font-semibold text-text">
                {formatPrice(forecast.predicted_close, focus.country_code)}
              </div>
              <div className={`mt-1 text-[11px] ${changeColor(focus.expected_return_pct)}`}>
                {formatPct(focus.expected_return_pct)}
              </div>
            </div>
            <div className="metric-card">
              <div className="text-[11px] text-text-secondary">동일 금액 기준 기대 수익</div>
              <div className={`mt-2 text-xl font-semibold ${changeColor(focus.expected_edge_pct)}`}>
                {formatPct(focus.expected_edge_pct)}
              </div>
              <div className="mt-1 text-[11px] text-text-secondary">
                상승 확률 {focus.profit_probability.toFixed(1)}%
              </div>
            </div>
            <div className="metric-card">
              <div className="text-[11px] text-text-secondary">차트 점수</div>
              <div className="mt-2 text-xl font-semibold text-text">{focus.chart_analysis.score.toFixed(1)} / 100</div>
              <div className="mt-1 text-[11px] text-text-secondary">
                {entryStyleLabel(focus.chart_analysis.entry_style)}
              </div>
            </div>
            <div className="metric-card">
              <div className="text-[11px] text-text-secondary">예상 고가 / 저가</div>
              <div className="mt-2 text-sm font-semibold text-text">
                {formatPrice(forecast.predicted_high, focus.country_code)} /{" "}
                {formatPrice(forecast.predicted_low, focus.country_code)}
              </div>
              <div className="mt-1 text-[11px] text-text-secondary">1일 범위 기준</div>
            </div>
            <div className="metric-card">
              <div className="text-[11px] text-text-secondary">손익비</div>
              <div className="mt-2 text-xl font-semibold text-text">{plan.risk_reward_estimate.toFixed(2)}</div>
              <div className="mt-1 text-[11px] text-text-secondary">{plan.expected_holding_days}거래일 기준</div>
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <div className="workspace-panel-tight">
              <div className="text-xs font-medium text-text-secondary">차트 해석</div>
              <div className="mt-3 rounded-xl border border-border/70 bg-surface/70 px-3 py-3 text-sm leading-6 text-text-secondary">
                {focus.chart_analysis.summary}
              </div>
              <div className="mt-3 grid gap-2">
                {chartFactors.map((factor) => (
                  <div
                    key={factor.key}
                    className={`rounded-xl border px-3 py-3 text-sm ${factorTone(factor.signal)}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium">{factor.label}</span>
                      <span className="text-[11px] font-semibold">{factor.score.toFixed(1)}</span>
                    </div>
                    <div className="mt-1 text-xs leading-5 opacity-90">{factor.detail}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="workspace-panel-tight">
              <div className="text-xs font-medium text-text-secondary">매매 근거</div>
              <div className="mt-3 space-y-2">
                {focus.thesis.map((item) => (
                  <div
                    key={item}
                    className="rounded-xl border border-border/70 bg-surface/70 px-3 py-2 text-sm text-text-secondary"
                  >
                    {item}
                  </div>
                ))}
              </div>
              <div className="mt-3 text-xs font-medium text-text-secondary">실행 메모</div>
              <div className="mt-2 rounded-xl border border-border/70 bg-surface/70 px-3 py-3 text-sm leading-6 text-text-secondary">
                {forecast.execution_note || "시가 추격 여부보다 체결 가격과 손절 기준을 먼저 확인하는 편이 좋습니다."}
              </div>
            </div>
          </div>
        </div>

        <div className="workspace-stack">
          <div className="workspace-panel-tight">
            <div className="text-xs font-medium text-text-secondary">1일 실행 가격</div>
            <div className="mt-3 space-y-3 text-sm">
              <div className="rounded-xl border border-border/70 bg-surface/70 px-3 py-3">
                <div className="text-[11px] text-text-secondary">진입 구간</div>
                <div className="mt-1 font-semibold text-text">{entryRangeText(focus)}</div>
              </div>
              <div className="rounded-xl border border-border/70 bg-surface/70 px-3 py-3">
                <div className="text-[11px] text-text-secondary">손절가</div>
                <div className="mt-1 font-semibold text-negative">
                  {plan.stop_loss != null ? formatPrice(plan.stop_loss, focus.country_code) : "미정"}
                </div>
              </div>
              <div className="rounded-xl border border-border/70 bg-surface/70 px-3 py-3">
                <div className="text-[11px] text-text-secondary">1차 목표 / 2차 목표</div>
                <div className="mt-1 font-semibold text-positive">
                  {plan.take_profit_1 != null ? formatPrice(plan.take_profit_1, focus.country_code) : "미정"}
                  {" / "}
                  {plan.take_profit_2 != null ? formatPrice(plan.take_profit_2, focus.country_code) : "미정"}
                </div>
              </div>
            </div>
          </div>

          <div className="workspace-panel-tight">
            <div className="text-xs font-medium text-text-secondary">운영 규칙</div>
            <div className="mt-3 space-y-3 text-sm text-text-secondary">
              <div className="rounded-xl border border-border/70 bg-surface/70 px-3 py-3">
                <div className="text-[11px] text-text-secondary">예상 보유 기간 / 손익비</div>
                <div className="mt-1 font-semibold text-text">
                  {plan.expected_holding_days}거래일 / {plan.risk_reward_estimate.toFixed(2)}
                </div>
              </div>
              <div className="rounded-xl border border-border/70 bg-surface/70 px-3 py-3">
                <div className="text-[11px] text-text-secondary">차트 진입 스타일</div>
                <div className="mt-1 font-semibold text-text">{entryStyleLabel(focus.chart_analysis.entry_style)}</div>
              </div>
              <div className="rounded-xl border border-border/70 bg-surface/70 px-3 py-3 leading-6">
                <div className="text-[11px] text-text-secondary">무효화 조건</div>
                <div className="mt-1">{plan.invalidation}</div>
              </div>
              {focus.risk_flags.length > 0 ? (
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-3">
                  <div className="text-[11px] text-amber-700">리스크 플래그</div>
                  <div className="mt-2 space-y-2">
                    {focus.risk_flags.map((item) => (
                      <div key={item} className="text-sm leading-6 text-amber-700">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
