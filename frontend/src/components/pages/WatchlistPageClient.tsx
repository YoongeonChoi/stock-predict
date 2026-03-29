"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import AuthGateCard from "@/components/AuthGateCard";
import { useAuth } from "@/components/AuthProvider";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import TickerResolutionHint from "@/components/TickerResolutionHint";
import { useToast } from "@/components/Toast";
import { api, isAuthRequiredError } from "@/lib/api";
import type { TickerResolution } from "@/lib/api";
import type { OpportunityRadarResponse, WatchlistItem } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

interface WatchlistPageClientProps {
  demoData?: OpportunityRadarResponse | null;
}

export default function WatchlistPageClient({ demoData = null }: WatchlistPageClientProps) {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [ticker, setTicker] = useState("");
  const [resolution, setResolution] = useState<TickerResolution | null>(null);
  const { toast } = useToast();
  const { session, loading: authLoading } = useAuth();

  const load = async () => {
    if (!session) {
      setItems([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setItems(await api.getWatchlist());
    } catch (error) {
      console.error(error);
      if (!isAuthRequiredError(error)) {
        toast("관심종목을 불러오지 못했습니다.", "error");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (authLoading) {
      return;
    }
    load();
  }, [authLoading, session]);

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
    try {
      await api.removeWatchlist(value);
      toast(`${value} 종목을 워치리스트에서 제거했습니다.`, "success");
      load();
    } catch {
      toast("워치리스트 삭제에 실패했습니다.", "error");
    }
  };

  if (!session) {
    return (
      <AuthGateCard
        title="관심종목은 로그인 후 사용합니다"
        description="워치리스트는 계정별로 분리 저장됩니다. 로그인하면 내가 저장한 종목만 따로 추적할 수 있습니다."
        nextPath="/watchlist"
        previewTitle="공개 레이더 기반 미리보기"
        preview={
          <div className="space-y-4">
            {demoData ? <PublicAuditStrip meta={demoData} /> : null}
            <div className="grid gap-3">
              {(demoData?.opportunities || []).slice(0, 4).map((item) => (
                <div key={item.ticker} className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="font-medium text-text">{item.name}</div>
                      <div className="mt-1 text-xs text-text-secondary">
                        {item.ticker} · {item.sector} · 레이더 미리보기
                      </div>
                      <div className="mt-2 text-sm leading-6 text-text-secondary">
                        공개 레이더 상위 후보를 먼저 고정해 두고, 로그인 후에는 저장과 추적을 계정별로 이어갑니다.
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-text">{formatPrice(item.current_price, item.country_code)}</div>
                      <div className={`mt-1 text-sm ${changeColor(item.change_pct ?? 0)}`}>{formatPct(item.change_pct)}</div>
                      <div className="mt-2 text-xs text-text-secondary">레이더 점수 {item.opportunity_score?.toFixed(1) ?? "대기"}</div>
                    </div>
                  </div>
                </div>
              ))}
              <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-4 text-sm leading-6 text-text-secondary">
                로그인하면 이 후보를 바로 저장하고, 내 관심종목만 따로 추적하며, 종목별 점수와 가격 변화를 계정별로 이어서 볼 수 있습니다.
              </div>
            </div>
          </div>
        }
      />
    );
  }

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
