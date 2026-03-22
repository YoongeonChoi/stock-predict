"use client";

import type { TechSummary, TechSummaryGroup } from "@/lib/api";

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
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${bg}`}>{signal}</span>;
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
        <span>Buy {group.buy}</span>
        <span>Neutral {group.neutral}</span>
        <span>Sell {group.sell}</span>
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
        <GaugeBar group={data.summary.overall} label="Overall" />
        <GaugeBar group={data.summary.moving_averages} label="Moving Averages" />
        <GaugeBar group={data.summary.oscillators} label="Oscillators" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h4 className="text-sm font-medium mb-2">Moving Averages</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-secondary border-b border-border">
                  <th className="pb-1 text-left">Name</th>
                  <th className="pb-1 text-right">Value</th>
                  <th className="pb-1 text-right">Signal</th>
                </tr>
              </thead>
              <tbody>
                {data.moving_averages.map((ma) => (
                  <tr key={ma.name} className="border-b border-border/30">
                    <td className="py-1">{ma.name}</td>
                    <td className="py-1 text-right font-mono">{ma.value?.toFixed(2) ?? "—"}</td>
                    <td className={`py-1 text-right font-medium ${signalColor(ma.signal)}`}>{ma.signal}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h4 className="text-sm font-medium mb-2">Oscillators</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-secondary border-b border-border">
                  <th className="pb-1 text-left">Name</th>
                  <th className="pb-1 text-right">Value</th>
                  <th className="pb-1 text-right">Signal</th>
                </tr>
              </thead>
              <tbody>
                {data.oscillators.map((osc) => (
                  <tr key={osc.name} className="border-b border-border/30">
                    <td className="py-1">{osc.name}</td>
                    <td className="py-1 text-right font-mono">{osc.value?.toFixed(2) ?? "—"}</td>
                    <td className={`py-1 text-right font-medium ${signalColor(osc.signal)}`}>{osc.signal}</td>
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
