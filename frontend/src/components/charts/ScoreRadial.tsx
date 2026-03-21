"use client";

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

interface Props {
  score: number;
  max?: number;
  size?: number;
  label?: string;
}

export default function ScoreRadial({ score, max = 100, size = 120, label }: Props) {
  const pct = Math.min(score / max, 1);
  const data = [
    { value: pct * 100 },
    { value: (1 - pct) * 100 },
  ];
  const color = pct >= 0.8 ? "#10b981" : pct >= 0.6 ? "#22c55e" : pct >= 0.4 ? "#eab308" : pct >= 0.2 ? "#f97316" : "#ef4444";

  return (
    <div className="flex flex-col items-center gap-1" style={{ width: size }}>
      <div style={{ width: size, height: size }} className="relative">
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius="70%"
              outerRadius="90%"
              startAngle={90}
              endAngle={-270}
              dataKey="value"
              stroke="none"
            >
              <Cell fill={color} />
              <Cell fill="var(--border)" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-bold">{score.toFixed(0)}</span>
        </div>
      </div>
      {label && <span className="text-xs text-text-secondary">{label}</span>}
    </div>
  );
}
