"use client";

import { useEffect, useMemo, useState } from "react";

import { Modal } from "@/components/ui";
import PageHeader from "@/components/PageHeader";
import PublicAuditStrip from "@/components/PublicAuditStrip";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { api } from "@/lib/api";
import { buildPublicAuditSummary } from "@/lib/public-audit";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import type { CalendarEvent, CalendarResponse } from "@/lib/api";

const COUNTRIES = [
  { code: "KR", label: "한국", flag: "🇰🇷" },
];

const WEEK_DAYS = ["일", "월", "화", "수", "목", "금", "토"];
const KOREA_TIME_ZONE = "Asia/Seoul";
const EVENT_COUNTRY_LABELS: Record<string, string> = {
  KR: "한국",
  US: "미국",
  EU: "유로존",
  JP: "일본",
};

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
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: KOREA_TIME_ZONE,
    year: "numeric",
    month: "long",
  }).format(date);
}

function formatDateLabel(date: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: KOREA_TIME_ZONE,
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date(`${date}T12:00:00`));
}

function getTodayKeyInKorea() {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: KOREA_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(new Date());
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

function jumpToDate(dateText: string, setViewYear: (value: number) => void, setViewMonth: (value: number) => void, setSelectedDate: (value: string) => void) {
  const next = new Date(`${dateText}T12:00:00`);
  if (Number.isNaN(next.getTime())) {
    setSelectedDate(dateText);
    return;
  }
  setViewYear(next.getFullYear());
  setViewMonth(next.getMonth());
  setSelectedDate(dateText);
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

function eventCountryLabel(countryCode?: string | null) {
  if (!countryCode) return "시장";
  return EVENT_COUNTRY_LABELS[countryCode] || countryCode;
}

interface CalendarPageClientProps {
  initialData?: (CalendarResponse & { partial?: boolean; fallback_reason?: string | null }) | null;
}

export default function CalendarPageClient({ initialData = null }: CalendarPageClientProps) {
  const todayKeySeed = useMemo(() => getTodayKeyInKorea(), []);
  const today = useMemo(() => new Date(`${todayKeySeed}T12:00:00`), [todayKeySeed]);
  const [country, setCountry] = useState("KR");
  const [data, setData] = useState<(CalendarResponse & { partial?: boolean; fallback_reason?: string | null }) | null>(initialData);
  const [loading, setLoading] = useState(!initialData);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());

  useEffect(() => {
    const shouldReuseInitialData =
      Boolean(initialData)
      && reloadToken === 0
      && country === "KR"
      && viewYear === today.getFullYear()
      && viewMonth === today.getMonth();
    if (shouldReuseInitialData) {
      return;
    }
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
        console.warn(caught);
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
  }, [country, initialData, reloadToken, viewMonth, viewYear]);

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

  const auditSummary = buildPublicAuditSummary(data, {
    defaultSummary: "공식 발표 일정과 주요 실적을 월간 캘린더에 표시합니다.",
  });

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="시장 일정"
        title="시장 일정 캘린더"
        description="정책 발표, 경제지표, 주요 실적 일정을 한 달 단위로 정리합니다. 날짜를 선택하면 세부 일정과 공식 출처를 바로 확인할 수 있습니다."
        variant="compact"
        meta={
          <>
            <span className="info-chip">{activeCountry.flag} {activeCountry.label} 기준</span>
            <span className="info-chip">{formatMonthLabel(currentMonthDate)}</span>
            {data ? <span className="info-chip">고중요도 {data.summary.high_impact_count}건</span> : null}
            {refreshing ? <span className="info-chip">갱신 중</span> : null}
          </>
        }
        actions={COUNTRIES.length > 1 ? (
          <div className="ui-segmented-control-responsive">
            {COUNTRIES.map((item) => (
              <button
                key={item.code}
                onClick={() => setCountry(item.code)}
                className={[
                  "ui-segmented-option",
                  country === item.code && "ui-segmented-option-active",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {item.flag} {item.label}
              </button>
            ))}
          </div>
        ) : undefined}
      />

      {loading ? (
        <div className="space-y-4">
          <WorkspaceLoadingCard
            title="월간 캘린더를 준비하고 있습니다"
            message="정책, 지표, 실적 일정을 날짜별로 배치하고 있습니다."
            className="min-h-[160px]"
          />
          <WorkspaceLoadingCard
            title="월간 일정 보드를 그리고 있습니다"
            message="날짜별 이벤트 수와 중요도를 캘린더 격자에 배치하고 있습니다."
            className="min-h-[620px]"
          />
        </div>
      ) : data ? (
        <>
          {error ? (
            <WorkspaceStateCard
              eyebrow="부분 업데이트"
              title="새 일정 동기화가 잠시 늦어지고 있습니다"
              message={`${error} 기존에 확인하던 일정은 유지됩니다.`}
              tone="warning"
              kind="partial"
            />
          ) : null}

          <section className="card overflow-hidden !p-0">
            <div className="border-b border-border/70 bg-white px-4 py-4 sm:px-5">
              <div className="section-heading gap-4">
                <div className="min-w-0">
                  <h2 className="section-title">{formatMonthLabel(currentMonthDate)}</h2>
                  <p className="section-copy">{auditSummary}</p>
                </div>
                <div className="ui-button-cluster">
                  <button onClick={() => moveMonth(-1)} className="ui-button-secondary px-4">
                    이전 달
                  </button>
                  <button onClick={resetToToday} className="ui-button-primary px-4">
                    오늘
                  </button>
                  <button onClick={() => moveMonth(1)} className="ui-button-secondary px-4">
                    다음 달
                  </button>
                </div>
              </div>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-wrap gap-2 text-xs">
                  <span className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-white px-3 py-1.5 text-text-secondary">
                    <span className="h-2 w-2 rounded-full bg-rose-500" /> 정책
                  </span>
                  <span className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-white px-3 py-1.5 text-text-secondary">
                    <span className="h-2 w-2 rounded-full bg-sky-500" /> 물가 / 지표
                  </span>
                  <span className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-white px-3 py-1.5 text-text-secondary">
                    <span className="h-2 w-2 rounded-full bg-amber-500" /> 실적
                  </span>
                </div>
                <PublicAuditStrip meta={data} />
              </div>
            </div>

            <div className="bg-white px-2 pb-3 pt-2 sm:px-4 sm:pb-5">
              <div className="grid grid-cols-7 border-b border-border/60 text-xs font-medium text-text-secondary">
                {WEEK_DAYS.map((day, index) => (
                  <div key={day} className={`py-3 text-center ${index === 0 ? "text-rose-500" : index === 6 ? "text-sky-500" : ""}`}>
                    {day}
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-7">
                {days.map((date, index) => {
                  const key = dateKey(date);
                  const inMonth = date.getMonth() === viewMonth;
                  const isToday = key === todayKey;
                  const isSelected = key === selectedDate;
                  const dayEvents = eventsByDate[key] || [];
                  const hasHighImpact = dayEvents.some((event) => event.impact === "high");
                  const isWeekEnd = index % 7 === 6;

                  return (
                    <button
                      key={key}
                      onClick={() => setSelectedDate(key)}
                      className={`min-h-[74px] border-b border-border/55 p-1.5 text-left transition-[background-color,box-shadow,opacity] sm:min-h-[112px] sm:p-2.5 lg:min-h-[132px] ${
                        isWeekEnd ? "" : "border-r"
                      } ${
                        isSelected
                          ? "bg-accent/10 shadow-[inset_0_0_0_2px_rgb(var(--accent-rgb)/0.42)]"
                          : "bg-white hover:bg-surface/80"
                      } ${!inMonth ? "opacity-45" : "opacity-100"} ${hasHighImpact && !isSelected ? "bg-rose-50/55" : ""}`}
                      aria-pressed={isSelected}
                      aria-label={`${date.getMonth() + 1}월 ${date.getDate()}일${dayEvents.length > 0 ? `, 일정 ${dayEvents.length}건` : ""}${isToday ? ", 오늘" : ""}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium sm:h-8 sm:w-8 sm:text-sm ${
                            isToday ? "bg-accent text-white" : isSelected ? "bg-accent/15 text-accent" : "text-text"
                          }`}
                        >
                          {date.getDate()}
                        </span>
                        {dayEvents.length > 0 ? (
                          <span className="text-[10px] text-text-secondary">{dayEvents.length}건</span>
                        ) : null}
                      </div>

                      <div className="mt-2 hidden space-y-1.5 sm:block">
                        {dayEvents.slice(0, 2).map((event) => {
                          const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                          return (
                            <div key={event.id} className="rounded-md bg-surface/95 px-2 py-1.5">
                              <div className="flex items-center gap-1.5">
                                <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
                                <span className={`text-[10px] font-medium ${style.label}`}>{typeLabel(event)}</span>
                              </div>
                              <div className="mt-1 line-clamp-1 text-[11px] leading-tight text-text">{event.title}</div>
                            </div>
                          );
                        })}
                        {dayEvents.length > 2 ? (
                          <div className="px-1 text-[11px] text-text-secondary">+{dayEvents.length - 2}건</div>
                        ) : null}
                      </div>

                      <div className="mt-3 flex min-h-[24px] items-end justify-between gap-2 sm:hidden">
                        <div className="flex items-center gap-1">
                          {dayEvents.slice(0, 3).map((event) => {
                            const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                            return <span key={event.id} className={`h-2 w-2 rounded-full ${style.dot}`} />;
                          })}
                          {dayEvents.length > 3 ? <span className="text-[10px] text-text-secondary">+{dayEvents.length - 3}</span> : null}
                        </div>
                        {hasHighImpact ? <span className="text-[10px] font-medium text-rose-600">중요</span> : null}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </section>

          <section className="card !p-5 space-y-4">
            <div className="section-heading gap-4">
              <div>
                <h2 className="section-title">선택한 날짜 일정</h2>
                <p className="section-copy">
                  {selectedDate ? formatDateLabel(selectedDate) : "캘린더에서 날짜를 선택해 주세요."}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <div>
                  <div className="text-xs text-text-secondary">전체</div>
                  <div className="mt-1 font-semibold text-text">{data.summary.total_events}건</div>
                </div>
                <div>
                  <div className="text-xs text-text-secondary">중요</div>
                  <div className="mt-1 font-semibold text-text">{data.summary.high_impact_count}건</div>
                </div>
                <div>
                  <div className="text-xs text-text-secondary">정책</div>
                  <div className="mt-1 font-semibold text-text">{data.summary.policy_count}건</div>
                </div>
                <div>
                  <div className="text-xs text-text-secondary">실적</div>
                  <div className="mt-1 font-semibold text-text">{data.summary.earnings_count}건</div>
                </div>
              </div>
            </div>

            {selectedDate && selectedEvents.length > 0 ? (
              <div className="space-y-2">
                {selectedEvents.map((event) => {
                  const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                  return (
                    <button
                      key={event.id}
                      onClick={() => setSelectedEvent(event)}
                      className="w-full rounded-xl border border-border/70 bg-white px-4 py-3 text-left transition-colors hover:border-accent/45 hover:bg-surface/50"
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
                            <div className="font-semibold text-text">{event.title}</div>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2 text-xs text-text-secondary">
                            <span>{eventCountryLabel(event.country_code)}</span>
                            <span>{typeLabel(event)}</span>
                            <span>{event.source === "recurring" ? "대표 일정" : "확인된 일정"}</span>
                            {event.subtitle ? <span>{event.subtitle}</span> : null}
                            {event.source_name ? <span>{event.source_name}</span> : null}
                          </div>
                          <p className="mt-2 line-clamp-2 text-sm leading-6 text-text-secondary">{event.description}</p>
                        </div>
                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${style.badge}`}>
                          {impactLabel(event.impact)}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-border px-4 py-6 text-sm text-text-secondary">
                선택한 날짜에는 표시할 일정이 없습니다.
              </div>
            )}
          </section>

          <section className="card !p-5 space-y-4">
            <div>
              <h2 className="section-title">다가오는 주요 일정</h2>
              <p className="section-copy">이번 달 안에서 가까운 순서대로 12개까지 표시합니다.</p>
            </div>
            <div className="space-y-2">
              {data.upcoming_events.length > 0 ? data.upcoming_events.map((event) => {
                const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                return (
                  <button
                    key={event.id}
                    onClick={() => {
                      jumpToDate(event.date, setViewYear, setViewMonth, setSelectedDate);
                      setSelectedEvent(event);
                    }}
                    className="w-full rounded-xl border border-border/70 bg-white px-4 py-3 text-left transition-colors hover:border-accent/45 hover:bg-surface/50"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
                          <span className="font-semibold text-text">{event.title}</span>
                        </div>
                        <div className="mt-1 text-xs text-text-secondary">
                          {eventCountryLabel(event.country_code)} · {formatDateLabel(event.date)}
                          {event.subtitle ? ` · ${event.subtitle}` : ""}
                          {event.source_name ? ` · ${event.source_name}` : ""}
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
          </section>

          <section className="card !p-5 space-y-4">
            <div>
              <h2 className="section-title">월간 체크포인트</h2>
              <p className="section-copy">매달 반복해서 확인할 대표 일정입니다.</p>
            </div>
            <div className="space-y-2">
              {data.major_events.map((event) => {
                const style = EVENT_STYLES[event.color] || EVENT_STYLES.slate;
                return (
                  <div key={event.name} className="rounded-xl border border-border/70 bg-white px-4 py-3">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="font-semibold text-text">{event.name_local}</div>
                        <div className="mt-1 text-xs text-text-secondary">{event.frequency}</div>
                        <p className="mt-2 text-sm leading-6 text-text-secondary">{event.description}</p>
                        {event.source_url ? (
                          <a
                            className="mt-3 inline-flex text-sm font-semibold text-accent transition-colors hover:text-accent-strong"
                            href={event.source_url}
                            rel="noreferrer"
                            target="_blank"
                          >
                            {event.source_name || "공식 출처"} 보기
                          </a>
                        ) : null}
                      </div>
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${style.badge}`}>
                        {impactLabel(event.impact)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <Modal
            className="max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-w-xl"
            onClose={() => setSelectedEvent(null)}
            open={Boolean(selectedEvent)}
            title={selectedEvent?.title || "일정 상세"}
          >
            {selectedEvent ? (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
                  <span className="info-chip">{formatDateLabel(selectedEvent.date)}</span>
                  <span className="info-chip">{eventCountryLabel(selectedEvent.country_code)}</span>
                  <span className="info-chip">{typeLabel(selectedEvent)}</span>
                  <span className="info-chip">{impactLabel(selectedEvent.impact)}</span>
                </div>
                {selectedEvent.subtitle ? (
                  <p className="text-sm font-medium text-text">{selectedEvent.subtitle}</p>
                ) : null}
                <p className="text-sm leading-6 text-text-secondary">{selectedEvent.description}</p>
                {selectedEvent.source_name || selectedEvent.source_url ? (
                  <div className="rounded-xl border border-border/70 bg-surface/55 px-4 py-3">
                    <div className="text-xs text-text-secondary">출처</div>
                    <div className="mt-1 font-medium text-text">{selectedEvent.source_name || selectedEvent.source}</div>
                    {selectedEvent.source_url ? (
                      <a
                        className="ui-button-primary mt-3 px-4"
                        href={selectedEvent.source_url}
                        rel="noreferrer"
                        target="_blank"
                      >
                        공식 발표 보기
                      </a>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}
          </Modal>
        </>
      ) : (
        <WorkspaceStateCard
          eyebrow="일정 지연"
          title="시장 일정 캘린더를 아직 불러오지 못했습니다"
          message={error || "시장 일정 데이터를 불러오지 못했습니다."}
          tone="warning"
          kind="blocking"
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
