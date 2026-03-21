"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function ComparePage() {
  const [input, setInput] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const handleCompare = async () => {
    const tickers = input.split(",").map((t) => t.trim()).filter(Boolean);
    if (tickers.length < 2) return;
    setLoading(true);
    try {
      const data = await api.compare(tickers);
      setResults(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Compare Stocks</h1>

      <div className="flex gap-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter tickers (e.g., AAPL,MSFT,GOOGL)"
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

      {results.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-secondary border-b border-border">
                <th className="pb-2">Metric</th>
                {results.map((r: any) => (
                  <th key={r.ticker} className="pb-2 text-right">{r.ticker}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {["current_price", "change_pct", "market_cap", "pe_ratio", "pb_ratio", "ev_ebitda", "roe", "revenue_growth", "dividend_yield", "beta"].map((metric) => (
                <tr key={metric} className="border-b border-border/30">
                  <td className="py-2 text-text-secondary">{metric.replace(/_/g, " ")}</td>
                  {results.map((r: any) => (
                    <td key={r.ticker} className="py-2 text-right font-mono">
                      {r[metric] != null ? (typeof r[metric] === "number" ? r[metric].toLocaleString(undefined, { maximumFractionDigits: 2 }) : r[metric]) : "N/A"}
                    </td>
                  ))}
                </tr>
              ))}
              <tr className="border-b border-border font-bold">
                <td className="py-2">Total Score</td>
                {results.map((r: any) => (
                  <td key={r.ticker} className="py-2 text-right">{r.score?.total?.toFixed(1) ?? "N/A"}</td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
