"use client";

import type { MarketRegime } from "@/lib/types";

interface Props {
  regime: MarketRegime;
  title?: string;
}

function tone(status: string) {
  if (["risk_on", "bullish", "strong", "uptrend"].includes(status)) return "text-positive bg-positive/10";
  if (["risk_off", "bearish", "weak", "downtrend", "high"].includes(status)) return "text-negative bg-negative/10";
  return "text-warning bg-warning/10";
}

function label(status: string) {
  if (status === "risk_on") return "위험 선호";
  if (status === "risk_off") return "위험 회피";
  if (status === "bullish") return "강세";
  if (status === "bearish") return "약세";
  if (status === "neutral") return "중립";
  if (status === "strong") return "강함";
  if (status === "weak") return "약함";
  if (status === "uptrend") return "상승 추세";
  if (status === "range") return "박스권";
  if (status === "downtrend") return "하락 추세";
  if (status === "high") return "높음";
  if (status === "normal") return "보통";
  if (status === "low") return "낮음";
  if (status === "mixed") return "혼조";
  return status.replaceAll("_", " ");
}

export default function MarketRegimeCard({ regime, title = "시장 국면" }: Props) {
  return (
    <div className="card !p-5 space-y-5">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.08fr)_220px] xl:items-start">
        <div className="min-w-0">
          <h2 className="font-semibold">{title}</h2>
          <p className="text-sm text-text-secondary mt-1">{regime.summary}</p>
          <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
            <span className={`px-2 py-1 rounded-full uppercase tracking-wide font-semibold ${tone(regime.stance)}`}>국면 {label(regime.stance)}</span>
            <span className={`px-2 py-1 rounded-full font-medium ${tone(regime.trend)}`}>추세 {label(regime.trend)}</span>
            <span className={`px-2 py-1 rounded-full font-medium ${tone(regime.volatility === "high" ? "risk_off" : regime.volatility === "low" ? "risk_on" : "neutral")}`}>변동성 {label(regime.volatility)}</span>
            <span className={`px-2 py-1 rounded-full font-medium ${tone(regime.breadth)}`}>시장 폭 {label(regime.breadth)}</span>
          </div>
        </div>
        <div className="workspace-panel-tight h-fit">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">판단 강도</div>
          <div className="mt-3 text-3xl font-bold text-text">{regime.score.toFixed(1)}</div>
          <div className="mt-1 text-xs text-text-secondary">확신도 {regime.conviction.toFixed(0)} / 100</div>
          <div className="mt-3 rounded-2xl border border-border/70 bg-surface/60 px-3 py-2 text-xs text-text-secondary">
            지금 국면을 먼저 읽고, 아래 플레이북과 세부 신호를 같은 축에서 이어 봅니다.
          </div>
        </div>
      </div>

      <div className="workspace-grid-balanced">
        <div className="workspace-panel-tight">
          <div className="text-xs font-medium text-text-secondary mb-2">실행 플레이북</div>
          <div className="space-y-2">
            {regime.playbook.map((item) => <div key={item} className="rounded-lg border border-border px-3 py-2 text-sm">{item}</div>)}
          </div>
          {regime.warnings.length > 0 ? (
            <div className="mt-4">
              <div className="text-xs font-medium text-text-secondary mb-2">경고 신호</div>
              <div className="space-y-2">
                {regime.warnings.map((item) => <div key={item} className="rounded-lg bg-negative/10 text-sm px-3 py-2 text-negative">{item}</div>)}
              </div>
            </div>
          ) : null}
        </div>

        <div className="workspace-panel-tight">
          <div className="text-xs font-medium text-text-secondary mb-2">세부 신호</div>
          <div className="space-y-2">
            {regime.signals.map((signal) => (
              <div key={signal.name} className="rounded-lg border border-border px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium">{signal.name}</span>
                  <span className={`text-[11px] px-2 py-0.5 rounded-full uppercase tracking-wide font-semibold ${tone(signal.signal)}`}>{label(signal.signal)}</span>
                </div>
                <div className="text-xs text-text-secondary mt-1">{signal.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
