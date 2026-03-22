"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import ErrorBanner from "@/components/ErrorBanner";
import { useToast } from "@/components/Toast";
import { api } from "@/lib/api";
import type { PredictionAccuracyStats } from "@/lib/api";
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

export default function ArchivePage() {
  const [archives, setArchives] = useState<any[]>([]);
  const [accuracy, setAccuracy] = useState<PredictionAccuracyStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
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

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">리포트 아카이브</h1>
        <p className="text-sm text-text-secondary">
          저장된 분석 리포트와 예측 이력을 다시 열어보고, PDF 또는 CSV로 안정적으로 내보낼 수 있습니다.
        </p>
      </div>

      {error ? <ErrorBanner error={error} onRetry={() => window.location.reload()} /> : null}

      {accuracy && accuracy.stored_predictions > 0 ? (
        <div className="space-y-3">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 rounded-2xl border border-border bg-surface/70 px-4 py-4">
            <div>
              <div className="font-medium">예측 검증을 더 깊게 보고 싶다면</div>
              <div className="text-sm text-text-secondary mt-1">
                Prediction Lab에서 보정 상태, 최근 오차, 모델 버전별 신뢰도를 함께 확인할 수 있습니다.
              </div>
            </div>
            <Link href="/lab" className="px-3 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90">
              Prediction Lab 열기
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

