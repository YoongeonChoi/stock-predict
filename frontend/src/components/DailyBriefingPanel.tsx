import Link from "next/link";

import type { DailyBriefingResponse } from "@/lib/api";
import { formatPct } from "@/lib/utils";

interface DailyBriefingPanelProps {
  data: DailyBriefingResponse;
}

const stanceTone: Record<string, string> = {
  risk_on: "bg-emerald-500/12 text-emerald-500",
  neutral: "bg-border/60 text-text-secondary",
  risk_off: "bg-rose-500/12 text-rose-500",
};

export default function DailyBriefingPanel({ data }: DailyBriefingPanelProps) {
  return (
    <div className="card !p-0 overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="section-title">오늘의 마켓 브리핑</h2>
            <p className="section-copy">장 상태, 국가별 체제, 오늘 우선 볼 기회와 이벤트를 한 흐름으로 묶었습니다.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="info-chip">리서치 {data.research_archive.todays_reports}건</span>
            <span className="info-chip">이벤트 {data.upcoming_events.length}건</span>
          </div>
        </div>
      </div>

      <div className="grid gap-6 px-5 py-5 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-5">
          <div className="space-y-2">
            {data.priorities.map((line) => (
              <div key={line} className="rounded-2xl border border-border/70 bg-surface/50 px-4 py-3 text-sm leading-6 text-text-secondary">
                {line}
              </div>
            ))}
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            {data.market_view.map((item) => (
              <div key={item.country_code} className="metric-card">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-medium text-text">{item.country_code}</div>
                  <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${stanceTone[item.stance] ?? stanceTone.neutral}`}>
                    {item.label}
                  </span>
                </div>
                <div className="mt-3 text-xs text-text-secondary">실행 가능 후보 {item.actionable_count}개 · 상방 우세 {item.bullish_count}개</div>
                <div className="mt-2 text-sm leading-6 text-text-secondary">{item.summary || "시장 체제 요약을 불러오는 중입니다."}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-5">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">오늘의 포커스</div>
            <div className="mt-3 grid gap-3">
              {data.focus_cards.slice(0, 3).map((item) => (
                <Link key={`${item.country_code}:${item.ticker}`} href={`/stock/${item.ticker}`} className="metric-card transition-colors hover:border-accent/35">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium text-text">{item.ticker}</div>
                      <div className="mt-1 text-xs text-text-secondary">{item.name} · {item.sector}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-sm text-text">{formatPct(item.predicted_return_pct)}</div>
                      <div className="mt-1 text-xs text-text-secondary">상방 {item.up_probability.toFixed(1)}%</div>
                    </div>
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-3 text-xs text-text-secondary">
                    <span>{item.country_code} · {item.action}</span>
                    <span>신뢰도 {item.confidence.toFixed(1)}</span>
                  </div>
                  {item.execution_note ? <div className="mt-2 text-sm text-text-secondary">{item.execution_note}</div> : null}
                </Link>
              ))}
            </div>
          </div>

          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">다가오는 일정</div>
            <div className="mt-3 space-y-2">
              {data.upcoming_events.map((event) => (
                <div key={`${event.country_code}:${event.date}:${event.title}`} className="rounded-2xl border border-border/70 bg-surface/45 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-text">{event.title}</div>
                    <div className="text-xs text-text-secondary">{event.date}</div>
                  </div>
                  <div className="mt-1 text-xs text-text-secondary">{event.summary}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
