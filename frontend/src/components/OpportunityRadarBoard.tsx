"use client";

import Link from "next/link";

import type { OpportunityRadarResponse } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

interface Props {
  data: OpportunityRadarResponse;
  compact?: boolean;
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

function priceRange(low?: number | null, high?: number | null, key = "US") {
  if (low == null && high == null) return "미정";
  if (low != null && high != null) return `${formatPrice(low, key)} - ${formatPrice(high, key)}`;
  return formatPrice(low ?? high, key);
}

export default function OpportunityRadarBoard({ data, compact = false }: Props) {
  const items = compact ? data.opportunities.slice(0, 6) : data.opportunities;

  return (
    <div className="card">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-4">
        <div>
          <h2 className="font-semibold">기회 레이더</h2>
          <p className="text-sm text-text-secondary mt-1">총 {data.total_scanned}개 종목을 스캔했고, 실행 가능한 후보 {data.actionable_count}개 중 강세 우위 {data.bullish_count}개가 추려졌습니다.</p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center shrink-0">
          <div className="rounded-lg bg-border/40 px-3 py-2"><div className="text-[11px] text-text-secondary">스캔 수</div><div className="font-bold">{data.total_scanned}</div></div>
          <div className="rounded-lg bg-positive/10 px-3 py-2"><div className="text-[11px] text-text-secondary">실행 후보</div><div className="font-bold text-positive">{data.actionable_count}</div></div>
          <div className="rounded-lg bg-accent/10 px-3 py-2"><div className="text-[11px] text-text-secondary">강세 우위</div><div className="font-bold text-accent">{data.bullish_count}</div></div>
        </div>
      </div>

      <div className="grid gap-4 grid-cols-1 xl:grid-cols-2">
        {items.map((item) => (
          <Link key={item.ticker} href={`/stock/${encodeURIComponent(item.ticker)}`} className="rounded-xl border border-border p-4 hover:border-accent/50 transition-colors">
            <div className="flex items-start justify-between gap-4 mb-3">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-semibold text-text-secondary">#{item.rank}</span>
                  <span className="font-semibold">{item.name}</span>
                  <span className="text-xs text-text-secondary">{item.ticker}</span>
                </div>
                <div className="text-xs text-text-secondary mt-1">{item.sector}</div>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold">{item.opportunity_score.toFixed(1)}</div>
                <div className="text-[11px] text-text-secondary">레이더 점수</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mb-3 text-[11px]">
              <span className={`px-2 py-1 rounded-full font-semibold uppercase tracking-wide ${actionTone(item.action)}`}>{actionLabel(item.action)}</span>
              <span className="px-2 py-1 rounded-full bg-border/40 text-text-secondary">{item.setup_label}</span>
              <span className="px-2 py-1 rounded-full bg-border/40 text-text-secondary">{item.regime_tailwind}</span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
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

            <div className="space-y-2 text-sm">{item.thesis.map((point) => <div key={point} className="text-text-secondary">{point}</div>)}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}