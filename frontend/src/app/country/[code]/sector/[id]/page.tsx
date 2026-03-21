"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { SectorReport } from "@/lib/types";
import { formatPct, changeColor } from "@/lib/utils";
import ScoreRadial from "@/components/charts/ScoreRadial";
import ScoreBreakdown from "@/components/charts/ScoreBreakdown";
import ErrorBanner, { WarningBanner } from "@/components/ErrorBanner";

export default function SectorPage() {
  const { code, id } = useParams<{ code: string; id: string }>();
  const [report, setReport] = useState<SectorReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!code || !id) return;
    setLoading(true);
    setError(null);
    api.getSectorReport(code, id).then(setReport).catch((e) => { console.error(e); setError(e); }).finally(() => setLoading(false));
  }, [code, id]);

  if (loading) return <div className="animate-pulse space-y-4"><div className="h-8 bg-border rounded w-48" /><div className="h-96 bg-border rounded" /></div>;
  if (!report && error) return (
    <div className="max-w-5xl mx-auto space-y-4">
      <Link href={`/country/${code}`} className="text-text-secondary hover:text-text">&larr; Back</Link>
      <ErrorBanner error={error} onRetry={() => window.location.reload()} />
    </div>
  );
  if (!report) return <div className="text-text-secondary">Failed to load sector report</div>;

  const scoreItems = [
    report.score.earnings_growth, report.score.institutional_consensus, report.score.valuation_attractiveness,
    report.score.policy_impact, report.score.technical_momentum, report.score.risk_adjusted_return,
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex items-center gap-4">
        <Link href={`/country/${code}`} className="text-text-secondary hover:text-text">&larr;</Link>
        <h1 className="text-2xl font-bold">{report.sector.name}</h1>
        <span className="text-text-secondary">({report.sector.stock_count} stocks)</span>
      </div>

      {(report as any).errors?.length > 0 && <WarningBanner codes={(report as any).errors} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="card lg:col-span-2">
          <div className="flex items-center gap-6">
            <ScoreRadial score={report.score.total} label="Sector Score" />
            <div className="flex-1">
              <ScoreBreakdown items={scoreItems} />
            </div>
          </div>
        </div>
        <div className="card">
          <h3 className="font-semibold mb-3">Summary</h3>
          <p className="text-sm leading-relaxed whitespace-pre-line">{report.summary}</p>
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold mb-4">Top 10 Stocks</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-secondary border-b border-border">
                <th className="pb-2 w-8">#</th>
                <th className="pb-2">Name</th>
                <th className="pb-2 text-right">Price</th>
                <th className="pb-2 text-right">Change</th>
                <th className="pb-2 text-right">Score</th>
                <th className="pb-2 hidden md:table-cell">Pros</th>
                <th className="pb-2 hidden md:table-cell">Cons</th>
              </tr>
            </thead>
            <tbody>
              {report.top_stocks.map((s) => (
                <tr key={s.ticker} className="border-b border-border/50 hover:bg-border/20">
                  <td className="py-3 font-bold text-accent">{s.rank}</td>
                  <td className="py-3">
                    <Link href={`/stock/${s.ticker}`} className="hover:text-accent transition-colors">
                      <div className="font-medium">{s.name}</div>
                      <div className="text-xs text-text-secondary">{s.ticker}</div>
                    </Link>
                  </td>
                  <td className="py-3 text-right font-mono">{s.current_price.toLocaleString()}</td>
                  <td className={`py-3 text-right ${changeColor(s.change_pct)}`}>{formatPct(s.change_pct)}</td>
                  <td className="py-3 text-right font-bold">{s.score.toFixed(1)}</td>
                  <td className="py-3 text-xs text-text-secondary hidden md:table-cell">
                    {s.pros.slice(0, 2).map((p, i) => <div key={i}>+ {p}</div>)}
                  </td>
                  <td className="py-3 text-xs text-text-secondary hidden md:table-cell">
                    {s.cons.slice(0, 2).map((c, i) => <div key={i}>- {c}</div>)}
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
