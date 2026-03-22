"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import ErrorBanner, { WarningBanner } from "@/components/ErrorBanner";
import ScoreBreakdown from "@/components/charts/ScoreBreakdown";
import ScoreRadial from "@/components/charts/ScoreRadial";
import { api } from "@/lib/api";
import type { ScoreItem, SectorReport } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "섹터 리포트를 불러오지 못했습니다.");
}

export default function SectorPage() {
  const { code, id } = useParams<{ code: string; id: string }>();
  const [report, setReport] = useState<SectorReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!code || !id) return;
    setLoading(true);
    setError(null);
    api.getSectorReport(code, id)
      .then(setReport)
      .catch((e) => {
        console.error(e);
        setError(toError(e));
      })
      .finally(() => setLoading(false));
  }, [code, id]);

  if (loading) {
    return <div className="animate-pulse space-y-4"><div className="h-8 bg-border rounded w-48" /><div className="h-96 bg-border rounded" /></div>;
  }

  if (!report && error) {
    return (
      <div className="max-w-5xl mx-auto space-y-4">
        <Link href={`/country/${code}`} className="text-text-secondary hover:text-text">&larr; 국가 리포트로</Link>
        <ErrorBanner error={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }

  if (!report) return <div className="text-text-secondary">섹터 리포트를 찾을 수 없습니다.</div>;

  const defaultScore: ScoreItem = { name: "", score: 0, max_score: 0, description: "" };
  const sc = report.score;
  const scoreItems = [
    sc.earnings_growth || defaultScore,
    sc.institutional_consensus || defaultScore,
    sc.valuation_attractiveness || defaultScore,
    sc.policy_impact || defaultScore,
    sc.technical_momentum || defaultScore,
    sc.risk_adjusted_return || defaultScore,
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex items-center gap-4">
        <Link href={`/country/${code}`} className="text-text-secondary hover:text-text">&larr;</Link>
        <div>
          <h1 className="text-2xl font-bold">{report.sector?.name || "섹터"} 리포트</h1>
          <span className="text-text-secondary text-sm">종목 수 {report.sector?.stock_count ?? 0}개</span>
        </div>
      </div>

      {report.errors && report.errors.length > 0 ? <WarningBanner codes={report.errors} /> : null}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="card lg:col-span-2">
          <div className="flex items-center gap-6">
            <ScoreRadial score={sc.total || 0} label="종합" />
            <div className="flex-1">
              <ScoreBreakdown items={scoreItems} />
            </div>
          </div>
        </div>
        <div className="card">
          <h3 className="font-semibold mb-3">섹터 요약</h3>
          <p className="text-sm leading-relaxed whitespace-pre-line">{report.summary || "요약 정보가 아직 없습니다."}</p>
        </div>
      </div>

      {report.top_stocks.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-4">상위 종목</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-text-secondary border-b border-border">
                  <th className="pb-2 w-8">순위</th>
                  <th className="pb-2">종목</th>
                  <th className="pb-2 text-right">현재가</th>
                  <th className="pb-2 text-right">등락률</th>
                  <th className="pb-2 text-right">점수</th>
                  <th className="pb-2 hidden md:table-cell">장점</th>
                  <th className="pb-2 hidden md:table-cell">주의점</th>
                </tr>
              </thead>
              <tbody>
                {report.top_stocks.map((stock) => (
                  <tr key={stock.ticker} className="border-b border-border/50 hover:bg-border/20">
                    <td className="py-3 font-bold text-accent">{stock.rank}</td>
                    <td className="py-3">
                      <Link href={`/stock/${stock.ticker}`} className="hover:text-accent transition-colors">
                        <div className="font-medium">{stock.name}</div>
                        <div className="text-xs text-text-secondary">{stock.ticker}</div>
                      </Link>
                    </td>
                    <td className="py-3 text-right font-mono">{formatPrice(stock.current_price, code)}</td>
                    <td className={`py-3 text-right ${changeColor(stock.change_pct ?? 0)}`}>{formatPct(stock.change_pct ?? 0)}</td>
                    <td className="py-3 text-right font-bold">{(stock.score ?? 0).toFixed(1)}</td>
                    <td className="py-3 text-xs text-text-secondary hidden md:table-cell">{(stock.pros || []).slice(0, 2).map((item, index) => <div key={index}>+ {item}</div>)}</td>
                    <td className="py-3 text-xs text-text-secondary hidden md:table-cell">{(stock.cons || []).slice(0, 2).map((item, index) => <div key={index}>- {item}</div>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}