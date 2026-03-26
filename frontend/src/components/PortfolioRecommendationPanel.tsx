"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import type {
  PortfolioRecommendationBudget,
  PortfolioRecommendationItem,
  PortfolioRecommendationMarketView,
  PortfolioRecommendationSummary,
} from "@/lib/api";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

interface Props {
  title: string;
  description: string;
  loading?: boolean;
  budget?: PortfolioRecommendationBudget | null;
  summary?: PortfolioRecommendationSummary | null;
  recommendations?: PortfolioRecommendationItem[];
  notes?: string[];
  marketView?: PortfolioRecommendationMarketView[];
  controls?: ReactNode;
  emptyMessage: string;
}

function expectedReturn20d(item: PortfolioRecommendationItem | PortfolioRecommendationSummary) {
  const value = item as Partial<PortfolioRecommendationItem & PortfolioRecommendationSummary>;
  return value.expected_return_pct_20d ?? value.model_predicted_return_pct ?? value.predicted_return_pct ?? 0;
}

function excessReturn20d(item: PortfolioRecommendationItem | PortfolioRecommendationSummary) {
  const value = item as Partial<PortfolioRecommendationItem & PortfolioRecommendationSummary>;
  return value.expected_excess_return_pct_20d ?? 0;
}

function upProbability20d(item: PortfolioRecommendationItem | PortfolioRecommendationSummary) {
  const value = item as Partial<PortfolioRecommendationItem & PortfolioRecommendationSummary>;
  return value.up_probability_20d ?? value.model_up_probability ?? value.up_probability ?? 0;
}

function downProbability20d(item: PortfolioRecommendationItem | PortfolioRecommendationSummary) {
  const value = item as Partial<PortfolioRecommendationItem & PortfolioRecommendationSummary>;
  return value.down_probability_20d ?? value.bear_probability ?? 0;
}

function volatility20d(item: PortfolioRecommendationItem | PortfolioRecommendationSummary) {
  const value = item as Partial<PortfolioRecommendationItem & PortfolioRecommendationSummary>;
  return value.forecast_volatility_pct_20d ?? 0;
}

function actionLabel(action?: string | null) {
  if (action === "accumulate") return "분할 매수";
  if (action === "breakout_watch") return "돌파 감시";
  if (action === "wait_pullback") return "눌림 대기";
  if (action === "reduce_risk") return "리스크 축소";
  if (action === "avoid") return "관망";
  return "선별 대응";
}

function actionTone(action?: string | null) {
  if (action === "accumulate" || action === "breakout_watch") return "text-positive bg-positive/10";
  if (action === "reduce_risk" || action === "avoid") return "text-negative bg-negative/10";
  if (action === "wait_pullback") return "text-amber-500 bg-amber-500/10";
  return "text-text-secondary bg-border/35";
}

function executionBiasLabel(bias?: string | null) {
  if (bias === "press_long") return "추세 대응";
  if (bias === "lean_long") return "상방 우세";
  if (bias === "reduce_risk") return "리스크 관리";
  if (bias === "capital_preservation") return "방어 우선";
  return "선별 대응";
}

function executionBiasTone(bias?: string | null) {
  if (bias === "press_long") return "text-positive bg-positive/10";
  if (bias === "lean_long") return "text-emerald-500 bg-emerald-500/10";
  if (bias === "reduce_risk") return "text-amber-500 bg-amber-500/10";
  if (bias === "capital_preservation") return "text-negative bg-negative/10";
  return "text-text-secondary bg-surface";
}

function sourceLabel(source: string) {
  if (source === "watchlist") return "워치리스트";
  if (source === "holding") return "보유";
  return "레이더";
}

function stanceLabel(stance?: string | null) {
  if (stance === "risk_on") return "위험 선호";
  if (stance === "risk_off") return "위험 회피";
  return "중립";
}

function stanceTone(stance?: string | null) {
  if (stance === "risk_on") return "text-positive bg-positive/10";
  if (stance === "risk_off") return "text-negative bg-negative/10";
  return "text-text-secondary bg-surface";
}

