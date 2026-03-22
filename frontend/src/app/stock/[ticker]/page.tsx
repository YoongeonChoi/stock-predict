"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import AnalystConsensus from "@/components/charts/AnalystConsensus";
import CandlestickChart from "@/components/charts/CandlestickChart";
import EarningsSurprise from "@/components/charts/EarningsSurprise";
import NextDayForecastCard from "@/components/charts/NextDayForecastCard";
import PriceChart from "@/components/charts/PriceChart";
import ScoreBreakdown from "@/components/charts/ScoreBreakdown";
import ScoreRadial from "@/components/charts/ScoreRadial";
import TechnicalSummary from "@/components/charts/TechnicalSummary";
import ErrorBanner, { WarningBanner } from "@/components/ErrorBanner";
import { api } from "@/lib/api";
import type { CompositeScore, PivotPoints, TechSummary } from "@/lib/api";
import type { PricePoint, StockDetail } from "@/lib/types";
import { changeColor, formatMarketCap, formatPct, formatPrice } from "@/lib/utils";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "Unknown error");
}

export default function StockPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const [stock, setStock] = useState<StockDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [techSummary, setTechSummary] = useState<TechSummary | null>(null);
  const [pivotPoints, setPivotPoints] = useState<PivotPoints | null>(null);
  const [chartPeriod, setChartPeriod] = useState("3mo");
  const [chartType, setChartType] = useState<"line" | "candle">("line");
  const [chartData, setChartData] = useState<PricePoint[]>([]);

  useEffect(() => {
    if (!ticker) return;
    const decodedTicker = decodeURIComponent(ticker);
    setLoading(true);
    setError(null);

    api.getStockDetail(decodedTicker)
      .then(setStock)
      .catch((err) => {
        console.error(err);
        setError(toError(err));
      })
      .finally(() => setLoading(false));

    api.getTechSummary(decodedTicker).then(setTechSummary).catch(console.error);
    api.getPivotPoints(decodedTicker).then(setPivotPoints).catch(console.error);
  }, [ticker]);

  const changeChartPeriod = async (period: string) => {
    if (!ticker) return;
    setChartPeriod(period);
    try {
      const response = await api.getStockChart(decodeURIComponent(ticker), period);
      setChartData(response.data);
    } catch {
      setChartData([]);
    }
  };

  const addToWatchlist = () => {
    if (stock) {
      api.addWatchlist(stock.ticker, stock.country_code).catch(console.error);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-border rounded w-64" />
        <div className="h-72 bg-border rounded" />
        <div className="h-48 bg-border rounded" />
      </div>
    );
  }

  if (!stock && error) {
    return (
      <div className="max-w-5xl mx-auto space-y-4">
        <Link href="/" className="text-text-secondary hover:text-text">&larr; Back</Link>
        <ErrorBanner error={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }

  if (!stock) return <div className="text-text-secondary">Failed to load stock data</div>;

  const defaultDetail = { total: 0, max_score: 0, items: [] };
  const bsg = stock.buy_sell_guide;
  const score = stock.score;
  const scoreCategories = [
    { label: "Fundamental", data: score.fundamental || defaultDetail },
    { label: "Valuation", data: score.valuation || defaultDetail },
    { label: "Growth", data: score.growth_momentum || defaultDetail },
    { label: "Analyst", data: score.analyst || defaultDetail },
    { label: "Risk", data: score.risk || defaultDetail },
  ];

  const composite = (stock as StockDetail & { composite_score?: CompositeScore }).composite_score ?? null;
  const compositeCategories = composite
    ? [
        { label: "Fundamental", data: composite.fundamental, color: "bg-blue-500" },
        { label: "Valuation", data: composite.valuation, color: "bg-purple-500" },
        { label: "Growth", data: composite.growth_momentum, color: "bg-emerald-500" },
        { label: "Analyst", data: composite.analyst, color: "bg-amber-500" },
        { label: "Risk", data: composite.risk, color: "bg-rose-500" },
        { label: "Technical", data: composite.technical, color: "bg-cyan-500" },
      ]
    : [];

  const displayedData = chartData.length > 0 ? chartData : stock.price_history;
  const ma20 = chartData.length === 0 ? stock.technical?.ma_20 : undefined;
  const ma60 = chartData.length === 0 ? stock.technical?.ma_60 : undefined;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-text-secondary hover:text-text">&larr;</Link>
          <div>
            <h1 className="text-2xl font-bold">{stock.name}</h1>
            <span className="text-text-secondary">{stock.ticker} · {stock.sector} · {stock.industry}</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={addToWatchlist} className="text-sm px-4 py-2 rounded-lg border border-border hover:border-accent transition-colors">
            + Watchlist
          </button>
          <div className="text-right">
            <div className="text-2xl font-bold font-mono">{formatPrice(stock.current_price, stock.ticker)}</div>
            <div className={`text-lg ${changeColor(stock.change_pct)}`}>{formatPct(stock.change_pct)}</div>
          </div>
        </div>
      </div>

      {stock.errors && stock.errors.length > 0 ? <WarningBanner codes={stock.errors} /> : null}

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Price Chart</h2>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {[{ label: "1M", value: "1mo" }, { label: "3M", value: "3mo" }, { label: "6M", value: "6mo" }, { label: "1Y", value: "1y" }].map((period) => (
                <button
                  key={period.value}
                  onClick={() => changeChartPeriod(period.value)}
                  className={`px-2 py-0.5 text-xs rounded ${chartPeriod === period.value ? "bg-accent text-white" : "bg-border text-text-secondary hover:text-text"}`}
                >
                  {period.label}
                </button>
              ))}
            </div>
            <div className="flex gap-1 ml-2 border-l border-border pl-2">
              <button
                onClick={() => setChartType("line")}
                className={`px-2 py-0.5 text-xs rounded ${chartType === "line" ? "bg-accent text-white" : "bg-border text-text-secondary hover:text-text"}`}
              >
                Line
              </button>
              <button
                onClick={() => setChartType("candle")}
                className={`px-2 py-0.5 text-xs rounded ${chartType === "candle" ? "bg-accent text-white" : "bg-border text-text-secondary hover:text-text"}`}
              >
                Candle
              </button>
            </div>
          </div>
        </div>

        {chartType === "candle" ? (
          <CandlestickChart data={displayedData} />
        ) : (
          <PriceChart
            data={displayedData}
            ma20={ma20}
            ma60={ma60}
            buyZone={{ low: bsg.buy_zone_low, high: bsg.buy_zone_high }}
            sellZone={{ low: bsg.sell_zone_low, high: bsg.sell_zone_high }}
            fairValue={bsg.fair_value}
            nextDayForecast={stock.next_day_forecast}
          />
        )}

        <div className="flex gap-4 mt-2 text-xs text-text-secondary flex-wrap">
          <span><span className="inline-block w-3 h-0.5 bg-accent mr-1" /> Price</span>
          <span><span className="inline-block w-3 h-0.5 bg-yellow-500 mr-1" /> MA20</span>
          <span><span className="inline-block w-3 h-0.5 bg-purple-500 mr-1" /> MA60</span>
          <span><span className="inline-block w-3 h-0.5 bg-emerald-500 mr-1" /> Forecast</span>
        </div>
      </div>

      {stock.next_day_forecast ? (
        <NextDayForecastCard forecast={stock.next_day_forecast} assetLabel={stock.name} priceKey={stock.ticker} />
      ) : null}

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">Buy / Sell Guide</h2>
          <span className={`text-sm px-3 py-1 rounded-full font-medium ${
            bsg.confidence_grade === "A" ? "bg-emerald-500/20 text-emerald-500" :
            bsg.confidence_grade === "B" ? "bg-yellow-500/20 text-yellow-500" :
            "bg-red-500/20 text-red-500"
          }`}>
            Confidence: {bsg.confidence_grade}
          </span>
        </div>

        <div className="grid grid-cols-5 gap-3 text-center mb-4">
          <div className="p-3 rounded-lg bg-blue-500/10">
            <div className="text-xs text-text-secondary">Buy Low</div>
            <div className="font-bold text-blue-500">{formatPrice(bsg.buy_zone_low, stock.ticker)}</div>
          </div>
          <div className="p-3 rounded-lg bg-blue-500/10">
            <div className="text-xs text-text-secondary">Buy High</div>
            <div className="font-bold text-blue-500">{formatPrice(bsg.buy_zone_high, stock.ticker)}</div>
          </div>
          <div className="p-3 rounded-lg bg-emerald-500/10">
            <div className="text-xs text-text-secondary">Fair Value</div>
            <div className="font-bold text-emerald-500">{formatPrice(bsg.fair_value, stock.ticker)}</div>
          </div>
          <div className="p-3 rounded-lg bg-red-500/10">
            <div className="text-xs text-text-secondary">Sell Low</div>
            <div className="font-bold text-red-500">{formatPrice(bsg.sell_zone_low, stock.ticker)}</div>
          </div>
          <div className="p-3 rounded-lg bg-red-500/10">
            <div className="text-xs text-text-secondary">Sell High</div>
            <div className="font-bold text-red-500">{formatPrice(bsg.sell_zone_high, stock.ticker)}</div>
          </div>
        </div>

        <div className="text-sm text-text-secondary">Risk/Reward Ratio: <strong>{bsg.risk_reward_ratio.toFixed(2)}</strong></div>
        {bsg.methodology.length > 0 ? (
          <div className="mt-3 text-xs text-text-secondary">
            {bsg.methodology.map((method, index) => (
              <div key={index}>
                • {method.name}: {formatPrice(method.value, stock.ticker)} (weight {(method.weight * 100).toFixed(0)}%) — {method.details}
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {techSummary ? (
        <div className="card">
          <h2 className="font-semibold mb-3">Technical Analysis</h2>
          <TechnicalSummary data={techSummary} />
        </div>
      ) : null}

      {pivotPoints ? (
        <div className="card">
          <h2 className="font-semibold mb-3">Pivot Points</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-xs text-text-secondary mb-2">Classic</h4>
              <div className="space-y-1 text-xs">
                {["r3", "r2", "r1", "pivot", "s1", "s2", "s3"].map((key) => (
                  <div key={key} className="flex justify-between">
                    <span className={key.startsWith("r") ? "text-positive" : key.startsWith("s") ? "text-negative" : "font-bold"}>
                      {key.toUpperCase()}
                    </span>
                    <span className="font-mono">{pivotPoints.classic[key as keyof typeof pivotPoints.classic]?.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-xs text-text-secondary mb-2">Fibonacci</h4>
              <div className="space-y-1 text-xs">
                {["r3", "r2", "r1", "pivot", "s1", "s2", "s3"].map((key) => (
                  <div key={key} className="flex justify-between">
                    <span className={key.startsWith("r") ? "text-positive" : key.startsWith("s") ? "text-negative" : "font-bold"}>
                      {key.toUpperCase()}
                    </span>
                    <span className="font-mono">{pivotPoints.fibonacci[key as keyof typeof pivotPoints.fibonacci]?.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {composite ? (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Composite Score</h2>
            <div className="flex items-center gap-3">
              <div className={`text-3xl font-bold ${
                composite.total >= 70 ? "text-positive" : composite.total >= 50 ? "text-warning" : "text-negative"
              }`}>
                {composite.total.toFixed(1)}
              </div>
              <span className="text-xs text-text-secondary">/100</span>
            </div>
          </div>

          <div className="space-y-3 mb-5">
            {compositeCategories.map((category) => (
              <div key={category.label}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium">{category.label}</span>
                  <span className="text-text-secondary">{category.data.total}/{category.data.max_score}</span>
                </div>
                <div className="h-2 bg-border rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${category.color}`}
                    style={{ width: `${(category.data.total / category.data.max_score) * 100}%` }}
                  />
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1">
                  {category.data.items.map((item) => (
                    <div key={item.name} className="flex items-center gap-1 text-[10px] text-text-secondary">
                      <span>{item.name}</span>
                      <span className={`font-mono font-medium ${
                        item.score / item.max_score >= 0.7 ? "text-positive" :
                        item.score / item.max_score >= 0.4 ? "text-warning" :
                        "text-negative"
                      }`}>
                        {item.score.toFixed(1)}/{item.max_score}
                      </span>
                      <span className="opacity-60">({item.description})</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="text-[10px] text-text-secondary border-t border-border pt-2">
            Raw: {composite.total_raw}/{composite.max_raw} (Fundamental 25 + Valuation 20 + Growth 15 + Analyst 20 + Risk 20 + Technical 25 = 125, scaled to 100)
          </div>
        </div>
      ) : null}

      <div className="card">
        <h2 className="font-semibold mb-4">Score Breakdown (Legacy)</h2>
        <div className="flex items-center gap-6 mb-4">
          <ScoreRadial score={score.total || 0} label="Total" />
          <div className="flex gap-3">
            {scoreCategories.map((category) => (
              <ScoreRadial key={category.label} score={category.data.total} max={category.data.max_score} size={80} label={category.label} />
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {scoreCategories.map((category) => (
            <div key={category.label}>
              <h3 className="font-medium text-sm mb-2">{category.label} ({category.data.total}/{category.data.max_score})</h3>
              <ScoreBreakdown items={category.data.items} />
            </div>
          ))}
        </div>
      </div>

      {(stock.analyst_ratings.buy > 0 || stock.analyst_ratings.hold > 0 || stock.analyst_ratings.sell > 0) ? (
        <div className="card">
          <h2 className="font-semibold mb-3">Analyst Consensus</h2>
          <AnalystConsensus
            buy={stock.analyst_ratings.buy}
            hold={stock.analyst_ratings.hold}
            sell={stock.analyst_ratings.sell}
            targetLow={stock.analyst_ratings.target_low ?? null}
            targetMean={stock.analyst_ratings.target_mean ?? null}
            targetHigh={stock.analyst_ratings.target_high ?? null}
            currentPrice={stock.current_price}
          />
        </div>
      ) : null}

      <div className="card">
        <h2 className="font-semibold mb-3">Financials</h2>
        {stock.week52_high && stock.week52_low ? (
          <div className="mb-4">
            <div className="text-xs text-text-secondary mb-1">52-Week Range</div>
            <div className="flex items-center gap-2 text-xs">
              <span className="font-mono">{stock.week52_low.toLocaleString()}</span>
              <div className="flex-1 h-2 bg-border rounded-full relative">
                <div
                  className="absolute top-0 bottom-0 w-1.5 bg-accent rounded-full"
                  style={{
                    left: `${Math.min(100, Math.max(0, ((stock.current_price - stock.week52_low) / Math.max(stock.week52_high - stock.week52_low, 1)) * 100))}%`,
                  }}
                />
              </div>
              <span className="font-mono">{stock.week52_high.toLocaleString()}</span>
            </div>
          </div>
        ) : null}

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
          <div><span className="text-xs text-text-secondary">Market Cap</span><div className="font-bold">{formatMarketCap(stock.market_cap, stock.ticker)}</div></div>
          <div><span className="text-xs text-text-secondary">P/E</span><div className="font-bold">{stock.pe_ratio?.toFixed(1) ?? "N/A"}</div></div>
          <div><span className="text-xs text-text-secondary">P/B</span><div className="font-bold">{stock.pb_ratio?.toFixed(1) ?? "N/A"}</div></div>
          <div><span className="text-xs text-text-secondary">EV/EBITDA</span><div className="font-bold">{stock.ev_ebitda?.toFixed(1) ?? "N/A"}</div></div>
          <div><span className="text-xs text-text-secondary">Dividend</span><div className="font-bold">{stock.dividend.dividend_yield ? `${(stock.dividend.dividend_yield * 100).toFixed(1)}%` : "N/A"}</div></div>
        </div>

        {stock.financials.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-secondary border-b border-border">
                  <th className="pb-1 text-left">Period</th>
                  <th className="pb-1 text-right">Revenue</th>
                  <th className="pb-1 text-right">Op. Income</th>
                  <th className="pb-1 text-right">Net Income</th>
                  <th className="pb-1 text-right">EBITDA</th>
                  <th className="pb-1 text-right">FCF</th>
                </tr>
              </thead>
              <tbody>
                {stock.financials.slice(0, 6).map((financial) => (
                  <tr key={financial.period} className="border-b border-border/30">
                    <td className="py-1">{financial.period}</td>
                    <td className="py-1 text-right font-mono">{formatMarketCap(financial.revenue, stock.ticker)}</td>
                    <td className="py-1 text-right font-mono">{formatMarketCap(financial.operating_income, stock.ticker)}</td>
                    <td className="py-1 text-right font-mono">{formatMarketCap(financial.net_income, stock.ticker)}</td>
                    <td className="py-1 text-right font-mono">{formatMarketCap(financial.ebitda, stock.ticker)}</td>
                    <td className="py-1 text-right font-mono">{formatMarketCap(financial.free_cash_flow, stock.ticker)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      {stock.earnings_history.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-3">Earnings Surprise</h2>
          <EarningsSurprise
            data={stock.earnings_history.map((event) => ({
              date: event.date,
              eps_estimate: event.eps_estimate ?? null,
              eps_actual: event.eps_actual ?? null,
              surprise_pct: event.surprise_pct ?? null,
            }))}
          />
        </div>
      ) : null}

      {stock.analysis_summary ? (
        <div className="card">
          <h2 className="font-semibold mb-3">AI Analysis</h2>
          <div className="text-sm leading-relaxed whitespace-pre-line">{stock.analysis_summary}</div>
          {stock.key_catalysts && stock.key_catalysts.length > 0 ? (
            <div className="mt-4">
              <h3 className="text-sm font-medium text-positive mb-1">Catalysts</h3>
              {stock.key_catalysts.map((catalyst, index) => <div key={index} className="text-sm text-text-secondary">+ {catalyst}</div>)}
            </div>
          ) : null}
          {stock.key_risks && stock.key_risks.length > 0 ? (
            <div className="mt-3">
              <h3 className="text-sm font-medium text-negative mb-1">Risks</h3>
              {stock.key_risks.map((risk, index) => <div key={index} className="text-sm text-text-secondary">- {risk}</div>)}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
