"use client";

import { useMemo } from "react";

interface PricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Props {
  data: PricePoint[];
  width?: number;
  height?: number;
}

export default function CandlestickChart({ data, width = 800, height = 320 }: Props) {
  const chart = useMemo(() => {
    if (data.length === 0) return null;

    const padding = { top: 10, bottom: 30, left: 50, right: 10 };
    const cw = width - padding.left - padding.right;
    const ch = height - padding.top - padding.bottom;

    const allHigh = Math.max(...data.map((d) => d.high));
    const allLow = Math.min(...data.map((d) => d.low));
    const range = allHigh - allLow || 1;

    const barW = Math.max(1, (cw / data.length) * 0.7);
    const gap = cw / data.length;

    const toY = (price: number) => padding.top + ch - ((price - allLow) / range) * ch;

    const candles = data.map((d, i) => {
      const x = padding.left + i * gap + gap / 2;
      const isUp = d.close >= d.open;
      const color = isUp ? "var(--positive)" : "var(--negative)";
      const bodyTop = toY(Math.max(d.open, d.close));
      const bodyBottom = toY(Math.min(d.open, d.close));
      const bodyH = Math.max(1, bodyBottom - bodyTop);

      return (
        <g key={i}>
          <line x1={x} y1={toY(d.high)} x2={x} y2={toY(d.low)} stroke={color} strokeWidth={1} />
          <rect x={x - barW / 2} y={bodyTop} width={barW} height={bodyH} fill={color} rx={0.5} />
        </g>
      );
    });

    const yTicks = Array.from({ length: 5 }, (_, i) => allLow + (range * i) / 4);
    const xLabels = data.filter((_, i) => i % Math.ceil(data.length / 6) === 0);

    return (
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        {yTicks.map((v) => (
          <g key={v}>
            <line x1={padding.left} y1={toY(v)} x2={width - padding.right} y2={toY(v)} stroke="var(--border)" strokeWidth={0.5} />
            <text x={padding.left - 5} y={toY(v) + 3} textAnchor="end" fontSize={9} fill="var(--text-secondary)">
              {v.toFixed(v > 1000 ? 0 : 2)}
            </text>
          </g>
        ))}
        {xLabels.map((d, i) => {
          const idx = data.indexOf(d);
          const x = padding.left + idx * gap + gap / 2;
          return (
            <text key={i} x={x} y={height - 8} textAnchor="middle" fontSize={9} fill="var(--text-secondary)">
              {d.date.slice(5)}
            </text>
          );
        })}
        {candles}
      </svg>
    );
  }, [data, width, height]);

  if (data.length === 0) return <p className="text-sm text-text-secondary text-center py-8">No data</p>;

  return <div className="w-full overflow-x-auto">{chart}</div>;
}
