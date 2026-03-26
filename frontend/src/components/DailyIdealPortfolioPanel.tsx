"use client";

import Link from "next/link";

import type { DailyIdealPortfolio, DailyIdealPortfolioPosition } from "@/lib/api";
import { cn, changeColor, formatPct, formatPrice } from "@/lib/utils";

interface Props {
  data: DailyIdealPortfolio;
  compact?: boolean;
  embedded?: boolean;
}

function expectedReturn20d(value: DailyIdealPortfolio["summary"] | DailyIdealPortfolioPosition) {
  const item = value as Partial<DailyIdealPortfolio["summary"] & DailyIdealPortfolioPosition>;
  return item.expected_return_pct_20d ?? item.predicted_portfolio_return_pct ?? item.predicted_return_pct ?? 0;
}

function excessReturn20d(value: DailyIdealPortfolio["summary"] | DailyIdealPortfolioPosition) {
  const item = value as Partial<DailyIdealPortfolio["summary"] & DailyIdealPortfolioPosition>;
  return item.expected_excess_return_pct_20d ?? 0;
}

function upProbability20d(value: DailyIdealPortfolio["summary"] | DailyIdealPortfolioPosition) {
  const item = value as Partial<DailyIdealPortfolio["summary"] & DailyIdealPortfolioPosition>;
  return item.up_probability_20d ?? item.portfolio_up_probability ?? item.up_probability ?? 0;
}

function downProbability20d(value: DailyIdealPortfolio["summary"] | DailyIdealPortfolioPosition) {
  const item = value as Partial<DailyIdealPortfolio["summary"] & DailyIdealPortfolioPosition>;
  return item.down_probability_20d ?? item.portfolio_down_probability ?? 0;
}

function volatility20d(value: DailyIdealPortfolio["summary"] | DailyIdealPortfolioPosition) {
  const item = value as Partial<DailyIdealPortfolio["summary"] & DailyIdealPortfolioPosition>;
  return item.forecast_volatility_pct_20d ?? 0;
}

function stanceLabel(stance: string) {
  if (stance === "risk_on") return "위험 선호";
  if (stance === "risk_off") return "위험 회피";
  return "중립";
}

