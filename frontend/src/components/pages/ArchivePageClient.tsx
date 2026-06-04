"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import PageHeader from "@/components/PageHeader";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { api } from "@/lib/api";
import { buildPublicAuditSummary } from "@/lib/public-audit";
import type {
  ResearchArchiveEntry,
  ResearchArchiveStatus,
  ResearchRegionCode,
} from "@/lib/api";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "알 수 없는 오류가 발생했습니다.");
}

const REGION_LABELS: Record<ResearchRegionCode, string> = {
  KR: "한국",
  US: "미국",
  EU: "유로존",
  JP: "일본",
};

type ResearchRegionFilter = ResearchRegionCode | "ALL";

const RESEARCH_REGION_LABELS: Record<ResearchRegionFilter, string> = {
  ALL: "전체",
  ...REGION_LABELS,
};

const RESEARCH_REGIONS: ResearchRegionFilter[] = ["ALL", "KR", "US", "EU", "JP"];

interface ArchivePageClientProps {
  initialResearchReports?: ResearchArchiveEntry[];
  initialResearchStatus?: ResearchArchiveStatus | null;
}

export default function ArchivePageClient({
  initialResearchReports = [],
  initialResearchStatus = null,
}: ArchivePageClientProps) {
  const [researchReports, setResearchReports] = useState<ResearchArchiveEntry[]>(initialResearchReports);
  const [researchStatus, setResearchStatus] = useState<ResearchArchiveStatus | null>(initialResearchStatus);
  const [researchRegion, setResearchRegion] = useState<ResearchRegionFilter>("ALL");
  const [researchLoading, setResearchLoading] = useState(initialResearchReports.length === 0 && !initialResearchStatus);
  const [refreshingResearch, setRefreshingResearch] = useState(false);
  const [researchError, setResearchError] = useState<Error | null>(null);
  const skippedInitialLoad = useRef(false);

  useEffect(() => {
    if (
      !skippedInitialLoad.current
      && researchRegion === "ALL"
      && (initialResearchReports.length > 0 || initialResearchStatus)
    ) {
      skippedInitialLoad.current = true;
      return;
    }
    skippedInitialLoad.current = true;
    void loadResearch(false);
  }, [initialResearchReports.length, initialResearchStatus, researchRegion]);

  async function loadResearch(forceRefresh: boolean) {
    setResearchLoading(true);
    setResearchError(null);
    try {
      if (forceRefresh) {
        await api.refreshResearchArchive();
      }
      const regionCode = researchRegion === "ALL" ? undefined : researchRegion;
      const [reports, status] = await Promise.all([
        api.getResearchArchive(regionCode, 40, !forceRefresh),
        api.getResearchArchiveStatus(true),
      ]);
      setResearchReports(reports);
      setResearchStatus(status);
    } catch (researchLoadError) {
      console.error(researchLoadError);
      setResearchError(toError(researchLoadError));
    } finally {
      setResearchLoading(false);
    }
  }

  async function handleResearchRefresh() {
    setRefreshingResearch(true);
    try {
      await loadResearch(true);
    } finally {
      setRefreshingResearch(false);
    }
  }

  const activeRegionTotal = useMemo(
    () => (
      researchRegion === "ALL"
        ? (researchStatus?.total_reports ?? researchReports.length)
        : (researchStatus?.regions.find((item) => item.region_code === researchRegion)?.total ?? researchReports.length)
    ),
    [researchReports.length, researchRegion, researchStatus],
  );

  const regionCounts = useMemo(() => {
    const counts: Partial<Record<ResearchRegionFilter, number>> = {
      ALL: researchStatus?.total_reports ?? researchReports.length,
    };
    for (const item of researchStatus?.regions ?? []) {
      counts[item.region_code] = item.total;
    }
    return counts;
  }, [researchReports.length, researchStatus]);

  const researchAuditSummary = buildPublicAuditSummary(
    researchStatus
      ? {
          generated_at: researchStatus.refreshed_at,
          partial: false,
          fallback_reason: refreshingResearch ? "research_sync_pending" : null,
        }
      : null,
    {
      staleLabel: researchStatus?.refreshed_at ? "공식 기관 원문 기준" : null,
      defaultSummary: "공식 기관 리포트와 정책·시장 분석 원문을 지역별로 정리합니다.",
    },
  );
  const summaryFallback = "요약이 제공되지 않는 원문입니다. 제목과 출처를 확인한 뒤 원문으로 이동할 수 있습니다.";

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="리서치"
        title="리서치 아카이브"
        description="공식 기관 리포트와 정책·시장 분석 원문을 지역별로 정리합니다. 필요한 자료는 PDF 또는 원문 링크로 바로 열 수 있습니다."
        meta={
          <>
            <span className="info-chip">공식 기관 원문</span>
            <span className="info-chip">{RESEARCH_REGION_LABELS[researchRegion]} 보기</span>
            {researchStatus ? <span className="info-chip">활성 소스 {researchStatus.source_count}개</span> : null}
          </>
        }
      />

      <section className="card !p-5 space-y-5">
        <div className="section-heading gap-4">
          <div className="min-w-0">
            <h2 className="section-title">리서치 아카이브</h2>
            <p className="section-copy">{researchAuditSummary}</p>
          </div>
          <div className="flex w-full flex-col gap-3 lg:w-auto lg:items-end">
            <PublicAuditStrip
              meta={
                researchStatus
                  ? {
                      generated_at: researchStatus.refreshed_at,
                      partial: false,
                      fallback_reason: refreshingResearch ? "research_sync_pending" : null,
                    }
                  : null
              }
              staleLabel="공식 기관 원문 기준"
            />
            <button
              onClick={handleResearchRefresh}
              disabled={refreshingResearch}
              className="ui-button-secondary w-full px-4 sm:w-auto"
            >
              {refreshingResearch ? "새로고침 중" : "새로고침"}
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-border/70 bg-surface/45 p-3 sm:p-4">
          <div className="mb-3 text-sm font-semibold text-text">지역</div>
          <div className="grid gap-2 sm:grid-cols-5">
            {RESEARCH_REGIONS.map((region) => (
              <button
                key={region}
                onClick={() => setResearchRegion(region)}
                aria-pressed={researchRegion === region}
                className={[
                  "min-h-[48px] rounded-xl border px-3 py-2 text-left text-sm transition-colors",
                  researchRegion === region
                    ? "border-accent bg-white text-accent shadow-sm"
                    : "border-border/70 bg-white text-text-secondary hover:border-accent/40 hover:text-text",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <span className="block font-semibold">{RESEARCH_REGION_LABELS[region]}</span>
                <span className="mt-1 block text-xs text-text-secondary">
                  {typeof regionCounts[region] === "number" ? `${regionCounts[region]}건` : "집계 대기"}
                </span>
              </button>
            ))}
          </div>
        </div>

        {researchStatus ? (
          <div className="grid gap-3 md:grid-cols-3">
            <div className="metric-card">
              <div className="text-xs text-text-secondary">현재 선택</div>
              <div className="mt-2 text-2xl font-semibold text-text">{activeRegionTotal}</div>
              <div className="mt-1 text-xs text-text-secondary">{RESEARCH_REGION_LABELS[researchRegion]} 리포트</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">활성 소스</div>
              <div className="mt-2 text-2xl font-semibold text-text">{researchStatus.source_count}</div>
              <div className="mt-1 text-xs text-text-secondary">공식 기관 기준</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">최근 동기화</div>
              <div className="mt-2 text-sm font-semibold text-text">
                {researchStatus.refreshed_at ? new Date(researchStatus.refreshed_at).toLocaleString("ko-KR") : "아직 없음"}
              </div>
              <div className="mt-1 text-xs text-text-secondary">하루 1회 기본 동기화</div>
            </div>
          </div>
        ) : null}

        {researchError ? (
          <WorkspaceStateCard
            eyebrow="기관 리포트 지연"
            title="리서치 아카이브를 다시 불러오지 못했습니다"
            message={researchError.message}
            tone="warning"
            actionLabel="다시 불러오기"
            onAction={() => void loadResearch(false)}
          />
        ) : null}

        {researchLoading ? (
          <div className="space-y-3">
            <WorkspaceLoadingCard
              title={`${RESEARCH_REGION_LABELS[researchRegion]} 리서치를 정리하고 있습니다`}
              message="출처, 발행일, PDF 여부와 원문 링크를 확인하고 있습니다."
              className="min-h-[160px]"
            />
            <WorkspaceLoadingCard
              title="목록을 준비하고 있습니다"
              message="같은 기관의 중복 항목을 줄이고 최신 발행일 순서로 배치합니다."
              className="min-h-[140px]"
            />
          </div>
        ) : researchReports.length === 0 ? (
          <WorkspaceStateCard
            eyebrow="리포트 대기"
            title={`${RESEARCH_REGION_LABELS[researchRegion]} 리서치가 아직 없습니다`}
            message="잠시 후 새로고침하거나 다른 지역을 확인해 주세요."
          />
        ) : (
          <div className="space-y-3">
            {researchReports.map((report) => (
              <article key={report.id} className="rounded-[22px] border border-border/70 bg-white px-5 py-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">{report.source_name}</span>
                      <span className="rounded-full bg-border/40 px-2 py-0.5 text-xs text-text-secondary">
                        {REGION_LABELS[report.region_code]}
                      </span>
                      <span className="text-xs text-text-secondary">{report.organization_type}</span>
                      {report.is_new_today ? <span className="rounded-full bg-positive/10 px-2 py-0.5 text-xs text-positive">오늘 반영</span> : null}
                      <span className="text-xs text-text-secondary lg:ml-auto">
                        {new Date(report.published_at).toLocaleDateString("ko-KR")}
                      </span>
                    </div>
                    <h3 className="mt-3 text-base font-semibold leading-7 text-text">{report.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-text-secondary">
                      {report.summary_plain || report.summary || summaryFallback}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-text-secondary">
                      {report.category ? <span>{report.category}</span> : null}
                      <span>{report.language === "ko" ? "한국어" : "영어"}</span>
                    </div>
                  </div>
                  <div className="flex w-full shrink-0 flex-col gap-2 sm:w-auto sm:flex-row lg:justify-end">
                    {report.has_pdf && report.pdf_url ? (
                      <a
                        href={report.pdf_url}
                        target="_blank"
                        rel="noreferrer"
                        className="ui-button-primary justify-center px-4"
                      >
                        PDF 열기
                      </a>
                    ) : null}
                    <a
                      href={report.report_url}
                      target="_blank"
                      rel="noreferrer"
                      className="ui-button-secondary justify-center px-4"
                    >
                      원문 보기
                    </a>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
