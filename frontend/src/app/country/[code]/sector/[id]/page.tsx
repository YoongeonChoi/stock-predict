"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import ErrorBanner, { WarningBanner } from "@/components/ErrorBanner";
import PageHeader from "@/components/PageHeader";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
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
      .catch((caught) => setError(toError(caught)))
      .finally(() => setLoading(false));
  }, [code, id]);

  if (loading) {
    return (
      <div className="page-shell">
        <WorkspaceLoadingCard
          title="섹터 리포트를 불러오고 있습니다"
          message="섹터 점수, 상위 종목, 강점과 주의 포인트를 다시 정리하는 중입니다."
          className="min-h-[220px]"
        />
      </div>
    );
  }

  if (!report && error) {
    return (
      <div className="page-shell">
        <Link href={`/country/${code}`} className="ui-button-ghost w-fit px-0">
          국가 리포트로
        </Link>
        <ErrorBanner error={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="page-shell">
        <WorkspaceStateCard
          kind="empty"
          title="섹터 리포트를 찾지 못했습니다"
          message="섹터 경로가 올바른지 다시 확인해 주세요."
        />
      </div>
    );
  }

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
    <div className="page-shell">
      <PageHeader
        eyebrow="시장 탐색"
        title={`${report.sector?.name || "섹터"} 리포트`}
        description={`종목 수 ${report.sector?.stock_count ?? 0}개 기준으로 섹터 점수, 상위 종목, 강점과 주의 포인트를 한 화면에서 정리합니다.`}
        meta={
          <>
            <span className="info-chip">{code}</span>
            <span className="info-chip">섹터 {id}</span>
          </>
        }
        actions={
          <Link href={`/country/${code}`} className="ui-button-secondary px-4">
            국가 리포트로
          </Link>
        }
      />

      {report.errors && report.errors.length > 0 ? <WarningBanner codes={report.errors} /> : null}

      <div className="workspace-grid-balanced">
        <section className="card !p-5">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center">
            <ScoreRadial score={sc.total || 0} label="종합" />
            <div className="min-w-0 flex-1">
              <ScoreBreakdown items={scoreItems} />
            </div>
          </div>
        </section>
        <section className="card !p-5">
          <div className="section-heading">
            <div>
              <h2 className="section-title">섹터 요약</h2>
            </div>
          </div>
          <div className="mt-4 text-sm leading-7 text-text-secondary">
            {report.summary || "섹터 요약 정보가 아직 없습니다."}
          </div>
        </section>
      </div>

      {report.top_stocks.length > 0 ? (
        <section className="card !p-5">
          <div className="section-heading">
            <div>
              <h2 className="section-title">상위 종목</h2>
            </div>
          </div>
          <div className="mt-4 space-y-3 md:hidden">
            {report.top_stocks.map((stock) => (
              <Link
                key={stock.ticker}
                href={`/stock/${stock.ticker}`}
                className="block rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4 transition-colors hover:border-accent/30"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-semibold text-accent">#{stock.rank}</span>
                      <span className="font-semibold text-text">{stock.name}</span>
                    </div>
                    <div className="mt-1 font-mono text-[12px] text-text-secondary">{stock.ticker}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-sm font-semibold text-text">{formatPrice(stock.current_price, code)}</div>
                    <div className={`mt-1 text-sm ${changeColor(stock.change_pct ?? 0)}`}>{formatPct(stock.change_pct ?? 0)}</div>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <div className="rounded-2xl border border-border/60 bg-surface/65 px-3 py-2">
                    <div className="text-[11px] text-text-secondary">점수</div>
                    <div className="mt-1 font-semibold text-text">{(stock.score ?? 0).toFixed(1)}</div>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-surface/65 px-3 py-2">
                    <div className="text-[11px] text-text-secondary">강점</div>
                    <div className="mt-1 text-xs leading-5 text-text-secondary">
                      {(stock.pros || []).slice(0, 1).join(" · ") || "요약 준비 중"}
                    </div>
                  </div>
                </div>
                {(stock.cons || []).length > 0 ? (
                  <div className="mt-3 text-xs leading-5 text-text-secondary">
                    주의점 · {(stock.cons || []).slice(0, 1).join(" · ")}
                  </div>
                ) : null}
              </Link>
            ))}
          </div>
          <div className="mt-4 hidden md:block ui-table-shell">
            <table>
              <thead>
                <tr className="border-b border-border/10 text-left text-text-secondary">
                  <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-[0.12em]">순위</th>
                  <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-[0.12em]">종목</th>
                  <th className="px-4 py-3 text-right font-mono text-[11px] uppercase tracking-[0.12em]">현재가</th>
                  <th className="px-4 py-3 text-right font-mono text-[11px] uppercase tracking-[0.12em]">등락률</th>
                  <th className="px-4 py-3 text-right font-mono text-[11px] uppercase tracking-[0.12em]">점수</th>
                  <th className="hidden px-4 py-3 font-mono text-[11px] uppercase tracking-[0.12em] md:table-cell">강점</th>
                  <th className="hidden px-4 py-3 font-mono text-[11px] uppercase tracking-[0.12em] md:table-cell">주의점</th>
                </tr>
              </thead>
              <tbody>
                {report.top_stocks.map((stock) => (
                  <tr key={stock.ticker} className="border-b border-border/10 last:border-b-0">
                    <td className="px-4 py-4 font-mono font-semibold text-accent">{stock.rank}</td>
                    <td className="px-4 py-4">
                      <Link href={`/stock/${stock.ticker}`} className="block hover:text-accent">
                        <div className="font-semibold text-text">{stock.name}</div>
                        <div className="mt-1 font-mono text-[12px] text-text-secondary">{stock.ticker}</div>
                      </Link>
                    </td>
                    <td className="px-4 py-4 text-right font-mono text-text">{formatPrice(stock.current_price, code)}</td>
                    <td className={`px-4 py-4 text-right font-mono ${changeColor(stock.change_pct ?? 0)}`}>
                      {formatPct(stock.change_pct ?? 0)}
                    </td>
                    <td className="px-4 py-4 text-right font-mono font-semibold text-text">
                      {(stock.score ?? 0).toFixed(1)}
                    </td>
                    <td className="hidden px-4 py-4 text-xs leading-6 text-text-secondary md:table-cell">
                      {(stock.pros || []).slice(0, 2).map((item, index) => (
                        <div key={index}>+ {item}</div>
                      ))}
                    </td>
                    <td className="hidden px-4 py-4 text-xs leading-6 text-text-secondary md:table-cell">
                      {(stock.cons || []).slice(0, 2).map((item, index) => (
                        <div key={index}>- {item}</div>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
