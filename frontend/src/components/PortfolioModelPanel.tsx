"use client";

import Link from "next/link";

import type { PortfolioModelItem, PortfolioModelPortfolio } from "@/lib/api";
import { changeColor, formatPct } from "@/lib/utils";

interface Props {
  model: PortfolioModelPortfolio;
}

function actionLabel(action: PortfolioModelItem["action"]) {
  if (action === "new") return "신규 편입";
  if (action === "add") return "비중 확대";
  if (action === "trim") return "비중 축소";
  if (action === "exit") return "정리";
  if (action === "watch") return "관찰";
  return "유지";
}

function actionTone(action: PortfolioModelItem["action"]) {
  if (action === "new" || action === "add") return "text-emerald-500 bg-emerald-500/10";
  if (action === "trim") return "text-amber-500 bg-amber-500/10";
  if (action === "exit") return "text-negative bg-negative/10";
  if (action === "watch") return "text-sky-500 bg-sky-500/10";
  return "text-text-secondary bg-surface";
}

function sourceLabel(source: PortfolioModelItem["source"]) {
  if (source === "holding") return "보유";
  if (source === "watchlist") return "워치리스트";
  return "레이더";
}

function priorityLabel(priority: PortfolioModelItem["priority"]) {
  if (priority === "high") return "높음";
  if (priority === "medium") return "보통";
  return "낮음";
}

function executionBiasLabel(bias?: PortfolioModelItem["execution_bias"]) {
  if (bias === "press_long") return "추세 대응";
  if (bias === "lean_long") return "상방 우세";
  if (bias === "reduce_risk") return "리스크 관리";
  if (bias === "capital_preservation") return "방어 우선";
  return "선별 대응";
}

function executionBiasTone(bias?: PortfolioModelItem["execution_bias"]) {
  if (bias === "press_long") return "text-positive bg-positive/10";
  if (bias === "lean_long") return "text-emerald-500 bg-emerald-500/10";
  if (bias === "reduce_risk") return "text-amber-500 bg-amber-500/10";
  if (bias === "capital_preservation") return "text-negative bg-negative/10";
  return "text-text-secondary bg-surface";
}

function WeightDelta({ value }: { value: number }) {
  const text = `${value >= 0 ? "+" : ""}${value.toFixed(1)}%p`;
  return <span className={changeColor(value)}>{text}</span>;
}

