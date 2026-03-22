"use client";

import type { TechSummary, TechSummaryGroup } from "@/lib/api";

function translateSignal(signal: string): string {
  if (signal.includes("Strong Buy")) return signal.replace("Strong Buy", "강한 매수");
  if (signal.includes("Buy")) return signal.replace("Buy", "매수");
  if (signal.includes("Strong Sell")) return signal.replace("Strong Sell", "강한 매도");
  if (signal.includes("Sell")) return signal.replace("Sell", "매도");
  if (signal.includes("Neutral")) return signal.replace("Neutral", "중립");
  return signal;
}

function signalColor(signal: string): string {
  if (signal.includes("Buy")) return "text-positive";
  if (signal.includes("Sell")) return "text-negative";
  return "text-text-secondary";
}

function SignalBadge({ signal }: { signal: string }) {
  const bg = signal.includes("Buy")
    ? "bg-positive/20 text-positive"
    : signal.includes("Sell")
      ? "bg-negative/20 text-negative"
      : "bg-border text-text-secondary";
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${bg}`}>{translateSignal(signal)}</span>;
}

function GaugeBar({ group, label }: { group: TechSummaryGroup; label: string }) {
  const total = group.buy + group.neutral + group.sell || 1;
  const buyPct = (group.buy / total) * 100;
  const neutralPct = (group.neutral / total) * 100;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{label}</span>
        <SignalBadge signal={group.signal} />
      </div>
      <div className="flex h-2 rounded-full overflow-hidden bg-border">
        <div className="bg-positive" style={{ width: `${buyPct}%` }} />
        <div className="bg-text-secondary/30" style={{ width: `${neutralPct}%` }} />
        <div className="bg-negative" style={{ width: `${100 - buyPct - neutralPct}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-text-secondary">
        <span>매수 {group.buy}</span>
        <span>중립 {group.neutral}</span>
        <span>매도 {group.sell}</span>
      </div>
    </div>
  );
}

interface Props {
  data: TechSummary | null;
  loading?: boolean;
}

export default function TechnicalSummary({ data, loading }: Props) {
  if (loading) return <div className="h-48 bg-border/30 rounded-lg animate-pulse" />;
  if (!data) return null;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <GaugeBar group={data.summary.overall} label="종합" />
        <GaugeBar group={data.summary.moving_averages} label="이동평균" />
        <GaugeBar group={data.summary.oscillators} label="오실레이터" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h4 className="text-sm font-medium mb-2">이동평균</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-secondary border-b border-border">
                  <th className="pb-1 text-left">지표</th>
                  <th className="pb-1 text-right">값</th>
                  <th className="pb-1 text-right">신호</th>
                </tr>
              </thead>
              <tbody>
                {data.moving_averages.map((average) => (
                  <tr key={average.name} className="border-b border-border/30">
                    <td className="py-1">{average.name}</td>
                    <td className="py-1 text-right font-mono">{average.value?.toFixed(2) ?? "미정"}</td>
                    <td className={`py-1 text-right font-medium ${signalColor(average.signal)}`}>{translateSignal(average.signal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h4 className="text-sm font-medium mb-2">오실레이터</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-secondary border-b border-border">
                  <th className="pb-1 text-left">지표</th>
                  <th className="pb-1 text-right">값</th>
                  <th className="pb-1 text-right">신호</th>
                </tr>
              </thead>
              <tbody>
                {data.oscillators.map((oscillator) => (
                  <tr key={oscillator.name} className="border-b border-border/30">
                    <td className="py-1">{oscillator.name}</td>
                    <td className="py-1 text-right font-mono">{oscillator.value?.toFixed(2) ?? "미정"}</td>
                    <td className={`py-1 text-right font-medium ${signalColor(oscillator.signal)}`}>{translateSignal(oscillator.signal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}