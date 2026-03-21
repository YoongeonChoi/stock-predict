"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { StockDetail } from "@/lib/types";
import { formatNumber, formatPct, changeColor, scoreColor } from "@/lib/utils";
import ScoreRadial from "@/components/charts/ScoreRadial";
import ScoreBreakdown from "@/components/charts/ScoreBreakdown";
import PriceChart from "@/components/charts/PriceChart";

export default function StockPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const [stock, setStock] = useState<StockDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    api.getStockDetail(decodeURIComponent(ticker)).then(setStock).catch(console.error).finally(() => setLoading(false));
  }, [ticker]);

  const addToWatchlist = () => {
    if (stock) api.addWatchlist(stock.ticker, stock.country_code).catch(console.error);
  };

  if (loading) return <div className="animate-pulse space-y-4"><div className="h-8 bg-border rounded w-64" /><div className="h-72 bg-border rounded" /><div className="h-48 bg-border rounded" /></div>;
  if (!stock) return <div className="text-text-secondary">Failed to load stock data</div>;

  const bsg = stock.buy_sell_guide;
  const scoreCategories = [
    { label: "Fundamental", data: stock.score.fundamental },
    { label: "Valuation", data: stock.score.valuation },
    { label: "Growth", data: stock.score.growth_momentum },
    { label: "Analyst", data: stock.score.analyst },
    { label: "Risk", data: stock.score.risk },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
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
            <div className="text-2xl font-bold font-mono">{formatNumber(stock.current_price)}</div>
            <div className={`text-lg ${changeColor(stock.change_pct)}`}>{formatPct(stock.change_pct)}</div>
          </div>
        </div>
      </div>

      {/* Price Chart */}
      <div className="card">
        <h2 className="font-semibold mb-3">3-Month Price Chart</h2>
        <PriceChart
          data={stock.price_history}
          ma20={stock.technical.ma_20}
          ma60={stock.technical.ma_60}
          buyZone={{ low: bsg.buy_zone_low, high: bsg.buy_zone_high }}
          sellZone={{ low: bsg.sell_zone_low, high: bsg.sell_zone_high }}
          fairValue={bsg.fair_value}
        />
        <div className="flex gap-4 mt-2 text-xs text-text-secondary">
          <span><span className="inline-block w-3 h-0.5 bg-accent mr-1" /> Price</span>
          <span><span className="inline-block w-3 h-0.5 bg-yellow-500 mr-1" /> MA20</span>
          <span><span className="inline-block w-3 h-0.5 bg-purple-500 mr-1" /> MA60</span>
        </div>
      </div>

      {/* Buy/Sell Guide */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">Buy / Sell Guide</h2>
          <span className={`text-sm px-3 py-1 rounded-full font-medium ${
            bsg.confidence_grade === "A" ? "bg-emerald-500/20 text-emerald-500" :
            bsg.confidence_grade === "B" ? "bg-yellow-500/20 text-yellow-500" : "bg-red-500/20 text-red-500"
          }`}>Confidence: {bsg.confidence_grade}</span>
        </div>
        <div className="grid grid-cols-5 gap-3 text-center mb-4">
          <div className="p-3 rounded-lg bg-blue-500/10">
            <div className="text-xs text-text-secondary">Buy Low</div>
            <div className="font-bold text-blue-500">{formatNumber(bsg.buy_zone_low)}</div>
          </div>
          <div className="p-3 rounded-lg bg-blue-500/10">
            <div className="text-xs text-text-secondary">Buy High</div>
            <div className="font-bold text-blue-500">{formatNumber(bsg.buy_zone_high)}</div>
          </div>
          <div className="p-3 rounded-lg bg-emerald-500/10">
            <div className="text-xs text-text-secondary">Fair Value</div>
            <div className="font-bold text-emerald-500">{formatNumber(bsg.fair_value)}</div>
          </div>
          <div className="p-3 rounded-lg bg-red-500/10">
            <div className="text-xs text-text-secondary">Sell Low</div>
            <div className="font-bold text-red-500">{formatNumber(bsg.sell_zone_low)}</div>
          </div>
          <div className="p-3 rounded-lg bg-red-500/10">
            <div className="text-xs text-text-secondary">Sell High</div>
            <div className="font-bold text-red-500">{formatNumber(bsg.sell_zone_high)}</div>
          </div>
        </div>
        <div className="text-sm text-text-secondary">Risk/Reward Ratio: <strong>{bsg.risk_reward_ratio.toFixed(2)}</strong></div>
        {bsg.methodology.length > 0 && (
          <div className="mt-3 text-xs text-text-secondary">
            {bsg.methodology.map((m, i) => (
              <div key={i}>• {m.name}: {formatNumber(m.value)} (weight {(m.weight * 100).toFixed(0)}%) — {m.details}</div>
            ))}
          </div>
        )}
      </div>

      {/* Score Breakdown */}
      <div className="card">
        <div className="flex items-center gap-6 mb-4">
          <ScoreRadial score={stock.score.total} label="Total" />
          <div className="flex gap-3">
            {scoreCategories.map((c) => (
              <ScoreRadial key={c.label} score={c.data.total} max={c.data.max_score} size={80} label={c.label} />
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {scoreCategories.map((c) => (
            <div key={c.label}>
              <h3 className="font-medium text-sm mb-2">{c.label} ({c.data.total}/{c.data.max_score})</h3>
              <ScoreBreakdown items={c.data.items} />
            </div>
          ))}
        </div>
      </div>

      {/* Financials */}
      <div className="card">
        <h2 className="font-semibold mb-3">Financials</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
          <div><span className="text-xs text-text-secondary">Market Cap</span><div className="font-bold">{formatNumber(stock.market_cap)}</div></div>
          <div><span className="text-xs text-text-secondary">P/E</span><div className="font-bold">{stock.pe_ratio?.toFixed(1) ?? "N/A"}</div></div>
          <div><span className="text-xs text-text-secondary">P/B</span><div className="font-bold">{stock.pb_ratio?.toFixed(1) ?? "N/A"}</div></div>
          <div><span className="text-xs text-text-secondary">EV/EBITDA</span><div className="font-bold">{stock.ev_ebitda?.toFixed(1) ?? "N/A"}</div></div>
          <div><span className="text-xs text-text-secondary">Dividend</span><div className="font-bold">{stock.dividend.dividend_yield ? (stock.dividend.dividend_yield * 100).toFixed(1) + "%" : "N/A"}</div></div>
        </div>
        {stock.financials.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-text-secondary border-b border-border">
                <th className="pb-1 text-left">Period</th><th className="pb-1 text-right">Revenue</th>
                <th className="pb-1 text-right">Op. Income</th><th className="pb-1 text-right">Net Income</th>
                <th className="pb-1 text-right">EBITDA</th><th className="pb-1 text-right">FCF</th>
              </tr></thead>
              <tbody>{stock.financials.slice(0, 6).map((f) => (
                <tr key={f.period} className="border-b border-border/30">
                  <td className="py-1">{f.period}</td>
                  <td className="py-1 text-right font-mono">{formatNumber(f.revenue)}</td>
                  <td className="py-1 text-right font-mono">{formatNumber(f.operating_income)}</td>
                  <td className="py-1 text-right font-mono">{formatNumber(f.net_income)}</td>
                  <td className="py-1 text-right font-mono">{formatNumber(f.ebitda)}</td>
                  <td className="py-1 text-right font-mono">{formatNumber(f.free_cash_flow)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>

      {/* Analysis Summary */}
      {stock.analysis_summary && (
        <div className="card">
          <h2 className="font-semibold mb-3">AI Analysis</h2>
          <div className="text-sm leading-relaxed whitespace-pre-line">{stock.analysis_summary}</div>
          {stock.key_catalysts && stock.key_catalysts.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-medium text-positive mb-1">Catalysts</h3>
              {stock.key_catalysts.map((c, i) => <div key={i} className="text-sm text-text-secondary">+ {c}</div>)}
            </div>
          )}
          {stock.key_risks && stock.key_risks.length > 0 && (
            <div className="mt-3">
              <h3 className="text-sm font-medium text-negative mb-1">Risks</h3>
              {stock.key_risks.map((r, i) => <div key={i} className="text-sm text-text-secondary">- {r}</div>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
