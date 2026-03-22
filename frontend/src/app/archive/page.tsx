"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import ErrorBanner from "@/components/ErrorBanner";
import type { PredictionAccuracyStats } from "@/lib/api";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "Unknown error");
}

function downloadFile(url: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export default function ArchivePage() {
  const [archives, setArchives] = useState<any[]>([]);
  const [accuracy, setAccuracy] = useState<PredictionAccuracyStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    api.getArchive()
      .then(setArchives)
      .catch((e) => { console.error(e); setError(toError(e)); })
      .finally(() => setLoading(false));

    api.getPredictionAccuracy().then(setAccuracy).catch(console.error);
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Report Archive</h1>

      {error ? <ErrorBanner error={error} onRetry={() => window.location.reload()} /> : null}

      {accuracy && accuracy.stored_predictions > 0 ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface/60 px-4 py-3">
            <div>
              <div className="font-medium">Need deeper validation?</div>
              <div className="text-sm text-text-secondary mt-1">Prediction Lab tracks calibration, recent misses, and model-level reliability.</div>
            </div>
            <Link href="/lab" className="px-3 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90">
              Open Lab
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="card">
            <div className="text-xs text-text-secondary">Stored Predictions</div>
            <div className="text-xl font-bold mt-1">{accuracy.stored_predictions}</div>
            <div className="text-[11px] text-text-secondary mt-1">Pending {accuracy.pending_predictions}</div>
          </div>
          <div className="card">
            <div className="text-xs text-text-secondary">Direction Accuracy</div>
            <div className="text-xl font-bold mt-1">{(accuracy.direction_accuracy * 100).toFixed(1)}%</div>
          </div>
          <div className="card">
            <div className="text-xs text-text-secondary">Within Range</div>
            <div className="text-xl font-bold mt-1">{(accuracy.within_range_rate * 100).toFixed(1)}%</div>
          </div>
          <div className="card">
            <div className="text-xs text-text-secondary">Avg Error</div>
            <div className="text-xl font-bold mt-1">{accuracy.avg_error_pct.toFixed(2)}%</div>
          </div>
        </div>
        </div>
      ) : null}

      {loading ? (
        <div className="animate-pulse space-y-3">{[1, 2, 3].map((i) => <div key={i} className="h-20 bg-border rounded" />)}</div>
      ) : archives.length === 0 ? (
        <p className="text-text-secondary">No archived reports yet. Reports are saved automatically when generated.</p>
      ) : (
        <div className="space-y-2">
          {archives.map((a: any) => (
            <div key={a.id} className="card flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${
                    a.report_type === "country" ? "bg-blue-500/20 text-blue-500" :
                    a.report_type === "sector" ? "bg-purple-500/20 text-purple-500" : "bg-emerald-500/20 text-emerald-500"
                  }`}>{a.report_type}</span>
                  {a.country_code && <span className="text-xs text-text-secondary">{a.country_code}</span>}
                  {a.ticker && <span className="text-xs font-mono">{a.ticker}</span>}
                  <span className="text-xs text-text-secondary ml-auto shrink-0">
                    {new Date(a.created_at * 1000).toLocaleDateString()}
                  </span>
                </div>
                <p className="text-sm text-text-secondary mt-1 truncate">{a.preview}</p>
              </div>
              <div className="flex gap-1.5 shrink-0 ml-4">
                <button
                  onClick={() => downloadFile(`/api/export/pdf/${a.id}`)}
                  className="px-2.5 py-1 rounded text-xs font-medium bg-accent text-white hover:opacity-90 transition-opacity"
                >
                  PDF
                </button>
                <button
                  onClick={() => downloadFile(`/api/export/csv/${a.id}`)}
                  className="px-2.5 py-1 rounded text-xs font-medium border border-border hover:border-accent/50 transition-colors"
                >
                  CSV
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
