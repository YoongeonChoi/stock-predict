"use client";

import type { WeeklyTradePlan } from "@/lib/types";
import { changeColor, cn, formatPct, formatPrice } from "@/lib/utils";

interface WeeklyTradePlanCardProps {
  plan: WeeklyTradePlan;
  priceKey: string;
  assetLabel?: string;
}

function actionLabel(action: WeeklyTradePlan["action"]) {
  if (action === "accumulate") return "분할 매수";
  if (action === "breakout_watch") return "돌파 확인";
  if (action === "wait_pullback") return "눌림 대기";
  if (action === "reduce_risk") return "리스크 축소";
  return "관망";
}

function actionTone(action: WeeklyTradePlan["action"]) {
  if (action === "accumulate" || action === "breakout_watch") return "bg-positive/10 text-positive";
  if (action === "reduce_risk" || action === "avoid") return "bg-negative/10 text-negative";
  return "bg-warning/10 text-warning";
}

function signalTone(signal: string) {
  if (signal === "bullish") return "border-positive/25 bg-positive/5 text-positive";
  if (signal === "bearish") return "border-negative/25 bg-negative/5 text-negative";
  return "border-border/70 bg-surface/55 text-text-secondary";
}

function sourceStatusLabel(status: string) {
  if (status === "fresh") return "반영";
  if (status === "partial") return "부분";
  if (status === "pending") return "대기";
  if (status === "not_configured") return "미설정";
  if (status === "missing") return "없음";
  return status || "대기";
}

function priceRange(low?: number | null, high?: number | null, priceKey = "KR") {
  if (low == null && high == null) return "대기";
  if (low != null && high != null) return `${formatPrice(low, priceKey)} - ${formatPrice(high, priceKey)}`;
  return formatPrice(low ?? high, priceKey);
}

function priceValue(value: number | null | undefined, priceKey: string) {
  return value == null ? "대기" : formatPrice(value, priceKey);
}

function prioritizeEvidence(items: WeeklyTradePlan["evidence"]) {
  const priority = ["distribution", "price_band", "official_research", "event", "market_regime", "flow", "fused"];
  return [...(items || [])].sort((a, b) => {
    const aIndex = priority.indexOf(a.key);
    const bIndex = priority.indexOf(b.key);
    const safeA = aIndex === -1 ? priority.length : aIndex;
    const safeB = bIndex === -1 ? priority.length : bIndex;
    return safeA - safeB;
  });
}

function prioritizeSources(items: WeeklyTradePlan["source_freshness"]) {
  const priority = [
    "가격·거래량",
    "공식 리서치·IB 메타데이터",
    "뉴스 메타데이터",
    "OpenDART 공시",
    "PyKRX 수급",
    "증권사 컨센서스",
    "펀더멘털",
    "ECOS 거시",
    "KOSIS 거시",
  ];
  return [...(items || [])].sort((a, b) => {
    const aIndex = priority.indexOf(a.name);
    const bIndex = priority.indexOf(b.name);
    const safeA = aIndex === -1 ? priority.length : aIndex;
    const safeB = bIndex === -1 ? priority.length : bIndex;
    return safeA - safeB;
  });
}

