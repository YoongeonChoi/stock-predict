"use client";

import Link from "next/link";

import type { DailyIdealPortfolio } from "@/lib/api";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

interface Props {
  data: DailyIdealPortfolio;
  compact?: boolean;
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

export default function DailyIdealPortfolioPanel({ data, compact = false }: Props) {
  const positions = compact ? data.positions.slice(0, 5) : data.positions;
  const history = compact ? data.history.slice(0, 6) : data.history;

  return (
    <div className="space-y-5">
      <div className="card !p-4 space-y-4">
        <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
          <div>
            <h2 className="font-semibold">내일의 이상적 포트폴리오</h2>
            <p className="text-sm text-text-secondary mt-1">{data.objective}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="rounded-full px-3 py-1.5 text-xs font-medium bg-accent/10 text-accent">
              {data.risk_budget.style_label}
            </div>
            {data.target_dates.map((item) => (
              <div key={`${item.country_code}-${item.target_date}`} className="rounded-full px-3 py-1.5 text-xs font-medium bg-surface border border-border">
                {item.country_code} {item.target_date}
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 xl:grid-cols-6 gap-4">
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">추천 종목 수</div>
            <div className="text-2xl font-bold mt-2">{data.summary.selected_count}</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">주식 비중</div>
            <div className="text-2xl font-bold mt-2">{data.risk_budget.recommended_equity_pct.toFixed(1)}%</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">현금 버퍼</div>
            <div className="text-2xl font-bold mt-2">{data.risk_budget.cash_buffer_pct.toFixed(1)}%</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">포트폴리오 상승 확률</div>
            <div className="text-2xl font-bold mt-2">{data.summary.portfolio_up_probability.toFixed(1)}%</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">예상 수익률</div>
            <div className={`text-2xl font-bold mt-2 ${changeColor(data.summary.predicted_portfolio_return_pct)}`}>
              {formatPct(data.summary.predicted_portfolio_return_pct)}
            </div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">단일 종목 상단</div>
            <div className="text-2xl font-bold mt-2">{data.risk_budget.max_single_weight_pct.toFixed(1)}%</div>
          </div>
        </div>

        <div className="grid xl:grid-cols-[1.2fr_1fr] gap-4">
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
                    <div className="text-[11px] text-text-secondary mt-1">{item.label}</div>
                  </div>
                  <div className="text-right">
                    <div className={`inline-flex rounded-full px-2 py-1 text-[11px] ${stanceTone(item.stance)}`}>{stanceLabel(item.stance)}</div>
                    <div className="text-[11px] text-text-secondary mt-1">실행 후보 {item.actionable_count}개</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card !p-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <h3 className="font-semibold">추천 비중 테이블</h3>
          <p className="text-xs text-text-secondary mt-1">다음 거래일 기준으로 바로 살펴볼 종목과 목표 비중을 정리했습니다.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[1120px]">
            <thead>
              <tr className="text-left text-text-secondary border-b border-border bg-surface/40">
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
                    <div className="text-[11px] text-text-secondary mt-1">{item.ticker} · {item.country_code} · {item.sector}</div>
                    <div className="text-[11px] text-text-secondary mt-1">다음 거래일 {item.target_date}</div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="font-semibold">{item.target_weight_pct.toFixed(1)}%</div>
                    <div className="text-[11px] text-text-secondary mt-1">점수 {item.selection_score.toFixed(1)}</div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    <div>{formatPrice(item.reference_price, item.country_code)}</div>
                    <div className="text-[11px] text-text-secondary mt-1">{item.setup_label || "기본 셋업"}</div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className={`font-semibold ${changeColor(item.predicted_return_pct)}`}>{formatPct(item.predicted_return_pct)}</div>
                    <div className="text-[11px] text-text-secondary mt-1">상승 확률 {item.up_probability.toFixed(1)}%</div>
                    <div className="text-[11px] text-text-secondary mt-1">신뢰도 {item.confidence.toFixed(1)}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className={`inline-flex px-2 py-1 rounded-full text-[11px] ${executionBiasTone(item.execution_bias)}`}>
                      {executionBiasLabel(item.execution_bias)}
                    </div>
                    <div className="text-[11px] text-text-secondary mt-2">{actionLabel(item.action)}</div>
                    {item.execution_note ? <div className="text-[11px] text-text-secondary mt-1 max-w-[220px]">{item.execution_note}</div> : null}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-[11px] text-text-secondary">상방 / 기준 / 하방</div>
                    <div className="font-mono text-xs mt-1">
                      {item.bull_case_price != null ? formatPrice(item.bull_case_price, item.country_code) : "미정"} / {item.base_case_price != null ? formatPrice(item.base_case_price, item.country_code) : "미정"} / {item.bear_case_price != null ? formatPrice(item.bear_case_price, item.country_code) : "미정"}
                    </div>
                    <div className="text-[11px] text-text-secondary mt-1">
                      {item.bull_probability?.toFixed(1) ?? "-"}% / {item.base_probability?.toFixed(1) ?? "-"}% / {item.bear_probability?.toFixed(1) ?? "-"}%
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="max-w-[280px] text-xs text-text-secondary">{item.thesis[0] || "추가 메모 없음"}</div>
                    {item.risk_flags.length > 0 ? <div className="max-w-[280px] text-[11px] text-amber-600 mt-2">{item.risk_flags[0]}</div> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid xl:grid-cols-[1.15fr_1fr] gap-5">
        <div className="card !p-4 space-y-3">
          <div>
            <h3 className="font-semibold text-sm">추천 비중 분해</h3>
            <p className="text-xs text-text-secondary mt-1">국가와 섹터 상단이 과해지지 않도록 같이 확인합니다.</p>
          </div>
          <div className="space-y-3">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary mb-2">국가 비중</div>
              <div className="flex flex-wrap gap-2">
                {data.allocation.by_country.map((item) => (
                  <div key={item.name} className="rounded-full border border-border px-3 py-1.5 text-xs">
                    {item.name} {item.value.toFixed(1)}%
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary mb-2">섹터 비중</div>
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
            <h3 className="font-semibold text-sm">기록 추적</h3>
            <p className="text-xs text-text-secondary mt-1">이전 추천안이 실제로 어땠는지 일자별로 추적합니다.</p>
          </div>
          <div className="space-y-2">
            {history.map((item) => (
              <div key={item.reference_date} className="rounded-xl border border-border/70 px-3 py-2">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">{item.reference_date}</div>
                    <div className="text-[11px] text-text-secondary mt-1">상위 종목 {item.top_tickers.join(", ")}</div>
                  </div>
                  <div className="text-right">
                    <div className={`font-semibold ${changeColor(item.realized_portfolio_return_pct ?? item.predicted_portfolio_return_pct)}`}>
                      {item.evaluated ? formatPct(item.realized_portfolio_return_pct ?? 0) : formatPct(item.predicted_portfolio_return_pct)}
                    </div>
                    <div className="text-[11px] text-text-secondary mt-1">
                      {item.evaluated ? `승률 ${item.hit_rate?.toFixed(1) ?? "-"}%` : "평가 대기"}
                    </div>
                  </div>
                </div>
                <div className="text-[11px] text-text-secondary mt-2">
                  예측 {formatPct(item.predicted_portfolio_return_pct)}{item.evaluated ? ` · 방향 적중 ${item.direction_accuracy?.toFixed(1) ?? "-"}%` : ""}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
