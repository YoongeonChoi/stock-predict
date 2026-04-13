"use client";

import type { MarketSessionPublic } from "@/lib/public-server-api";

interface Props {
  sessions: MarketSessionPublic[] | null;
}

export default function MarketSessionBadge({ sessions }: Props) {
  if (!sessions || sessions.length === 0) return null;

  const kr = sessions.find((s) => s.country_code === "KR");
  if (!kr) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ${
          kr.is_open
            ? "bg-emerald-500/12 text-emerald-600 dark:text-emerald-400"
            : "bg-border/50 text-text-secondary"
        }`}
      >
        <span
          className={`h-1.5 w-1.5 rounded-full ${kr.is_open ? "bg-emerald-500 animate-pulse" : "bg-text-secondary/40"}`}
          aria-hidden="true"
        />
        {kr.is_open ? "장중" : "장 마감"}
      </span>
      <span className="text-text-secondary">
        최근 종가 {kr.latest_closed_date} · 다음 거래일 {kr.next_trading_day}
      </span>
    </div>
  );
}
