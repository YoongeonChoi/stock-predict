"use client";

import { useEffect, useState } from "react";

import AccountSettingsPanel from "@/components/settings/AccountSettingsPanel";
import ErrorBanner from "@/components/ErrorBanner";
import MarketSessionPanel from "@/components/MarketSessionPanel";
import SystemStatusCard from "@/components/SystemStatusCard";
import { api, apiPath } from "@/lib/api";
import type { MarketSessionsResponse, ResearchArchiveStatus, SystemDiagnostics } from "@/lib/api";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "설정 정보를 불러오는 중 오류가 발생했습니다.");
}

const REGION_LABELS: Record<string, string> = {
  KR: "한국",
};

export default function SettingsPage() {
  const [diagnostics, setDiagnostics] = useState<SystemDiagnostics | null>(null);
  const [marketSessions, setMarketSessions] = useState<MarketSessionsResponse | null>(null);
  const [researchStatus, setResearchStatus] = useState<ResearchArchiveStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [diag, sessions, research] = await Promise.all([
        api.getDiagnostics(),
        api.getMarketSessions(),
        api.getResearchArchiveStatus(true),
      ]);
      setDiagnostics(diag);
      setMarketSessions(sessions);
      setResearchStatus(research);
    } catch (err) {
      console.error(err);
      setError(toError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const refreshResearchArchive = async () => {
    setRefreshing(true);
    try {
      await api.refreshResearchArchive();
      const [diag, sessions, research] = await Promise.all([
        api.getDiagnostics(),
        api.getMarketSessions(),
        api.getResearchArchiveStatus(true),
      ]);
      setDiagnostics(diag);
      setMarketSessions(sessions);
      setResearchStatus(research);
    } catch (err) {
      console.error(err);
      setError(toError(err));
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">설정 및 시스템</h1>
        <p className="mt-1 text-text-secondary">시장 세션, 시스템 상태, 공식 기관 리서치 동기화를 한 곳에서 확인합니다.</p>
      </div>

      <AccountSettingsPanel />

      {error ? <ErrorBanner error={error} onRetry={load} /> : null}

      {loading ? (
        <div className="space-y-4 animate-pulse">
          <div className="card h-56" />
          <div className="card h-80" />
          <div className="card h-44" />
        </div>
      ) : (
        <>
          {marketSessions ? <MarketSessionPanel sessions={marketSessions.sessions} /> : null}
          {diagnostics ? <SystemStatusCard diagnostics={diagnostics} /> : null}

          <div className="card !p-4 space-y-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold">공식 기관 리서치 아카이브</h2>
                <p className="mt-1 text-sm text-text-secondary">KDI와 한국은행에서 공개한 리포트를 하루 한 번 동기화합니다.</p>
              </div>
              <button
                onClick={refreshResearchArchive}
                disabled={refreshing}
                className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {refreshing ? "새로고침 중..." : "리서치 즉시 새로고침"}
              </button>
            </div>

            {researchStatus ? (
              <>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <div className="rounded-xl border border-border p-3">
                    <div className="text-xs text-text-secondary">누적 리포트</div>
                    <div className="mt-1 text-xl font-bold">{researchStatus.total_reports}</div>
                  </div>
                  <div className="rounded-xl border border-border p-3">
                    <div className="text-xs text-text-secondary">오늘 반영</div>
                    <div className="mt-1 text-xl font-bold">{researchStatus.todays_reports}</div>
                  </div>
                  <div className="rounded-xl border border-border p-3">
                    <div className="text-xs text-text-secondary">활성 소스</div>
                    <div className="mt-1 text-xl font-bold">{researchStatus.source_count}</div>
                  </div>
                  <div className="rounded-xl border border-border p-3">
                    <div className="text-xs text-text-secondary">최근 동기화</div>
                    <div className="mt-1 text-sm font-semibold">
                      {researchStatus.refreshed_at ? new Date(researchStatus.refreshed_at).toLocaleString("ko-KR") : "아직 없음"}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                  <div className="rounded-xl border border-border p-3">
                    <div className="mb-2 text-xs font-medium text-text-secondary">지역 분포</div>
                    <div className="space-y-2 text-sm">
                      {researchStatus.regions.map((region) => (
                        <div key={region.region_code} className="flex justify-between gap-3">
                          <span>{REGION_LABELS[region.region_code] || region.region_code}</span>
                          <span className="font-semibold">{region.total}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-xl border border-border p-3">
                    <div className="mb-2 text-xs font-medium text-text-secondary">소스별 누적 수</div>
                    <div className="space-y-2 text-sm">
                      {researchStatus.sources.slice(0, 8).map((source) => (
                        <div key={source.source_id} className="flex justify-between gap-3">
                          <span>{source.source_name}</span>
                          <span className="font-semibold">{source.total}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {researchStatus.errors.length > 0 ? (
                  <div className="rounded-xl border border-warning/30 bg-warning/10 p-3">
                    <div className="text-sm font-medium">동기화 중 일부 소스 경고</div>
                    <div className="mt-2 space-y-1 text-xs text-text-secondary">
                      {researchStatus.errors.map((source) => (
                        <div key={source.source_id}>
                          {source.source_name}: {source.detail}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}
          </div>

          <div className="card !p-4 space-y-3">
            <h2 className="text-lg font-semibold">기본 동작 정책</h2>
            <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
              <div className="rounded-xl border border-border p-3">
                <div className="font-medium">홈 화면 시작 시장</div>
                <div className="mt-1 text-text-secondary">기본값은 한국(KR)이며 대시보드도 한국 시장 상태부터 불러옵니다.</div>
              </div>
              <div className="rounded-xl border border-border p-3">
                <div className="font-medium">기관 리포트 보관 방식</div>
                <div className="mt-1 text-text-secondary">PDF가 있으면 PDF를 우선 연결하고, 없으면 공식 원문 링크로 이동합니다.</div>
              </div>
              <div className="rounded-xl border border-border p-3">
                <div className="font-medium">프론트 API 경로</div>
                <div className="mt-1 break-all text-text-secondary">{apiPath("/api/health")}</div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