export default function WeeklyTradePlanCard({ plan, priceKey, assetLabel }: WeeklyTradePlanCardProps) {
  const evidence = prioritizeEvidence(plan.evidence);
  const sources = prioritizeSources(plan.source_freshness);
  const reflectedSourceCount = sources.filter((source) => source.status === "fresh" || source.status === "partial").length;
  const probabilityRows = [
    { label: "상승", value: plan.p_up, tone: "bg-positive" },
    { label: "보합", value: plan.p_flat, tone: "bg-accent" },
    { label: "하락", value: plan.p_down, tone: "bg-negative" },
  ];
  const hasProbabilities = probabilityRows.some((row) => row.value != null);

  return (
    <section className="card w-full max-w-full space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn("rounded-full px-3 py-1 text-sm font-semibold", actionTone(plan.action))}>
              {actionLabel(plan.action)}
            </span>
            {plan.partial ? (
              <span className="rounded-full bg-border/45 px-3 py-1 text-sm text-text-secondary">부분 응답</span>
            ) : null}
          </div>
          <div>
            <h2 className="text-lg font-semibold">이번 주 판단</h2>
            <p className="mt-1 break-words text-sm leading-6 text-text-secondary [overflow-wrap:anywhere]">
              {assetLabel ? `${assetLabel} ` : ""}5거래일 조건부 분포 기준 매수 가능가, 매도 목표가, 손절가입니다.
            </p>
          </div>
        </div>
        <div className="grid w-full min-w-0 grid-cols-2 gap-2 text-sm sm:grid-cols-4 lg:w-auto lg:min-w-[420px]">
          <div className="rounded-lg bg-border/35 px-3 py-2">
            <div className="text-[11px] text-text-secondary">기준가</div>
            <div className="mt-1 font-semibold">{formatPrice(plan.reference_price, priceKey)}</div>
          </div>
          <div className="rounded-lg bg-border/35 px-3 py-2">
            <div className="text-[11px] text-text-secondary">목표일</div>
            <div className="mt-1 font-semibold">{plan.target_date || "대기"}</div>
          </div>
          <div className="rounded-lg bg-border/35 px-3 py-2">
            <div className="text-[11px] text-text-secondary">신뢰도</div>
            <div className="mt-1 font-semibold">{plan.confidence.toFixed(0)}</div>
          </div>
          <div className="rounded-lg bg-border/35 px-3 py-2">
            <div className="text-[11px] text-text-secondary">손익비</div>
            <div className="mt-1 font-semibold">{plan.risk_reward_estimate.toFixed(2)}</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="metric-card bg-positive/5">
          <div className="text-xs text-text-secondary">이번 주 매수 가능가</div>
          <div className="mt-2 break-words text-2xl font-bold text-positive">{priceValue(plan.buy_price, priceKey)}</div>
          <div className="mt-2 text-sm text-text-secondary">{priceRange(plan.buy_zone_low, plan.buy_zone_high, priceKey)}</div>
        </div>
        <div className="metric-card bg-accent/5">
          <div className="text-xs text-text-secondary">매도 목표가</div>
          <div className="mt-2 break-words text-2xl font-bold text-accent">{priceValue(plan.sell_price, priceKey)}</div>
          <div className="mt-2 text-sm text-text-secondary">{priceRange(plan.sell_zone_low, plan.sell_zone_high, priceKey)}</div>
        </div>
        <div className="metric-card bg-negative/5">
          <div className="text-xs text-text-secondary">손절가</div>
          <div className="mt-2 break-words text-2xl font-bold text-negative">{priceValue(plan.stop_loss, priceKey)}</div>
          <div className={cn("mt-2 text-sm", changeColor(plan.expected_return_pct ?? 0))}>
            기대수익 {plan.expected_return_pct == null ? "대기" : formatPct(plan.expected_return_pct)}
          </div>
        </div>
      </div>

      {hasProbabilities ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">5거래일 확률</h3>
            <span className="text-xs text-text-secondary">상승·보합·하락 합산 기준</span>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            {probabilityRows.map((row) => (
              <div key={row.label} className="min-w-0">
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-text-secondary">{row.label}</span>
                  <span className="font-semibold">{row.value == null ? "대기" : `${row.value.toFixed(1)}%`}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-border/50">
                  <div className={cn("h-full rounded-full", row.tone)} style={{ width: `${Math.max(0, Math.min(row.value ?? 0, 100))}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="section-slab-muted !px-4 !py-4">
        <div className="text-xs text-text-secondary">데이터 상태</div>
        <p className="mt-2 break-words text-sm leading-6 text-text [overflow-wrap:anywhere]">{plan.data_quality || "데이터 품질 메모가 아직 없습니다."}</p>
      </div>

      {evidence.length > 0 ? (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {evidence.map((item) => (
            <div key={`${item.key}-${item.label}`} className={cn("rounded-lg border px-3 py-3", signalTone(item.signal))}>
              <div className="text-sm font-semibold text-text">{item.label}</div>
              <p className="mt-1 break-words text-sm leading-6 text-text-secondary [overflow-wrap:anywhere]">{item.detail}</p>
            </div>
          ))}
        </div>
      ) : null}

      {sources.length > 0 ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">근거 최신성</h3>
            <span className="text-xs text-text-secondary">
              {reflectedSourceCount}/{sources.length}개 소스 반영
            </span>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
            {sources.map((source) => (
              <span
                key={source.name}
                title={[source.note, source.updated_at ? `업데이트 ${source.updated_at}` : ""].filter(Boolean).join(" · ")}
                className="max-w-full break-words rounded-full border border-border/70 bg-surface/70 px-2 py-1 [overflow-wrap:anywhere]"
              >
                {source.name} {sourceStatusLabel(source.status)}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
