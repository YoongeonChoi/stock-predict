"use client";

import { useState } from "react";

import ErrorBanner from "@/components/ErrorBanner";
import { api } from "@/lib/api";
import { changeColor, formatMarketCap, formatPct, formatPrice } from "@/lib/utils";

const METRICS: { key: string; label: string; fmt?: "pct" | "ratio_pct" | "num" | "money" | "cap" }[] = [
  { key: "current_price", label: "현재가", fmt: "money" },
  { key: "change_pct", label: "등락률", fmt: "pct" },
  { key: "market_cap", label: "시가총액", fmt: "cap" },
  { key: "pe_ratio", label: "P/E" },
  { key: "pb_ratio", label: "P/B" },
  { key: "ev_ebitda", label: "EV/EBITDA" },
  { key: "roe", label: "ROE", fmt: "ratio_pct" },
  { key: "revenue_growth", label: "매출 성장률", fmt: "ratio_pct" },
  { key: "dividend_yield", label: "배당수익률", fmt: "ratio_pct" },
  { key: "beta", label: "베타" },
];

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "알 수 없는 오류가 발생했습니다.");
}

function fmtVal(value: unknown, fmt?: string, ticker?: string): string {
  if (value == null) return "없음";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  if (fmt === "pct") return formatPct(number);
  if (fmt === "ratio_pct") return `${(number * 100).toFixed(2)}%`;
  if (fmt === "money") return formatPrice(number, ticker ?? "US");
  if (fmt === "cap") return formatMarketCap(number, ticker ?? "US");
  return number.toFixed(2);
}

function bestVal(results: any[], key: string): number | null {
  const values = results.map((result) => result[key]).filter((value) => value != null && typeof value === "number");
  if (values.length === 0) return null;
  if (["pe_ratio", "beta", "pb_ratio"].includes(key)) return Math.min(...values);
  return Math.max(...values);
}

export default function ComparePage() {
  const [input, setInput] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const handleCompare = async () => {
    const tickers = input.split(",").map((ticker) => ticker.trim().toUpperCase()).filter(Boolean);
    if (tickers.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.compare(tickers);
      setResults(Array.isArray(data) ? data : []);
    } catch (caught) {
      console.error(caught);
      setError(toError(caught));
    } finally {
      setLoading(false);
    }
  };

  const validResults = results.filter((result) => !result.error);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">종목 비교</h1>

      <div className="flex gap-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCompare()}
          placeholder="비교할 티커를 쉼표로 입력하세요. 예: AAPL, MSFT, GOOGL"
          className="flex-1 px-4 py-2 rounded-lg bg-surface border border-border text-sm focus:outline-none focus:border-accent"
        />
        <button onClick={handleCompare} disabled={loading} className="px-6 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90 disabled:opacity-50">
          {loading ? "불러오는 중..." : "비교"}
        </button>
      </div>

      {error ? <ErrorBanner error={error} onRetry={handleCompare} /> : null}

      {results.length > 0 && results.some((result) => result.error) ? (
        <div className="text-sm text-warning space-y-1">
          {results.filter((result) => result.error).map((result) => (
            <div key={result.ticker}>제외됨 {result.ticker}: {result.error}</div>
          ))}
        </div>
      ) : null}

      {validResults.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-secondary border-b border-border">
                <th className="pb-2 pr-4">항목</th>
                {validResults.map((result) => (
                  <th key={result.ticker} className="pb-2 text-right pr-4">
                    <div className="font-bold text-text">{result.ticker}</div>
                    <div className="text-xs font-normal">{result.name}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {METRICS.map((metric) => {
                const best = bestVal(validResults, metric.key);
                return (
                  <tr key={metric.key} className="border-b border-border/30">
                    <td className="py-2.5 pr-4 text-text-secondary">{metric.label}</td>
                    {validResults.map((result) => {
                      const value = result[metric.key];
                      const isBest = value != null && value === best;
                      return (
                        <td key={result.ticker} className={`py-2.5 text-right pr-4 font-mono ${metric.key === "change_pct" ? changeColor(value ?? 0) : ""} ${isBest ? "font-bold text-accent" : ""}`}>
                          {fmtVal(value, metric.fmt, result.ticker)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
              <tr className="border-t-2 border-border font-bold">
                <td className="py-3 pr-4">종합 점수</td>
                {validResults.map((result) => (
                  <td key={result.ticker} className="py-3 text-right pr-4 text-lg">
                    {result.score?.total?.toFixed(1) ?? "없음"}
                    <span className="text-xs font-normal text-text-secondary"> / 100</span>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      ) : null}

      {!loading && results.length === 0 && !error ? (
        <div className="card text-center text-text-secondary py-12">
          <p className="text-lg mb-2">2개에서 4개 종목까지 한 번에 비교할 수 있습니다</p>
          <p className="text-sm">예시: AAPL, MSFT, GOOGL, AMZN</p>
        </div>
      ) : null}
    </div>
  );
}