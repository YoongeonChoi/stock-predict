import type { MarketSessionItem } from "@/lib/api";

interface MarketSessionPanelProps {
  sessions: MarketSessionItem[];
}

export default function MarketSessionPanel({ sessions }: MarketSessionPanelProps) {
  return (
    <div className="card !p-0 overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <h2 className="section-title">시장 세션 상태</h2>
        <p className="section-copy">어느 시장이 열려 있고, 예측이 어떤 완결 종가를 기준으로 준비됐는지 바로 확인합니다.</p>
      </div>
      <div className="px-5 py-5 space-y-3">
        {sessions.map((session) => (
          <div key={session.country_code} className="rounded-2xl border border-border/70 bg-surface/50 px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-medium text-text">{session.name_local}</div>
                <div className="mt-1 text-xs text-text-secondary">{session.country_code} · {session.phase}</div>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${session.is_open ? "bg-emerald-500/12 text-emerald-500" : "bg-border/60 text-text-secondary"}`}>
                {session.is_open ? "장중" : "비장중"}
              </span>
            </div>
            <div className="mt-3 grid gap-2 text-sm text-text-secondary">
              <div>최근 완결 종가: {session.latest_closed_date}</div>
              <div>다음 거래일: {session.next_trading_day}</div>
              <div>{session.forecast_ready_note}</div>
              <div className="text-xs">{session.provider_note}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
