"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { NextDayForecast, PricePoint } from "@/lib/types";

interface Props {
  data: PricePoint[];
  ma20?: (number | null)[];
  ma60?: (number | null)[];
  buyZone?: { low: number; high: number };
  sellZone?: { low: number; high: number };
  fairValue?: number;
  nextDayForecast?: NextDayForecast;
}

export default function PriceChart({ data, ma20, ma60, buyZone, sellZone, fairValue, nextDayForecast }: Props) {
  const chartData: Array<{
    date: string;
    close?: number;
    ma20?: number;
    ma60?: number;
    projection?: number;
    forecastHigh?: number;
    forecastLow?: number;
  }> = data.map((p, i) => ({
    date: p.date.slice(5),
    close: p.close,
    ma20: ma20?.[i] ?? undefined,
    ma60: ma60?.[i] ?? undefined,
  }));

  if (nextDayForecast && data.length > 0) {
    const lastClose = data[data.length - 1].close;
    chartData[chartData.length - 1] = {
      ...chartData[chartData.length - 1],
      projection: lastClose,
      forecastHigh: lastClose,
      forecastLow: lastClose,
    };
    chartData.push({
      date: nextDayForecast.target_date.slice(5),
      close: undefined,
      ma20: undefined,
      ma60: undefined,
      projection: nextDayForecast.predicted_close,
      forecastHigh: nextDayForecast.predicted_high,
      forecastLow: nextDayForecast.predicted_low,
    });
  }

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
          {nextDayForecast && (
            <>
              <Line
                type="monotone"
                dataKey="projection"
                stroke="#10b981"
                dot={{ r: 3, fill: "#10b981" }}
                strokeWidth={2}
                strokeDasharray="5 4"
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="forecastHigh"
                stroke="#22c55e"
                dot={false}
                strokeWidth={1}
                strokeDasharray="3 3"
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="forecastLow"
                stroke="#ef4444"
                dot={false}
                strokeWidth={1}
                strokeDasharray="3 3"
                connectNulls
              />
            </>
          )}
          {fairValue && <ReferenceLine y={fairValue} stroke="#22c55e" strokeDasharray="6 3" label={{ value: "???", fill: "#22c55e", fontSize: 10 }} />}
          {buyZone && <ReferenceLine y={buyZone.high} stroke="#3b82f6" strokeDasharray="4 4" label={{ value: "??", fill: "#3b82f6", fontSize: 10 }} />}
          {sellZone && <ReferenceLine y={sellZone.low} stroke="#ef4444" strokeDasharray="4 4" label={{ value: "??", fill: "#ef4444", fontSize: 10 }} />}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
