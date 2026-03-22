"use client";

import { useState } from "react";
import Link from "next/link";

import { api } from "@/lib/api";
import type { ScreenerResult } from "@/lib/api";
import { changeColor, formatMarketCap, formatPct, formatPrice } from "@/lib/utils";

export default function ScreenerPage() {
  const [country, setCountry] = useState("KR");
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
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir(sortDir === "desc" ? "asc" : "desc");
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">종목 스크리너</h1>

      <div className="card !p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="text-xs text-text-secondary block mb-1">국가</label>
          <select value={country} onChange={(e) => setCountry(e.target.value)} className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm">
            <option value="KR">KR</option>
            <option value="US">US</option>
            <option value="JP">JP</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">섹터</label>
          <select value={sector} onChange={(e) => setSector(e.target.value)} className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm">
            <option value="">전체 섹터</option>
            {sectors.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">최대 P/E</label>
          <input value={peMax} onChange={(e) => setPeMax(e.target.value)} placeholder="예: 30" className="w-24 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">최소 배당수익률 %</label>
          <input value={divMin} onChange={(e) => setDivMin(e.target.value)} placeholder="예: 2" className="w-24 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <button onClick={search} disabled={loading} className="px-6 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90 disabled:opacity-50">
          {loading ? "검색 중..." : "검색"}
        </button>
      </div>

      {results.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-secondary border-b border-border">
                {[
                  { key: "ticker", label: "티커" },
                  { key: "current_price", label: "현재가" },
                  { key: "change_pct", label: "등락률" },
                  { key: "market_cap", label: "시가총액" },
                  { key: "pe_ratio", label: "P/E" },
                  { key: "dividend_yield", label: "배당 %" },
                  { key: "pct_from_52w_high", label: "52주 고점 대비" },
                ].map((column) => (
                  <th key={column.key} className="pb-2 pr-3 cursor-pointer hover:text-text" onClick={() => toggleSort(column.key)}>
                    {column.label} {sortBy === column.key ? (sortDir === "desc" ? "▼" : "▲") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.map((result) => (
                <tr key={result.ticker} className="border-b border-border/30 hover:bg-border/20">
                  <td className="py-2 pr-3">
                    <Link href={`/stock/${result.ticker}`} className="hover:text-accent">
                      <div className="font-medium">{result.ticker}</div>
                      <div className="text-[10px] text-text-secondary">{result.name}</div>
                    </Link>
                  </td>
                  <td className="py-2 pr-3 font-mono">{formatPrice(result.current_price, result.country_code)}</td>
                  <td className={`py-2 pr-3 ${changeColor(result.change_pct)}`}>{formatPct(result.change_pct)}</td>
                  <td className="py-2 pr-3 font-mono">{formatMarketCap(result.market_cap, result.country_code)}</td>
                  <td className="py-2 pr-3">{result.pe_ratio?.toFixed(1) ?? "없음"}</td>
                  <td className="py-2 pr-3">{result.dividend_yield != null ? `${result.dividend_yield.toFixed(2)}%` : "없음"}</td>
                  <td className={`py-2 pr-3 ${result.pct_from_52w_high > -5 ? "text-positive" : result.pct_from_52w_high < -20 ? "text-negative" : ""}`}>{result.pct_from_52w_high.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {!loading && results.length === 0 ? (
        <div className="card text-center text-text-secondary py-12">
          <p className="text-lg mb-2">조건을 설정해 원하는 종목을 골라보세요</p>
          <p className="text-sm">국가, 섹터, P/E, 배당수익률 기준으로 빠르게 선별할 수 있습니다.</p>
        </div>
      ) : null}
    </div>
  );
}