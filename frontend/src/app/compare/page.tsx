"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { formatNumber, formatPct, changeColor } from "@/lib/utils";
import ErrorBanner from "@/components/ErrorBanner";

const METRICS: { key: string; label: string; fmt?: "pct" | "num" | "money" }[] = [
  { key: "current_price", label: "Price", fmt: "money" },
  { key: "change_pct", label: "Change %", fmt: "pct" },
  { key: "market_cap", label: "Market Cap", fmt: "money" },
  { key: "pe_ratio", label: "P/E" },
  { key: "pb_ratio", label: "P/B" },
  { key: "ev_ebitda", label: "EV/EBITDA" },
  { key: "roe", label: "ROE", fmt: "pct" },
  { key: "revenue_growth", label: "Revenue Growth", fmt: "pct" },
  { key: "dividend_yield", label: "Dividend Yield", fmt: "pct" },
  { key: "beta", label: "Beta" },
];

function fmtVal(val: unknown, fmt?: string): string {
  if (val == null) return "N/A";
  const n = Number(val);
  if (isNaN(n)) return String(val);
  if (fmt === "pct") return (n * 100).toFixed(2) + "%";
  if (fmt === "money") return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return n.toFixed(2);
}

function bestVal(results: any[], key: string): number | null {
  const vals = results.map((r) => r[key]).filter((v) => v != null && typeof v === "number");
  if (vals.length === 0) return null;
  if (key === "pe_ratio" || key === "beta") return Math.min(...vals);
  return Math.max(...vals);
}

export default function ComparePage() {
  const [input, setInput] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const handleCompare = async () => {
    const tickers = input.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean);
    if (tickers.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.compare(tickers);
      setResults(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
      setError(e);
    }
    setLoading(false);
  };

  const validResults = results.filter((r) => !r.error);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Compare Stocks</h1>

      <div className="flex gap-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCompare()}
          placeholder="Enter tickers (e.g., AAPL, MSFT, GOOGL)"
          className="flex-1 px-4 py-2 rounded-lg bg-surface border border-border text-sm focus:outline-none focus:border-accent"
        />
        <button
          onClick={handleCompare}
          disabled={loading}
          className="px-6 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Loading..." : "Compare"}
        </button>
      </div>

      {error && <ErrorBanner error={error} onRetry={handleCompare} />}

      {results.length > 0 && results.some((r) => r.error) && (
        <div className="text-sm text-warning">
          {results.filter((r) => r.error).map((r) => (
            <div key={r.ticker}>⚠ {r.ticker}: {r.error}</div>
          ))}
        </div>
      )}

      {validResults.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-secondary border-b border-border">
                <th className="pb-2 pr-4">Metric</th>
                {validResults.map((r) => (
                  <th key={r.ticker} className="pb-2 text-right pr-4">
                    <div className="font-bold text-text">{r.ticker}</div>
                    <div className="text-xs font-normal">{r.name}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {METRICS.map((m) => {
                const best = bestVal(validResults, m.key);
                return (
                  <tr key={m.key} className="border-b border-border/30">
                    <td className="py-2.5 pr-4 text-text-secondary">{m.label}</td>
                    {validResults.map((r) => {
                      const val = r[m.key];
                      const isBest = val != null && val === best;
                      return (
                        <td key={r.ticker} className={`py-2.5 text-right pr-4 font-mono ${m.key === "change_pct" ? changeColor(val ?? 0) : ""} ${isBest ? "font-bold text-accent" : ""}`}>
                          {fmtVal(val, m.fmt)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
              <tr className="border-t-2 border-border font-bold">
                <td className="py-3 pr-4">Total Score</td>
                {validResults.map((r) => (
                  <td key={r.ticker} className="py-3 text-right pr-4 text-lg">
                    {r.score?.total?.toFixed(1) ?? "N/A"}
                    <span className="text-xs font-normal text-text-secondary"> / 100</span>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {!loading && results.length === 0 && !error && (
        <div className="card text-center text-text-secondary py-12">
          <p className="text-lg mb-2">Enter 2-4 ticker symbols to compare</p>
          <p className="text-sm">Example: AAPL, MSFT, GOOGL, AMZN</p>
        </div>
      )}
    </div>
  );
}
