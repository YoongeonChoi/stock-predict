"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from "recharts";
import type { IndexForecast } from "@/lib/types";

export default function ForecastBand({ forecast }: { forecast: IndexForecast }) {
  const data = forecast.scenarios.map((s) => ({
    name: s.name,
    price: s.price,
    probability: s.probability,
    fill: s.name === "Bull" ? "#22c55e" : s.name === "Bear" ? "#ef4444" : "#3b82f6",
  }));

  return (
    <div className="space-y-3">
      <div className="flex items-baseline gap-4">
        <span className="text-sm text-text-secondary">Current</span>
        <span className="text-lg font-bold">{forecast.current_price.toLocaleString()}</span>
        <span className="text-sm text-text-secondary">Fair Value</span>
        <span className="text-lg font-bold text-emerald-500">{forecast.fair_value.toLocaleString()}</span>
      </div>

      <div className="w-full h-44">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ left: 40, right: 20 }}>
            <XAxis type="number" domain={["auto", "auto"]} tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: "var(--text-secondary)" }} width={40} />
            <Tooltip
              contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
              formatter={(v: number) => v.toLocaleString()}
            />
            <ReferenceLine x={forecast.current_price} stroke="var(--text-secondary)" strokeDasharray="4 4" />
            <Bar dataKey="price" radius={[0, 6, 6, 0]}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center text-sm">
        {forecast.scenarios.map((s) => (
          <div key={s.name} className="card !p-3">
            <div className="font-medium">{s.name}</div>
            <div className="text-lg font-bold">{s.price.toLocaleString()}</div>
            <div className="text-text-secondary">{s.probability}%</div>
          </div>
        ))}
      </div>

      {forecast.confidence_note && (
        <p className="text-xs text-text-secondary">{forecast.confidence_note}</p>
      )}
    </div>
  );
}
