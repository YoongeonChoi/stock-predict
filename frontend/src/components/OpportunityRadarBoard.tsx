"use client";

import Link from "next/link";

import type { OpportunityRadarResponse } from "@/lib/types";
import { cn, changeColor, formatPct, formatPrice } from "@/lib/utils";

interface Props {
  data: OpportunityRadarResponse;
  compact?: boolean;
  embedded?: boolean;
}

function actionTone(action: string) {
  if (action === "accumulate" || action === "breakout_watch") return "text-positive bg-positive/10";
  if (action === "reduce_risk" || action === "avoid") return "text-negative bg-negative/10";
  return "text-warning bg-warning/10";
}

function actionLabel(action: string) {
  if (action === "accumulate") return "분할 매수";
  if (action === "breakout_watch") return "돌파 감시";
  if (action === "reduce_risk") return "리스크 축소";
  if (action === "wait_pullback") return "눌림 대기";
  if (action === "avoid") return "관망";
  return action.replaceAll("_", " ");
}

function executionBiasLabel(bias?: string) {
  if (bias === "press_long") return "추세 대응";
  if (bias === "lean_long") return "상방 우세";
  if (bias === "reduce_risk") return "리스크 관리";
  if (bias === "capital_preservation") return "방어 우선";
  return "선별 대응";
}

function executionBiasTone(bias?: string) {
  if (bias === "press_long") return "text-positive bg-positive/10";
  if (bias === "lean_long") return "text-emerald-500 bg-emerald-500/10";
  if (bias === "reduce_risk") return "text-amber-500 bg-amber-500/10";
  if (bias === "capital_preservation") return "text-negative bg-negative/10";
  return "text-text-secondary bg-border/40";
}

function priceRange(low?: number | null, high?: number | null, key = "KR") {
  if (low == null && high == null) return "미정";
  if (low != null && high != null) return `${formatPrice(low, key)} - ${formatPrice(high, key)}`;
  return formatPrice(low ?? high, key);
}

