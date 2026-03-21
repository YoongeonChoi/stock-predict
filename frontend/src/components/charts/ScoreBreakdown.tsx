"use client";

import type { ScoreItem } from "@/lib/types";

export default function ScoreBreakdown({ items }: { items: ScoreItem[] }) {
  if (!items?.length) return null;
  return (
    <div className="space-y-3">
      {items.filter(Boolean).map((item) => {
        const pct = item.max_score ? (item.score / item.max_score) * 100 : 0;
        const color =
          pct >= 80 ? "bg-emerald-500" : pct >= 60 ? "bg-green-500" : pct >= 40 ? "bg-yellow-500" : pct >= 20 ? "bg-orange-500" : "bg-red-500";
        return (
          <div key={item.name}>
            <div className="flex justify-between text-sm mb-1">
              <span>{item.name}</span>
              <span className="text-text-secondary">
                {(item.score ?? 0).toFixed(1)} / {item.max_score ?? 0}
              </span>
            </div>
            <div className="h-2 rounded-full bg-border overflow-hidden">
              <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
            </div>
            {item.description && (
              <p className="text-xs text-text-secondary mt-0.5">{item.description}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
