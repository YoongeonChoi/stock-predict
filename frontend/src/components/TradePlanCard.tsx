"use client";

import type { TradePlan } from "@/lib/types";
import { formatPrice } from "@/lib/utils";

interface Props {
  plan: TradePlan;
  priceKey: string;
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

function valueOrPending(value: number | null | undefined, priceKey: string) {
  return value == null ? "미정" : formatPrice(value, priceKey);
}

export default function TradePlanCard({ plan, priceKey }: Props) {
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h2 className="font-semibold">트레이드 플랜</h2>
          <p className="text-sm text-text-secondary mt-1">{plan.setup_label}</p>
        </div>
        <div className="text-right">
          <div className={`inline-flex px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide ${actionTone(plan.action)}`}>{actionLabel(plan.action)}</div>
          <div className="text-xs text-text-secondary mt-2">확신도 {plan.conviction.toFixed(0)} / 100</div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <div className="p-3 rounded-lg bg-border/40"><div className="text-[11px] text-text-secondary">진입 하단</div><div className="font-bold">{valueOrPending(plan.entry_low, priceKey)}</div></div>
        <div className="p-3 rounded-lg bg-border/40"><div className="text-[11px] text-text-secondary">진입 상단</div><div className="font-bold">{valueOrPending(plan.entry_high, priceKey)}</div></div>
        <div className="p-3 rounded-lg bg-negative/10"><div className="text-[11px] text-text-secondary">손절가</div><div className="font-bold text-negative">{valueOrPending(plan.stop_loss, priceKey)}</div></div>
        <div className="p-3 rounded-lg bg-positive/10"><div className="text-[11px] text-text-secondary">1차 목표</div><div className="font-bold text-positive">{valueOrPending(plan.take_profit_1, priceKey)}</div></div>
        <div className="p-3 rounded-lg bg-positive/10"><div className="text-[11px] text-text-secondary">2차 목표</div><div className="font-bold text-positive">{valueOrPending(plan.take_profit_2, priceKey)}</div></div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div>
          <div className="text-xs font-medium text-text-secondary mb-2">핵심 논리</div>
          <div className="space-y-2">{plan.thesis.map((item) => <div key={item} className="rounded-lg border border-border px-3 py-2 text-sm">{item}</div>)}</div>
        </div>
        <div className="space-y-3">
          <div className="rounded-lg border border-border px-3 py-3"><div className="text-xs font-medium text-text-secondary mb-1">예상 손익비</div><div className="text-xl font-bold">{plan.risk_reward_estimate.toFixed(2)}</div></div>
          <div className="rounded-lg border border-border px-3 py-3"><div className="text-xs font-medium text-text-secondary mb-1">예상 보유 기간</div><div className="text-sm">{plan.expected_holding_days} 거래일</div></div>
          <div className="rounded-lg border border-border px-3 py-3"><div className="text-xs font-medium text-text-secondary mb-1">무효화 조건</div><div className="text-sm text-text-secondary">{plan.invalidation}</div></div>
        </div>
      </div>
    </div>
  );
}