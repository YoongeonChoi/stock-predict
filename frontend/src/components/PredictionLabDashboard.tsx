"use client";

import type { PredictionLabResponse } from "@/lib/api";
import { changeColor } from "@/lib/utils";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props {
  data: PredictionLabResponse;
}

function pct(value: number, scaled = true) {
  const v = scaled ? value * 100 : value;
  return `${v.toFixed(1)}%`;
}

export default function PredictionLabDashboard({ data }: Props) {
  const accuracy = data.accuracy;
  const trendData = data.recent_trend.map((row) => ({
    ...row,
    direction_accuracy_pct: row.direction_accuracy * 100,
    within_range_rate_pct: row.within_range_rate * 100,
  }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 xl:grid-cols-5 gap-4">
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">Stored Forecasts</div>
          <div className="text-2xl font-bold mt-3">{accuracy.stored_predictions}</div>
          <div className="text-[11px] text-text-secondary mt-1">Pending {accuracy.pending_predictions}</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">Validated</div>
          <div className="text-2xl font-bold mt-3">{accuracy.total_predictions}</div>
          <div className="text-[11px] text-text-secondary mt-1">Completed samples</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">Direction Accuracy</div>
          <div className="text-2xl font-bold mt-3">{pct(accuracy.direction_accuracy)}</div>
          <div className="text-[11px] text-text-secondary mt-1">Directional hit rate</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">Within Range</div>
          <div className="text-2xl font-bold mt-3">{pct(accuracy.within_range_rate)}</div>
          <div className="text-[11px] text-text-secondary mt-1">Close landed in the band</div>
        </div>
        <div className="card !p-4">
          <div className="text-xs text-text-secondary">Avg Error</div>
          <div className="text-2xl font-bold mt-3">{accuracy.avg_error_pct.toFixed(2)}%</div>
          <div className="text-[11px] text-text-secondary mt-1">Avg confidence {accuracy.avg_confidence.toFixed(1)}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.15fr_1fr] gap-5">
        <div className="card !p-4 space-y-4">
          <div>
            <h2 className="font-semibold text-base">What The Lab Is Seeing</h2>
            <p className="text-sm text-text-secondary mt-1">Calibration notes generated from live stored predictions and realized closes.</p>
          </div>
          <div className="space-y-2">
            {data.insights.map((insight) => (
              <div key={insight} className="rounded-xl border border-border/70 bg-surface/60 px-3 py-2 text-sm">
                {insight}
              </div>
            ))}
          </div>
        </div>

        <div className="card !p-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-base">Confidence Calibration</h2>
              <p className="text-sm text-text-secondary mt-1">Higher-confidence buckets should deliver tighter error and better direction accuracy.</p>
            </div>
          </div>
          <div className="h-[320px] mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.calibration}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} width={44} />
                <Tooltip formatter={(value: number) => `${Number(value).toFixed(1)}%`} />
                <Bar dataKey="direction_accuracy" name="Direction" fill="#0f766e" radius={[6, 6, 0, 0]} />
                <Bar dataKey="avg_confidence" name="Confidence" fill="#f59e0b" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-5">
        <div className="card !p-4">
          <div>
            <h2 className="font-semibold text-base">Recent Validation Trend</h2>
            <p className="text-sm text-text-secondary mt-1">Direction accuracy and forecast error over the most recent target dates.</p>
          </div>
          <div className="h-[320px] mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="target_date" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="left" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} width={44} />
                <YAxis yAxisId="right" orientation="right" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} width={44} />
                <Tooltip
                  formatter={(value: number, name: string) =>
                    name === "Direction Accuracy"
                      ? `${Number(value).toFixed(1)}%`
                      : `${Number(value).toFixed(2)}%`
                  }
                />
                <Line yAxisId="left" type="monotone" dataKey="direction_accuracy_pct" name="Direction Accuracy" stroke="#2563eb" strokeWidth={2} dot={false} />
                <Line yAxisId="right" type="monotone" dataKey="avg_error_pct" name="Avg Error" stroke="#ef4444" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card !p-4 space-y-4">
          <div>
            <h2 className="font-semibold text-base">Breakdown By Market</h2>
            <p className="text-sm text-text-secondary mt-1">Where the engine is behaving best right now.</p>
          </div>
          <div className="space-y-2">
            {data.breakdown.by_country.length === 0 ? (
              <div className="text-sm text-text-secondary">Validated samples are still building up.</div>
            ) : (
              data.breakdown.by_country.map((row) => (
                <div key={row.label} className="rounded-xl border border-border/70 px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium">{row.label}</div>
                      <div className="text-xs text-text-secondary mt-1">{row.total} validated forecasts</div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold">{pct(row.direction_accuracy)}</div>
                      <div className="text-xs text-text-secondary mt-1">Error {row.avg_error_pct.toFixed(2)}%</div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className="card !p-4 space-y-3">
          <div>
            <h2 className="font-semibold text-base">Scope Reliability</h2>
            <p className="text-sm text-text-secondary mt-1">Country, stock, and sector forecast slices are tracked separately.</p>
          </div>
          <div className="space-y-2">
            {data.breakdown.by_scope.map((row) => (
              <div key={row.label} className="rounded-xl border border-border/70 px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium capitalize">{row.label}</div>
                    <div className="text-xs text-text-secondary mt-1">{row.total} samples</div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold">{pct(row.direction_accuracy)}</div>
                    <div className="text-xs text-text-secondary mt-1">Range {pct(row.within_range_rate)}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card !p-4 space-y-3">
          <div>
            <h2 className="font-semibold text-base">Model Versions</h2>
            <p className="text-sm text-text-secondary mt-1">Helps us see whether newer engines are actually earning their keep.</p>
          </div>
          <div className="space-y-2">
            {data.breakdown.by_model.map((row) => (
              <div key={row.label} className="rounded-xl border border-border/70 px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium">{row.label}</div>
                    <div className="text-xs text-text-secondary mt-1">{row.total} samples</div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold">{pct(row.direction_accuracy)}</div>
                    <div className="text-xs text-text-secondary mt-1">Confidence {row.avg_confidence.toFixed(1)}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card !p-4">
        <div>
          <h2 className="font-semibold text-base">Recent Predictions</h2>
          <p className="text-sm text-text-secondary mt-1">Quick audit trail of the latest forecasted closes versus realized outcomes.</p>
        </div>
        <div className="overflow-x-auto mt-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-text-secondary">
                <th className="pb-2">Symbol</th>
                <th className="pb-2">Scope</th>
                <th className="pb-2 text-right">Predicted</th>
                <th className="pb-2 text-right">Actual</th>
                <th className="pb-2 text-right">Error</th>
                <th className="pb-2 text-right">Confidence</th>
                <th className="pb-2 text-right">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_records.map((row) => (
                <tr key={row.id} className="border-b border-border/40">
                  <td className="py-2">
                    <div className="font-medium">{row.symbol}</div>
                    <div className="text-[11px] text-text-secondary">{row.target_date}{row.country_code ? ` • ${row.country_code}` : ""}</div>
                  </td>
                  <td className="py-2 capitalize">{row.scope}</td>
                  <td className="py-2 text-right font-mono">{row.predicted_close.toFixed(2)}</td>
                  <td className="py-2 text-right font-mono">{row.actual_close != null ? row.actual_close.toFixed(2) : "Pending"}</td>
                  <td className="py-2 text-right font-mono">{row.abs_error_pct != null ? `${row.abs_error_pct.toFixed(2)}%` : "-"}</td>
                  <td className="py-2 text-right">{row.confidence.toFixed(1)}</td>
                  <td className={`py-2 text-right font-medium ${
                    row.direction_hit == null
                      ? "text-text-secondary"
                      : row.direction_hit
                        ? "text-emerald-500"
                        : "text-red-500"
                  }`}>
                    {row.direction_hit == null ? "Pending" : row.direction_hit ? "Hit" : "Miss"}
                    {row.within_range != null ? (
                      <span className={`ml-2 text-[11px] ${changeColor(row.within_range ? 1 : -1)}`}>
                        {row.within_range ? "Band" : "Out"}
                      </span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
