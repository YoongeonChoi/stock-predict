"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

interface EarningsEvent {
  date: string;
  eps_estimate: number | null;
  eps_actual: number | null;
  surprise_pct: number | null;
}

interface Props {
  data: EarningsEvent[];
}

export default function EarningsSurprise({ data }: Props) {
  const valid = data.filter((d) => d.eps_estimate != null && d.eps_actual != null);
  if (valid.length === 0) return null;

  const chartData = valid.slice(0, 8).reverse().map((d) => ({
    date: d.date.slice(0, 7),
    estimate: d.eps_estimate,
    actual: d.eps_actual,
    surprise: d.surprise_pct,
  }));

  return (
    <div>
      <div className="h-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} barGap={2}>
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--text-secondary)" }} />
            <YAxis tick={{ fontSize: 10, fill: "var(--text-secondary)" }} width={40} />
            <Tooltip
              contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
              formatter={(value: number, name: string) => [value?.toFixed(2), name === "estimate" ? "예상 EPS" : "실제 EPS"]}
            />
            <ReferenceLine y={0} stroke="var(--border)" />
            <Bar dataKey="estimate" fill="var(--text-secondary)" opacity={0.4} radius={[2, 2, 0, 0]} />
            <Bar dataKey="actual" fill="var(--accent)" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex gap-4 mt-1 text-[10px] text-text-secondary">
        <span><span className="inline-block w-3 h-2 bg-text-secondary/40 mr-1 rounded-sm" /> 예상 EPS</span>
        <span><span className="inline-block w-3 h-2 bg-accent mr-1 rounded-sm" /> 실제 EPS</span>
      </div>
    </div>
  );
}
