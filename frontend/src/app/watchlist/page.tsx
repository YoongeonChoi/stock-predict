"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { WatchlistItem } from "@/lib/types";
import { formatPct, formatPrice, changeColor } from "@/lib/utils";
import { useToast } from "@/components/Toast";

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [ticker, setTicker] = useState("");
  const [country, setCountry] = useState("US");
  const { toast } = useToast();

  const load = () => {
    setLoading(true);
    api.getWatchlist().then(setItems).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const add = async () => {
    if (!ticker.trim()) return;
    try {
      await api.addWatchlist(ticker.trim().toUpperCase(), country);
      toast(`${ticker.toUpperCase()} added to watchlist`);
      setTicker("");
      load();
    } catch { toast("Failed to add", "error"); }
  };

  const remove = async (t: string) => {
    await api.removeWatchlist(t);
    toast(`${t} removed`);
    load();
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Watchlist</h1>

      <div className="flex gap-2 items-center">
        <input
          value={ticker} onChange={(e) => setTicker(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="Add ticker (e.g. AAPL)"
          className="flex-1 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm focus:outline-none focus:border-accent"
        />
        <select value={country} onChange={(e) => setCountry(e.target.value)}
          className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm">
          <option value="US">US</option><option value="KR">KR</option><option value="JP">JP</option>
        </select>
        <button onClick={add} className="px-4 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90">Add</button>
      </div>

      {loading ? (
        <div className="animate-pulse space-y-3">{[1, 2, 3].map((i) => <div key={i} className="h-16 bg-border rounded" />)}</div>
      ) : items.length === 0 ? (
        <div className="card text-center text-text-secondary py-12">
          <p className="text-lg mb-2">No stocks in watchlist</p>
          <p className="text-sm">Add tickers above or from the stock detail page</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.ticker} className="card flex items-center justify-between">
              <Link href={`/stock/${item.ticker}`} className="flex-1 hover:text-accent transition-colors">
                <div className="font-medium">{item.name || item.ticker}</div>
                <div className="text-xs text-text-secondary">{item.ticker} · {item.country_code}</div>
              </Link>
              <div className="text-right mr-4">
                <div className="font-mono">{formatPrice(item.current_price, item.ticker)}</div>
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
