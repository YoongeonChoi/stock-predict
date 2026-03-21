"use client";

import type { FearGreedIndex } from "@/lib/types";

export default function FearGreedGauge({ data }: { data: FearGreedIndex }) {
  const rotation = (data.score / 100) * 180 - 90;
  const color =
    data.score >= 80 ? "#22c55e" : data.score >= 60 ? "#84cc16" : data.score >= 40 ? "#eab308" : data.score >= 20 ? "#f97316" : "#ef4444";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-40 h-20 overflow-hidden">
        <div className="absolute inset-0 rounded-t-full border-8 border-border" />
        <div
          className="absolute bottom-0 left-1/2 w-1 h-16 origin-bottom rounded-full transition-transform duration-700"
          style={{ background: color, transform: `translateX(-50%) rotate(${rotation}deg)` }}
        />
        <div className="absolute bottom-0 left-1/2 w-3 h-3 -translate-x-1/2 translate-y-1/2 rounded-full bg-text" />
      </div>
      <div className="text-center">
        <span className="text-2xl font-bold" style={{ color }}>{data.score.toFixed(0)}</span>
        <span className="text-sm text-text-secondary ml-2">{data.label}</span>
      </div>
      <div className="grid grid-cols-5 gap-2 w-full mt-2">
        {data.components.map((c) => (
          <div key={c.name} className="text-center">
            <div className="text-xs text-text-secondary">{c.name.split(" ")[0]}</div>
            <div className="text-sm font-medium">{c.value.toFixed(0)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
