"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import ErrorBanner from "@/components/ErrorBanner";
import PageHeader from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { api } from "@/lib/api";
import { changeColor, cn, formatMarketCap, formatPct, formatPrice } from "@/lib/utils";

type CompareMetric = {
  key: string;
  label: string;
  fmt?: "pct" | "ratio_pct" | "num" | "money" | "cap";
};

const METRICS: CompareMetric[] = [
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

function formatValue(value: unknown, fmt?: CompareMetric["fmt"], ticker?: string): string {
  if (value == null) return "없음";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  if (fmt === "pct") return formatPct(number);
  if (fmt === "ratio_pct") return `${(number * 100).toFixed(2)}%`;
  if (fmt === "money") return formatPrice(number, ticker ?? "KR");
  if (fmt === "cap") return formatMarketCap(number, ticker ?? "KR");
  return number.toFixed(2);
}

function bestValue(results: Array<Record<string, unknown>>, key: string): number | null {
  const values = results
    .map((result) => result[key])
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (values.length === 0) return null;
  if (["pe_ratio", "beta", "pb_ratio"].includes(key)) return Math.min(...values);
  return Math.max(...values);
}

interface CompareResult {
  ticker: string;
  name?: string;
  error?: string;
  current_price?: number;
  change_pct?: number;
  market_cap?: number;
  pe_ratio?: number;
  pb_ratio?: number;
  ev_ebitda?: number;
  roe?: number;
  revenue_growth?: number;
  dividend_yield?: number;
  beta?: number;
  score?: { total?: number };
  [key: string]: unknown;
}

export default function ComparePage() {
  const searchParams = useSearchParams();
  const [input, setInput] = useState(searchParams.get("tickers") ?? "");
  const [results, setResults] = useState<CompareResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const { toast } = useToast();

  const autoComparedRef = useRef(false);
  useEffect(() => {
    if (autoComparedRef.current) return;
    const tickersParam = searchParams.get("tickers");
    if (tickersParam && tickersParam.includes(",")) {
      autoComparedRef.current = true;
      handleCompare();
    }
  }, []);

  const handleCompare = async () => {
    const tickers = input
      .split(",")
      .map((ticker) => ticker.trim().toUpperCase())
      .filter(Boolean);
    if (tickers.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.compare(tickers);
      setResults(Array.isArray(data) ? (data as CompareResult[]) : []);
      const url = new URL(window.location.href);
      url.searchParams.set("tickers", tickers.join(","));
      window.history.replaceState(null, "", url.toString());
    } catch (caught) {
      setError(toError(caught));
    } finally {
      setLoading(false);
    }
  };

  const handleShareLink = () => {
    const tickers = input.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean);
    if (tickers.length < 2) return;
    const url = new URL(window.location.href);
    url.searchParams.set("tickers", tickers.join(","));
    navigator.clipboard.writeText(url.toString()).then(() => {
      toast("비교 링크가 클립보드에 복사되었습니다.", "success");
    }).catch(() => {
      toast("링크 복사에 실패했습니다.", "error");
    });
  };

  const validResults = results.filter((result) => !result.error);
  const failedResults = results.filter((result) => result.error);

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="시장 탐색"
        title="종목 비교"
        description="종목 2~4개 나란히 비교하면서 가격, 밸류에이션, 성장 지표, 종합 점수를 같은 축에서 한 번에 봅니다."
        meta={
          <>
            <span className="status-token">2-4개 종목</span>
            <span className="status-token">공통 지표 정렬</span>
          </>
        }
      />

      <section className="card !p-5 space-y-4">
        <div className="section-heading">
          <div>
            <h2 className="section-title">비교할 종목 입력</h2>
            <p className="section-copy">
              쉼표로 구분해 입력하면 같은 축에서 바로 비교합니다. 예시: `005930, 000660, 035420`
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3 md:flex-row">
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && handleCompare()}
            placeholder="비교할 종목을 쉼표로 입력해 주세요"
            className="ui-input flex-1"
            aria-label="비교할 종목 입력"
          />
          <button onClick={handleCompare} disabled={loading} className="ui-button-primary px-6">
            {loading ? "불러오는 중..." : "비교 시작"}
          </button>
          {validResults.length > 0 ? (
            <button onClick={handleShareLink} className="ui-button-secondary px-4">
              링크 복사
            </button>
          ) : null}
        </div>
      </section>

      {error ? <ErrorBanner error={error} onRetry={handleCompare} /> : null}

      {failedResults.length > 0 ? (
        <section className="ui-panel-warning !p-4 space-y-2 text-sm">
          {failedResults.map((result) => (
            <div key={result.ticker}>
              제외됨 {result.ticker}: {result.error}
            </div>
          ))}
        </section>
      ) : null}

      {validResults.length > 0 ? (
        <section className="card !p-5 space-y-4">
          <div className="section-heading">
            <div>
              <h2 className="section-title">비교 결과</h2>
              <p className="section-copy">
                종목 2~4개 나란히 비교하면서 같은 지표를 오른쪽 정렬과 mono 숫자로 읽기 쉽게 정리했습니다.
              </p>
            </div>
          </div>

          <div className="space-y-3 md:hidden">
            {validResults.map((result) => (
              <article key={result.ticker} className="ui-panel space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-semibold text-text">{result.name}</div>
                    <div className="mt-1 font-mono text-[0.8rem] text-text-secondary">{result.ticker}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[0.74rem] uppercase tracking-[0.14em] text-text-secondary">종합 점수</div>
                    <div className="mt-1 font-mono text-lg font-semibold text-text">
                      {result.score?.total?.toFixed(1) ?? "없음"}
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 text-[0.9rem]">
                  {METRICS.slice(0, 6).map((metric) => (
                    <div key={`${result.ticker}-${metric.key}`}>
                      <div className="text-[0.74rem] uppercase tracking-[0.14em] text-text-secondary">{metric.label}</div>
                      <div
                        className={cn(
                          "mt-1 font-mono font-medium",
                          metric.key === "change_pct" ? changeColor(Number(result[metric.key] ?? 0)) : "text-text",
                        )}
                      >
                        {formatValue(result[metric.key], metric.fmt, result.ticker)}
                      </div>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>

          <div className="hidden md:block ui-table-shell">
            <table>
              <thead>
                <tr className="border-b border-border/10 text-left text-text-secondary">
                  <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-[0.12em]">항목</th>
                  {validResults.map((result) => (
                    <th key={result.ticker} className="px-4 py-3 text-right">
                      <div className="font-mono text-[0.9rem] font-semibold text-text">{result.ticker}</div>
                      <div className="mt-1 text-xs font-normal text-text-secondary">{result.name}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {METRICS.map((metric) => {
                  const best = bestValue(validResults, metric.key);
                  return (
                    <tr key={metric.key} className="border-b border-border/10 last:border-b-0">
                      <td className="px-4 py-3 text-text-secondary">{metric.label}</td>
                      {validResults.map((result) => {
                        const value = result[metric.key];
                        const isBest = value != null && value === best;
                        return (
                          <td
                            key={result.ticker}
                            className={cn(
                              "px-4 py-3 text-right font-mono",
                              metric.key === "change_pct" ? changeColor(Number(value ?? 0)) : "text-text",
                              isBest ? "font-semibold text-accent" : "",
                            )}
                          >
                            {formatValue(value, metric.fmt, result.ticker)}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
                <tr className="border-t border-text/15">
                  <td className="px-4 py-4 font-semibold text-text">종합 점수</td>
                  {validResults.map((result) => (
                    <td key={result.ticker} className="px-4 py-4 text-right font-mono text-lg font-semibold text-text">
                      {result.score?.total?.toFixed(1) ?? "없음"}
                      <span className="ml-1 text-xs font-normal text-text-secondary">/ 100</span>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {!loading && results.length === 0 && !error ? (
        <section className="card !p-8 text-center">
          <div className="font-semibold text-text">종목 2~4개 나란히 비교해 같은 기준으로 읽을 수 있습니다</div>
          <div className="mt-2 text-sm text-text-secondary">예시: 005930, 000660, 035420, 051910</div>
        </section>
      ) : null}
    </div>
  );
}
