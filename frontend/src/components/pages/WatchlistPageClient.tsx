"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import AuthGateCard from "@/components/AuthGateCard";
import { useAuth } from "@/components/AuthProvider";
import PageHeader from "@/components/PageHeader";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import TickerResolutionHint from "@/components/TickerResolutionHint";
import { useToast } from "@/components/Toast";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { api, isAuthRequiredError } from "@/lib/api";
import type { TickerResolution } from "@/lib/api";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import type { OpportunityRadarResponse, WatchlistItem } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

interface WatchlistPageClientProps {
  demoData?: OpportunityRadarResponse | null;
}

export default function WatchlistPageClient({ demoData = null }: WatchlistPageClientProps) {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [ticker, setTicker] = useState("");
  const [resolution, setResolution] = useState<TickerResolution | null>(null);
  const { toast } = useToast();
  const { session, loading: authLoading } = useAuth();

  const load = async (showFailureToast = false) => {
    if (!session) {
      setItems([]);
      setLoadError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setItems(await api.getWatchlist());
      setLoadError(null);
    } catch (error) {
      console.error(error);
      if (!isAuthRequiredError(error)) {
        const message = getUserFacingErrorMessage(error, "관심종목을 불러오지 못했습니다.");
        setLoadError(message);
        if (showFailureToast) {
          toast(message, "error");
        }
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
      void load(true);
    } catch {
      toast("워치리스트 추가에 실패했습니다.", "error");
    }
  };

  const remove = async (value: string) => {
    try {
      await api.removeWatchlist(value);
      toast(`${value} 종목을 워치리스트에서 제거했습니다.`, "success");
      void load(true);
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
    <div className="page-shell">
      <PageHeader
        eyebrow="Watchlist"
        title="관심종목"
        description="추적할 종목을 먼저 저장해 두고, 가격 변화와 점수를 같은 화면에서 빠르게 확인합니다."
        meta={
          <>
            <span className="info-chip">저장 {items.length}개</span>
            <span className="info-chip">KR 기준 입력</span>
          </>
        }
      />

      <section className="workspace-grid-balanced">
        <div className="card !p-5 space-y-4">
          <div>
            <h2 className="section-title">관심종목 추가</h2>
            <p className="section-copy">숫자 6자리나 표준 티커를 입력하면 저장 전에 해석 결과를 먼저 보여줍니다.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_92px_auto]">
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && add()}
              placeholder="티커 입력 예: 005930"
              className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm focus:outline-none focus:border-accent"
            />
            <div className="flex items-center justify-center rounded-2xl border border-border bg-surface/60 px-3 py-3 text-sm text-text-secondary">KR</div>
            <button onClick={add} className="action-chip-primary w-full justify-center">추가</button>
          </div>
          <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-3">
            <TickerResolutionHint resolution={resolution} />
          </div>
        </div>

        <div className="card !p-5 space-y-3 h-fit">
          <div>
            <h2 className="section-title">현재 상태</h2>
            <p className="section-copy">저장된 종목 수와 이 화면의 역할을 먼저 보여줍니다.</p>
          </div>
          <div className="workspace-panel-tight">
            <div className="text-xs text-text-secondary">저장된 관심종목</div>
            <div className="mt-2 text-2xl font-semibold text-text">{items.length}</div>
            <div className="mt-2 text-sm leading-6 text-text-secondary">
              관심종목은 빠른 접근과 추적용입니다. 상세 분석과 실행 판단은 종목 상세나 레이더에서 이어서 확인합니다.
            </div>
          </div>
        </div>
      </section>

      <section className="card !p-0 overflow-hidden">
        <div className="border-b border-border px-5 py-4">
          <h2 className="section-title">저장된 관심종목</h2>
          <p className="section-copy">실시간 가격과 점수를 한 줄 흐름으로 정리합니다.</p>
        </div>

        {loading ? (
          <div className="px-5 py-5">
            <WorkspaceLoadingCard
              title="관심종목을 불러오고 있습니다"
              message="저장된 종목과 현재 가격, 점수를 같은 표 흐름으로 다시 정리하는 중입니다."
              className="min-h-[220px]"
            />
          </div>
        ) : loadError && items.length === 0 ? (
          <div className="px-5 py-5">
            <WorkspaceStateCard
              eyebrow="관심종목 지연"
              title="저장된 관심종목 목록을 아직 불러오지 못했습니다"
              message={loadError}
              tone="warning"
              className="min-h-[220px]"
              actionLabel="관심종목 다시 불러오기"
              onAction={() => {
                void load(true);
              }}
            />
          </div>
        ) : items.length === 0 ? (
          <div className="px-5 py-5">
            <WorkspaceStateCard
              eyebrow="관심종목 비어 있음"
              title="워치리스트가 아직 비어 있습니다"
              message="관심 있는 종목을 추가하면 가격 변화와 점수를 함께 추적할 수 있습니다."
              tone="neutral"
            />
          </div>
        ) : (
          <div className="space-y-2 px-5 py-5">
            {loadError ? (
              <WorkspaceStateCard
                eyebrow="부분 재동기화 지연"
                title="이전 관심종목 목록을 먼저 보여주고 있습니다"
                message={loadError}
                tone="warning"
                actionLabel="관심종목 다시 불러오기"
                onAction={() => {
                  void load(true);
                }}
                aside={<span className="info-chip">마지막 성공 목록 유지</span>}
              />
            ) : null}
            {items.map((item) => (
              <div key={item.ticker} className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <Link href={`/stock/${item.ticker}`} className="min-w-0 flex-1 hover:text-accent transition-colors">
                    <div className="font-medium">{item.name || item.ticker}</div>
                    <div className="mt-1 text-xs text-text-secondary">{item.ticker} · {item.country_code}</div>
                    {item.resolution_note ? <div className="mt-1 text-[11px] text-text-secondary">{item.resolution_note}</div> : null}
                  </Link>
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
                  <div className="flex justify-end lg:justify-start">
                    <button onClick={() => remove(item.ticker)} className="text-xs text-negative hover:underline">삭제</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
