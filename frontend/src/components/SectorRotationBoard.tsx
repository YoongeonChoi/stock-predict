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

      <div className="dashboard-signal-grid dashboard-signal-grid-wide">
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

      <div className="dashboard-sector-list">
        {data.map((sector) => {
          const isPositive = sector.change_pct > 0;
          return (
            <div
              key={sector.sector}
              className="dashboard-sector-row"
            >
              <div className="dashboard-sector-name">
                <Link
                  href={`/country/${countryCode}/sector/${encodeURIComponent(sector.sector)}`}
                  className="dashboard-sector-link"
                >
                  {sector.sector}
                </Link>
                <div className="dashboard-sector-detail">
                  <Link
                    href={`/stock/${encodeURIComponent(sector.ticker)}`}
                    className="hover:text-accent transition-colors"
                  >
                    {sector.leader_name}
                  </Link>
                  {" · "}{sector.breadth}종목
                </div>
              </div>

              <div className="dashboard-sector-meter">
                <div className="dashboard-sector-bar">
                  <div
                    className={`dashboard-sector-fill ${
                      isPositive ? "bg-positive/70" : "bg-negative/70"
                    }`}
                    style={{ width: barWidth(sector.change_pct, maxAbsPct) }}
                  />
                </div>
                <span
                  className={`dashboard-sector-change ${
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
