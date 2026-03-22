"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { PortfolioData } from "@/lib/api";
import { formatPrice, formatPct, changeColor } from "@/lib/utils";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"];

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
      setTicker(""); setBuyPrice(""); setQty("");
      load();
    } catch (e) { console.error(e); }
  };

  const remove = async (id: number) => {
    await api.removePortfolioHolding(id);
    load();
  };

  if (loading) return <div className="animate-pulse space-y-4"><div className="h-8 bg-border rounded w-48" /><div className="h-64 bg-border rounded" /></div>;

  const s = data?.summary;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Portfolio</h1>

      {/* Add Holding */}
      <div className="card !p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="text-xs text-text-secondary block mb-1">Ticker</label>
          <input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="AAPL"
            className="w-24 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">Buy Price</label>
          <input value={buyPrice} onChange={(e) => setBuyPrice(e.target.value)} placeholder="150.00" type="number"
            className="w-24 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">Qty</label>
          <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="10" type="number"
            className="w-20 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">Date</label>
          <input value={buyDate} onChange={(e) => setBuyDate(e.target.value)} type="date"
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">Country</label>
          <select value={countryCode} onChange={(e) => setCountryCode(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm">
            <option value="US">US</option><option value="KR">KR</option><option value="JP">JP</option>
          </select>
        </div>
        <button onClick={addHolding} className="px-6 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90">
          Add
        </button>
      </div>

      {/* Summary */}
      {s && s.holding_count > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="card !p-3 text-center">
            <div className="text-xs text-text-secondary">Invested</div>
            <div className="font-bold font-mono">${s.total_invested.toLocaleString()}</div>
          </div>
          <div className="card !p-3 text-center">
            <div className="text-xs text-text-secondary">Current Value</div>
            <div className="font-bold font-mono">${s.total_current.toLocaleString()}</div>
          </div>
          <div className="card !p-3 text-center">
            <div className="text-xs text-text-secondary">P&L</div>
            <div className={`font-bold font-mono ${changeColor(s.total_pnl)}`}>
              {s.total_pnl >= 0 ? "+" : ""}{s.total_pnl.toLocaleString()}
            </div>
          </div>
          <div className="card !p-3 text-center">
            <div className="text-xs text-text-secondary">Return</div>
            <div className={`font-bold font-mono ${changeColor(s.total_pnl_pct)}`}>
              {formatPct(s.total_pnl_pct)}
            </div>
          </div>
        </div>
      )}

      {/* Allocation Charts */}
      {data && data.allocation.by_sector.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="card">
            <h3 className="font-semibold mb-3 text-sm">Sector Allocation</h3>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={data.allocation.by_sector} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={(e) => e.name.slice(0, 10)}>
                    {data.allocation.by_sector.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="card">
            <h3 className="font-semibold mb-3 text-sm">Country Allocation</h3>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={data.allocation.by_country} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={(e) => e.name}>
                    {data.allocation.by_country.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Holdings Table */}
      {data && data.holdings.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-secondary border-b border-border">
                <th className="pb-2">Stock</th><th className="pb-2 text-right">Buy Price</th>
                <th className="pb-2 text-right">Current</th><th className="pb-2 text-right">Qty</th>
                <th className="pb-2 text-right">P&L</th><th className="pb-2 text-right">Return</th><th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {data.holdings.map((h) => (
                <tr key={h.id} className="border-b border-border/30 hover:bg-border/20">
                  <td className="py-2">
                    <Link href={`/stock/${h.ticker}`} className="hover:text-accent">
                      <div className="font-medium">{h.name}</div>
                      <div className="text-[10px] text-text-secondary">{h.ticker}</div>
                    </Link>
                  </td>
                  <td className="py-2 text-right font-mono">{formatPrice(h.buy_price, h.ticker)}</td>
                  <td className="py-2 text-right font-mono">{formatPrice(h.current_price, h.ticker)}</td>
                  <td className="py-2 text-right">{h.quantity}</td>
                  <td className={`py-2 text-right font-mono ${changeColor(h.pnl)}`}>{h.pnl >= 0 ? "+" : ""}{h.pnl.toLocaleString()}</td>
                  <td className={`py-2 text-right ${changeColor(h.pnl_pct)}`}>{formatPct(h.pnl_pct)}</td>
                  <td className="py-2 text-right">
                    <button onClick={() => remove(h.id)} className="text-xs text-negative hover:underline">Del</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card text-center text-text-secondary py-12">
          <p className="text-lg mb-2">No holdings yet</p>
          <p className="text-sm">Add your first holding above to start tracking your portfolio</p>
        </div>
      )}
    </div>
  );
}
