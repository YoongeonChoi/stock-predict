"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import ErrorBanner from "@/components/ErrorBanner";
import PageHeader from "@/components/PageHeader";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { useToast } from "@/components/Toast";
import { api } from "@/lib/api";
import { buildPublicAuditSummary } from "@/lib/public-audit";
import type {
  ArchiveEntry,
  PredictionAccuracyStats,
  ResearchArchiveEntry,
  ResearchArchiveStatus,
  ResearchRegionCode,
} from "@/lib/api";
import { downloadApiFile } from "@/lib/download";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "알 수 없는 오류가 발생했습니다.");
}

function reportTypeLabel(type: string) {
  if (type === "country") return "국가";
  if (type === "sector") return "섹터";
  return "종목";
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
  initialArchives?: ArchiveEntry[];
  initialAccuracy?: PredictionAccuracyStats | null;
  initialResearchReports?: ResearchArchiveEntry[];
  initialResearchStatus?: ResearchArchiveStatus | null;
}

export default function ArchivePageClient({
  initialArchives = [],
  initialAccuracy = null,
  initialResearchReports = [],
  initialResearchStatus = null,
}: ArchivePageClientProps) {
  const [archives, setArchives] = useState<ArchiveEntry[]>(initialArchives);
  const [accuracy, setAccuracy] = useState<PredictionAccuracyStats | null>(initialAccuracy);
  const [researchReports, setResearchReports] = useState<ResearchArchiveEntry[]>(initialResearchReports);
  const [researchStatus, setResearchStatus] = useState<ResearchArchiveStatus | null>(initialResearchStatus);
  const [researchRegion, setResearchRegion] = useState<ResearchRegionFilter>("ALL");
  const [loading, setLoading] = useState(initialArchives.length === 0);
  const [researchLoading, setResearchLoading] = useState(initialResearchReports.length === 0 && !initialResearchStatus);
  const [refreshingResearch, setRefreshingResearch] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [researchError, setResearchError] = useState<Error | null>(null);
  const router = useRouter();
  const { toast } = useToast();

  useEffect(() => {
    if (initialArchives.length > 0 || initialAccuracy) {
      setLoading(false);
      return;
    }
    api.getArchive()
      .then(setArchives)
      .catch((e) => {
        console.error(e);
        setError(toError(e));
      })
      .finally(() => setLoading(false));

    api.getPredictionAccuracy().then(setAccuracy).catch(console.error);
  }, [initialAccuracy, initialArchives.length]);

  useEffect(() => {
    void loadResearch(false);
  }, [researchRegion]);

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

  async function handleDownload(reportId: number, format: "pdf" | "csv") {
    try {
      await downloadApiFile(`/api/export/${format}/${reportId}`, `report_${reportId}.${format}`);
      toast(`${format.toUpperCase()} 다운로드를 시작했습니다.`, "success");
    } catch (downloadError) {
      console.error(downloadError);
      toast("직접 다운로드가 어려워 내보내기 페이지로 이동합니다.", "info");
      router.push(`/archive/export/${reportId}?format=${format}`);
    }
  }

  async function handleResearchRefresh() {
    setRefreshingResearch(true);
    await loadResearch(true);
    setRefreshingResearch(false);
  }

  const activeRegionTotal = useMemo(
    () => (
      researchRegion === "ALL"
        ? (researchStatus?.total_reports ?? researchReports.length)
        : (researchStatus?.regions.find((item) => item.region_code === researchRegion)?.total ?? researchReports.length)
    ),
    [researchReports.length, researchRegion, researchStatus],
  );
  const visibleSources = useMemo(() => researchStatus?.sources.slice(0, 12) ?? [], [researchStatus]);
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
      defaultSummary: "기관별 최신 리포트를 먼저 보여주고, 지역 전환 시 같은 구조로 다시 정리합니다.",
    },
  );
  const summaryFallback = "요약이 제공되지 않는 원문입니다. 출처와 제목을 확인한 뒤 바로 원문으로 이동할 수 있습니다.";

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="리서치 기록"
        title="리포트 아카이브"
        description="내부 분석 리포트와 공식 기관 원문 리서치를 한곳에서 다시 열어보고, 필요한 자료는 바로 내려받거나 원문으로 이동할 수 있습니다."
        meta={
          <>
            <span className="info-chip">공식 기관 우선</span>
            <span className="info-chip">{RESEARCH_REGION_LABELS[researchRegion]} 보기</span>
            {researchStatus ? <span className="info-chip">활성 소스 {researchStatus.source_count}개</span> : null}
          </>
        }
      />

      {error ? <ErrorBanner error={error} onRetry={() => window.location.reload()} /> : null}

      <section className="card !p-5 space-y-4">
        <div className="section-heading gap-4">
          <div>
            <h2 className="section-title">최신 기관 리포트</h2>
            <p className="section-copy">{researchAuditSummary}</p>
          </div>
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
        </div>
        {researchReports.slice(0, 2).length > 0 ? (
          <div className="grid gap-3 xl:grid-cols-2">
            {researchReports.slice(0, 2).map((report) => (
              <div key={`latest-${report.id}`} className="rounded-[22px] border border-border/70 bg-surface/55 px-5 py-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-accent/10 px-2 py-0.5 text-xs text-accent">{report.source_name}</span>
                  <span className="rounded-full bg-border/40 px-2 py-0.5 text-xs text-text-secondary">{REGION_LABELS[report.region_code]}</span>
                  <span className="text-xs text-text-secondary">{new Date(report.published_at).toLocaleDateString("ko-KR")}</span>
                </div>
                <div className="mt-3 font-medium text-text">{report.title}</div>
                <p className="mt-2 text-sm leading-6 text-text-secondary">
                  {report.summary_plain || report.summary || summaryFallback}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {report.has_pdf && report.pdf_url ? (
                    <a
                      href={report.pdf_url}
                      target="_blank"
                      rel="noreferrer"
                      className="ui-button-primary px-4"
                    >
                      PDF 열기
                    </a>
                  ) : null}
                  <a
                    href={report.report_url}
                    target="_blank"
                    rel="noreferrer"
                    className="ui-button-secondary px-4"
                  >
                    원문 보기
                  </a>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <WorkspaceStateCard
            eyebrow="최신 리포트 대기"
            title="상단에 먼저 보여줄 최신 기관 리포트가 아직 없습니다"
            message="지역별 기관 리포트 목록은 아래에서 바로 확인할 수 있고, 새 원문이 잡히면 이 상단 요약 카드부터 채워집니다."
            tone="neutral"
          />
        )}
      </section>

      <section className="card !p-5 space-y-5">
        <div className="section-heading gap-4">
          <div>
            <h2 className="section-title">기관 리서치 아카이브</h2>
            <p className="section-copy">
              한국은행, KDI, Federal Reserve, ECB, BOJ와 추가 해외 정책·연구 리포트를 함께 모읍니다. 전체 보기로 표본을 넓히고, 필요하면 지역별로 다시 좁힐 수 있습니다.
            </p>
          </div>
<<<<<<< HEAD
<<<<<<< HEAD
          <div className="flex flex-wrap gap-2">
            {RESEARCH_REGIONS.map((region) => (
              <button
                key={region}
                onClick={() => setResearchRegion(region)}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  researchRegion === region
                    ? "bg-accent text-white"
                    : "border border-border bg-surface/60 text-text-secondary hover:border-accent/40 hover:text-text"
                }`}
              >
                {REGION_LABELS[region]}
              </button>
            ))}
=======
=======
>>>>>>> main
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
            <div className="ui-segmented-control-responsive">
              {RESEARCH_REGIONS.map((region) => (
                <button
                  key={region}
                  onClick={() => setResearchRegion(region)}
                  className={[
                    "ui-segmented-option",
                    researchRegion === region && "ui-segmented-option-active",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> dev-local-20260413
                  {RESEARCH_REGION_LABELS[region]}
                </button>
              ))}
            </div>
>>>>>>> 373595e (feat: expand archive and calendar coverage)
=======
                  {REGION_LABELS[region]}
=======
                  {RESEARCH_REGION_LABELS[region]}
>>>>>>> dev-local-20260413
                </button>
              ))}
            </div>
>>>>>>> main
            <button
              onClick={handleResearchRefresh}
              disabled={refreshingResearch}
              className="ui-button-secondary px-4 sm:shrink-0"
            >
              {refreshingResearch ? "새로고침 중..." : "기관 리포트 새로고침"}
            </button>
          </div>
        </div>

        {researchError ? (
          <WorkspaceStateCard
            eyebrow="기관 리포트 지연"
            title="기관 리포트 목록을 다시 불러오지 못했습니다"
            message={researchError.message}
            tone="warning"
            actionLabel="목록 다시 불러오기"
            onAction={() => void loadResearch(false)}
          />
        ) : null}

        {researchStatus ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="metric-card">
              <div className="text-xs text-text-secondary">현재 선택 리포트</div>
              <div className="mt-2 text-2xl font-semibold text-text">{activeRegionTotal}</div>
              <div className="mt-1 text-xs text-text-secondary">{RESEARCH_REGION_LABELS[researchRegion]} 기준</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">전체 소스</div>
              <div className="mt-2 text-2xl font-semibold text-text">{researchStatus.source_count}</div>
              <div className="mt-1 text-xs text-text-secondary">활성 공식 기관</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">오늘 반영</div>
              <div className="mt-2 text-2xl font-semibold text-text">{researchStatus.todays_reports}</div>
              <div className="mt-1 text-xs text-text-secondary">전체 지역 합산</div>
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

        {researchStatus?.regions?.length ? (
          <div className="flex flex-wrap gap-2">
            {researchStatus.regions.map((item) => (
              <span key={item.region_code} className="info-chip">
                {REGION_LABELS[item.region_code]} {item.total}건
              </span>
            ))}
          </div>
        ) : null}

        {visibleSources.length ? (
          <div className="flex flex-wrap gap-2">
            {visibleSources.map((source) => (
              <span key={source.source_id} className="rounded-full border border-border/70 bg-surface/55 px-3 py-1.5 text-xs text-text-secondary">
                {source.source_name} {source.total}건
              </span>
            ))}
          </div>
        ) : null}

        {researchLoading ? (
          <div className="space-y-3">
            <WorkspaceLoadingCard
              title={`${RESEARCH_REGION_LABELS[researchRegion]} 기관 리포트를 정리하고 있습니다`}
              message="출처, 발행일, PDF 여부를 먼저 읽은 뒤 지역별 목록으로 다시 배치합니다."
              className="min-h-[160px]"
            />
            <WorkspaceLoadingCard
              title="최신 원문을 확인하고 있습니다"
              message="같은 기관의 중복 항목을 정리하고 바로 열 수 있는 링크를 우선 붙입니다."
              className="min-h-[140px]"
            />
          </div>
        ) : researchReports.length === 0 ? (
          <WorkspaceStateCard
            eyebrow="리포트 대기"
            title={`${RESEARCH_REGION_LABELS[researchRegion]} 공개 리포트가 아직 없습니다`}
            message="잠시 후 새로고침하거나 다른 지역을 먼저 확인해 주세요. 원문이 반영되면 이 목록에 바로 추가됩니다."
          />
        ) : (
          <div className="space-y-3">
            {researchReports.map((report) => (
              <div key={report.id} className="rounded-[22px] border border-border/70 bg-surface/55 px-5 py-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-accent/10 px-2 py-0.5 text-xs text-accent">{report.source_name}</span>
                      <span className="rounded-full bg-border/40 px-2 py-0.5 text-xs text-text-secondary">
                        {REGION_LABELS[report.region_code]}
                      </span>
                      <span className="text-xs text-text-secondary">{report.organization_type}</span>
                      {report.is_new_today ? <span className="rounded-full bg-positive/10 px-2 py-0.5 text-xs text-positive">오늘 반영</span> : null}
                      <span className="text-xs text-text-secondary lg:ml-auto">
                        {new Date(report.published_at).toLocaleDateString("ko-KR")}
                      </span>
                    </div>
                    <div className="mt-3 font-medium text-text">{report.title}</div>
                    <p className="mt-2 text-sm leading-6 text-text-secondary">
                      {report.summary_plain || report.summary || summaryFallback}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-text-secondary">
                      {report.category ? <span>{report.category}</span> : null}
                      <span>{report.language === "ko" ? "한국어" : "영어"}</span>
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    {report.has_pdf && report.pdf_url ? (
                      <a
                        href={report.pdf_url}
                        target="_blank"
                        rel="noreferrer"
                        className="ui-button-primary px-4"
                      >
                        PDF 열기
                      </a>
                    ) : null}
                    <a
                      href={report.report_url}
                      target="_blank"
                      rel="noreferrer"
                      className="ui-button-secondary px-4"
                    >
                      원문 보기
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {accuracy && accuracy.stored_predictions > 0 ? (
        <section className="space-y-3">
          <div className="flex flex-col gap-3 rounded-[22px] border border-border bg-surface/70 px-4 py-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="font-medium">예측 검증을 더 깊게 보고 싶다면</div>
              <div className="mt-1 text-sm text-text-secondary">
                예측 연구실에서 보정 상태, 최근 오차, 모델 버전별 신뢰도를 함께 확인할 수 있습니다.
              </div>
            </div>
            <Link href="/lab" className="ui-button-primary px-4">
              예측 연구실 열기
            </Link>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="metric-card">
              <div className="text-xs text-text-secondary">저장된 예측</div>
              <div className="mt-2 text-2xl font-semibold text-text">{accuracy.stored_predictions}</div>
              <div className="mt-1 text-xs text-text-secondary">평가 대기 {accuracy.pending_predictions}</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">방향 적중률</div>
              <div className="mt-2 text-2xl font-semibold text-text">{(accuracy.direction_accuracy * 100).toFixed(1)}%</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">예상 밴드 적중률</div>
              <div className="mt-2 text-2xl font-semibold text-text">{(accuracy.within_range_rate * 100).toFixed(1)}%</div>
            </div>
            <div className="metric-card">
              <div className="text-xs text-text-secondary">평균 오차</div>
              <div className="mt-2 text-2xl font-semibold text-text">{accuracy.avg_error_pct.toFixed(2)}%</div>
            </div>
          </div>
        </section>
      ) : null}

      <section className="space-y-3">
        <div>
          <h2 className="section-title">내부 분석 리포트</h2>
          <p className="section-copy">국가, 섹터, 종목 분석을 실행하면 자동으로 저장되는 내부 리포트입니다.</p>
        </div>

        {loading ? (
          <div className="space-y-3">
            <WorkspaceLoadingCard
              title="저장된 내부 리포트를 불러오고 있습니다"
              message="국가, 섹터, 종목 리포트를 날짜순으로 다시 정리하는 중입니다."
              className="min-h-[140px]"
            />
          </div>
        ) : archives.length === 0 ? (
          <WorkspaceStateCard
            eyebrow="리포트 대기"
            title="아직 저장된 내부 분석 리포트가 없습니다"
            message="국가, 섹터, 종목 분석을 실행하면 이 아카이브에 자동으로 쌓입니다."
          />
        ) : (
          <div className="space-y-3">
            {archives.map((archive) => (
              <div key={archive.id} className="rounded-[22px] border border-border/70 bg-surface/55 px-5 py-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${
                        archive.report_type === "country" ? "bg-blue-500/20 text-blue-500" :
                        archive.report_type === "sector" ? "bg-amber-500/20 text-amber-500" : "bg-emerald-500/20 text-emerald-500"
                      }`}>{reportTypeLabel(archive.report_type)}</span>
                      {archive.country_code ? <span className="text-xs text-text-secondary">{archive.country_code}</span> : null}
                      {archive.ticker ? <span className="text-xs font-mono">{archive.ticker}</span> : null}
                      <span className="text-xs text-text-secondary lg:ml-auto">
                        {new Date(archive.created_at * 1000).toLocaleDateString("ko-KR")}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-text-secondary">
                      {archive.preview || "저장된 요약이 없어 원본 리포트 메타데이터만 제공합니다."}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    <button
                      onClick={() => handleDownload(archive.id, "pdf")}
                      className="ui-button-primary px-4"
                    >
                      PDF 바로받기
                    </button>
                    <button
                      onClick={() => handleDownload(archive.id, "csv")}
                      className="ui-button-secondary px-4"
                    >
                      CSV 바로받기
                    </button>
                    <Link
                      href={`/archive/export/${archive.id}`}
                      className="ui-button-secondary px-4"
                    >
                      내보내기 허브
                    </Link>
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
