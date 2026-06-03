"use client";

import Link from "next/link";
import type { SectorPerformanceItem } from "@/lib/public-server-api";

interface Props {
  data: SectorPerformanceItem[] | null;
  countryCode?: string;
}

function barWidth(pct: number, maxAbsPct: number): string {
  if (maxAbsPct === 0) return "0%";
  return `${Math.min(Math.abs(pct) / maxAbsPct * 100, 100)}%`;
}

function changeLabel(pct: number): string {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export default function SectorRotationBoard({ data, countryCode = "KR" }: Props) {
  if (!data || data.length === 0) return null;

  const maxAbsPct = Math.max(...data.map((s) => Math.abs(s.change_pct)), 0.01);
  const gainers = data.filter((s) => s.change_pct > 0);
  const losers = data.filter((s) => s.change_pct <= 0);

  return (
    <section className="dashboard-panel">
      <div className="dashboard-section-header">
        <div>
          <h2 className="dashboard-section-title">섹터 로테이션</h2>
          <p className="dashboard-section-copy">
            {countryCode === "KR" ? "한국" : countryCode} 시장 섹터별 평균 등락률과 대장주를 비교합니다.
          </p>
        </div>
      </div>

      <div className="dashboard-signal-grid">
        <div className="dashboard-signal-tile">
          <span className="dashboard-tile-label">전체 섹터</span>
          <strong className="dashboard-tile-value">{data.length}</strong>
          <span className="dashboard-tile-detail">시세 반영 기준</span>
        </div>
        <div className="dashboard-signal-tile">
          <span className="dashboard-tile-label">상승 섹터</span>
          <strong className="dashboard-tile-value text-positive">{gainers.length}</strong>
          <span className="dashboard-tile-detail">평균 등락 &gt; 0</span>
        </div>
        <div className="dashboard-signal-tile">
          <span className="dashboard-tile-label">하락 섹터</span>
          <strong className="dashboard-tile-value text-negative">{losers.length}</strong>
          <span className="dashboard-tile-detail">평균 등락 ≤ 0</span>
        </div>
        <div className="dashboard-signal-tile">
          <span className="dashboard-tile-label">최대 움직임</span>
          <strong className="dashboard-tile-value">{changeLabel(data[0]?.change_pct ?? 0)}</strong>
          <span className="dashboard-tile-detail">{data[0]?.sector ?? "-"}</span>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {data.map((sector) => {
          const isPositive = sector.change_pct > 0;
          return (
            <div
              key={sector.sector}
              className="group flex items-center gap-3 rounded-[14px] border border-border bg-surface/65 px-4 py-3 transition-colors hover:border-accent/35"
            >
              <div className="min-w-[140px] shrink-0 sm:min-w-[180px]">
                <Link
                  href={`/country/${countryCode}/sector/${encodeURIComponent(sector.sector)}`}
                  className="text-sm font-medium text-text hover:text-accent transition-colors"
                >
                  {sector.sector}
                </Link>
                <div className="mt-0.5 text-[11px] text-text-secondary">
                  <Link
                    href={`/stock/${encodeURIComponent(sector.ticker)}`}
                    className="hover:text-accent transition-colors"
                  >
                    {sector.leader_name}
                  </Link>
                  {" · "}{sector.breadth}종목
                </div>
              </div>

              <div className="flex flex-1 items-center gap-2">
                <div className="relative h-5 flex-1 overflow-hidden rounded-full bg-border/25">
                  <div
                    className={`absolute inset-y-0 left-0 rounded-full transition-all ${
                      isPositive ? "bg-positive/70" : "bg-negative/70"
                    }`}
                    style={{ width: barWidth(sector.change_pct, maxAbsPct) }}
                  />
                </div>
                <span
                  className={`min-w-[64px] text-right text-sm font-semibold ${
                    isPositive ? "text-positive" : sector.change_pct < 0 ? "text-negative" : "text-text-secondary"
                  }`}
                >
                  {changeLabel(sector.change_pct)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
