"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import ErrorBanner, { WarningBanner } from "@/components/ErrorBanner";
import FearGreedGauge from "@/components/charts/FearGreedGauge";
import ForecastBand from "@/components/charts/ForecastBand";
import NextDayForecastCard from "@/components/charts/NextDayForecastCard";
import MarketRegimeCard from "@/components/MarketRegimeCard";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import PriceChart from "@/components/charts/PriceChart";
import ScoreBreakdown from "@/components/charts/ScoreBreakdown";
import ScoreRadial from "@/components/charts/ScoreRadial";
import { api } from "@/lib/api";
import type { CountryReport, OpportunityRadarResponse, ScoreItem, SectorListItem } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "Unknown error");
}

export default function CountryPage() {
  const { code } = useParams<{ code: string }>();
  const [report, setReport] = useState<CountryReport | null>(null);
  const [sectors, setSectors] = useState<SectorListItem[]>([]);
  const [opportunities, setOpportunities] = useState<OpportunityRadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!code) return;
    setLoading(true);
    setError(null);

    const loadReport = api.getCountryReport(code)
      .then(setReport)
      .catch((err) => {
        console.error(err);
        setError(toError(err));
      });

    const loadSectors = api.getSectors(code).then(setSectors).catch(console.error);
    const loadOpportunities = api.getMarketOpportunities(code, 8).then(setOpportunities).catch(console.error);

    Promise.all([loadReport, loadSectors, loadOpportunities]).finally(() => setLoading(false));
  }, [code]);

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-border rounded w-48" />
        <div className="h-96 bg-border rounded" />
      </div>
    );
  }

  if (!report && error) {
    return (
      <div className="max-w-5xl mx-auto space-y-4">
        <Link href="/" className="text-text-secondary hover:text-text">&larr; Back</Link>
        <ErrorBanner error={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }

  if (!report) return <div className="text-text-secondary">Failed to load report</div>;

  const defaultScore: ScoreItem = { name: "", score: 0, max_score: 0, description: "" };
  const score = report.score;
  const scoreItems = [
    score.monetary_policy || defaultScore,
    score.economic_growth || defaultScore,
    score.market_valuation || defaultScore,
    score.earnings_momentum || defaultScore,
    score.institutional_consensus || defaultScore,
    score.risk_assessment || defaultScore,
  ];
  const institutions = report.institutional_analysis;
  const news = report.key_news || [];
  const topStocks = report.top_stocks || [];
  const primaryIndex = report.country.indices?.[0];
  const priceKey = primaryIndex?.ticker ?? code ?? "US";

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-text-secondary hover:text-text">&larr;</Link>
          <h1 className="text-2xl font-bold">{report.country?.name_local || report.country?.name || "Report"} Market Report</h1>
        </div>
        <div className="flex gap-2 shrink-0">
          <a
            href={`/api/country/${code}/report/pdf`}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:opacity-90 transition-opacity"
          >
            PDF
          </a>
          <a
            href={`/api/country/${code}/report/csv`}
            className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:border-accent/50 transition-colors"
          >
            CSV
          </a>
        </div>
      </div>

      {report.errors && report.errors.length > 0 ? <WarningBanner codes={report.errors} /> : null}

      <div className="card">
        <h2 className="font-semibold mb-3">Market Summary</h2>
        <div className="text-sm leading-relaxed whitespace-pre-line">{report.market_summary || "No summary available."}</div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="card lg:col-span-2">
          <div className="flex items-center gap-6 mb-4">
            <ScoreRadial score={score.total || 0} label="Total Score" />
            <div className="flex-1">
              <ScoreBreakdown items={scoreItems} />
            </div>
          </div>
        </div>
        {report.fear_greed ? (
          <div className="card flex flex-col items-center justify-center">
            <h3 className="font-semibold mb-3">Fear & Greed</h3>
            <FearGreedGauge data={report.fear_greed} />
          </div>
        ) : null}
      </div>

      {report.primary_index_history && report.primary_index_history.length > 0 ? (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="font-semibold">{primaryIndex?.name || "Primary Index"} Chart</h2>
              <p className="text-xs text-text-secondary mt-1">
                {primaryIndex?.ticker} · latest {formatPrice(report.next_day_forecast?.reference_price, priceKey)}
              </p>
            </div>
          </div>
          <PriceChart
            data={report.primary_index_history}
            nextDayForecast={report.next_day_forecast}
          />
          <div className="flex gap-4 mt-2 text-xs text-text-secondary flex-wrap">
            <span><span className="inline-block w-3 h-0.5 bg-accent mr-1" /> Price</span>
            <span><span className="inline-block w-3 h-0.5 bg-emerald-500 mr-1" /> Forecast</span>
          </div>
        </div>
      ) : null}

      {report.next_day_forecast ? (
        <NextDayForecastCard
          forecast={report.next_day_forecast}
          assetLabel={primaryIndex?.name || report.country?.name || "Index"}
          priceKey={priceKey}
        />
      ) : null}

      {report.market_regime ? (
        <MarketRegimeCard
          regime={report.market_regime}
          title={`${primaryIndex?.name || report.country?.name || "Market"} Regime`}
        />
      ) : null}

      {report.forecast && report.forecast.scenarios?.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-3">1-Month Index Forecast</h2>
          <ForecastBand forecast={report.forecast} />
        </div>
      ) : null}

      {opportunities ? <OpportunityRadarBoard data={opportunities} compact /> : null}

      {news.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-3">Key News</h2>
          <div className="space-y-2">
            {news.slice(0, 8).map((item, index) => (
              <a
                key={index}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block text-sm hover:text-accent transition-colors"
              >
                <span className="text-text-secondary mr-2">{item.source}</span>
                {item.title}
              </a>
            ))}
          </div>
        </div>
      ) : null}

      {(institutions.policy_institutions?.length > 0 || institutions.sell_side?.length > 0) ? (
        <div className="card">
          <h2 className="font-semibold mb-3">Institutional Consensus</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <h3 className="text-sm font-medium text-text-secondary mb-2">Policy Institutions</h3>
              {institutions.policy_institutions.map((institution, index) => (
                <div key={index} className="mb-2 text-sm">
                  <span className="font-medium">{institution.name}</span>
                  <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                    institution.stance === "bullish" ? "bg-positive/20 text-positive" :
                    institution.stance === "bearish" ? "bg-negative/20 text-negative" :
                    "bg-border text-text-secondary"
                  }`}>
                    {institution.stance}
                  </span>
                  <ul className="mt-1 text-text-secondary">
                    {institution.key_points.map((point, pointIndex) => <li key={pointIndex}>• {point}</li>)}
                  </ul>
                </div>
              ))}
            </div>
            <div>
              <h3 className="text-sm font-medium text-text-secondary mb-2">Sell-Side</h3>
              {institutions.sell_side.map((institution, index) => (
                <div key={index} className="mb-2 text-sm">
                  <span className="font-medium">{institution.name}</span>
                  <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                    institution.stance === "bullish" ? "bg-positive/20 text-positive" :
                    institution.stance === "bearish" ? "bg-negative/20 text-negative" :
                    "bg-border text-text-secondary"
                  }`}>
                    {institution.stance}
                  </span>
                  <ul className="mt-1 text-text-secondary">
                    {institution.key_points.map((point, pointIndex) => <li key={pointIndex}>• {point}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          </div>
          {institutions.consensus_summary ? <p className="text-sm text-text-secondary">{institutions.consensus_summary}</p> : null}
        </div>
      ) : null}

      {topStocks.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-3">Top 5 Recommended Stocks</h2>
          <div className="space-y-3">
            {topStocks.map((stock) => (
              <Link
                key={stock.ticker}
                href={`/stock/${stock.ticker}`}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-border/30 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="flex flex-col items-center w-12 shrink-0">
                    <span className="text-lg font-bold text-accent">#{stock.rank}</span>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                      stock.score >= 70 ? "bg-positive/20 text-positive" :
                      stock.score >= 50 ? "bg-warning/20 text-warning" :
                      "bg-negative/20 text-negative"
                    }`}>
                      {stock.score.toFixed(1)}pt
                    </span>
                  </div>
                  <div>
                    <div className="font-medium">{stock.name}</div>
                    <div className="text-xs text-text-secondary">{stock.ticker}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono">{formatPrice(stock.current_price, code ?? "US")}</div>
                  <div className={`text-sm ${changeColor(stock.change_pct)}`}>{formatPct(stock.change_pct)}</div>
                </div>
                <div className="text-sm text-text-secondary max-w-xs hidden md:block">{stock.reason}</div>
              </Link>
            ))}
          </div>
        </div>
      ) : null}

      <div className="card">
        <h2 className="font-semibold mb-3">Sectors</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {sectors.map((sector) => (
            <Link
              key={sector.id}
              href={`/country/${code}/sector/${sector.id}`}
              className="p-3 rounded-lg border border-border hover:border-accent/50 transition-colors text-sm"
            >
              <div className="font-medium">{sector.name}</div>
              <div className="text-xs text-text-secondary">{sector.stock_count} stocks</div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
