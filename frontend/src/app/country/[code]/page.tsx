"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { CountryReport, SectorListItem } from "@/lib/types";
import { formatPct, changeColor } from "@/lib/utils";
import ScoreRadial from "@/components/charts/ScoreRadial";
import ScoreBreakdown from "@/components/charts/ScoreBreakdown";
import FearGreedGauge from "@/components/charts/FearGreedGauge";
import ForecastBand from "@/components/charts/ForecastBand";
import ErrorBanner, { WarningBanner } from "@/components/ErrorBanner";

export default function CountryPage() {
  const { code } = useParams<{ code: string }>();
  const [report, setReport] = useState<CountryReport | null>(null);
  const [sectors, setSectors] = useState<SectorListItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!code) return;
    setLoading(true);
    setError(null);

    const loadReport = api.getCountryReport(code)
      .then(setReport)
      .catch((e) => { console.error(e); setError(e); });

    const loadSectors = api.getSectors(code)
      .then(setSectors)
      .catch(console.error);

    Promise.all([loadReport, loadSectors]).finally(() => setLoading(false));
  }, [code]);

  if (loading) return <div className="animate-pulse space-y-4"><div className="h-8 bg-border rounded w-48" /><div className="h-96 bg-border rounded" /></div>;
  if (!report && error) return (
    <div className="max-w-5xl mx-auto space-y-4">
      <Link href="/" className="text-text-secondary hover:text-text">&larr; Back</Link>
      <ErrorBanner error={error} onRetry={() => window.location.reload()} />
    </div>
  );
  if (!report) return <div className="text-text-secondary">Failed to load report</div>;

  const scoreItems = [
    report.score.monetary_policy, report.score.economic_growth, report.score.market_valuation,
    report.score.earnings_momentum, report.score.institutional_consensus, report.score.risk_assessment,
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-text-secondary hover:text-text">&larr;</Link>
        <h1 className="text-2xl font-bold">{report.country.name_local} Market Report</h1>
      </div>

      {/* Error code warnings */}
      {(report as any).errors?.length > 0 && (
        <WarningBanner codes={(report as any).errors} />
      )}

      {/* Market Summary */}
      <div className="card">
        <h2 className="font-semibold mb-3">Market Summary</h2>
        <div className="text-sm leading-relaxed whitespace-pre-line">{report.market_summary}</div>
      </div>

      {/* Score + Fear & Greed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="card lg:col-span-2">
          <div className="flex items-center gap-6 mb-4">
            <ScoreRadial score={report.score.total} label="Total Score" />
            <div className="flex-1">
              <ScoreBreakdown items={scoreItems} />
            </div>
          </div>
        </div>
        <div className="card flex flex-col items-center justify-center">
          <h3 className="font-semibold mb-3">Fear & Greed</h3>
          <FearGreedGauge data={report.fear_greed} />
        </div>
      </div>

      {/* Index Forecast */}
      <div className="card">
        <h2 className="font-semibold mb-3">1-Month Index Forecast</h2>
        <ForecastBand forecast={report.forecast} />
      </div>

      {/* Key News */}
      <div className="card">
        <h2 className="font-semibold mb-3">Key News</h2>
        <div className="space-y-2">
          {report.key_news.slice(0, 8).map((n, i) => (
            <a key={i} href={n.url} target="_blank" rel="noopener noreferrer"
               className="block text-sm hover:text-accent transition-colors">
              <span className="text-text-secondary mr-2">{n.source}</span>
              {n.title}
            </a>
          ))}
        </div>
      </div>

      {/* Institutional Analysis */}
      <div className="card">
        <h2 className="font-semibold mb-3">Institutional Consensus</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <h3 className="text-sm font-medium text-text-secondary mb-2">Policy Institutions</h3>
            {report.institutional_analysis.policy_institutions.map((inst, i) => (
              <div key={i} className="mb-2 text-sm">
                <span className="font-medium">{inst.name}</span>
                <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                  inst.stance === "bullish" ? "bg-positive/20 text-positive" :
                  inst.stance === "bearish" ? "bg-negative/20 text-negative" : "bg-border text-text-secondary"
                }`}>{inst.stance}</span>
                <ul className="mt-1 text-text-secondary">{inst.key_points.map((p, j) => <li key={j}>• {p}</li>)}</ul>
              </div>
            ))}
          </div>
          <div>
            <h3 className="text-sm font-medium text-text-secondary mb-2">Sell-Side</h3>
            {report.institutional_analysis.sell_side.map((inst, i) => (
              <div key={i} className="mb-2 text-sm">
                <span className="font-medium">{inst.name}</span>
                <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                  inst.stance === "bullish" ? "bg-positive/20 text-positive" :
                  inst.stance === "bearish" ? "bg-negative/20 text-negative" : "bg-border text-text-secondary"
                }`}>{inst.stance}</span>
                <ul className="mt-1 text-text-secondary">{inst.key_points.map((p, j) => <li key={j}>• {p}</li>)}</ul>
              </div>
            ))}
          </div>
        </div>
        <p className="text-sm text-text-secondary">{report.institutional_analysis.consensus_summary}</p>
      </div>

      {/* Top 5 Stocks */}
      {report.top_stocks.length > 0 && (
      <div className="card">
        <h2 className="font-semibold mb-3">Top 5 Recommended Stocks</h2>
        <div className="space-y-3">
          {report.top_stocks.map((s) => (
            <Link key={s.ticker} href={`/stock/${s.ticker}`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-border/30 transition-colors">
              <div className="flex items-center gap-3">
                <span className="text-lg font-bold text-accent w-8">#{s.rank}</span>
                <div>
                  <div className="font-medium">{s.name}</div>
                  <div className="text-xs text-text-secondary">{s.ticker}</div>
                </div>
              </div>
              <div className="text-right">
                <div className="font-mono">{s.current_price.toLocaleString()}</div>
                <div className={`text-sm ${changeColor(s.change_pct)}`}>{formatPct(s.change_pct)}</div>
              </div>
              <div className="text-sm text-text-secondary max-w-xs hidden md:block">{s.reason}</div>
            </Link>
          ))}
        </div>
      </div>
      )}

      {/* Sectors */}
      <div className="card">
        <h2 className="font-semibold mb-3">Sectors</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {sectors.map((s) => (
            <Link key={s.id} href={`/country/${code}/sector/${s.id}`}
                  className="p-3 rounded-lg border border-border hover:border-accent/50 transition-colors text-sm">
              <div className="font-medium">{s.name}</div>
              <div className="text-xs text-text-secondary">{s.stock_count} stocks</div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
