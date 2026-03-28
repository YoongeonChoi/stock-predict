"use client";

import { useEffect, useMemo, useState } from "react";

import PageHeader from "@/components/PageHeader";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { api } from "@/lib/api";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import type { CalendarEvent, CalendarResponse } from "@/lib/api";

const COUNTRIES = [
  { code: "KR", label: "한국", flag: "🇰🇷" },
];

const WEEK_DAYS = ["일", "월", "화", "수", "목", "금", "토"];

const EVENT_STYLES: Record<string, { dot: string; chip: string; label: string; badge: string }> = {
  rose: {
    dot: "bg-rose-500",
    chip: "border-rose-500/20 bg-rose-500/10",
    label: "text-rose-700 dark:text-rose-300",
    badge: "bg-rose-500/12 text-rose-700 dark:text-rose-300",
  },
  sky: {
    dot: "bg-sky-500",
    chip: "border-sky-500/20 bg-sky-500/10",
    label: "text-sky-700 dark:text-sky-300",
    badge: "bg-sky-500/12 text-sky-700 dark:text-sky-300",
  },
  emerald: {
    dot: "bg-emerald-500",
    chip: "border-emerald-500/20 bg-emerald-500/10",
    label: "text-emerald-700 dark:text-emerald-300",
    badge: "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
  },
  amber: {
    dot: "bg-amber-500",
    chip: "border-amber-500/20 bg-amber-500/10",
    label: "text-amber-700 dark:text-amber-300",
    badge: "bg-amber-500/12 text-amber-700 dark:text-amber-300",
  },
  orange: {
    dot: "bg-orange-500",
    chip: "border-orange-500/20 bg-orange-500/10",
    label: "text-orange-700 dark:text-orange-300",
    badge: "bg-orange-500/12 text-orange-700 dark:text-orange-300",
  },
  slate: {
    dot: "bg-slate-500",
    chip: "border-border bg-border/20",
    label: "text-text-secondary",
    badge: "bg-border/40 text-text-secondary",
  },
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
  const today = useMemo(() => new Date(), []);
  const [country, setCountry] = useState("KR");
  const [data, setData] = useState<CalendarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());

  useEffect(() => {
    const hasExistingData = Boolean(data);
    if (hasExistingData) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    api.getCalendar(country, viewYear, viewMonth + 1, { timeoutMs: 18_000 })
      .then(setData)
      .catch((caught) => {
        console.error(caught);
        setError(
          getUserFacingErrorMessage(
            caught,
            "시장 일정 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
          ),
        );
      })
      .finally(() => {
        setLoading(false);
        setRefreshing(false);
      });
  }, [country, reloadToken, viewMonth, viewYear]);

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
  const todayKey = dateKey(today);

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
  const activeCountry = COUNTRIES.find((item) => item.code === country) || COUNTRIES[0];
  const currentMonthDate = new Date(viewYear, viewMonth, 1);

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

  const summaryCards = data ? [
    { label: "이번 달 총 일정", value: data.summary.total_events, note: data.month_label },
    { label: "고중요도 일정", value: data.summary.high_impact_count, note: "정책 / CPI / 대형 실적 포함" },
    { label: "정책 일정", value: data.summary.policy_count, note: "중앙은행·금리 이벤트" },
    { label: "실적 일정", value: data.summary.earnings_count, note: "주요 기업 발표" },
  ] : [];

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="Market Schedule Workspace"
        title="시장 일정 캘린더"
        description="한국장의 월간 경제지표, 정책 일정, 실적 발표를 한 달 보드와 상세 패널로 함께 읽습니다. 실제 외부 일정이 있으면 그 날짜를 우선 사용하고, 부족한 구간만 반복 스케줄 추정으로 보완합니다."
        meta={
          <>
            <span className="info-chip">{activeCountry.flag} {activeCountry.label} 기준</span>
            <span className="info-chip">{formatMonthLabel(currentMonthDate)}</span>
            {data ? <span className="info-chip">총 일정 {data.summary.total_events}건</span> : null}
            {data ? <span className="info-chip">고중요도 {data.summary.high_impact_count}건</span> : null}
            {refreshing ? <span className="info-chip">월간 보드 갱신 중</span> : null}
          </>
        }
        actions={
          <>
            {COUNTRIES.map((item) => (
              <button
                key={item.code}
                onClick={() => setCountry(item.code)}
                className={country === item.code ? "action-chip-primary" : "action-chip-secondary"}
              >
                {item.flag} {item.label}
              </button>
            ))}
          </>
        }
      />

      {loading ? (
        <div className="space-y-4">
          <WorkspaceLoadingCard
            title="월간 일정 요약을 준비하고 있습니다"
            message="정책, 지표, 실적 일정을 한 달 보드용 요약으로 먼저 묶는 중입니다."
            className="min-h-[160px]"
          />
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.95fr)]">
            <WorkspaceLoadingCard
              title="월간 일정 보드를 그리고 있습니다"
              message="날짜별 이벤트 수와 중요도를 월간 캘린더 격자에 다시 배치하고 있습니다."
              className="min-h-[620px]"
            />
            <div className="space-y-4">
              <WorkspaceLoadingCard
                title="선택한 날짜 패널을 준비하고 있습니다"
                message="날짜별 상세 설명과 태그를 먼저 정리하는 중입니다."
                className="min-h-[190px]"
              />
              <WorkspaceLoadingCard
                title="다가오는 일정 목록을 준비하고 있습니다"
                message="가까운 일정 순서대로 재정렬해 오른쪽 패널에 채웁니다."
                className="min-h-[180px]"
              />
              <WorkspaceLoadingCard
                title="정기 체크포인트를 준비하고 있습니다"
                message="매달 반복 확인할 대표 일정만 따로 다시 묶습니다."
                className="min-h-[180px]"
              />
            </div>
          </div>
        </div>
      ) : data ? (
        <>
          {error ? (
            <WorkspaceStateCard
              eyebrow="부분 업데이트"
              title="새 일정 동기화가 잠시 늦어지고 있습니다"
              message={`${error} 기존에 확인하던 일정은 먼저 유지해 두었습니다.`}
              tone="warning"
            />
          ) : null}
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {summaryCards.map((item) => (
              <div key={item.label} className="metric-card">
                <div className="text-xs text-text-secondary">{item.label}</div>
                <div className="mt-3 text-2xl font-bold">{item.value}</div>
                <div className="mt-2 text-xs leading-5 text-text-secondary">{item.note}</div>
              </div>
            ))}
          </section>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.95fr)]">
            <div className="min-w-0 card !p-4 space-y-4">
              <div className="section-heading gap-4">
                <div className="min-w-0">
                  <h2 className="section-title">{formatMonthLabel(currentMonthDate)}</h2>
                  <p className="section-copy">{data.summary.note}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button onClick={() => moveMonth(-1)} className="action-chip-secondary">
                    이전 달
                  </button>
                  <button onClick={resetToToday} className="action-chip-primary">
                    오늘
                  </button>
                  <button onClick={() => moveMonth(1)} className="action-chip-secondary">
                    다음 달
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded-full border border-rose-500/20 bg-rose-500/10 px-3 py-1.5 text-rose-700 dark:text-rose-300">정책</span>
                <span className="rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1.5 text-sky-700 dark:text-sky-300">물가 / 핵심 지표</span>
                <span className="rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1.5 text-amber-700 dark:text-amber-300">실적</span>
                <span className="rounded-full border border-border bg-border/20 px-3 py-1.5 text-text-secondary">같은 월간 지표는 한 달에 1회만 표시</span>
              </div>

              <div className="grid grid-cols-7 gap-2 px-1 text-xs text-text-secondary">
                {WEEK_DAYS.map((day, index) => (
                  <div key={day} className={`py-2 text-center ${index === 0 ? "text-rose-500" : index === 6 ? "text-sky-500" : ""}`}>
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
                      className={`min-h-[118px] rounded-2xl border p-2.5 text-left transition-all ${
                        isSelected
                          ? "border-accent bg-accent/10 shadow-[0_0_0_1px_rgba(15,118,110,0.16)]"
                          : "border-border bg-surface/60 hover:border-accent/35 hover:bg-surface"
                      } ${!inMonth ? "opacity-55" : "opacity-100"}`}
                    >
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <span
                          className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                            isToday ? "bg-accent text-white" : "bg-border/45 text-text"
                          }`}
                        >
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
                                <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
                                <span className={`text-[10px] font-medium ${style.label}`}>{typeLabel(event)}</span>
                              </div>
                              <div className="mt-1 line-clamp-2 text-[11px] leading-tight text-text">{event.title}</div>
                            </div>
                          );
                        })}
                        {dayEvents.length > 2 ? (
                          <div className="px-1 text-[11px] text-text-secondary">+{dayEvents.length - 2}건 더 보기</div>
                        ) : null}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-4">
              <div className="card !p-4 space-y-3">
                <div>
                  <h2 className="text-base font-semibold">선택한 날짜</h2>
                  <p className="mt-1 text-sm text-text-secondary">
                    {selectedDate ? formatDateLabel(selectedDate) : "달력에서 날짜를 선택해 주세요."}
                  </p>
                </div>

                {selectedDate && selectedEvents.length > 0 ? (
                  <div className="max-h-[380px] space-y-2 overflow-y-auto pr-1">
                    {selectedEvents.map((event) => {
                      const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                      return (
                        <div key={event.id} className="rounded-2xl border border-border bg-surface/60 p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className={`h-2 w-2 rounded-full ${style.dot}`} />
                                <div className="font-medium text-text">{event.title}</div>
                              </div>
                              <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-text-secondary">
                                <span>{typeLabel(event)}</span>
                                {event.subtitle ? <span>{event.subtitle}</span> : null}
                              </div>
                            </div>
                            <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${style.badge}`}>
                              {impactLabel(event.impact)}
                            </span>
                          </div>
                          <p className="mt-2 text-sm leading-relaxed text-text-secondary">{event.description}</p>
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
                  <h2 className="text-base font-semibold">다가오는 핵심 일정</h2>
                  <p className="mt-1 text-sm text-text-secondary">이번 달 안에서 가까운 순서대로 보여줍니다.</p>
                </div>
                <div className="max-h-[320px] space-y-2 overflow-y-auto pr-1">
                  {data.upcoming_events.length > 0 ? data.upcoming_events.map((event) => {
                    const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                    return (
                      <button
                        key={event.id}
                        onClick={() => setSelectedDate(event.date)}
                        className="w-full rounded-2xl border border-border bg-surface/50 px-3 py-3 text-left transition-colors hover:border-accent/35"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className={`h-2 w-2 rounded-full ${style.dot}`} />
                              <span className="font-medium text-text">{event.title}</span>
                            </div>
                            <div className="mt-1 text-xs text-text-secondary">
                              {formatDateLabel(event.date)}
                              {event.subtitle ? ` · ${event.subtitle}` : ""}
                            </div>
                          </div>
                          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${style.badge}`}>
                            {impactLabel(event.impact)}
                          </span>
                        </div>
                      </button>
                    );
                  }) : (
                    <div className="text-sm text-text-secondary">표시할 일정이 없습니다.</div>
                  )}
                </div>
              </div>

              <div className="card !p-4 space-y-3">
                <div>
                  <h2 className="text-base font-semibold">정기 체크포인트</h2>
                  <p className="mt-1 text-sm text-text-secondary">매달 반복해서 확인할 대표 일정들입니다.</p>
                </div>
                <div className="space-y-2">
                  {data.major_events.map((event) => {
                    const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                    return (
                      <div key={event.name} className="rounded-2xl border border-border bg-surface/60 px-3 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="font-medium text-text">{event.name_local}</div>
                            <div className="mt-1 text-xs text-text-secondary">{event.frequency}</div>
                          </div>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${style.badge}`}>
                            {impactLabel(event.impact)}
                          </span>
                        </div>
                        <p className="mt-2 text-sm leading-relaxed text-text-secondary">{event.description}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </section>
        </>
      ) : (
        <WorkspaceStateCard
          eyebrow="일정 지연"
          title="시장 일정 캘린더를 아직 불러오지 못했습니다"
          message={error || "시장 일정 데이터를 불러오지 못했습니다."}
          tone="warning"
          actionLabel="다시 시도"
          onAction={() => {
            setLoading(true);
            setError(null);
            setData(null);
            setReloadToken((value) => value + 1);
          }}
        />
      )}
    </div>
  );
}