function RecommendationCard({ item }: { item: PortfolioRecommendationItem }) {
  return (
    <Link
      href={`/stock/${encodeURIComponent(item.ticker)}`}
      className="block rounded-[22px] border border-border/80 bg-surface/65 px-4 py-4 transition-colors hover:border-accent/35"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-border px-2 py-1 text-[11px] text-text-secondary">
              {item.country_code}
            </span>
            <span className="truncate font-semibold text-text">{item.name}</span>
            <span className="text-xs text-text-secondary">{item.ticker}</span>
          </div>
          <div className="mt-1 text-xs text-text-secondary">{item.sector} · {sourceLabel(item.source)}</div>
        </div>
        <div className="text-right">
          <div className="text-xl font-bold text-text">{item.target_weight_pct.toFixed(1)}%</div>
          <div className="text-[11px] text-text-secondary">목표 비중</div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
        <span className={`rounded-full px-2 py-1 font-medium ${actionTone(item.action)}`}>{actionLabel(item.action)}</span>
        <span className={`rounded-full px-2 py-1 font-medium ${executionBiasTone(item.execution_bias)}`}>
          {executionBiasLabel(item.execution_bias)}
        </span>
        <span className="rounded-full border border-border px-2 py-1 text-text-secondary">
          현재 {item.current_weight_pct.toFixed(1)}%
        </span>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
          <div className="text-[11px] text-text-secondary">20거래일 기대수익률</div>
          <div className={`mt-1 font-semibold ${changeColor(expectedReturn20d(item))}`}>{formatPct(expectedReturn20d(item))}</div>
        </div>
        <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
          <div className="text-[11px] text-text-secondary">기대초과수익률</div>
          <div className={`mt-1 font-semibold ${changeColor(excessReturn20d(item))}`}>{formatPct(excessReturn20d(item))}</div>
        </div>
        <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
          <div className="text-[11px] text-text-secondary">상방 / 하방</div>
          <div className="mt-1 font-semibold">{upProbability20d(item).toFixed(1)}% / {downProbability20d(item).toFixed(1)}%</div>
        </div>
        <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
          <div className="text-[11px] text-text-secondary">변동성 / 노출</div>
          <div className="mt-1 text-sm font-semibold">{volatility20d(item).toFixed(2)}% / {item.current_country_exposure_pct.toFixed(1)}%</div>
          <div className="mt-1 text-[11px] text-text-secondary">섹터 {item.current_sector_exposure_pct.toFixed(1)}%</div>
        </div>
      </div>

      <div className="mt-3 text-sm leading-6 text-text-secondary">
        {item.rationale[0] || "핵심 메모가 아직 없습니다."}
      </div>

        <div className="mt-3 grid gap-2 text-xs text-text-secondary sm:grid-cols-2">
          <div>
            진입 {item.entry_low != null && item.entry_high != null ? `${formatPrice(item.entry_low, item.country_code)} - ${formatPrice(item.entry_high, item.country_code)}` : "미정"}
          </div>
          <div>
            손절 / 1차 목표 {item.stop_loss != null ? formatPrice(item.stop_loss, item.country_code) : "미정"} / {item.take_profit_1 != null ? formatPrice(item.take_profit_1, item.country_code) : "미정"}
            {item.target_date_20d ? ` · ${item.target_date_20d}` : ""}
          </div>
        </div>

      {item.risk_flags.length > 0 ? (
        <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-600">
          {item.risk_flags[0]}
        </div>
      ) : null}
    </Link>
  );
}

export default function PortfolioRecommendationPanel({
  title,
  description,
  loading = false,
  budget,
  summary,
  recommendations = [],
  notes = [],
  marketView = [],
  controls,
  emptyMessage,
}: Props) {
  return (
    <div className="card min-w-0 !p-0 overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="section-title">{title}</h2>
            <p className="section-copy">{description}</p>
          </div>
          {budget ? <span className="info-chip">{budget.style_label}</span> : null}
        </div>
      </div>

      <div className="px-5 py-5 space-y-5">
        {controls}

        {loading ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[1, 2, 3, 4].map((item) => <div key={item} className="metric-card h-24 animate-pulse" />)}
          </div>
        ) : null}

        {!loading && budget && summary ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="metric-card">
              <div className="text-xs text-text-secondary">추천 종목 수</div>
              <div className="mt-2 text-2xl font-bold text-text">{summary.selected_count}</div>
              <div className="mt-1 text-[11px] text-text-secondary">후보 {summary.candidate_count}개</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">주식 / 현금</div>
              <div className="mt-2 text-lg font-semibold text-text">
                {budget.recommended_equity_pct.toFixed(1)}% / {budget.cash_buffer_pct.toFixed(1)}%
              </div>
              <div className="mt-1 text-[11px] text-text-secondary">최대 {budget.target_position_count}개</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">20거래일 기대수익률</div>
              <div className={`mt-2 text-2xl font-bold ${changeColor(expectedReturn20d(summary))}`}>{formatPct(expectedReturn20d(summary))}</div>
              <div className={`mt-1 text-[11px] ${changeColor(excessReturn20d(summary))}`}>
                기대초과 {formatPct(excessReturn20d(summary))}
              </div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">상방 / 하방 / 변동성</div>
              <div className="mt-2 text-lg font-semibold text-text">
                {upProbability20d(summary).toFixed(1)}% / {downProbability20d(summary).toFixed(1)}%
              </div>
              <div className="mt-1 text-[11px] text-text-secondary">
                변동성 {volatility20d(summary).toFixed(2)}% · 회전율 {summary.turnover_pct.toFixed(2)}%
              </div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">집중 포커스</div>
              <div className="mt-2 text-lg font-semibold text-text">
                {(summary.focus_country || "시장 분산")} / {(summary.focus_sector || "섹터 분산")}
              </div>
              <div className="mt-1 text-[11px] text-text-secondary">워치리스트 반영 {summary.watchlist_focus_count}개</div>
            </div>
          </div>
        ) : null}

        {!loading && notes.length > 0 ? (
          <div className="grid gap-2">
            {notes.map((note) => (
              <div key={note} className="rounded-2xl border border-border/70 bg-surface/50 px-4 py-3 text-sm text-text-secondary">
                {note}
              </div>
            ))}
          </div>
        ) : null}

        {!loading && marketView.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-3">
            {marketView.map((item) => (
              <div key={`${item.country_code}-${item.label}`} className="rounded-2xl border border-border/70 bg-surface/50 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-text">{item.country_code}</div>
                  <span className={`rounded-full px-2 py-1 text-[11px] ${stanceTone(item.stance)}`}>
                    {stanceLabel(item.stance)}
                  </span>
                </div>
                <div className="mt-1 text-xs text-text-secondary">{item.label || "시장 체제 확인 중"}</div>
                <div className="mt-2 text-xs text-text-secondary">실행 후보 {item.actionable_count}개</div>
              </div>
            ))}
          </div>
        ) : null}

        {!loading && recommendations.length > 0 ? (
          <div className="space-y-3">
            {recommendations.map((item) => (
              <RecommendationCard key={item.key} item={item} />
            ))}
          </div>
        ) : null}

        {!loading && recommendations.length === 0 ? (
          <div className="rounded-2xl border border-border/70 bg-surface/45 px-4 py-6 text-sm text-text-secondary">
            {emptyMessage}
          </div>
        ) : null}
      </div>
    </div>
  );
}
