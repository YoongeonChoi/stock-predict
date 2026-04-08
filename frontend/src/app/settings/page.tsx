"use client";

import AccountSettingsPanel from "@/components/settings/AccountSettingsPanel";
import MarketSessionPanel from "@/components/MarketSessionPanel";
import PageHeader from "@/components/PageHeader";
import SystemStatusCard from "@/components/SystemStatusCard";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { useSettingsPageLoader } from "@/app/settings/useSettingsPageLoader";
import { apiPath } from "@/lib/api";
import { FRONTEND_APP_VERSION } from "@/lib/app-meta";

const REGION_LABELS: Record<string, string> = {
  KR: "한국",
  US: "미국",
  EU: "유로존",
  JP: "일본",
};

const SETTINGS_TIMEOUT_MS = 15_000;

export default function SettingsPage() {
  const {
    diagnostics,
    marketSessions,
    researchStatus,
    loading,
    refreshing,
    diagnosticsError,
    marketSessionsError,
    researchError,
    load,
    refreshResearchArchive,
  } = useSettingsPageLoader({ timeoutMs: SETTINGS_TIMEOUT_MS });

  const delayedSections = [
    diagnosticsError ? "시스템 진단" : null,
    marketSessionsError ? "시장 세션" : null,
    researchError ? "기관 리서치 상태" : null,
  ].filter(Boolean) as string[];

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="운영"
        title="설정 및 시스템"
        description="계정 보안, 시장 세션, 시스템 상태, 기관 리서치 동기화를 한 곳에서 확인합니다."
        meta={
          <>
            <span className="info-chip">프론트 v{FRONTEND_APP_VERSION}</span>
            {diagnostics?.version ? <span className="info-chip">백엔드 v{diagnostics.version}</span> : null}
            {refreshing ? <span className="info-chip">리서치 상태 갱신 중</span> : null}
          </>
        }
      />

      {delayedSections.length > 0 ? (
        <WorkspaceStateCard
          eyebrow="부분 업데이트"
          title="일부 운영 패널이 잠시 지연되고 있습니다"
          message={`${delayedSections.join(", ")} 패널은 늦어지고 있지만, 확인 가능한 정보부터 먼저 보여주고 있습니다.`}
          tone="warning"
          actionLabel="시스템 패널 다시 불러오기"
          onAction={load}
        />
      ) : null}

      <AccountSettingsPanel />

      {loading ? (
        <div className="space-y-4">
          <WorkspaceLoadingCard
            title="시장 세션과 시스템 상태를 불러오고 있습니다"
            message="현재 운영 상태와 버전 비교 정보를 먼저 정리하는 중입니다."
            className="min-h-[180px]"
          />
          <WorkspaceLoadingCard
            title="기관 리서치 동기화 상태를 확인하고 있습니다"
            message="지역별 누적 수와 소스별 반영 상태를 다시 집계하는 중입니다."
            className="min-h-[220px]"
          />
        </div>
      ) : (
        <>
          {marketSessions ? (
            <MarketSessionPanel sessions={marketSessions.sessions} />
          ) : (
            <WorkspaceStateCard
              eyebrow="시장 세션 지연"
              title="시장 세션 요약을 아직 불러오지 못했습니다"
              message={marketSessionsError || "시장 세션 요약을 아직 불러오지 못했습니다."}
              tone="warning"
              actionLabel="세션 다시 불러오기"
              onAction={load}
            />
          )}

          {diagnostics ? (
            <SystemStatusCard diagnostics={diagnostics} frontendVersion={FRONTEND_APP_VERSION} />
          ) : (
            <WorkspaceStateCard
              eyebrow="시스템 진단 지연"
              title="시스템 상태 카드를 아직 불러오지 못했습니다"
              message={diagnosticsError || "시스템 진단 정보를 아직 불러오지 못했습니다."}
              tone="warning"
              actionLabel="진단 다시 불러오기"
              onAction={load}
            />
          )}

          <section className="card !p-5 space-y-5">
            <div className="section-heading">
              <div>
                <h2 className="section-title">공식 기관 리서치 아카이브</h2>
                <p className="section-copy">KDI, 한국은행, Federal Reserve, ECB, BOJ 공식 리포트를 하루 한 번 동기화합니다.</p>
              </div>
              <button
                onClick={refreshResearchArchive}
                disabled={refreshing}
                className="ui-button-primary px-4"
              >
                {refreshing ? "새로고침 중..." : "리서치 즉시 새로고침"}
              </button>
            </div>

            {researchStatus ? (
              <>
                <div className="grid gap-3 md:grid-cols-4">
                  <div className="metric-card">
                    <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-secondary">누적 리포트</div>
                    <div className="mt-2 font-mono text-[1.4rem] font-semibold text-text">{researchStatus.total_reports}</div>
                  </div>
                  <div className="metric-card">
                    <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-secondary">오늘 반영</div>
                    <div className="mt-2 font-mono text-[1.4rem] font-semibold text-text">{researchStatus.todays_reports}</div>
                  </div>
                  <div className="metric-card">
                    <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-secondary">활성 소스</div>
                    <div className="mt-2 font-mono text-[1.4rem] font-semibold text-text">{researchStatus.source_count}</div>
                  </div>
                  <div className="metric-card">
                    <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-secondary">최근 동기화</div>
                    <div className="mt-2 text-sm font-semibold text-text">
                      {researchStatus.refreshed_at ? new Date(researchStatus.refreshed_at).toLocaleString("ko-KR") : "아직 없음"}
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                  <div className="section-slab-subtle space-y-3">
                    <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-secondary">지역 분포</div>
                    <div className="space-y-2 text-sm">
                      {researchStatus.regions.map((region) => (
                        <div key={region.region_code} className="flex justify-between gap-3">
                          <span>{REGION_LABELS[region.region_code] || region.region_code}</span>
                          <span className="font-mono font-semibold text-text">{region.total}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="section-slab-subtle space-y-3">
                    <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-secondary">소스별 누적 수</div>
                    <div className="space-y-2 text-sm">
                      {researchStatus.sources.slice(0, 8).map((source) => (
                        <div key={source.source_id} className="flex justify-between gap-3">
                          <span>{source.source_name}</span>
                          <span className="font-mono font-semibold text-text">{source.total}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {researchStatus.errors.length > 0 ? (
                  <section className="ui-panel-warning !p-4">
                    <div className="font-semibold text-text">동기화 중 일부 소스 경고</div>
                    <div className="mt-2 space-y-1 text-sm text-text-secondary">
                      {researchStatus.errors.map((source) => (
                        <div key={source.source_id}>
                          {source.source_name}: {source.detail}
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}
              </>
            ) : (
              <WorkspaceStateCard
                eyebrow="리서치 상태 지연"
                title="기관 리서치 동기화 상태를 아직 불러오지 못했습니다"
                message={researchError || "기관 리서치 상태를 아직 불러오지 못했습니다."}
                tone="warning"
                actionLabel="리서치 상태 다시 불러오기"
                onAction={load}
              />
            )}
          </section>

          <section className="card !p-5 space-y-4">
            <div className="section-heading">
              <div>
                <h2 className="section-title">기본 동작 정책</h2>
                <p className="section-copy">앱이 어떤 기준으로 시작하고, 어떤 링크와 경로를 쓰는지 운영 기준을 정리합니다.</p>
              </div>
            </div>
            <div className="grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
              <div className="metric-card">
                <div className="font-semibold text-text">홈 화면 시작 시장</div>
                <div className="mt-2 leading-7 text-text-secondary">기본값은 한국(KR)이며 대시보드도 한국 시장 상태부터 불러옵니다.</div>
              </div>
              <div className="metric-card">
                <div className="font-semibold text-text">기관 리포트 보관 방식</div>
                <div className="mt-2 leading-7 text-text-secondary">PDF가 있으면 PDF를 우선 연결하고, 없으면 공식 원문 링크로 이동합니다.</div>
              </div>
              <div className="metric-card">
                <div className="font-semibold text-text">프론트 API 경로</div>
                <div className="mt-2 break-all font-mono text-[12px] leading-6 text-text-secondary">{apiPath("/api/health")}</div>
              </div>
              <div className="metric-card">
                <div className="font-semibold text-text">현재 프론트 버전</div>
                <div className="mt-2 font-mono text-[0.95rem] text-text-secondary">v{FRONTEND_APP_VERSION}</div>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