export default function OpportunityRadarBoard({ data, compact = false, embedded = false }: Props) {
  const items = compact ? data.opportunities.slice(0, 4) : data.opportunities;
  const usingFallbackUniverse = data.universe_source === "fallback";

  if (compact) {
    return (
      <div className={cn("min-w-0 space-y-4", embedded ? "" : "card !p-5")}>
        <div className="space-y-3">
          {!embedded ? (
            <div>
              <h2 className="font-semibold">기회 레이더</h2>
              <p className="mt-1 text-sm text-text-secondary">
                KR 유니버스 {data.universe_size}개 중 {data.total_scanned}개를 1차 스캔했고, 상위 {data.detailed_scanned_count}개를 정밀 분석했습니다.
              </p>
            </div>
          ) : null}

          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            {usingFallbackUniverse ? (
              <div className="inline-flex rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-700">
                {data.universe_note || "실시간 유니버스 연결이 제한돼 기본 종목군으로 추천 중입니다."}
              </div>
            ) : (
              <div className="inline-flex rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-700">
                실시간 유니버스 기반 추천
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:w-[420px]">
              <div className="rounded-2xl border border-border/70 bg-surface/70 px-3 py-2 text-center">
                <div className="text-[11px] text-text-secondary">전체 유니버스</div>
                <div className="mt-1 font-semibold">{data.universe_size}</div>
              </div>
              <div className="rounded-2xl border border-border/70 bg-surface/70 px-3 py-2 text-center">
                <div className="text-[11px] text-text-secondary">1차 스캔</div>
                <div className="mt-1 font-semibold">{data.total_scanned}</div>
              </div>
              <div className="rounded-2xl border border-border/70 bg-accent/10 px-3 py-2 text-center">
                <div className="text-[11px] text-text-secondary">정밀 분석</div>
                <div className="mt-1 font-semibold text-accent">{data.detailed_scanned_count}</div>
              </div>
              <div className="rounded-2xl border border-border/70 bg-positive/10 px-3 py-2 text-center">
                <div className="text-[11px] text-text-secondary">표시 후보</div>
                <div className="mt-1 font-semibold text-positive">{data.actionable_count}</div>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          {items.map((item) => (
            <Link
              key={item.ticker}
              href={`/stock/${encodeURIComponent(item.ticker)}`}
              className="block rounded-[22px] border border-border/80 bg-surface/65 px-4 py-4 transition-colors hover:border-accent/45"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-text-secondary">#{item.rank}</span>
                    <span className="truncate font-semibold text-text">{item.name}</span>
                    <span className="text-xs text-text-secondary">{item.ticker}</span>
                  </div>
                  <div className="mt-1 truncate text-xs text-text-secondary">{item.sector}</div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-lg font-bold">{item.opportunity_score.toFixed(1)}</div>
                  <div className="text-[11px] text-text-secondary">레이더 점수</div>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                <span className={`rounded-full px-2 py-1 font-semibold uppercase tracking-wide ${actionTone(item.action)}`}>
                  {actionLabel(item.action)}
                </span>
                <span className={`rounded-full px-2 py-1 ${executionBiasTone(item.execution_bias)}`}>
                  {executionBiasLabel(item.execution_bias)}
                </span>
                <span className="rounded-full bg-border/35 px-2 py-1 text-text-secondary">{item.setup_label}</span>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
                  <div className="text-[11px] text-text-secondary">현재가</div>
                  <div className="mt-1 font-semibold">{formatPrice(item.current_price, item.country_code)}</div>
                  <div className={`text-[11px] ${changeColor(item.change_pct)}`}>{formatPct(item.change_pct)}</div>
                </div>
                <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
                  <div className="text-[11px] text-text-secondary">상승 확률</div>
                  <div className="mt-1 font-semibold">{item.up_probability.toFixed(1)}%</div>
                  <div className="text-[11px] text-text-secondary">신뢰도 {item.confidence.toFixed(0)}</div>
                </div>
                <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
                  <div className="text-[11px] text-text-secondary">예상 수익률</div>
                  <div className={`mt-1 font-semibold ${changeColor(item.predicted_return_pct)}`}>
                    {formatPct(item.predicted_return_pct)}
                  </div>
                  <div className="text-[11px] text-text-secondary">손익비 {item.risk_reward_estimate.toFixed(2)}</div>
                </div>
                <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
                  <div className="text-[11px] text-text-secondary">진입 구간</div>
                  <div className="mt-1 font-semibold">{priceRange(item.entry_low, item.entry_high, item.country_code)}</div>
                </div>
              </div>

              <div className="mt-3 text-sm leading-6 text-text-secondary line-clamp-2">
                {item.thesis[0] || "핵심 메모가 아직 없습니다."}
              </div>

              {item.risk_flags.length > 0 ? (
                <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-600">
                  {item.risk_flags[0]}
                </div>
              ) : null}
            </Link>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("min-w-0", embedded ? "" : "card")}>
      <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="font-semibold">기회 레이더</h2>
          <p className="mt-1 text-sm text-text-secondary">
            KR 유니버스 {data.universe_size}개 중 {data.total_scanned}개를 1차 스캔했고, 상위 {data.detailed_scanned_count}개를 정밀 분석해 {data.opportunities.length}개 후보를 표시합니다.
          </p>
          {usingFallbackUniverse ? (
            <div className="mt-2 inline-flex rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-700">
              {data.universe_note || "실시간 유니버스 연결이 제한돼 기본 종목군으로 추천 중입니다."}
            </div>
          ) : (
            <div className="mt-2 inline-flex rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-700">
              실시간 유니버스 기반 추천
            </div>
          )}
        </div>
        <div className="grid shrink-0 grid-cols-2 gap-2 text-center sm:grid-cols-4">
          <div className="rounded-lg bg-border/40 px-3 py-2">
            <div className="text-[11px] text-text-secondary">전체 유니버스</div>
            <div className="font-bold">{data.universe_size}</div>
          </div>
          <div className="rounded-lg bg-border/40 px-3 py-2">
            <div className="text-[11px] text-text-secondary">1차 스캔</div>
            <div className="font-bold">{data.total_scanned}</div>
          </div>
          <div className="rounded-lg bg-accent/10 px-3 py-2">
            <div className="text-[11px] text-text-secondary">정밀 분석</div>
            <div className="font-bold text-accent">{data.detailed_scanned_count}</div>
          </div>
          <div className="rounded-lg bg-positive/10 px-3 py-2">
            <div className="text-[11px] text-text-secondary">표시 후보</div>
            <div className="font-bold text-positive">{data.actionable_count}</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {items.map((item) => (
          <Link
            key={item.ticker}
            href={`/stock/${encodeURIComponent(item.ticker)}`}
            className="rounded-xl border border-border p-4 transition-colors hover:border-accent/50"
          >
            <div className="mb-3 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-text-secondary">#{item.rank}</span>
                  <span className="font-semibold">{item.name}</span>
                  <span className="text-xs text-text-secondary">{item.ticker}</span>
                </div>
                <div className="mt-1 text-xs text-text-secondary">{item.sector}</div>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold">{item.opportunity_score.toFixed(1)}</div>
                <div className="text-[11px] text-text-secondary">레이더 점수</div>
              </div>
            </div>

            <div className="mb-3 flex flex-wrap gap-2 text-[11px]">
              <span className={`rounded-full px-2 py-1 font-semibold uppercase tracking-wide ${actionTone(item.action)}`}>
                {actionLabel(item.action)}
              </span>
              <span className="rounded-full bg-border/40 px-2 py-1 text-text-secondary">{item.setup_label}</span>
              <span className="rounded-full bg-border/40 px-2 py-1 text-text-secondary">{item.regime_tailwind}</span>
              <span className={`rounded-full px-2 py-1 ${executionBiasTone(item.execution_bias)}`}>
                {executionBiasLabel(item.execution_bias)}
              </span>
            </div>

            <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
              <div>
                <div className="text-[11px] text-text-secondary">현재가</div>
                <div className="font-semibold">{formatPrice(item.current_price, item.country_code)}</div>
                <div className={`text-[11px] ${changeColor(item.change_pct)}`}>{formatPct(item.change_pct)}</div>
              </div>
              <div>
                <div className="text-[11px] text-text-secondary">상승 확률</div>
                <div className="font-semibold">{item.up_probability.toFixed(1)}%</div>
                <div className="text-[11px] text-text-secondary">신뢰도 {item.confidence.toFixed(0)}</div>
              </div>
              <div>
                <div className="text-[11px] text-text-secondary">진입 구간</div>
                <div className="font-semibold">{priceRange(item.entry_low, item.entry_high, item.country_code)}</div>
              </div>
              <div>
                <div className="text-[11px] text-text-secondary">손익비</div>
                <div className="font-semibold">{item.risk_reward_estimate.toFixed(2)}</div>
                <div className={`text-[11px] ${changeColor(item.predicted_return_pct)}`}>{formatPct(item.predicted_return_pct)}</div>
              </div>
            </div>

            {(item.bull_case_price != null || item.bear_case_price != null) ? (
              <div className="mb-3 grid grid-cols-3 gap-2 text-[11px]">
                <div className="rounded-lg bg-positive/5 px-2 py-2">
                  <div className="text-text-secondary">상방</div>
                  <div className="font-semibold text-positive">
                    {item.bull_case_price != null ? formatPrice(item.bull_case_price, item.country_code) : "미정"}
                  </div>
                  <div className="text-text-secondary">{item.bull_probability?.toFixed(1) ?? "-"}%</div>
                </div>
                <div className="rounded-lg bg-border/30 px-2 py-2">
                  <div className="text-text-secondary">기준</div>
                  <div className="font-semibold">
                    {item.base_case_price != null ? formatPrice(item.base_case_price, item.country_code) : "미정"}
                  </div>
                  <div className="text-text-secondary">{item.base_probability?.toFixed(1) ?? "-"}%</div>
                </div>
                <div className="rounded-lg bg-negative/5 px-2 py-2">
                  <div className="text-text-secondary">하방</div>
                  <div className="font-semibold text-negative">
                    {item.bear_case_price != null ? formatPrice(item.bear_case_price, item.country_code) : "미정"}
                  </div>
                  <div className="text-text-secondary">{item.bear_probability?.toFixed(1) ?? "-"}%</div>
                </div>
              </div>
            ) : null}

            <div className="space-y-2 text-sm">
              {item.thesis.map((point) => (
                <div key={point} className="text-text-secondary">
                  {point}
                </div>
              ))}
            </div>
            {item.execution_note ? <div className="mt-3 text-xs text-text-secondary">{item.execution_note}</div> : null}
            {item.risk_flags.length > 0 ? (
              <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-600">
                {item.risk_flags[0]}
              </div>
            ) : null}
          </Link>
        ))}
      </div>
    </div>
  );
}
