"use client";

import Link from "next/link";

import type { SystemDiagnostics } from "@/lib/api";

interface Props {
  diagnostics: SystemDiagnostics;
}

function statusTone(status: string) {
  if (status === "ok") return "text-positive bg-positive/10";
  if (status === "starting") return "text-warning bg-warning/10";
  return "text-negative bg-negative/10";
}

export default function SystemStatusCard({ diagnostics }: Props) {
  const model = diagnostics.forecast_models[0];
  const criticalSources = diagnostics.data_sources.slice(0, 4);

  return (
    <div className="card !p-4">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3 mb-4">
        <div>
          <h2 className="font-semibold text-lg">System Readiness</h2>
          <p className="text-sm text-text-secondary mt-1">
            API v{diagnostics.version} · next-day model {model?.version ?? "N/A"}
          </p>
        </div>
        <div className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide ${statusTone(diagnostics.status)}`}>
          {diagnostics.status}
        </div>
      </div>

      <div className="flex items-center justify-end mb-4">
        <Link href="/lab" className="text-sm text-accent hover:underline">
          Open Prediction Lab
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-border p-3">
          <div className="text-xs font-medium text-text-secondary mb-2">Prediction Snapshot</div>
          {diagnostics.prediction_accuracy ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <span>Stored forecasts</span>
                <span className="font-semibold">{diagnostics.prediction_accuracy.stored_predictions}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span>Direction accuracy</span>
                <span className="font-semibold">{(diagnostics.prediction_accuracy.direction_accuracy * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between gap-3">
                <span>Within range</span>
                <span className="font-semibold">{(diagnostics.prediction_accuracy.within_range_rate * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between gap-3">
                <span>Avg. error</span>
                <span className="font-semibold">{diagnostics.prediction_accuracy.avg_error_pct.toFixed(2)}%</span>
              </div>
            </div>
          ) : (
            <div className="text-sm text-text-secondary">
              {diagnostics.prediction_accuracy_error || "Accuracy history is not available yet."}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border p-3">
          <div className="text-xs font-medium text-text-secondary mb-2">Startup Tasks</div>
          <div className="space-y-2">
            {diagnostics.startup_tasks.map((task) => (
              <div key={task.name} className="flex items-start justify-between gap-3 text-sm">
                <div>
                  <div className="font-medium">{task.name}</div>
                  <div className="text-xs text-text-secondary mt-1">{task.detail}</div>
                </div>
                <span className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${statusTone(task.status)}`}>
                  {task.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border p-3">
          <div className="text-xs font-medium text-text-secondary mb-2">Core Data Sources</div>
          <div className="space-y-2">
            {criticalSources.map((source) => (
              <div key={source.name} className="rounded-lg bg-border/30 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-sm">{source.name}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${statusTone(source.configured ? "ok" : "degraded")}`}>
                    {source.status}
                  </span>
                </div>
                <div className="text-xs text-text-secondary mt-1">{source.purpose}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {model ? (
        <div className="mt-4 rounded-xl border border-border p-3">
          <div className="text-xs font-medium text-text-secondary mb-2">Forecast Coverage</div>
          <div className="text-sm">
            Markets: {model.markets.join(", ")} · Signals: {model.signals.slice(0, 5).join(", ")}
          </div>
          <div className="text-xs text-text-secondary mt-2">
            {model.notes.join(" ")}
          </div>
        </div>
      ) : null}
    </div>
  );
}
