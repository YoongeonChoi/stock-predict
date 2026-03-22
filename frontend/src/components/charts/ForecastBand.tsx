"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from "recharts";
import type { IndexForecast } from "@/lib/types";

function scenarioLabel(name: string) {
  if (name === "Bull") return "강세";
  if (name === "Bear") return "약세";
  if (name === "Base") return "기본";
  return name;
}

export default function ForecastBand({ forecast }: { forecast: IndexForecast }) {
  if (!forecast?.scenarios?.length) return <p className="text-sm text-text-secondary">예측 시나리오가 아직 없습니다.</p>;
  const data = forecast.scenarios.map((scenario) => ({
    name: scenarioLabel(scenario.name),
    price: scenario.price,
    probability: scenario.probability,
    fill: scenario.name === "Bull" ? "#22c55e" : scenario.name === "Bear" ? "#ef4444" : "#3b82f6",
  }));

  return (
    <div className="space-y-3">
      <div className="flex items-baseline gap-4">
        <span className="text-sm text-text-secondary">현재가</span>
        <span className="text-lg font-bold">{(forecast.current_price ?? 0).toLocaleString()}</span>
        <span className="text-sm text-text-secondary">적정가</span>
        <span className="text-lg font-bold text-emerald-500">{(forecast.fair_value ?? 0).toLocaleString()}</span>
      </div>

      <div className="w-full h-44">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ left: 40, right: 20 }}>
            <XAxis type="number" domain={["auto", "auto"]} tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: "var(--text-secondary)" }} width={48} />
            <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} formatter={(value: number) => value.toLocaleString()} />
            <ReferenceLine x={forecast.current_price} stroke="var(--text-secondary)" strokeDasharray="4 4" />
            <Bar dataKey="price" radius={[0, 6, 6, 0]}>{data.map((item, index) => <Cell key={index} fill={item.fill} />)}</Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center text-sm">
        {forecast.scenarios.map((scenario) => (
          <div key={scenario.name} className="card !p-3">
            <div className="font-medium">{scenarioLabel(scenario.name)}</div>
            <div className="text-lg font-bold">{scenario.price.toLocaleString()}</div>
            <div className="text-text-secondary">확률 {scenario.probability}%</div>
          </div>
        ))}
      </div>

      {forecast.confidence_note ? <p className="text-xs text-text-secondary">{forecast.confidence_note}</p> : null}
    </div>
  );
}