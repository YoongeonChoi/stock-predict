"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import ErrorBanner from "@/components/ErrorBanner";
import { useToast } from "@/components/Toast";
import { api, apiPath } from "@/lib/api";
import { downloadApiFile } from "@/lib/download";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "알 수 없는 오류가 발생했습니다.");
}

function reportTypeLabel(type: string) {
  if (type === "country") return "국가 리포트";
  if (type === "sector") return "섹터 리포트";
  return "종목 리포트";
}

interface ArchiveExportPageClientProps {
  initialReportId: number;
  initialFormat?: string;
}

export default function ArchiveExportPageClient({
  initialReportId,
  initialFormat,
}: ArchiveExportPageClientProps) {
  const { toast } = useToast();
  const autoTriggered = useRef(false);
  const reportId = initialReportId;

  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!Number.isFinite(reportId)) {
      setError(new Error("잘못된 리포트 ID입니다."));
      setLoading(false);
      return;
    }

    api.getArchiveDetail(reportId)
      .then(setReport)
      .catch((archiveError) => {
        console.error(archiveError);
        setError(toError(archiveError));
      })
      .finally(() => setLoading(false));
  }, [reportId]);

  useEffect(() => {
    if (!reportId || autoTriggered.current || (initialFormat !== "pdf" && initialFormat !== "csv")) return;

    autoTriggered.current = true;
    downloadApiFile(`/api/export/${initialFormat}/${reportId}`, `report_${reportId}.${initialFormat}`)
      .then(() => toast(`${initialFormat.toUpperCase()} 다운로드를 시작했습니다.`, "success"))
      .catch((downloadError) => {
        console.error(downloadError);
        toast("자동 다운로드에 실패했습니다. 아래 버튼을 눌러 다시 시도해 주세요.", "error");
      });
  }, [initialFormat, reportId, toast]);

  const preview = useMemo(() => {
    if (!report?.report_json) return "";
    return report.report_json.market_summary || report.report_json.summary || report.report_json.analysis_summary || "";
  }, [report]);

  const pdfHref = apiPath(`/api/export/pdf/${reportId}`);
  const csvHref = apiPath(`/api/export/csv/${reportId}`);

  async function manualDownload(format: "pdf" | "csv") {
    try {
      await downloadApiFile(`/api/export/${format}/${reportId}`, `report_${reportId}.${format}`);
      toast(`${format.toUpperCase()} 다운로드를 시작했습니다.`, "success");
    } catch (downloadError) {
      console.error(downloadError);
      toast("브라우저 다운로드가 실패했습니다. 새 탭 링크를 사용해 주세요.", "error");
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="space-y-2">
        <Link href="/archive" className="ui-button-ghost w-fit px-0">
          아카이브로 돌아가기
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">리포트 내보내기</h1>
        <p className="text-sm text-text-secondary">
          자동 다운로드가 막히는 환경을 대비해, 직접 다운로드와 새 탭 열기 경로를 함께 제공합니다.
        </p>
      </div>

      {error ? <ErrorBanner error={error} onRetry={() => window.location.reload()} /> : null}

      {loading ? (
        <div className="space-y-3 animate-pulse">
          <div className="h-28 rounded-2xl bg-border" />
          <div className="h-56 rounded-2xl bg-border" />
        </div>
      ) : report ? (
        <>
          <div className="card space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondary">
              <span className="px-2 py-1 rounded-full bg-border/60 text-text">{reportTypeLabel(report.report_type)}</span>
              {report.country_code ? <span>{report.country_code}</span> : null}
              {report.ticker ? <span className="font-mono">{report.ticker}</span> : null}
              <span>#{report.id}</span>
              <span>{new Date(report.created_at * 1000).toLocaleString("ko-KR")}</span>
            </div>
            <div className="text-sm leading-relaxed text-text-secondary whitespace-pre-wrap">
              {preview || "미리보기 텍스트가 없어 원본 메타데이터만 표시합니다."}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="card space-y-3">
              <div>
                <h2 className="font-semibold">직접 다운로드</h2>
                <p className="text-sm text-text-secondary mt-1">
                  현재 페이지에서 바로 파일을 받아봅니다. 일반적으로 가장 빠른 방식입니다.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => manualDownload("pdf")}
                  className="ui-button-primary px-4"
                >
                  PDF 다운로드
                </button>
                <button
                  onClick={() => manualDownload("csv")}
                  className="ui-button-secondary px-4"
                >
                  CSV 다운로드
                </button>
              </div>
            </div>

            <div className="card space-y-3">
              <div>
                <h2 className="font-semibold">새 탭 우회 경로</h2>
                <p className="text-sm text-text-secondary mt-1">
                  브라우저 보안 설정으로 직접 다운로드가 막히면 새 탭으로 열어 저장할 수 있습니다.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <a
                  href={pdfHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ui-button-secondary px-4"
                >
                  PDF 새 탭 열기
                </a>
                <a
                  href={csvHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ui-button-secondary px-4"
                >
                  CSV 새 탭 열기
                </a>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="card text-text-secondary">리포트 정보를 불러오지 못했습니다.</div>
      )}
    </div>
  );
}
