"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import AuthGateCard from "@/components/AuthGateCard";
import { useAuth } from "@/components/AuthProvider";
import PageHeader from "@/components/PageHeader";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import TickerResolutionHint from "@/components/TickerResolutionHint";
import { useToast } from "@/components/Toast";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { useWatchlistWorkspace } from "@/components/pages/useWatchlistWorkspace";
import { api } from "@/lib/api";
import type { TickerResolution } from "@/lib/api";
import type { OpportunityRadarResponse, WatchlistItem } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

interface WatchlistPageClientProps {
  demoData?: OpportunityRadarResponse | null;
}

type WatchlistFilter = "all" | "tracked";

function opportunityScoreLabel(setupLabel?: string) {
  return setupLabel === "매수 1차 스크린" ? "1차 스크린 점수" : "레이더 점수";
}

function trackingSummary(item: WatchlistItem) {
  if (!item.tracking_enabled) {
    return "심화 추적을 시작하면 최근 예측 변화와 적중 기록을 이어서 볼 수 있습니다.";
  }

  const parts: string[] = [];
  if (item.last_outlook_label) {
    parts.push(item.last_outlook_label);
  }
  if (item.last_confidence != null) {
    parts.push(`신뢰도 ${item.last_confidence.toFixed(1)}`);
  }
  if (item.last_prediction_at) {
    parts.push(`최근 기록 ${new Date(item.last_prediction_at).toLocaleDateString("ko-KR")}`);
  }

  return parts.length > 0 ? parts.join(" · ") : "심화 추적이 활성화되어 있습니다.";
}

