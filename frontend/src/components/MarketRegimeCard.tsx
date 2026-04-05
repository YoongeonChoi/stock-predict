"use client";

import type { MarketRegime } from "@/lib/types";

interface Props {
  regime: MarketRegime;
  title?: string;
}

const OPERATIONAL_FALLBACK_PATTERNS = [
  "1차 시세 스캔 후보",
  "시세 스냅샷",
  "fresh quick",
  "사용 가능한 후보",
  "정밀 시장 국면 계산",
  "정밀 국면 계산",
  "대표 후보",
  "다시 열어",
];

function isOperationalFallbackCopy(text?: string | null) {
  if (!text) return false;
  return OPERATIONAL_FALLBACK_PATTERNS.some((pattern) => text.includes(pattern));
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
  const playbook = regime.playbook.filter((item) => !isOperationalFallbackCopy(item));
  const warnings = regime.warnings.filter((item) => !isOperationalFallbackCopy(item));
  const hasOperationalFallback =
    regime.playbook.some((item) => isOperationalFallbackCopy(item))
    || regime.warnings.some((item) => isOperationalFallbackCopy(item));

  return (
    <div className="card !p-5">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(280px,340px)]">
        <div className="workspace-stack">
          <div className="workspace-panel min-w-0">
            <h2 className="font-semibold">{title}</h2>
            <p className="mt-1 text-sm text-text-secondary">{regime.summary}</p>
            <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
              <span className={`rounded-full px-2 py-1 font-semibold uppercase tracking-wide ${tone(regime.stance)}`}>국면 {label(regime.stance)}</span>
              <span className={`rounded-full px-2 py-1 font-medium ${tone(regime.trend)}`}>추세 {label(regime.trend)}</span>
              <span className={`rounded-full px-2 py-1 font-medium ${tone(regime.volatility === "high" ? "risk_off" : regime.volatility === "low" ? "risk_on" : "neutral")}`}>변동성 {label(regime.volatility)}</span>
              <span className={`rounded-full px-2 py-1 font-medium ${tone(regime.breadth)}`}>시장 폭 {label(regime.breadth)}</span>
            </div>
          </div>

          <div className="workspace-panel-tight">
            <div className="text-xs font-medium text-text-secondary">실행 플레이북</div>
            {playbook.length > 0 ? (
              <div className="mt-3 space-y-2">
                {playbook.map((item) => (
                  <div key={item} className="rounded-xl border border-border/70 bg-surface/70 px-3 py-2 text-sm text-text-secondary">
                    {item}
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-3 rounded-xl border border-border/70 bg-surface/70 px-3 py-3 text-sm text-text-secondary">
                이번 응답에서는 확보된 후보와 핵심 지표를 먼저 읽고, 정밀 플레이북은 회복 시 다시 이어집니다.
              </div>
            )}

            {hasOperationalFallback ? (
              <div className="mt-3 rounded-xl border border-border/70 bg-surface/60 px-3 py-3 text-sm text-text-secondary">
                정밀 국면 해석이 지연돼 운영성 안내는 짧게 줄이고, 실제 후보 신호를 우선 표시했습니다.
              </div>
            ) : null}

            {warnings.length > 0 ? (
              <div className="mt-4">
                <div className="text-xs font-medium text-text-secondary">경고 신호</div>
                <div className="mt-3 space-y-2">
                  {warnings.map((item) => (
                    <div key={item} className="rounded-xl bg-negative/10 px-3 py-2 text-sm text-negative">
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="workspace-stack">
          <div className="workspace-panel-tight">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">판단 강도</div>
            <div className="mt-3 text-3xl font-bold text-text">{regime.score.toFixed(1)}</div>
            <div className="mt-1 text-xs text-text-secondary">확신도 {regime.conviction.toFixed(0)} / 100</div>
            <div className="mt-3 rounded-2xl border border-border/70 bg-surface/60 px-3 py-2 text-xs text-text-secondary">
              지금 국면을 먼저 읽고, 바로 아래 세부 신호와 실행 플레이북을 같은 축에서 이어 봅니다.
            </div>
          </div>

          <div className="workspace-panel-tight">
            <div className="text-xs font-medium text-text-secondary">세부 신호</div>
            <div className="mt-3 space-y-2">
              {regime.signals.map((signal) => (
                <div key={signal.name} className="rounded-xl border border-border/70 bg-surface/70 px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-text">{signal.name}</span>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${tone(signal.signal)}`}>
                      {label(signal.signal)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-text-secondary">{signal.detail}</div>
                </div>
              ))}
            </div>
            {regime.signals.length === 0 ? (
              <div className="mt-3 rounded-xl border border-border/70 bg-surface/70 px-3 py-3 text-sm text-text-secondary">
                세부 신호는 아직 정리 중입니다. 이번 응답에서는 시장 국면 요약과 실행 플레이북을 먼저 확인해 주세요.
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
