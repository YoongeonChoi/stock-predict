"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { WatchlistItem } from "@/lib/types";
import { formatPct, changeColor } from "@/lib/utils";

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.getWatchlist().then(setItems).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const remove = async (ticker: string) => {
    await api.removeWatchlist(ticker);
    load();
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Watchlist</h1>

      {loading ? (
        <div className="animate-pulse space-y-3">{[1, 2, 3].map((i) => <div key={i} className="h-16 bg-border rounded" />)}</div>
      ) : items.length === 0 ? (
        <p className="text-text-secondary">No stocks in watchlist. Add stocks from the detail page.</p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.ticker} className="card flex items-center justify-between">
              <Link href={`/stock/${item.ticker}`} className="flex-1 hover:text-accent transition-colors">
                <div className="font-medium">{item.name || item.ticker}</div>
                <div className="text-xs text-text-secondary">{item.ticker} · {item.country_code}</div>
              </Link>
              <div className="text-right mr-4">
                <div className="font-mono">{item.current_price?.toLocaleString() ?? "—"}</div>
                <div className={`text-sm ${changeColor(item.change_pct ?? 0)}`}>{formatPct(item.change_pct)}</div>
              </div>
              <div className="text-right mr-4">
                <div className="text-sm text-text-secondary">Score</div>
                <div className="font-bold">{item.score_total?.toFixed(1) ?? "—"}</div>
              </div>
              <button onClick={() => remove(item.ticker)} className="text-xs text-negative hover:underline">Remove</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