function CompactIdea({ item }: { item: PortfolioModelItem }) {
  return (
    <div className="rounded-xl border border-border/70 px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Link href={`/stock/${encodeURIComponent(item.ticker)}`} className="font-medium hover:text-accent">
              {item.name}
            </Link>
            <span className="text-[11px] text-text-secondary">{item.ticker}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] ${actionTone(item.action)}`}>{actionLabel(item.action)}</span>
          </div>
          <div className="text-xs text-text-secondary mt-1">{item.rationale[0] || item.risk_flags[0] || "추가 설명 없음"}</div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-sm font-semibold">{item.target_weight_pct.toFixed(1)}%</div>
          <div className="text-[11px] text-text-secondary mt-1">{priorityLabel(item.priority)}</div>
        </div>
      </div>
    </div>
  );
}

export default function PortfolioModelPanel({ model }: Props) {
  const hasIdeas = model.recommended_holdings.length > 0;

  return (
    <div className="space-y-5">
      <div className="card !p-4 space-y-4">
        <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
          <div>
            <h3 className="font-semibold text-sm">모델 포트폴리오</h3>
            <p className="text-xs text-text-secondary mt-1">{model.objective}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="rounded-full px-3 py-1.5 text-xs font-medium bg-accent/10 text-accent">
              {model.risk_budget.style_label}
            </div>
            <div className="rounded-full px-3 py-1.5 text-xs font-medium bg-surface border border-border">
              단일 종목 상단 {model.risk_budget.max_single_weight_pct.toFixed(1)}%
            </div>
            <div className="rounded-full px-3 py-1.5 text-xs font-medium bg-surface border border-border">
              국가 상단 {model.risk_budget.max_country_weight_pct.toFixed(1)}%
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 xl:grid-cols-6 gap-4">
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">추천 주식 비중</div>
            <div className="text-2xl font-bold mt-2">{model.risk_budget.recommended_equity_pct.toFixed(1)}%</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">현금 버퍼</div>
            <div className="text-2xl font-bold mt-2">{model.risk_budget.cash_buffer_pct.toFixed(1)}%</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">모델 상승 확률</div>
            <div className="text-2xl font-bold mt-2">{model.summary.model_up_probability.toFixed(1)}%</div>
            <div className={`text-[11px] mt-1 ${changeColor(model.summary.model_predicted_return_pct)}`}>다음 거래일 {formatPct(model.summary.model_predicted_return_pct)}</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">권장 포지션 수</div>
            <div className="text-2xl font-bold mt-2">{model.summary.selected_count}</div>
            <div className="text-[11px] text-text-secondary mt-1">목표 {model.risk_budget.target_position_count}개</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">신규 편입 후보</div>
            <div className="text-2xl font-bold mt-2">{model.summary.new_position_count}</div>
            <div className="text-[11px] text-text-secondary mt-1">워치리스트 반영 {model.summary.watchlist_focus_count}개</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/60 px-3 py-3">
            <div className="text-xs text-text-secondary">축소/정리 후보</div>
            <div className="text-2xl font-bold mt-2">{model.summary.trim_count}</div>
            <div className="text-[11px] text-text-secondary mt-1">리밸런싱 큐 기준</div>
          </div>
        </div>

        <div className="grid xl:grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary">핵심 메모</div>
            {model.notes.map((note) => (
              <div key={note} className="rounded-xl border border-border/70 bg-surface/50 px-3 py-2 text-sm">
                {note}
              </div>
            ))}
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="rounded-2xl border border-border/70 bg-surface/50 px-3 py-3">
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary">추천 국가 비중</div>
              <div className="flex flex-wrap gap-2 mt-3">
                {model.allocation.by_country.length > 0 ? model.allocation.by_country.map((item) => (
                  <div key={item.name} className="rounded-full border border-border px-3 py-1.5 text-xs">
                    {item.name} {item.value.toFixed(1)}%
                  </div>
                )) : <div className="text-sm text-text-secondary">아직 계산된 비중이 없습니다.</div>}
              </div>
            </div>
            <div className="rounded-2xl border border-border/70 bg-surface/50 px-3 py-3">
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary">추천 섹터 비중</div>
              <div className="flex flex-wrap gap-2 mt-3">
                {model.allocation.by_sector.length > 0 ? model.allocation.by_sector.map((item) => (
                  <div key={item.name} className="rounded-full border border-border px-3 py-1.5 text-xs">
                    {item.name} {item.value.toFixed(1)}%
                  </div>
                )) : <div className="text-sm text-text-secondary">아직 계산된 비중이 없습니다.</div>}
              </div>
            </div>
          </div>
        </div>
      </div>

      {hasIdeas ? (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,1fr)]">
          <div className="min-w-0 card !p-0 overflow-hidden">
            <div className="px-4 py-3 border-b border-border">
              <h3 className="font-semibold">권장 비중 테이블</h3>
              <p className="text-xs text-text-secondary mt-1">현재 보유 비중과 목표 비중의 차이를 바로 확인하고, 어떤 종목을 늘리거나 줄일지 결정할 수 있습니다.</p>
            </div>
            <div className="overflow-x-auto px-2 pb-2 pt-1 md:px-3">
              <table className="w-full text-sm min-w-[920px]">
                <thead>
                  <tr className="text-left text-text-secondary border-b border-border bg-surface/40">
                    <th className="px-4 py-3">종목</th>
                    <th className="px-4 py-3">출처</th>
                    <th className="px-4 py-3 text-right">현재</th>
                    <th className="px-4 py-3 text-right">목표</th>
                    <th className="px-4 py-3 text-right">변화</th>
                    <th className="px-4 py-3 text-right">모델 점수</th>
                    <th className="px-4 py-3">시그널</th>
                    <th className="px-4 py-3">근거</th>
                  </tr>
                </thead>
                <tbody>
                  {model.recommended_holdings.map((item) => (
                    <tr key={`${item.country_code}-${item.ticker}`} className="border-b border-border/30 align-top hover:bg-border/10">
                      <td className="px-4 py-3">
                        <Link href={`/stock/${encodeURIComponent(item.ticker)}`} className="font-medium hover:text-accent">
                          {item.name}
                        </Link>
                        <div className="text-[11px] text-text-secondary mt-1">{item.ticker} · {item.country_code} · {item.sector}</div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col items-start gap-2">
                          <span className="rounded-full px-2 py-1 text-[11px] bg-surface border border-border">{sourceLabel(item.source)}</span>
                          {item.in_watchlist ? <span className="rounded-full px-2 py-1 text-[11px] text-sky-500 bg-sky-500/10">관심 종목</span> : null}
                          <span className={`rounded-full px-2 py-1 text-[11px] ${actionTone(item.action)}`}>{actionLabel(item.action)}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right font-semibold">{item.current_weight_pct.toFixed(1)}%</td>
                      <td className="px-4 py-3 text-right font-semibold">{item.target_weight_pct.toFixed(1)}%</td>
                      <td className="px-4 py-3 text-right font-semibold">
                        <WeightDelta value={item.delta_weight_pct} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="font-semibold">{item.model_score.toFixed(1)}</div>
                        <div className="text-[11px] text-text-secondary mt-1">{priorityLabel(item.priority)}</div>
                      </td>
                      <td className="px-4 py-3">
                        <div className={`inline-flex px-2 py-1 rounded-full text-[11px] ${executionBiasTone(item.execution_bias)}`}>
                          {executionBiasLabel(item.execution_bias)}
                        </div>
                        <div className="text-[11px] text-text-secondary mt-2">
                          상승 {item.up_probability?.toFixed(1) ?? "-"}% / 하방 {item.bear_probability?.toFixed(1) ?? "-"}%
                        </div>
                        {item.setup_label ? <div className="text-[11px] text-text-secondary mt-1">{item.setup_label}</div> : null}
                      </td>
                      <td className="px-4 py-3">
                        <div className="max-w-[280px] text-xs text-text-secondary">{item.rationale[0] || "근거 없음"}</div>
                        {item.risk_flags.length > 0 ? <div className="max-w-[280px] text-[11px] text-amber-600 mt-2">{item.risk_flags[0]}</div> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="min-w-0 space-y-5">
            <div className="card !p-4 space-y-3">
              <div>
                <h3 className="font-semibold text-sm">리밸런싱 큐</h3>
                <p className="text-xs text-text-secondary mt-1">지금 바로 확인할 우선 액션을 큰 변화부터 정렬했습니다.</p>
              </div>
              <div className="space-y-2">
                {model.rebalance_actions.map((item) => (
                  <CompactIdea key={`${item.ticker}-${item.action}`} item={item} />
                ))}
              </div>
            </div>

            <div className="card !p-4 space-y-3">
              <div>
                <h3 className="font-semibold text-sm">후보 파이프라인</h3>
                <p className="text-xs text-text-secondary mt-1">이번 라운드에서는 제외했지만 다음 자금 투입 때 볼 만한 후보입니다.</p>
              </div>
              {model.candidate_pipeline.length > 0 ? (
                <div className="space-y-2">
                  {model.candidate_pipeline.map((item) => (
                    <div key={`${item.country_code}-${item.ticker}`} className="rounded-xl border border-border/70 px-3 py-2">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Link href={`/stock/${encodeURIComponent(item.ticker)}`} className="font-medium hover:text-accent">
                              {item.name}
                            </Link>
                            <span className="text-[11px] text-text-secondary">{item.ticker}</span>
                            <span className="rounded-full px-2 py-0.5 text-[11px] bg-surface border border-border">{sourceLabel(item.source)}</span>
                          </div>
                          <div className="text-xs text-text-secondary mt-1">{item.rationale[0] || "근거 없음"}</div>
                        </div>
                        <div className="text-right shrink-0">
                          <div className="font-semibold">{item.model_score.toFixed(1)}</div>
                          <div className={`text-[11px] mt-1 ${executionBiasTone(item.execution_bias)}`}>{executionBiasLabel(item.execution_bias)}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-text-secondary">지금은 추가 후보보다 기존 포지션 정리가 우선입니다.</div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="card !p-6 text-sm text-text-secondary">
          추천 비중을 계산할 만큼 확신 높은 후보가 아직 부족합니다. 워치리스트를 더 채우거나 보유 종목을 추가하면 모델 포트폴리오가 더 정교해집니다.
        </div>
      )}
    </div>
  );
}