export default function WatchlistPageClient({ demoData = null }: WatchlistPageClientProps) {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [ticker, setTicker] = useState("");
  const [resolution, setResolution] = useState<TickerResolution | null>(null);
  const [filter, setFilter] = useState<WatchlistFilter>("all");
  const [pendingTicker, setPendingTicker] = useState<string | null>(null);
  const { toast } = useToast();
  const { session, loading: authLoading } = useAuth();
  const { load } = useWatchlistWorkspace({
    hasSession: Boolean(session),
    authLoading,
    items,
    loading,
    loadError,
    setItems,
    setLoading,
    setLoadError,
    toast,
  });

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

  const sortedItems = useMemo(() => {
    return [...items].sort((left, right) => {
      const trackingDelta = Number(right.tracking_enabled) - Number(left.tracking_enabled);
      if (trackingDelta !== 0) {
        return trackingDelta;
      }

      const leftPrediction = left.last_prediction_at ? Date.parse(left.last_prediction_at) : 0;
      const rightPrediction = right.last_prediction_at ? Date.parse(right.last_prediction_at) : 0;
      if (rightPrediction !== leftPrediction) {
        return rightPrediction - leftPrediction;
      }

      return (right.score_total ?? -Infinity) - (left.score_total ?? -Infinity);
    });
  }, [items]);

  const visibleItems = useMemo(() => {
    if (filter === "tracked") {
      return sortedItems.filter((item) => item.tracking_enabled);
    }
    return sortedItems;
  }, [filter, sortedItems]);

  const trackedCount = useMemo(
    () => items.filter((item) => item.tracking_enabled).length,
    [items],
  );

  const add = async () => {
    const rawTicker = ticker.trim().toUpperCase();
    if (!rawTicker) {
      return;
    }

    try {
      const saved = await api.addWatchlist(rawTicker, "KR");
      toast(`${saved.ticker} 종목을 관심종목에 추가했습니다.`, "success");
      setTicker("");
      setResolution(null);
      await load(true);
    } catch (error) {
      console.error(error);
      toast("관심종목 추가에 실패했습니다.", "error");
    }
  };

  const remove = async (value: string) => {
    try {
      setPendingTicker(value);
      await api.removeWatchlist(value);
      toast(`${value} 종목을 관심종목에서 제거했습니다.`, "success");
      await load(true);
    } catch (error) {
      console.error(error);
      toast("관심종목 제거에 실패했습니다.", "error");
    } finally {
      setPendingTicker(null);
    }
  };

  const toggleTracking = async (item: WatchlistItem) => {
    try {
      setPendingTicker(item.ticker);
      if (item.tracking_enabled) {
        await api.disableWatchlistTracking(item.ticker, item.country_code);
        toast(`${item.ticker} 심화 추적을 중지했습니다.`, "success");
      } else {
        await api.enableWatchlistTracking(item.ticker, item.country_code);
        toast(`${item.ticker} 심화 추적을 시작했습니다.`, "success");
      }
      await load(true);
    } catch (error) {
      console.error(error);
      toast(
        item.tracking_enabled
          ? "심화 추적 중지에 실패했습니다."
          : "심화 추적 시작에 실패했습니다.",
        "error",
      );
    } finally {
      setPendingTicker(null);
    }
  };

  if (!session) {
    return (
      <AuthGateCard
        title="관심종목은 로그인 후 사용할 수 있습니다"
        description="관심종목과 심화 추적은 계정별로 분리되어 저장됩니다. 로그인하면 내가 고른 종목만 따로 추적하고 최근 예측 변화를 이어서 볼 수 있습니다."
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
                        공개 레이더 상위 후보를 먼저 보여드리고, 로그인 후에는 심화 추적 화면에서 최근 예측 변화와 적중 기록을 이어서 확인할 수 있습니다.
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-text">{formatPrice(item.current_price, item.country_code)}</div>
                      <div className={`mt-1 text-sm ${changeColor(item.change_pct ?? 0)}`}>{formatPct(item.change_pct)}</div>
                      <div className="mt-2 text-xs text-text-secondary">
                        {opportunityScoreLabel(item.setup_label)} {item.opportunity_score?.toFixed(1) ?? "대기"}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-4 text-sm leading-6 text-text-secondary">
                로그인하면 관심종목을 따로 저장하고, 추적 중인 종목만 모아서 예측 변화와 현재 판단 근거를 이어서 볼 수 있습니다.
              </div>
            </div>
          </div>
        }
      />
    );
  }

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="Watchlist"
        title="관심종목"
        description="추적할 종목을 먼저 저장해 두고, 필요한 종목은 심화 추적으로 올려 최근 예측 변화와 적중 기록까지 이어서 확인합니다."
        meta={
          <>
            <span className="info-chip">전체 {items.length}개</span>
            <span className="info-chip">심화 추적 {trackedCount}개</span>
            <span className="info-chip">KR 기준 입력</span>
          </>
        }
      />

      <section className="workspace-grid-balanced">
        <div className="card !p-5 space-y-4">
          <div>
            <h2 className="section-title">관심종목 추가</h2>
            <p className="section-copy">숫자 6자리 또는 티커를 입력하면 먼저 해석 결과를 보여드리고, 저장 후 심화 추적 화면으로 이어집니다.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_92px_auto]">
            <input
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && void add()}
              placeholder="티커 입력 · 예: 005930"
              className="ui-input w-full"
            />
            <div className="flex items-center justify-center rounded-2xl border border-border bg-surface/60 px-3 py-3 text-sm text-text-secondary">
              KR
            </div>
            <button onClick={() => void add()} className="action-chip-primary w-full justify-center">
              추가
            </button>
          </div>
          <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-3">
            <TickerResolutionHint resolution={resolution} />
          </div>
        </div>

        <div className="card !p-5 space-y-3 h-fit">
          <div>
            <h2 className="section-title">현재 상태</h2>
            <p className="section-copy">심화 추적을 켠 종목은 목록 상단으로 올리고, 최근 예측 기록이 있으면 요약까지 함께 보여드립니다.</p>
          </div>
          <div className="workspace-panel-tight">
            <div className="text-xs text-text-secondary">저장된 관심종목</div>
            <div className="mt-2 text-2xl font-semibold text-text">{items.length}</div>
            <div className="mt-2 text-sm leading-6 text-text-secondary">
              심화 추적을 켠 종목은 별도 화면에서 최근 방향 변화, 신뢰도, 적중 기록을 이어서 볼 수 있습니다.
            </div>
          </div>
        </div>
      </section>

      <section className="card !p-0 overflow-hidden">
        <div className="border-b border-border px-5 py-4 space-y-3">
          <div>
            <h2 className="section-title">저장한 관심종목</h2>
            <p className="section-copy">심화 추적 종목을 먼저 보여주고, 상세 보기에서 최근 예측 변화와 현재 판단 근거를 이어서 확인합니다.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setFilter("all")}
              className={filter === "all" ? "action-chip-primary" : "action-chip-secondary"}
            >
              전체
            </button>
            <button
              onClick={() => setFilter("tracked")}
              className={filter === "tracked" ? "action-chip-primary" : "action-chip-secondary"}
            >
              추적 중
            </button>
          </div>
        </div>

        {loading ? (
          <div className="px-5 py-5">
            <WorkspaceLoadingCard
              title="관심종목을 불러오고 있습니다"
              message="저장된 종목과 최근 추적 상태를 같은 목록으로 정리하고 있습니다."
              className="min-h-[220px]"
            />
          </div>
        ) : loadError && items.length === 0 ? (
          <div className="px-5 py-5">
            <WorkspaceStateCard
              eyebrow="관심종목 지연"
              title="관심종목 목록을 아직 불러오지 못했습니다"
              message={loadError}
              tone="warning"
              actionLabel="목록 다시 불러오기"
              onAction={() => void load(true)}
            />
          </div>
        ) : items.length === 0 ? (
          <div className="px-5 py-5">
            <WorkspaceStateCard
              eyebrow="관심종목 비어 있음"
              title="관심종목이 아직 비어 있습니다"
              message="관심 있는 종목을 추가하면 가격 변화와 현재 점수를 먼저 정리해 두고, 필요할 때 심화 추적으로 올릴 수 있습니다."
              tone="neutral"
            />
          </div>
        ) : visibleItems.length === 0 ? (
          <div className="px-5 py-5">
            <WorkspaceStateCard
              eyebrow="추적 중 없음"
              title="아직 심화 추적 중인 종목이 없습니다"
              message="목록에서 심화 추적 시작을 누르면 최근 예측 변화와 적중 기록을 이어서 볼 수 있습니다."
              tone="neutral"
            />
          </div>
        ) : (
          <div className="space-y-2 px-5 py-5">
            {loadError ? (
              <WorkspaceStateCard
                eyebrow="부분 업데이트"
                title="관심종목 목록 일부가 늦어지고 있습니다"
                message={`${loadError} 기존에 확인하던 종목은 유지한 채 다시 불러오기를 기다립니다.`}
                tone="warning"
                actionLabel="목록 다시 불러오기"
                onAction={() => void load(true)}
              />
            ) : null}

            {visibleItems.map((item) => {
              const isPending = pendingTicker === item.ticker;
              return (
                <div key={item.ticker} className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4">
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div className="min-w-0 flex-1">
                        <Link href={`/stock/${item.ticker}`} className="font-medium text-text transition-colors hover:text-accent">
                          {item.name || item.ticker}
                        </Link>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-text-secondary">
                          <span>{item.ticker}</span>
                          <span>·</span>
                          <span>{item.country_code}</span>
                          {item.tracking_enabled ? <span className="info-chip">추적 중</span> : null}
                        </div>
                        {item.resolution_note ? (
                          <div className="mt-2 text-xs leading-5 text-text-secondary">{item.resolution_note}</div>
                        ) : null}
                        <div className="mt-3 text-sm leading-6 text-text-secondary">{trackingSummary(item)}</div>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[360px]">
                        <div className="rounded-2xl border border-border/60 bg-surface/65 px-3 py-2 text-right">
                          <div className="text-[11px] text-text-secondary">현재가</div>
                          <div className="mt-1 font-mono text-text">{formatPrice(item.current_price, item.country_code)}</div>
                        </div>
                        <div className="rounded-2xl border border-border/60 bg-surface/65 px-3 py-2 text-right">
                          <div className="text-[11px] text-text-secondary">등락</div>
                          <div className={`mt-1 font-medium ${changeColor(item.change_pct ?? 0)}`}>{formatPct(item.change_pct)}</div>
                        </div>
                        <div className="rounded-2xl border border-border/60 bg-surface/65 px-3 py-2 text-right">
                          <div className="text-[11px] text-text-secondary">점수</div>
                          <div className="mt-1 font-semibold text-text">{item.score_total?.toFixed(1) ?? "없음"}</div>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={() => void toggleTracking(item)}
                        disabled={isPending}
                        className={item.tracking_enabled ? "action-chip-primary" : "action-chip-secondary"}
                      >
                        {isPending
                          ? "처리 중"
                          : item.tracking_enabled
                            ? "심화 추적 중지"
                            : "심화 추적 시작"}
                      </button>
                      <Link href={`/watchlist/${encodeURIComponent(item.ticker)}`} className="action-chip-secondary">
                        상세 보기
                      </Link>
                      <button
                        onClick={() => void remove(item.ticker)}
                        disabled={isPending}
                        className="action-chip-secondary text-negative"
                      >
                        제거
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
