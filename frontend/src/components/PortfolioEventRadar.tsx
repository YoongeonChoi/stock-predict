import Link from "next/link";

import type { PortfolioEventRadarResponse } from "@/lib/api";

interface PortfolioEventRadarProps {
  data: PortfolioEventRadarResponse;
}

export default function PortfolioEventRadar({ data }: PortfolioEventRadarProps) {
  return (
    <div className="card !p-0 overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="section-title">포트폴리오 이벤트 레이더</h2>
            <p className="section-copy">보유 종목과 국가 익스포저를 기준으로 다음 {data.window_days}일 안에 체크할 일정만 추렸습니다.</p>
          </div>
          <span className="info-chip">이벤트 {data.events.length}건</span>
        </div>
      </div>
      <div className="px-5 py-5 space-y-3">
        {data.events.length === 0 ? (
          <div className="rounded-2xl border border-border/70 bg-surface/45 px-4 py-5 text-sm text-text-secondary">
            현재 보유 종목 기준으로 가까운 일정이 아직 없습니다. 보유 종목을 추가하면 국가/실적 이벤트를 자동으로 연결합니다.
          </div>
        ) : (
          data.events.map((event) => (
            <div key={`${event.country_code}:${event.id}`} className="rounded-2xl border border-border/70 bg-surface/50 px-4 py-4">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                  <div className="font-medium text-text">{event.title}</div>
                  <div className="mt-1 text-xs text-text-secondary">{event.date} · {event.country_code} · {event.impact}</div>
                </div>
                <div className="text-right text-xs text-text-secondary">
                  <div>직접 영향 {event.portfolio_weight.toFixed(1)}%</div>
                  <div>국가 노출 {event.country_weight.toFixed(1)}%</div>
                </div>
              </div>
              {event.subtitle ? <div className="mt-2 text-sm text-text-secondary">{event.subtitle}</div> : null}
              <div className="mt-2 text-sm text-text-secondary">{event.summary}</div>
              {event.affected_holdings.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {event.affected_holdings.map((holding) => (
                    <Link key={holding.ticker} href={`/stock/${holding.ticker}`} className="info-chip hover:border-accent/35 hover:text-text">
                      {holding.ticker} · {holding.weight_pct.toFixed(1)}%
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
