"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import ErrorBanner from "@/components/ErrorBanner";
import { useToast } from "@/components/Toast";
import { api } from "@/lib/api";
import type {
  ArchiveEntry,
  PredictionAccuracyStats,
  ResearchArchiveEntry,
  ResearchArchiveStatus,
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

const REGION_LABELS: Record<string, string> = {
  KR: "한국",
};

export default function ArchivePage() {
  const [archives, setArchives] = useState<ArchiveEntry[]>([]);
  const [accuracy, setAccuracy] = useState<PredictionAccuracyStats | null>(null);
  const [researchReports, setResearchReports] = useState<ResearchArchiveEntry[]>([]);
  const [researchStatus, setResearchStatus] = useState<ResearchArchiveStatus | null>(null);
  const [researchRegion, setResearchRegion] = useState<"KR">("KR");
  const [loading, setLoading] = useState(true);
  const [researchLoading, setResearchLoading] = useState(true);
  const [refreshingResearch, setRefreshingResearch] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [researchError, setResearchError] = useState<Error | null>(null);
  const router = useRouter();
  const { toast } = useToast();

  useEffect(() => {
    api.getArchive()
      .then(setArchives)
      .catch((e) => {
        console.error(e);
        setError(toError(e));
      })
      .finally(() => setLoading(false));

    api.getPredictionAccuracy().then(setAccuracy).catch(console.error);
  }, []);

  useEffect(() => {
    loadResearch(false);
  }, [researchRegion]);

  async function loadResearch(forceRefresh: boolean) {
    setResearchLoading(true);
    setResearchError(null);
    try {
      if (forceRefresh) {
        await api.refreshResearchArchive();
      }
      const [reports, status] = await Promise.all([
        api.getResearchArchive(researchRegion, 24, !forceRefresh),
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

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">리포트 아카이브</h1>
        <p className="text-sm text-text-secondary">
          내부 분석 리포트와 공식 기관 원문 리서치를 한곳에서 다시 열어보고, 필요한 자료는 바로 내려받거나 원문으로 이동할 수 있습니다.
        </p>
      </div>

      {error ? <ErrorBanner error={error} onRetry={() => window.location.reload()} /> : null}

      <div className="space-y-3">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <h2 className="font-semibold text-lg">기관 리서치 아카이브</h2>
            <p className="text-sm text-text-secondary mt-1">
              KDI와 한국은행 공식 리포트를 하루 한 번 동기화합니다. PDF가 있으면 바로 열고, 없으면 원문으로 이동합니다.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {(["KR"] as const).map((region) => (
              <button
                key={region}
                onClick={() => setResearchRegion(region)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  researchRegion === region ? "bg-accent text-white" : "border border-border hover:border-accent/50"
                }`}
              >
                {REGION_LABELS[region]}
              </button>
            ))}
            <button
              onClick={handleResearchRefresh}
              disabled={refreshingResearch}
              className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:border-accent/50 disabled:opacity-50"
            >
              {refreshingResearch ? "새로고침 중..." : "기관 리포트 새로고침"}
            </button>
          </div>
        </div>

        {researchError ? <ErrorBanner error={researchError} onRetry={() => loadResearch(false)} /> : null}

        {researchStatus ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="card">
              <div className="text-xs text-text-secondary">누적 기관 리포트</div>
              <div className="text-xl font-bold mt-1">{researchStatus.total_reports}</div>
            </div>
            <div className="card">
              <div className="text-xs text-text-secondary">오늘 반영</div>
              <div className="text-xl font-bold mt-1">{researchStatus.todays_reports}</div>
            </div>
            <div className="card">
              <div className="text-xs text-text-secondary">활성 소스</div>
              <div className="text-xl font-bold mt-1">{researchStatus.source_count}</div>
            </div>
            <div className="card">
              <div className="text-xs text-text-secondary">최근 동기화</div>
              <div className="text-sm font-bold mt-1">
                {researchStatus.refreshed_at ? new Date(researchStatus.refreshed_at).toLocaleString("ko-KR") : "아직 없음"}
              </div>
            </div>
          </div>
        ) : null}

        {researchLoading ? (
          <div className="animate-pulse space-y-3">
            {[1, 2, 3].map((i) => <div key={i} className="h-28 bg-border rounded" />)}
          </div>
        ) : researchReports.length === 0 ? (
          <div className="card text-text-secondary">
            아직 반영된 기관 리포트가 없습니다. 잠시 후 새로고침하거나 설정 페이지에서 동기화 상태를 확인해 주세요.
          </div>
        ) : (
          <div className="space-y-3">
            {researchReports.map((report) => (
              <div key={report.id} className="card flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs px-2 py-0.5 rounded bg-accent/10 text-accent">{report.source_name}</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-border text-text-secondary">
                      {REGION_LABELS[report.region_code] || report.region_code}
                    </span>
                    <span className="text-xs text-text-secondary">{report.organization_type}</span>
                    {report.is_new_today ? <span className="text-xs px-2 py-0.5 rounded bg-positive/10 text-positive">오늘 반영</span> : null}
                    <span className="text-xs text-text-secondary lg:ml-auto">
                      {new Date(report.published_at).toLocaleDateString("ko-KR")}
                    </span>
                  </div>
                  <div className="mt-2 font-medium">{report.title}</div>
                  <p className="text-sm text-text-secondary mt-2 line-clamp-3">
                    {report.summary || "요약이 제공되지 않는 원문입니다. 출처와 제목을 확인한 뒤 바로 원문으로 이동할 수 있습니다."}
                  </p>
                  <div className="flex flex-wrap gap-2 mt-3 text-[11px] text-text-secondary">
                    {report.category ? <span>{report.category}</span> : null}
                    <span>{report.language === "ko" ? "한국어" : "영어"}</span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 shrink-0">
                  {report.has_pdf && report.pdf_url ? (
                    <a
                      href={report.pdf_url}
                      target="_blank"
                      rel="noreferrer"
                      className="px-3 py-1.5 rounded text-xs font-medium bg-accent text-white hover:opacity-90 transition-opacity"
                    >
                      PDF 열기
                    </a>
                  ) : null}
                  <a
                    href={report.report_url}
                    target="_blank"
                    rel="noreferrer"
                    className="px-3 py-1.5 rounded text-xs font-medium border border-border hover:border-accent/50 transition-colors"
                  >
                    원문 보기
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {accuracy && accuracy.stored_predictions > 0 ? (
        <div className="space-y-3">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 rounded-2xl border border-border bg-surface/70 px-4 py-4">
            <div>
              <div className="font-medium">예측 검증을 더 깊게 보고 싶다면</div>
              <div className="text-sm text-text-secondary mt-1">
                예측 연구실에서 보정 상태, 최근 오차, 모델 버전별 신뢰도를 함께 확인할 수 있습니다.
              </div>
            </div>
            <Link href="/lab" className="px-3 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90">
              예측 연구실 열기
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="card">
              <div className="text-xs text-text-secondary">저장된 예측</div>
              <div className="text-xl font-bold mt-1">{accuracy.stored_predictions}</div>
              <div className="text-[11px] text-text-secondary mt-1">평가 대기 {accuracy.pending_predictions}</div>
            </div>
            <div className="card">
              <div className="text-xs text-text-secondary">방향 적중률</div>
              <div className="text-xl font-bold mt-1">{(accuracy.direction_accuracy * 100).toFixed(1)}%</div>
            </div>
            <div className="card">
              <div className="text-xs text-text-secondary">예상 밴드 적중률</div>
              <div className="text-xl font-bold mt-1">{(accuracy.within_range_rate * 100).toFixed(1)}%</div>
            </div>
            <div className="card">
              <div className="text-xs text-text-secondary">평균 오차</div>
              <div className="text-xl font-bold mt-1">{accuracy.avg_error_pct.toFixed(2)}%</div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="pt-2">
        <h2 className="font-semibold text-lg">내부 분석 리포트</h2>
        <p className="text-sm text-text-secondary mt-1">
          국가, 섹터, 종목 분석을 실행하면 자동으로 저장되는 내부 리포트입니다.
        </p>
      </div>

      {loading ? (
        <div className="animate-pulse space-y-3">{[1, 2, 3].map((i) => <div key={i} className="h-24 bg-border rounded" />)}</div>
      ) : archives.length === 0 ? (
        <div className="card text-text-secondary">
          아직 저장된 리포트가 없습니다. 국가, 섹터, 종목 분석을 실행하면 아카이브에 자동으로 쌓입니다.
        </div>
      ) : (
        <div className="space-y-3">
          {archives.map((archive) => (
            <div key={archive.id} className="card flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${
                    archive.report_type === "country" ? "bg-blue-500/20 text-blue-500" :
                    archive.report_type === "sector" ? "bg-amber-500/20 text-amber-500" : "bg-emerald-500/20 text-emerald-500"
                  }`}>{reportTypeLabel(archive.report_type)}</span>
                  {archive.country_code ? <span className="text-xs text-text-secondary">{archive.country_code}</span> : null}
                  {archive.ticker ? <span className="text-xs font-mono">{archive.ticker}</span> : null}
                  <span className="text-xs text-text-secondary lg:ml-auto">
                    {new Date(archive.created_at * 1000).toLocaleDateString("ko-KR")}
                  </span>
                </div>
                <p className="text-sm text-text-secondary mt-2 line-clamp-2">
                  {archive.preview || "저장된 요약이 없어 원본 리포트 메타데이터만 제공합니다."}
                </p>
              </div>
              <div className="flex flex-wrap gap-2 shrink-0">
                <button
                  onClick={() => handleDownload(archive.id, "pdf")}
                  className="px-3 py-1.5 rounded text-xs font-medium bg-accent text-white hover:opacity-90 transition-opacity"
                >
                  PDF 바로받기
                </button>
                <button
                  onClick={() => handleDownload(archive.id, "csv")}
                  className="px-3 py-1.5 rounded text-xs font-medium border border-border hover:border-accent/50 transition-colors"
                >
                  CSV 바로받기
                </button>
                <Link
                  href={`/archive/export/${archive.id}`}
                  className="px-3 py-1.5 rounded text-xs font-medium border border-border hover:border-accent/50 transition-colors"
                >
                  내보내기 허브
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
