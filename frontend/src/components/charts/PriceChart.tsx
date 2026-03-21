"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import type { PricePoint } from "@/lib/types";

interface Props {
  data: PricePoint[];
  ma20?: (number | null)[];
  ma60?: (number | null)[];
  buyZone?: { low: number; high: number };
  sellZone?: { low: number; high: number };
  fairValue?: number;
}

export default function PriceChart({ data, ma20, ma60, buyZone, sellZone, fairValue }: Props) {
  const chartData = data.map((p, i) => ({
    date: p.date.slice(5),
    close: p.close,
    ma20: ma20?.[i] ?? undefined,
    ma60: ma60?.[i] ?? undefined,
  }));

  return (
    <div className="w-full h-72">
      <ResponsiveContainer>
        <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
          <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11, fill: "var(--text-secondary)" }} width={60} />
          <Tooltip
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
          />
          <Line type="monotone" dataKey="close" stroke="var(--accent)" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="ma20" stroke="#f59e0b" dot={false} strokeWidth={1} strokeDasharray="4 2" />
          <Line type="monotone" dataKey="ma60" stroke="#8b5cf6" dot={false} strokeWidth={1} strokeDasharray="4 2" />
          {fairValue && <ReferenceLine y={fairValue} stroke="#22c55e" strokeDasharray="6 3" label={{ value: "Fair", fill: "#22c55e", fontSize: 10 }} />}
          {buyZone && <ReferenceLine y={buyZone.high} stroke="#3b82f6" strokeDasharray="4 4" label={{ value: "Buy", fill: "#3b82f6", fontSize: 10 }} />}
          {sellZone && <ReferenceLine y={sellZone.low} stroke="#ef4444" strokeDasharray="4 4" label={{ value: "Sell", fill: "#ef4444", fontSize: 10 }} />}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
