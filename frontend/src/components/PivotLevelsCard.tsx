"use client";

import type { PivotLevel } from "@/lib/api";

interface Props {
  title: string;
  levels: PivotLevel;
}

const ORDER = ["r3", "r2", "r1", "pivot", "s1", "s2", "s3"] as const;

export default function PivotLevelsCard({ title, levels }: Props) {
  return (
    <div>
      <h4 className="text-xs text-text-secondary mb-2">{title}</h4>
      <div className="space-y-1 text-xs">
        {ORDER.map((key) => (
          <div key={key} className="flex justify-between">
            <span className={key.startsWith("r") ? "text-positive" : key.startsWith("s") ? "text-negative" : "font-bold"}>
              {key.toUpperCase()}
            </span>
            <span className="font-mono">{levels[key]?.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
