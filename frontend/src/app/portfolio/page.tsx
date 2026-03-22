"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

import PortfolioRiskPanel from "@/components/PortfolioRiskPanel";
import { api } from "@/lib/api";
import type { PortfolioData } from "@/lib/api";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

const COLORS = ["#0f766e", "#2563eb", "#f59e0b", "#ef4444", "#7c3aed", "#ec4899", "#0891b2", "#65a30d"];

export default function PortfolioPage() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [ticker, setTicker] = useState("");
  const [buyPrice, setBuyPrice] = useState("");
  const [qty, setQty] = useState("");
  const [buyDate, setBuyDate] = useState(new Date().toISOString().slice(0, 10));
  const [countryCode, setCountryCode] = useState("US");

  const load = () => {
    setLoading(true);
    api.getPortfolio().then(setData).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const addHolding = async () => {
    if (!ticker || !buyPrice || !qty) return;
    try {
      await api.addPortfolioHolding({
        ticker: ticker.toUpperCase(),
        buy_price: Number(buyPrice),
        quantity: Number(qty),
        buy_date: buyDate,
        country_code: countryCode,
      });
      setTicker("");
      setBuyPrice("");
      setQty("");
      load();
    } catch (error) {
      console.error(error);
    }
  };

  const remove = async (id: number) => {
    await api.removePortfolioHolding(id);
    load();
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-border rounded w-48" />
        <div className="h-40 bg-border rounded" />
        <div className="h-64 bg-border rounded" />
      </div>
    );
  }

  const summary = data?.summary;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Portfolio</h1>
        <p className="text-text-secondary mt-1">Track P&L, stress-test the book, and get action-oriented execution guidance per holding.</p>
      </div>

      <div className="card !p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="text-xs text-text-secondary block mb-1">Ticker</label>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="AAPL"
            className="w-24 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">Buy Price</label>
          <input
            value={buyPrice}
            onChange={(e) => setBuyPrice(e.target.value)}
            placeholder="150.00"
            type="number"
            className="w-24 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">Qty</label>
          <input
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            placeholder="10"
            type="number"
            className="w-20 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">Date</label>
          <input
            value={buyDate}
            onChange={(e) => setBuyDate(e.target.value)}
            type="date"
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">Country</label>
          <select
            value={countryCode}
            onChange={(e) => setCountryCode(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm"
          >
            <option value="US">US</option>
            <option value="KR">KR</option>
            <option value="JP">JP</option>
          </select>
        </div>
        <button onClick={addHolding} className="px-6 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90">
          Add
        </button>
      </div>

      {summary && summary.holding_count > 0 && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card !p-3 text-center">
              <div className="text-xs text-text-secondary">Invested</div>
              <div className="font-bold font-mono">${summary.total_invested.toLocaleString()}</div>
            </div>
            <div className="card !p-3 text-center">
              <div className="text-xs text-text-secondary">Current Value</div>
              <div className="font-bold font-mono">${summary.total_current.toLocaleString()}</div>
            </div>
            <div className="card !p-3 text-center">
              <div className="text-xs text-text-secondary">P&amp;L</div>
              <div className={`font-bold font-mono ${changeColor(summary.total_pnl)}`}>
                {summary.total_pnl >= 0 ? "+" : ""}{summary.total_pnl.toLocaleString()}
              </div>
            </div>
            <div className="card !p-3 text-center">
              <div className="text-xs text-text-secondary">Return</div>
              <div className={`font-bold font-mono ${changeColor(summary.total_pnl_pct)}`}>{formatPct(summary.total_pnl_pct)}</div>
            </div>
          </div>

          <PortfolioRiskPanel risk={data!.risk} stressTest={data!.stress_test} />
        </>
      )}

      {data && data.allocation.by_sector.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="card">
            <h3 className="font-semibold mb-3 text-sm">Sector Allocation</h3>
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.allocation.by_sector}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={84}
                    label={(entry) => entry.name.slice(0, 10)}
                  >
                    {data.allocation.by_sector.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(value: number) => `$${value.toLocaleString()}`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="card">
            <h3 className="font-semibold mb-3 text-sm">Country Allocation</h3>
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.allocation.by_country}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={84}
                    label={(entry) => entry.name}
                  >
                    {data.allocation.by_country.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(value: number) => `$${value.toLocaleString()}`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {data && data.holdings.length > 0 ? (
        <div className="card !p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="font-semibold">Holdings Intelligence</h2>
            <p className="text-xs text-text-secondary mt-1">Each row combines live P&amp;L, position risk, next-session bias, and the preferred execution action.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[1080px]">
              <thead>
                <tr className="text-left text-text-secondary border-b border-border bg-surface/40">
                  <th className="px-4 py-3">Stock</th>
                  <th className="px-4 py-3 text-right">Weight</th>
                  <th className="px-4 py-3 text-right">Current</th>
                  <th className="px-4 py-3 text-right">P&amp;L</th>
                  <th className="px-4 py-3 text-right">Risk</th>
                  <th className="px-4 py-3 text-right">Forecast</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3 text-right">Levels</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {data.holdings.map((holding) => (
                  <tr key={holding.id} className="border-b border-border/30 align-top hover:bg-border/10">
                    <td className="px-4 py-3">
                      <Link href={`/stock/${holding.ticker}`} className="hover:text-accent">
                        <div className="font-medium">{holding.name}</div>
                        <div className="text-[11px] text-text-secondary">{holding.ticker} • {holding.country_code} • {holding.sector}</div>
                      </Link>
                      {holding.market_regime_label ? (
                        <div className="text-[11px] text-text-secondary mt-1">{holding.market_regime_label}</div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="font-semibold">{holding.weight_pct.toFixed(1)}%</div>
                      <div className="text-[11px] text-text-secondary mt-1">{holding.quantity} shares</div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      <div>{formatPrice(holding.current_price, holding.ticker)}</div>
                      <div className="text-[11px] text-text-secondary mt-1">Avg {formatPrice(holding.buy_price, holding.ticker)}</div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className={`font-mono font-semibold ${changeColor(holding.pnl)}`}>
                        {holding.pnl >= 0 ? "+" : ""}{holding.pnl.toLocaleString()}
                      </div>
                      <div className={`text-[11px] mt-1 ${changeColor(holding.pnl_pct)}`}>{formatPct(holding.pnl_pct)}</div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className={`font-semibold ${
                        holding.risk_level === "high" ? "text-red-500" : holding.risk_level === "medium" ? "text-yellow-500" : "text-emerald-500"
                      }`}>
                        {holding.risk_level.toUpperCase()}
                      </div>
                      <div className="text-[11px] text-text-secondary mt-1">
                        Score {holding.risk_score.toFixed(1)} • Vol {holding.realized_volatility_pct.toFixed(1)}%
                      </div>
                      <div className="text-[11px] text-text-secondary mt-1">
                        DD {holding.max_drawdown_pct.toFixed(1)}%{holding.beta != null ? ` • β ${holding.beta.toFixed(2)}` : ""}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className={`font-semibold ${changeColor(holding.predicted_return_pct ?? 0)}`}>
                        {holding.predicted_return_pct != null ? formatPct(holding.predicted_return_pct) : "N/A"}
                      </div>
                      <div className="text-[11px] text-text-secondary mt-1">
                        {holding.up_probability != null ? `${holding.up_probability.toFixed(1)}% up odds` : "No forecast"}
                      </div>
                      <div className="text-[11px] text-text-secondary mt-1">{holding.forecast_date ?? ""}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-semibold capitalize">{holding.trade_action?.replace("_", " ") || "observe"}</div>
                      <div className="text-[11px] text-text-secondary mt-1">{holding.trade_setup || "No execution setup"}</div>
                      {holding.thesis.length > 0 ? (
                        <div className="text-[11px] text-text-secondary mt-2 max-w-[220px]">{holding.thesis[0]}</div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="text-[11px] text-text-secondary">Entry</div>
                      <div className="font-mono text-xs">
                        {holding.entry_low != null && holding.entry_high != null
                          ? `${holding.entry_low.toFixed(2)} - ${holding.entry_high.toFixed(2)}`
                          : "-"}
                      </div>
                      <div className="text-[11px] text-text-secondary mt-2">Stop / TP1</div>
                      <div className="font-mono text-xs">
                        {holding.stop_loss != null ? holding.stop_loss.toFixed(2) : "-"} / {holding.take_profit_1 != null ? holding.take_profit_1.toFixed(2) : "-"}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => remove(holding.id)} className="text-xs text-negative hover:underline">
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="card text-center text-text-secondary py-12">
          <p className="text-lg mb-2">No holdings yet</p>
          <p className="text-sm">Add your first holding above to unlock portfolio analytics, risk coaching, and scenario testing.</p>
        </div>
      )}
    </div>
  );
}
