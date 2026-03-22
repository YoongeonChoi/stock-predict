"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { CalendarEvent, CalendarResponse } from "@/lib/api";

const COUNTRIES = [
  { code: "US", label: "미국", flag: "🇺🇸" },
  { code: "KR", label: "한국", flag: "🇰🇷" },
  { code: "JP", label: "일본", flag: "🇯🇵" },
];

const WEEK_DAYS = ["일", "월", "화", "수", "목", "금", "토"];

const EVENT_STYLES: Record<string, { dot: string; chip: string; text: string; badge: string }> = {
  rose: { dot: "bg-rose-500", chip: "bg-rose-500/15 border-rose-500/40", text: "text-rose-200", badge: "bg-rose-500/15 text-rose-300" },
  sky: { dot: "bg-sky-500", chip: "bg-sky-500/15 border-sky-500/40", text: "text-sky-200", badge: "bg-sky-500/15 text-sky-300" },
  emerald: { dot: "bg-emerald-500", chip: "bg-emerald-500/15 border-emerald-500/40", text: "text-emerald-200", badge: "bg-emerald-500/15 text-emerald-300" },
  amber: { dot: "bg-amber-500", chip: "bg-amber-500/15 border-amber-500/40", text: "text-amber-200", badge: "bg-amber-500/15 text-amber-300" },
  orange: { dot: "bg-orange-500", chip: "bg-orange-500/15 border-orange-500/40", text: "text-orange-200", badge: "bg-orange-500/15 text-orange-300" },
  slate: { dot: "bg-slate-500", chip: "bg-slate-500/15 border-slate-500/40", text: "text-slate-200", badge: "bg-slate-500/15 text-slate-300" },
};

function formatMonthLabel(date: Date) {
  return new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long" }).format(date);
}

function formatDateLabel(date: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date(`${date}T12:00:00`));
}

function buildCalendarDays(year: number, month: number) {
  const first = new Date(year, month, 1);
  const start = new Date(first);
  start.setDate(1 - first.getDay());

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);
    return date;
  });
}

function dateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function typeLabel(event: CalendarEvent) {
  if (event.type === "policy") return "정책";
  if (event.type === "earnings") return "실적";
  return "지표";
}

function impactLabel(impact: CalendarEvent["impact"]) {
  if (impact === "high") return "중요";
  if (impact === "medium") return "보통";
  return "참고";
}

