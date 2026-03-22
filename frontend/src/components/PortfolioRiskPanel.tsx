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

export default function PortfolioRiskPanel({ risk, stressTest }: Props) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">Risk Posture</div>
          <div className={`inline-flex mt-2 px-2.5 py-1 rounded-full text-xs font-semibold capitalize ${labelTone(risk.overall_label)}`}>
            {risk.overall_label}
          </div>
          <div className="text-2xl font-bold mt-3">{risk.score.toFixed(1)}</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">Diversification</div>
          <div className="text-2xl font-bold mt-3">{risk.diversification_score.toFixed(1)}</div>
          <div className="text-[11px] text-text-secondary mt-1">Top holding {risk.top_holding_weight.toFixed(1)}%</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">Portfolio Beta</div>
          <div className="text-2xl font-bold mt-3">{risk.portfolio_beta.toFixed(2)}</div>
          <div className="text-[11px] text-text-secondary mt-1">Avg vol {risk.avg_volatility_pct.toFixed(1)}%</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">Upside Odds</div>
          <div className="text-2xl font-bold mt-3">{risk.portfolio_up_probability.toFixed(1)}%</div>
          <div className={`text-[11px] mt-1 ${changeColor(risk.projected_next_day_return_pct)}`}>
            {formatPct(risk.projected_next_day_return_pct)} next session
          </div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">Warnings</div>
          <div className="text-2xl font-bold mt-3">{risk.warning_count}</div>
          <div className="text-[11px] text-text-secondary mt-1">HHI {risk.concentration_hhi.toFixed(3)}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.3fr_1fr] gap-5">
        <div className="card !p-4 space-y-4">
          <div>
            <h3 className="font-semibold text-sm">Portfolio Playbook</h3>
            <p className="text-xs text-text-secondary mt-1">Execution guidance from concentration, volatility, market regime, and next-session forecast alignment.</p>
          </div>
          <div className="space-y-2">
            {risk.playbook.map((item) => (
              <div key={item} className="rounded-xl border border-border/70 bg-surface/60 px-3 py-2 text-sm">
                {item}
              </div>
            ))}
          </div>
          {risk.warnings.length > 0 ? (
            <div className="space-y-2">
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-red-500">Watchouts</div>
              {risk.warnings.map((item) => (
                <div key={item} className="rounded-xl border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-500">
                  {item}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-500">
              No structural warning is currently firing. The book is behaving within normal risk limits.
            </div>
          )}
        </div>

        <div className="space-y-5">
          <div className="card !p-4 space-y-3">
            <div>
              <h3 className="font-semibold text-sm">Market Regimes In The Book</h3>
              <p className="text-xs text-text-secondary mt-1">Weighted by current exposure per country sleeve.</p>
            </div>
            {risk.regimes.length === 0 ? (
              <div className="text-sm text-text-secondary">Market regime context will appear once country benchmarks are available.</div>
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
                        <div className="text-[11px] text-text-secondary capitalize">{regime.stance.replace("_", " ")}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card !p-4 space-y-3">
            <div>
              <h3 className="font-semibold text-sm">Stress Test</h3>
              <p className="text-xs text-text-secondary mt-1">Scenario-level P&L estimates based on live forecast, beta, volatility, and concentration.</p>
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
                      <div className={`font-semibold ${changeColor(scenario.projected_portfolio_pct)}`}>
                        {formatPct(scenario.projected_portfolio_pct)}
                      </div>
                      <div className={`text-xs mt-1 ${changeColor(scenario.projected_pnl)}`}>
                        {scenario.projected_pnl >= 0 ? "+" : ""}{scenario.projected_pnl.toLocaleString()}
                      </div>
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
