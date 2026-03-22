"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HistoricalPatternForecast, NextDayForecast, PricePoint } from "@/lib/types";

interface Props {
  data: PricePoint[];
  ma20?: (number | null)[];
  ma60?: (number | null)[];
  buyZone?: { low: number; high: number };
  sellZone?: { low: number; high: number };
  fairValue?: number;
  nextDayForecast?: NextDayForecast;
  historicalPatternForecast?: HistoricalPatternForecast | null;
}

export default function PriceChart({
  data,
  ma20,
  ma60,
  buyZone,
  sellZone,
  fairValue,
  nextDayForecast,
  historicalPatternForecast,
}: Props) {
  const chartData: Array<{
    date: string;
    close?: number;
    ma20?: number;
    ma60?: number;
    projection?: number;
    forecastHigh?: number;
    forecastLow?: number;
    analogProjection?: number;
    analogBandLow?: number;
    analogBandHigh?: number;
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

  if (historicalPatternForecast && data.length > 0) {
    chartData[chartData.length - 1] = {
      ...chartData[chartData.length - 1],
      analogProjection: data[data.length - 1].close,
      analogBandLow: data[data.length - 1].close,
      analogBandHigh: data[data.length - 1].close,
    };
    for (const point of historicalPatternForecast.projected_path) {
      const label = point.target_date.slice(5);
      const existing = chartData.find((item) => item.date === label);
      if (existing) {
        existing.analogProjection = point.expected_price;
        existing.analogBandLow = point.band_low;
        existing.analogBandHigh = point.band_high;
      } else {
        chartData.push({
          date: label,
          close: undefined,
          ma20: undefined,
          ma60: undefined,
          analogProjection: point.expected_price,
          analogBandLow: point.band_low,
          analogBandHigh: point.band_high,
        });
      }
    }
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
          {historicalPatternForecast && (
            <>
              <Line
                type="monotone"
                dataKey="analogProjection"
                stroke="#0ea5e9"
                dot={false}
                strokeWidth={2}
                strokeDasharray="7 4"
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="analogBandLow"
                stroke="#38bdf8"
                dot={false}
                strokeWidth={1}
                strokeDasharray="2 3"
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="analogBandHigh"
                stroke="#0284c7"
                dot={false}
                strokeWidth={1}
                strokeDasharray="2 3"
                connectNulls
              />
            </>
          )}
          {fairValue ? (
            <ReferenceLine y={fairValue} stroke="#22c55e" strokeDasharray="6 3" label={{ value: "적정가", fill: "#22c55e", fontSize: 10 }} />
          ) : null}
          {buyZone ? (
            <ReferenceLine y={buyZone.high} stroke="#3b82f6" strokeDasharray="4 4" label={{ value: "매수 구간", fill: "#3b82f6", fontSize: 10 }} />
          ) : null}
          {sellZone ? (
            <ReferenceLine y={sellZone.low} stroke="#ef4444" strokeDasharray="4 4" label={{ value: "매도 구간", fill: "#ef4444", fontSize: 10 }} />
          ) : null}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