export default function CalendarPage() {
  const today = new Date();
  const [country, setCountry] = useState("US");
  const [data, setData] = useState<CalendarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());

  useEffect(() => {
    setLoading(true);
    api.getCalendar(country, viewYear, viewMonth + 1)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [country, viewYear, viewMonth]);

  useEffect(() => {
    if (!data) return;

    const currentMonthPrefix = `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}`;
    if (selectedDate?.startsWith(currentMonthPrefix)) return;

    const todayKey = dateKey(today);
    if (todayKey.startsWith(currentMonthPrefix)) {
      setSelectedDate(todayKey);
      return;
    }

    setSelectedDate(data.upcoming_events[0]?.date || data.events[0]?.date || null);
  }, [data, selectedDate, today, viewMonth, viewYear]);

  const days = useMemo(() => buildCalendarDays(viewYear, viewMonth), [viewYear, viewMonth]);

  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    for (const event of data?.events || []) {
      if (!map[event.date]) map[event.date] = [];
      map[event.date].push(event);
    }

    for (const key of Object.keys(map)) {
      map[key] = map[key].sort((a, b) => {
        const impactRank = { high: 0, medium: 1, low: 2 };
        return impactRank[a.impact] - impactRank[b.impact];
      });
    }
    return map;
  }, [data]);

  const selectedEvents = selectedDate ? eventsByDate[selectedDate] || [] : [];
  const todayKey = dateKey(today);

  function moveMonth(offset: number) {
    const next = new Date(viewYear, viewMonth + offset, 1);
    setViewYear(next.getFullYear());
    setViewMonth(next.getMonth());
  }

  function resetToToday() {
    setViewYear(today.getFullYear());
    setViewMonth(today.getMonth());
    setSelectedDate(todayKey);
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="relative overflow-hidden rounded-[28px] border border-border bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.18),transparent_35%),radial-gradient(circle_at_top_right,rgba(244,114,182,0.14),transparent_30%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(15,23,42,0.78))] px-6 py-6">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5">
          <div className="max-w-2xl">
            <div className="text-xs uppercase tracking-[0.22em] text-sky-200/80">Monthly Market Calendar</div>
            <h1 className="text-3xl font-bold mt-2">시장 일정 캘린더</h1>
            <p className="text-sm text-slate-300 mt-3 leading-relaxed">
              월을 넘길 때마다 해당 월의 경제 일정과 실적 일정을 다시 동기화합니다. 색상과 칩만 봐도 정책 일정, 경제지표, 실적 이벤트를 한눈에 구분할 수 있게 구성했습니다.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {COUNTRIES.map((item) => (
              <button
                key={item.code}
                onClick={() => setCountry(item.code)}
                className={`px-3.5 py-2 rounded-full text-sm transition-colors ${
                  country === item.code
                    ? "bg-white text-slate-950 font-medium"
                    : "bg-white/10 text-slate-100 border border-white/10 hover:bg-white/15"
                }`}
              >
                {item.flag} {item.label}
              </button>
            ))}
          </div>
        </div>

        {data ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-6">
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
              <div className="text-[11px] text-slate-300">이번 달 총 일정</div>
              <div className="text-2xl font-bold mt-2">{data.summary.total_events}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
              <div className="text-[11px] text-slate-300">고중요도 일정</div>
              <div className="text-2xl font-bold mt-2">{data.summary.high_impact_count}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
              <div className="text-[11px] text-slate-300">정책 일정</div>
              <div className="text-2xl font-bold mt-2">{data.summary.policy_count}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
              <div className="text-[11px] text-slate-300">실적 일정</div>
              <div className="text-2xl font-bold mt-2">{data.summary.earnings_count}</div>
            </div>
          </div>
        ) : null}
      </div>

      {loading ? (
        <div className="space-y-4 animate-pulse">
          <div className="h-20 rounded-3xl bg-border" />
          <div className="h-[760px] rounded-3xl bg-border" />
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 xl:grid-cols-[1.6fr_0.9fr] gap-6">
          <div className="space-y-4">
            <div className="card !p-4 space-y-4">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                <div>
                  <h2 className="text-xl font-semibold">{formatMonthLabel(new Date(viewYear, viewMonth, 1))}</h2>
                  <p className="text-sm text-text-secondary mt-1">{data.summary.note}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => moveMonth(-1)} className="px-3 py-2 rounded-xl border border-border hover:border-accent/40 transition-colors">이전 달</button>
                  <button onClick={resetToToday} className="px-3 py-2 rounded-xl bg-accent text-white hover:opacity-90 transition-opacity">오늘</button>
                  <button onClick={() => moveMonth(1)} className="px-3 py-2 rounded-xl border border-border hover:border-accent/40 transition-colors">다음 달</button>
                </div>
              </div>

              <div className="grid grid-cols-7 gap-2 text-xs text-text-secondary px-1">
                {WEEK_DAYS.map((day, index) => (
                  <div key={day} className={`py-2 text-center ${index === 0 ? "text-rose-400" : index === 6 ? "text-sky-400" : ""}`}>
                    {day}
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-7 gap-2">
                {days.map((date) => {
                  const key = dateKey(date);
                  const inMonth = date.getMonth() === viewMonth;
                  const isToday = key === todayKey;
                  const isSelected = key === selectedDate;
                  const dayEvents = eventsByDate[key] || [];

                  return (
                    <button
                      key={key}
                      onClick={() => setSelectedDate(key)}
                      className={`min-h-[132px] rounded-2xl border p-2.5 text-left transition-all ${
                        isSelected
                          ? "border-accent bg-accent/10 shadow-[0_0_0_1px_rgba(56,189,248,0.18)]"
                          : "border-border bg-surface/60 hover:border-accent/35 hover:bg-surface"
                      } ${!inMonth ? "opacity-55" : "opacity-100"}`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                          isToday ? "bg-accent text-white" : "bg-border/50 text-text"
                        }`}>
                          {date.getDate()}
                        </span>
                        {dayEvents.length > 0 ? (
                          <span className="text-[10px] text-text-secondary">{dayEvents.length}건</span>
                        ) : null}
                      </div>

                      <div className="space-y-1.5">
                        {dayEvents.slice(0, 2).map((event) => {
                          const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                          return (
                            <div key={event.id} className={`rounded-xl border px-2 py-1.5 ${style.chip}`}>
                              <div className="flex items-center gap-1.5">
                                <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
                                <span className={`text-[10px] font-medium ${style.text}`}>{typeLabel(event)}</span>
                              </div>
                              <div className="text-[11px] mt-1 leading-tight line-clamp-2">{event.title}</div>
                            </div>
                          );
                        })}
                        {dayEvents.length > 2 ? (
                          <div className="text-[11px] text-text-secondary px-1">+{dayEvents.length - 2}건 더 보기</div>
                        ) : null}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="card !p-4 space-y-3">
              <div>
                <h2 className="font-semibold text-base">선택한 날짜</h2>
                <p className="text-sm text-text-secondary mt-1">
                  {selectedDate ? formatDateLabel(selectedDate) : "달력에서 날짜를 선택해 주세요."}
                </p>
              </div>
              {selectedDate && selectedEvents.length > 0 ? (
                <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
                  {selectedEvents.map((event) => {
                    const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                    return (
                      <div key={event.id} className="rounded-2xl border border-border bg-surface/60 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${style.dot}`} />
                            <div className="font-medium">{event.title}</div>
                          </div>
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${style.badge}`}>
                            {impactLabel(event.impact)}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-2 mt-2 text-[11px] text-text-secondary">
                          <span>{typeLabel(event)}</span>
                          {event.subtitle ? <span>{event.subtitle}</span> : null}
                        </div>
                        <p className="text-sm text-text-secondary mt-2 leading-relaxed">{event.description}</p>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-border px-4 py-6 text-sm text-text-secondary">
                  선택한 날짜에는 표시할 일정이 없습니다.
                </div>
              )}
            </div>

            <div className="card !p-4 space-y-3">
              <div>
                <h2 className="font-semibold text-base">다가오는 핵심 일정</h2>
                <p className="text-sm text-text-secondary mt-1">이번 달 안에서 가까운 순서대로 보여줍니다.</p>
              </div>
              <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
                {data.upcoming_events.length > 0 ? data.upcoming_events.map((event) => {
                  const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                  return (
                    <button
                      key={event.id}
                      onClick={() => setSelectedDate(event.date)}
                      className="w-full text-left rounded-2xl border border-border bg-surface/50 px-3 py-2.5 hover:border-accent/35 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${style.dot}`} />
                          <span className="font-medium">{event.title}</span>
                        </div>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${style.badge}`}>{impactLabel(event.impact)}</span>
                      </div>
                      <div className="text-xs text-text-secondary mt-1">{formatDateLabel(event.date)}{event.subtitle ? ` · ${event.subtitle}` : ""}</div>
                    </button>
                  );
                }) : (
                  <div className="text-sm text-text-secondary">표시할 일정이 없습니다.</div>
                )}
              </div>
            </div>

            <div className="card !p-4 space-y-3">
              <div>
                <h2 className="font-semibold text-base">정기 체크포인트</h2>
                <p className="text-sm text-text-secondary mt-1">매달 반복해서 확인할 대표 일정들입니다.</p>
              </div>
              <div className="space-y-2">
                {data.major_events.map((event) => {
                  const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                  return (
                    <div key={event.name} className="rounded-2xl border border-border bg-surface/60 px-3 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-medium">{event.name_local}</div>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${style.badge}`}>{impactLabel(event.impact)}</span>
                      </div>
                      <div className="text-xs text-text-secondary mt-1">{event.frequency}</div>
                      <p className="text-sm text-text-secondary mt-2 leading-relaxed">{event.description}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="card text-text-secondary">일정 데이터를 불러오지 못했습니다.</div>
      )}
    </div>
  );
}

