"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import TickerResolutionHint from "@/components/TickerResolutionHint";
import { useToast } from "@/components/Toast";
import { api } from "@/lib/api";
import type { TickerResolution } from "@/lib/api";
import type { WatchlistItem } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [ticker, setTicker] = useState("");
  const [resolution, setResolution] = useState<TickerResolution | null>(null);
  const { toast } = useToast();

  const load = () => {
    setLoading(true);
    api.getWatchlist().then(setItems).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(load, []);

  useEffect(() => {
    const trimmed = ticker.trim();
    if (!trimmed) {
      setResolution(null);
      return;
    }

    const timer = setTimeout(() => {
      api.resolveTicker(trimmed, "KR").then(setResolution).catch(() => setResolution(null));
    }, 250);
    return () => clearTimeout(timer);
  }, [ticker]);

  const add = async () => {
    if (!ticker.trim()) return;
    try {
      const saved = await api.addWatchlist(ticker.trim().toUpperCase(), "KR");
      toast(`${saved.ticker} 종목을 워치리스트에 추가했습니다.`, "success");
      setTicker("");
      setResolution(null);
      load();
    } catch {
      toast("워치리스트 추가에 실패했습니다.", "error");
    }
  };

  const remove = async (value: string) => {
    await api.removeWatchlist(value);
    toast(`${value} 종목을 워치리스트에서 제거했습니다.`, "success");
    load();
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">워치리스트</h1>

      <div className="flex gap-2 items-center">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="티커 입력 예: 005930"
          className="flex-1 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm focus:outline-none focus:border-accent"
        />
        <div className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-secondary">KR</div>
        <button onClick={add} className="px-4 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90">추가</button>
      </div>

      <TickerResolutionHint resolution={resolution} />

      {loading ? (
        <div className="animate-pulse space-y-3">{[1, 2, 3].map((item) => <div key={item} className="h-16 bg-border rounded" />)}</div>
      ) : items.length === 0 ? (
        <div className="card text-center text-text-secondary py-12">
          <p className="text-lg mb-2">워치리스트가 아직 비어 있습니다</p>
          <p className="text-sm">관심 있는 종목을 추가하면 실시간 가격과 점수를 함께 볼 수 있습니다.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.ticker} className="card flex items-center justify-between">
              <Link href={`/stock/${item.ticker}`} className="flex-1 hover:text-accent transition-colors">
                <div className="font-medium">{item.name || item.ticker}</div>
                <div className="text-xs text-text-secondary">{item.ticker} · {item.country_code}</div>
                {item.resolution_note ? <div className="mt-1 text-[11px] text-text-secondary">{item.resolution_note}</div> : null}
              </Link>
              <div className="text-right mr-4">
                <div className="font-mono">{formatPrice(item.current_price, item.country_code)}</div>
                <div className={`text-sm ${changeColor(item.change_pct ?? 0)}`}>{formatPct(item.change_pct)}</div>
              </div>
              <div className="text-right mr-4">
                <div className="text-sm text-text-secondary">점수</div>
                <div className="font-bold">{item.score_total?.toFixed(1) ?? "없음"}</div>
              </div>
              <button onClick={() => remove(item.ticker)} className="text-xs text-negative hover:underline">삭제</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
