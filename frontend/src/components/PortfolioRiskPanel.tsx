"use client";

import type { PortfolioRiskSnapshot, PortfolioStressScenario } from "@/lib/api";
import { changeColor, formatPct } from "@/lib/utils";

interface Props {
  risk: PortfolioRiskSnapshot;
  stressTest: PortfolioStressScenario[];
}

function labelTone(label: PortfolioRiskSnapshot["overall_label"]) {
  if (label === "balanced") return "text-emerald-500 bg-emerald-500/10";
  if (label === "moderate") return "text-yellow-500 bg-yellow-500/10";
  if (label === "elevated") return "text-orange-500 bg-orange-500/10";
  if (label === "aggressive") return "text-red-500 bg-red-500/10";
  return "text-text-secondary bg-surface";
}

function overallLabel(label: PortfolioRiskSnapshot["overall_label"]) {
  if (label === "balanced") return "안정";
  if (label === "moderate") return "보통";
  if (label === "elevated") return "주의";
  if (label === "aggressive") return "공격적";
  return "비어 있음";
}

function regimeStanceLabel(stance: string) {
  if (stance === "risk_on") return "위험 선호";
  if (stance === "risk_off") return "위험 회피";
  if (stance === "bullish") return "강세";
  if (stance === "bearish") return "약세";
  return stance.replaceAll("_", " ");
}

export default function PortfolioRiskPanel({ risk, stressTest }: Props) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">전체 리스크</div>
          <div className={`inline-flex mt-2 px-2.5 py-1 rounded-full text-xs font-semibold ${labelTone(risk.overall_label)}`}>{overallLabel(risk.overall_label)}</div>
          <div className="text-2xl font-bold mt-3">{risk.score.toFixed(1)}</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">분산 점수</div>
          <div className="text-2xl font-bold mt-3">{risk.diversification_score.toFixed(1)}</div>
          <div className="text-[11px] text-text-secondary mt-1">최대 비중 {risk.top_holding_weight.toFixed(1)}%</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">포트폴리오 베타</div>
          <div className="text-2xl font-bold mt-3">{risk.portfolio_beta.toFixed(2)}</div>
          <div className="text-[11px] text-text-secondary mt-1">평균 변동성 {risk.avg_volatility_pct.toFixed(1)}%</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">상승 확률</div>
          <div className="text-2xl font-bold mt-3">{risk.portfolio_up_probability.toFixed(1)}%</div>
          <div className={`text-[11px] mt-1 ${changeColor(risk.projected_next_day_return_pct)}`}>다음 거래일 {formatPct(risk.projected_next_day_return_pct)}</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">경고 수</div>
          <div className="text-2xl font-bold mt-3">{risk.warning_count}</div>
          <div className="text-[11px] text-text-secondary mt-1">HHI {risk.concentration_hhi.toFixed(3)}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.3fr_1fr] gap-5">
        <div className="card !p-4 space-y-4">
          <div>
            <h3 className="font-semibold text-sm">실행 플레이북</h3>
            <p className="text-xs text-text-secondary mt-1">집중도, 변동성, 시장 국면, 단기 기대 수익을 함께 반영한 운영 가이드입니다.</p>
          </div>
          <div className="space-y-2">
            {risk.playbook.map((item) => <div key={item} className="rounded-xl border border-border/70 bg-surface/60 px-3 py-2 text-sm">{item}</div>)}
          </div>
          {risk.warnings.length > 0 ? (
            <div className="space-y-2">
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-red-500">주의 경고</div>
              {risk.warnings.map((item) => <div key={item} className="rounded-xl border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-500">{item}</div>)}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-500">현재 뚜렷한 위험 경고는 없습니다. 그래도 분산과 현금 비중은 계속 점검해 주세요.</div>
          )}
        </div>

        <div className="space-y-5">
          <div className="card !p-4 space-y-3">
            <div>
              <h3 className="font-semibold text-sm">국가별 시장 국면</h3>
              <p className="text-xs text-text-secondary mt-1">보유 비중이 높은 시장부터 어떤 분위기인지 바로 확인할 수 있습니다.</p>
            </div>
            {risk.regimes.length === 0 ? (
              <div className="text-sm text-text-secondary">국가별 국면 데이터를 계산할 표본이 아직 부족합니다.</div>
            ) : (
              <div className="space-y-2">
                {risk.regimes.map((regime) => (
                  <div key={regime.country_code} className="rounded-xl border border-border/70 px-3 py-2">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-medium">{regime.country_code}</div>
                        <div className="text-xs text-text-secondary mt-0.5">{regime.label}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold">{regime.weight.toFixed(1)}%</div>
                        <div className="text-[11px] text-text-secondary">{regimeStanceLabel(regime.stance)}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card !p-4 space-y-3">
            <div>
              <h3 className="font-semibold text-sm">스트레스 테스트</h3>
              <p className="text-xs text-text-secondary mt-1">금리 쇼크, 급락, 안도 랠리 같은 상황에서 예상 손익을 빠르게 봅니다.</p>
            </div>
            <div className="space-y-2">
              {stressTest.map((scenario) => (
                <div key={scenario.name} className="rounded-xl border border-border/70 px-3 py-2">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">{scenario.name}</div>
                      <div className="text-xs text-text-secondary mt-1">{scenario.description}</div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className={`font-semibold ${changeColor(scenario.projected_portfolio_pct)}`}>{formatPct(scenario.projected_portfolio_pct)}</div>
                      <div className={`text-xs mt-1 ${changeColor(scenario.projected_pnl)}`}>{scenario.projected_pnl >= 0 ? "+" : ""}{scenario.projected_pnl.toLocaleString()}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}