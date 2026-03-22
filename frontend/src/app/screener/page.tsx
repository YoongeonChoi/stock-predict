"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ScreenerResult, ScreenerResponse } from "@/lib/api";
import { formatPrice, formatMarketCap, formatPct, changeColor } from "@/lib/utils";

export default function ScreenerPage() {
  const [country, setCountry] = useState("US");
  const [sector, setSector] = useState("");
  const [peMax, setPeMax] = useState("");
  const [divMin, setDivMin] = useState("");
  const [results, setResults] = useState<ScreenerResult[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy] = useState("market_cap");
  const [sortDir, setSortDir] = useState("desc");

  const search = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { country, sort_by: sortBy, sort_dir: sortDir, limit: "100" };
      if (sector) params.sector = sector;
      if (peMax) params.pe_max = peMax;
      if (divMin) params.dividend_yield_min = String(Number(divMin) / 100);
      const data = await api.getScreener(params);
      setResults(data.results);
      setSectors(data.sectors);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) setSortDir(sortDir === "desc" ? "asc" : "desc");
    else { setSortBy(field); setSortDir("desc"); }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Stock Screener</h1>

      <div className="card !p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="text-xs text-text-secondary block mb-1">Country</label>
          <select value={country} onChange={(e) => setCountry(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm">
            <option value="US">US</option>
            <option value="KR">KR</option>
            <option value="JP">JP</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">Sector</label>
          <select value={sector} onChange={(e) => setSector(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm">
            <option value="">All Sectors</option>
            {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">P/E Max</label>
          <input value={peMax} onChange={(e) => setPeMax(e.target.value)}
            placeholder="e.g. 30" className="w-20 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">Div Yield Min %</label>
          <input value={divMin} onChange={(e) => setDivMin(e.target.value)}
            placeholder="e.g. 2" className="w-20 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <button onClick={search} disabled={loading}
          className="px-6 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90 disabled:opacity-50">
          {loading ? "Searching..." : "Screen"}
        </button>
      </div>

      {results.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-secondary border-b border-border">
                {[
                  { key: "ticker", label: "Ticker" },
                  { key: "current_price", label: "Price" },
                  { key: "change_pct", label: "Change" },
                  { key: "market_cap", label: "Market Cap" },
                  { key: "pe_ratio", label: "P/E" },
                  { key: "dividend_yield", label: "Div %" },
                  { key: "pct_from_52w_high", label: "vs 52W H" },
                ].map((col) => (
                  <th key={col.key} className="pb-2 pr-3 cursor-pointer hover:text-text" onClick={() => toggleSort(col.key)}>
                    {col.label} {sortBy === col.key ? (sortDir === "desc" ? "↓" : "↑") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.ticker} className="border-b border-border/30 hover:bg-border/20">
                  <td className="py-2 pr-3">
                    <Link href={`/stock/${r.ticker}`} className="hover:text-accent">
                      <div className="font-medium">{r.ticker}</div>
                      <div className="text-[10px] text-text-secondary">{r.name}</div>
                    </Link>
                  </td>
                  <td className="py-2 pr-3 font-mono">{formatPrice(r.current_price, r.country_code)}</td>
                  <td className={`py-2 pr-3 ${changeColor(r.change_pct)}`}>{formatPct(r.change_pct)}</td>
                  <td className="py-2 pr-3 font-mono">{formatMarketCap(r.market_cap, r.country_code)}</td>
                  <td className="py-2 pr-3">{r.pe_ratio?.toFixed(1) ?? "—"}</td>
                  <td className="py-2 pr-3">{r.dividend_yield != null ? r.dividend_yield.toFixed(2) + "%" : "—"}</td>
                  <td className={`py-2 pr-3 ${r.pct_from_52w_high > -5 ? "text-positive" : r.pct_from_52w_high < -20 ? "text-negative" : ""}`}>
                    {r.pct_from_52w_high.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && results.length === 0 && (
        <div className="card text-center text-text-secondary py-12">
          <p className="text-lg mb-2">Configure filters and click Screen</p>
          <p className="text-sm">Filter stocks by country, sector, P/E, dividend yield, and more</p>
        </div>
      )}
    </div>
  );
}