function stanceTone(stance: string) {
  if (stance === "risk_on") return "text-positive bg-positive/10";
  if (stance === "risk_off") return "text-negative bg-negative/10";
  return "text-text-secondary bg-surface";
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

function CompactPositionCard({ item }: { item: DailyIdealPortfolioPosition }) {
  return (
    <Link
      href={`/stock/${encodeURIComponent(item.ticker)}`}
      className="block rounded-[22px] border border-border/80 bg-surface/70 px-4 py-4 transition-colors hover:border-accent/45"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-border px-2 py-1 text-[11px] text-text-secondary">
              {item.country_code}
            </span>
            <span className="truncate font-semibold text-text">{item.name}</span>
            <span className="text-xs text-text-secondary">{item.ticker}</span>
          </div>
          <div className="mt-1 truncate text-xs text-text-secondary">
            {item.sector} · 20거래일 목표 {item.target_date_20d || item.target_date}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-xl font-bold">{item.target_weight_pct.toFixed(1)}%</div>
          <div className="text-[11px] text-text-secondary">목표 비중</div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
        <span className={`rounded-full px-2 py-1 font-medium ${actionTone(item.action)}`}>{actionLabel(item.action)}</span>
        <span className={`rounded-full px-2 py-1 font-medium ${executionBiasTone(item.execution_bias)}`}>
          {executionBiasLabel(item.execution_bias)}
        </span>
        <span className="rounded-full bg-border/35 px-2 py-1 text-text-secondary">
          {item.setup_label || "기본 셋업"}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
          <div className="text-[11px] text-text-secondary">현재가</div>
          <div className="mt-1 font-semibold">{formatPrice(item.reference_price, item.country_code)}</div>
        </div>
        <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
          <div className="text-[11px] text-text-secondary">20거래일 기대수익률</div>
          <div className={`mt-1 font-semibold ${changeColor(expectedReturn20d(item))}`}>
            {formatPct(expectedReturn20d(item))}
          </div>
        </div>
        <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
          <div className="text-[11px] text-text-secondary">상방 / 하방</div>
          <div className="mt-1 font-semibold">{upProbability20d(item).toFixed(1)}% / {downProbability20d(item).toFixed(1)}%</div>
        </div>
        <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
          <div className="text-[11px] text-text-secondary">변동성 / 점수</div>
          <div className="mt-1 font-semibold">{volatility20d(item).toFixed(2)}% / {item.selection_score.toFixed(1)}</div>
        </div>
      </div>

      <div className="mt-3 text-sm leading-6 text-text-secondary line-clamp-2">
        {item.thesis[0] || item.execution_note || "핵심 메모가 아직 없습니다."}
      </div>

      {item.risk_flags.length > 0 ? (
        <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-600">
          {item.risk_flags[0]}
        </div>
      ) : null}
    </Link>
  );
}

export default function DailyIdealPortfolioPanel({ data, compact = false, embedded = false }: Props) {
  const positions = compact ? data.positions.slice(0, 4) : data.positions;
  const history = compact ? data.history.slice(0, 3) : data.history;

  if (compact) {
    return (
      <div className={cn("min-w-0 space-y-4", embedded ? "" : "card !p-5")}>
        {!embedded ? (
          <div>
            <h2 className="font-semibold">이상적 포트폴리오</h2>
            <p className="mt-1 text-sm text-text-secondary">{data.objective}</p>
          </div>
        ) : null}

        <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <p className="text-sm leading-6 text-text-secondary">{data.objective}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="rounded-full bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent">
              {data.risk_budget.style_label}
            </div>
            {data.target_dates.map((item) => (
              <div
                key={`${item.country_code}-${item.target_date}`}
                className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium"
              >
                {item.country_code} {item.target_date}
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-border/70 bg-surface/70 px-4 py-3">
            <div className="text-[11px] text-text-secondary">추천 종목 수</div>
            <div className="mt-2 text-2xl font-bold">{data.summary.selected_count}</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/70 px-4 py-3">
            <div className="text-[11px] text-text-secondary">주식 / 현금 비중</div>
            <div className="mt-2 text-base font-semibold">
              {data.risk_budget.recommended_equity_pct.toFixed(1)}% / {data.risk_budget.cash_buffer_pct.toFixed(1)}%
            </div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/70 px-4 py-3">
            <div className="text-[11px] text-text-secondary">20거래일 기대수익률</div>
            <div className={`mt-2 text-2xl font-bold ${changeColor(expectedReturn20d(data.summary))}`}>{formatPct(expectedReturn20d(data.summary))}</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/70 px-4 py-3">
            <div className="text-[11px] text-text-secondary">기대초과 / 변동성</div>
            <div className={`mt-2 text-2xl font-bold ${changeColor(excessReturn20d(data.summary))}`}>{formatPct(excessReturn20d(data.summary))}</div>
            <div className="mt-1 text-[11px] text-text-secondary">변동성 {volatility20d(data.summary).toFixed(2)}%</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/70 px-4 py-3">
            <div className="text-[11px] text-text-secondary">상방 / 하방 / 회전율</div>
            <div className="mt-2 text-2xl font-bold">{upProbability20d(data.summary).toFixed(1)}%</div>
            <div className="mt-1 text-[11px] text-text-secondary">하방 {downProbability20d(data.summary).toFixed(1)}% · 회전율 {data.summary.turnover_pct.toFixed(2)}%</div>
          </div>
        </div>

        <div className="space-y-3">
          {positions.map((item) => (
            <CompactPositionCard key={`${item.country_code}-${item.ticker}`} item={item} />
          ))}
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
          <div className="rounded-[22px] border border-border/80 bg-surface/55 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-text-secondary">운영 플레이북</div>
            <div className="mt-3 space-y-2">
              {data.playbook.slice(0, 3).map((item) => (
                <div key={item} className="rounded-xl border border-border/70 bg-surface/60 px-3 py-2 text-sm">
                  {item}
                </div>
              ))}
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              {data.market_view.map((item) => (
                <div key={item.country_code} className="rounded-xl border border-border/70 px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-medium">{item.country_code}</div>
                    <div className={`rounded-full px-2 py-1 text-[11px] ${stanceTone(item.stance)}`}>
                      {stanceLabel(item.stance)}
                    </div>
                  </div>
                  <div className="mt-1 text-[11px] text-text-secondary">{item.label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[22px] border border-border/80 bg-surface/55 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-text-secondary">최근 기록 추적</div>
            <div className="mt-3 space-y-2">
              {history.map((item) => (
                <div key={item.reference_date} className="rounded-xl border border-border/70 px-3 py-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium">{item.reference_date}</div>
                      <div className="mt-1 truncate text-[11px] text-text-secondary">
                        상위 종목 {item.top_tickers.join(", ")}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className={`font-semibold ${changeColor(item.realized_portfolio_return_pct ?? item.predicted_portfolio_return_pct)}`}>
                        {item.evaluated ? formatPct(item.realized_portfolio_return_pct ?? 0) : formatPct(item.predicted_portfolio_return_pct)}
                      </div>
                      <div className="mt-1 text-[11px] text-text-secondary">
                        {item.evaluated ? `승률 ${item.hit_rate?.toFixed(1) ?? "-"}%` : "평가 대기"}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="card !p-4 space-y-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <h2 className="font-semibold">이상적 포트폴리오</h2>
            <p className="mt-1 text-sm text-text-secondary">{data.objective}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="rounded-full bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent">
              {data.risk_budget.style_label}
            </div>
            {data.target_dates.map((item) => (
              <div
                key={`${item.country_code}-${item.target_date}`}
                className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium"
              >
                {item.country_code} {item.target_date}
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 xl:grid-cols-6">
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">추천 종목 수</div>
            <div className="mt-2 text-2xl font-bold">{data.summary.selected_count}</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">주식 비중</div>
            <div className="mt-2 text-2xl font-bold">{data.risk_budget.recommended_equity_pct.toFixed(1)}%</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">현금 버퍼</div>
            <div className="mt-2 text-2xl font-bold">{data.risk_budget.cash_buffer_pct.toFixed(1)}%</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">20거래일 기대수익률</div>
            <div className={`mt-2 text-2xl font-bold ${changeColor(expectedReturn20d(data.summary))}`}>{formatPct(expectedReturn20d(data.summary))}</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">기대초과 / 변동성</div>
            <div className={`mt-2 text-2xl font-bold ${changeColor(excessReturn20d(data.summary))}`}>{formatPct(excessReturn20d(data.summary))}</div>
            <div className="mt-1 text-[11px] text-text-secondary">변동성 {volatility20d(data.summary).toFixed(2)}%</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">상방 / 하방 / 회전율</div>
            <div className="mt-2 text-2xl font-bold">{upProbability20d(data.summary).toFixed(1)}%</div>
            <div className="mt-1 text-[11px] text-text-secondary">하방 {downProbability20d(data.summary).toFixed(1)}% · 회전율 {data.summary.turnover_pct.toFixed(2)}%</div>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary">운영 플레이북</div>
            {data.playbook.map((item) => (
              <div key={item} className="rounded-xl border border-border/70 bg-surface/50 px-3 py-2 text-sm">
                {item}
              </div>
            ))}
          </div>
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary">시장 국면</div>
            {data.market_view.map((item) => (
              <div key={item.country_code} className="rounded-xl border border-border/70 px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium">{item.country_code}</div>
                    <div className="mt-1 text-[11px] text-text-secondary">{item.label}</div>
                  </div>
                  <div className="text-right">
                    <div className={`inline-flex rounded-full px-2 py-1 text-[11px] ${stanceTone(item.stance)}`}>
                      {stanceLabel(item.stance)}
                    </div>
                    <div className="mt-1 text-[11px] text-text-secondary">실행 후보 {item.actionable_count}개</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card !p-0 overflow-hidden">
        <div className="border-b border-border px-4 py-3">
          <h3 className="font-semibold">추천 비중 테이블</h3>
          <p className="mt-1 text-xs text-text-secondary">
            20거래일 분포 기대수익률과 기대초과수익률 기준으로 바로 살펴볼 종목과 목표 비중을 정리했습니다.
          </p>
        </div>
        <div className="overflow-x-auto px-2 pb-2 pt-1 md:px-3">
          <table className="w-full min-w-[1040px] text-sm">
            <thead>
              <tr className="border-b border-border bg-surface/40 text-left text-text-secondary">
                <th className="px-4 py-3">종목</th>
                <th className="px-4 py-3 text-right">목표 비중</th>
                <th className="px-4 py-3 text-right">현재가</th>
                <th className="px-4 py-3 text-right">예상</th>
                <th className="px-4 py-3">액션</th>
                <th className="px-4 py-3">시나리오</th>
                <th className="px-4 py-3">핵심 메모</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((item) => (
                <tr key={`${item.country_code}-${item.ticker}`} className="border-b border-border/30 align-top hover:bg-border/10">
                  <td className="px-4 py-3">
                    <Link href={`/stock/${encodeURIComponent(item.ticker)}`} className="font-medium hover:text-accent">
                      {item.name}
                    </Link>
                    <div className="mt-1 text-[11px] text-text-secondary">
                      {item.ticker} · {item.country_code} · {item.sector}
                    </div>
                    <div className="mt-1 text-[11px] text-text-secondary">20거래일 목표 {item.target_date_20d || item.target_date}</div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="font-semibold">{item.target_weight_pct.toFixed(1)}%</div>
                    <div className="mt-1 text-[11px] text-text-secondary">점수 {item.selection_score.toFixed(1)}</div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    <div>{formatPrice(item.reference_price, item.country_code)}</div>
                    <div className="mt-1 text-[11px] text-text-secondary">{item.setup_label || "기본 셋업"}</div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className={`font-semibold ${changeColor(expectedReturn20d(item))}`}>{formatPct(expectedReturn20d(item))}</div>
                    <div className={`mt-1 text-[11px] ${changeColor(excessReturn20d(item))}`}>기대초과 {formatPct(excessReturn20d(item))}</div>
                    <div className="mt-1 text-[11px] text-text-secondary">상방 {upProbability20d(item).toFixed(1)}% · 변동성 {volatility20d(item).toFixed(2)}%</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className={`inline-flex rounded-full px-2 py-1 text-[11px] ${executionBiasTone(item.execution_bias)}`}>
                      {executionBiasLabel(item.execution_bias)}
                    </div>
                    <div className="mt-2 text-[11px] text-text-secondary">{actionLabel(item.action)}</div>
                    {item.execution_note ? <div className="mt-1 max-w-[220px] text-[11px] text-text-secondary">{item.execution_note}</div> : null}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-[11px] text-text-secondary">상방 / 기준 / 하방</div>
                    <div className="mt-1 font-mono text-xs">
                      {item.bull_case_price != null ? formatPrice(item.bull_case_price, item.country_code) : "미정"} /{" "}
                      {item.base_case_price != null ? formatPrice(item.base_case_price, item.country_code) : "미정"} /{" "}
                      {item.bear_case_price != null ? formatPrice(item.bear_case_price, item.country_code) : "미정"}
                    </div>
                    <div className="mt-1 text-[11px] text-text-secondary">
                      {item.bull_probability?.toFixed(1) ?? "-"}% / {item.base_probability?.toFixed(1) ?? "-"}% / {item.bear_probability?.toFixed(1) ?? "-"}%
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="max-w-[280px] text-xs text-text-secondary">{item.thesis[0] || "추가 메모 없음"}</div>
                    {item.risk_flags.length > 0 ? <div className="mt-2 max-w-[280px] text-[11px] text-amber-600">{item.risk_flags[0]}</div> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.15fr_1fr]">
        <div className="card !p-4 space-y-3">
          <div>
            <h3 className="text-sm font-semibold">추천 비중 분해</h3>
            <p className="mt-1 text-xs text-text-secondary">국가와 섹터 상단이 과해지지 않도록 같이 확인합니다.</p>
          </div>
          <div className="space-y-3">
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary">국가 비중</div>
              <div className="flex flex-wrap gap-2">
                {data.allocation.by_country.map((item) => (
                  <div key={item.name} className="rounded-full border border-border px-3 py-1.5 text-xs">
                    {item.name} {item.value.toFixed(1)}%
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary">섹터 비중</div>
              <div className="flex flex-wrap gap-2">
                {data.allocation.by_sector.map((item) => (
                  <div key={item.name} className="rounded-full border border-border px-3 py-1.5 text-xs">
                    {item.name} {item.value.toFixed(1)}%
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="card !p-4 space-y-3">
          <div>
            <h3 className="text-sm font-semibold">기록 추적</h3>
            <p className="mt-1 text-xs text-text-secondary">이전 추천안이 실제로 어땠는지 일자별로 추적합니다.</p>
          </div>
          <div className="space-y-2">
            {history.map((item) => (
              <div key={item.reference_date} className="rounded-xl border border-border/70 px-3 py-2">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">{item.reference_date}</div>
                    <div className="mt-1 text-[11px] text-text-secondary">상위 종목 {item.top_tickers.join(", ")}</div>
                  </div>
                  <div className="text-right">
                    <div className={`font-semibold ${changeColor(item.realized_portfolio_return_pct ?? item.predicted_portfolio_return_pct)}`}>
                      {item.evaluated ? formatPct(item.realized_portfolio_return_pct ?? 0) : formatPct(item.predicted_portfolio_return_pct)}
                    </div>
                    <div className="mt-1 text-[11px] text-text-secondary">
                      {item.evaluated ? `승률 ${item.hit_rate?.toFixed(1) ?? "-"}%` : "평가 대기"}
                    </div>
                  </div>
                </div>
                <div className="mt-2 text-[11px] text-text-secondary">
                  예측 {formatPct(item.predicted_portfolio_return_pct)}
                  {item.evaluated ? ` · 방향 적중 ${item.direction_accuracy?.toFixed(1) ?? "-"}%` : ""}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
