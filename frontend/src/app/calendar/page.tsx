"use client";

import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";

const COUNTRIES = [
  { code: "US", label: "🇺🇸 US" },
  { code: "KR", label: "🇰🇷 KR" },
  { code: "JP", label: "🇯🇵 JP" },
];

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

interface CalEvent {
  type: "economic" | "earnings";
  title: string;
  date: string;
  detail?: string;
}

const EVENT_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  economic: { bg: "bg-blue-500/15", text: "text-blue-600 dark:text-blue-400", border: "border-l-blue-500" },
  earnings: { bg: "bg-amber-500/15", text: "text-amber-600 dark:text-amber-400", border: "border-l-amber-500" },
};

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay();
}

function formatMonthYear(year: number, month: number) {
  return new Date(year, month).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

function parseDate(d: string): string | null {
  if (!d) return null;
  const m = d.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[1]}-${m[2]}-${m[3]}` : null;
}

export default function CalendarPage() {
  const [country, setCountry] = useState("US");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const now = new Date();
  const [viewYear, setViewYear] = useState(now.getFullYear());
  const [viewMonth, setViewMonth] = useState(now.getMonth());

  useEffect(() => {
    setLoading(true);
    api.getCalendar(country).then(setData).catch(console.error).finally(() => setLoading(false));
  }, [country]);

  const events = useMemo<CalEvent[]>(() => {
    if (!data) return [];
    const list: CalEvent[] = [];
    (data.economic_events || []).forEach((e: any) => {
      const d = parseDate(e.date);
      if (d) list.push({ type: "economic", title: e.event || e.name || "Economic Event", date: d, detail: e.country });
    });
    (data.earnings_events || []).forEach((e: any) => {
      const d = parseDate(e.date);
      if (d) list.push({ type: "earnings", title: `${e.symbol || "?"} Earnings`, date: d, detail: e.symbol });
    });
    return list;
  }, [data]);

  const eventsByDate = useMemo(() => {
    const map: Record<string, CalEvent[]> = {};
    events.forEach((e) => {
      if (!map[e.date]) map[e.date] = [];
      map[e.date].push(e);
    });
    return map;
  }, [events]);

  const daysInMonth = getDaysInMonth(viewYear, viewMonth);
  const firstDay = getFirstDayOfMonth(viewYear, viewMonth);

  const calendarCells: (number | null)[] = [];
  for (let i = 0; i < firstDay; i++) calendarCells.push(null);
  for (let d = 1; d <= daysInMonth; d++) calendarCells.push(d);
  while (calendarCells.length % 7 !== 0) calendarCells.push(null);

  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;

  const goToPrevMonth = () => {
    if (viewMonth === 0) { setViewMonth(11); setViewYear(viewYear - 1); }
    else setViewMonth(viewMonth - 1);
  };

  const goToNextMonth = () => {
    if (viewMonth === 11) { setViewMonth(0); setViewYear(viewYear + 1); }
    else setViewMonth(viewMonth + 1);
  };

  const selectedEvents = selectedDate ? (eventsByDate[selectedDate] || []) : [];

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Economic Calendar</h1>
        <div className="flex gap-2">
          {COUNTRIES.map((c) => (
            <button
              key={c.code}
              onClick={() => setCountry(c.code)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                country === c.code ? "bg-accent text-white" : "bg-surface border border-border hover:border-accent/50"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="animate-pulse space-y-3">{[1, 2, 3].map((i) => <div key={i} className="h-16 bg-border rounded" />)}</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Calendar Grid */}
          <div className="lg:col-span-3 card !p-4">
            <div className="flex items-center justify-between mb-4">
              <button onClick={goToPrevMonth} className="p-2 rounded-lg hover:bg-border/50 transition-colors text-text-secondary hover:text-text">&larr;</button>
              <h2 className="font-semibold text-lg">{formatMonthYear(viewYear, viewMonth)}</h2>
              <button onClick={goToNextMonth} className="p-2 rounded-lg hover:bg-border/50 transition-colors text-text-secondary hover:text-text">&rarr;</button>
            </div>

            {/* Day headers */}
            <div className="grid grid-cols-7 border-b border-border mb-1">
              {DAYS.map((d) => (
                <div key={d} className="text-center text-xs font-medium text-text-secondary py-2">{d}</div>
              ))}
            </div>

            {/* Calendar cells */}
            <div className="grid grid-cols-7">
              {calendarCells.map((day, idx) => {
                if (day === null) return <div key={idx} className="min-h-[90px] border-b border-r border-border/30" />;

                const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                const dayEvents = eventsByDate[dateStr] || [];
                const isToday = dateStr === todayStr;
                const isSelected = dateStr === selectedDate;

                return (
                  <button
                    key={idx}
                    onClick={() => setSelectedDate(isSelected ? null : dateStr)}
                    className={`min-h-[90px] border-b border-r border-border/30 p-1 text-left flex flex-col transition-colors
                      ${isSelected ? "bg-accent/10" : "hover:bg-border/20"}
                    `}
                  >
                    <span className={`text-xs font-medium mb-0.5 w-6 h-6 flex items-center justify-center rounded-full
                      ${isToday ? "bg-accent text-white" : "text-text-secondary"}
                    `}>
                      {day}
                    </span>

                    {/* Event bars */}
                    <div className="flex flex-col gap-[2px] w-full overflow-hidden flex-1">
                      {dayEvents.slice(0, 3).map((e, i) => {
                        const c = EVENT_COLORS[e.type];
                        return (
                          <div
                            key={i}
                            className={`text-[10px] leading-tight px-1 py-[1px] rounded-sm truncate border-l-2 ${c.bg} ${c.text} ${c.border}`}
                          >
                            {e.title}
                          </div>
                        );
                      })}
                      {dayEvents.length > 3 && (
                        <span className="text-[10px] text-text-secondary pl-1">+{dayEvents.length - 3} more</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Legend */}
            <div className="flex gap-6 mt-3 text-xs text-text-secondary">
              <div className="flex items-center gap-1.5">
                <div className="w-8 h-3 rounded-sm bg-blue-500/15 border-l-2 border-l-blue-500" />
                Economic
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-8 h-3 rounded-sm bg-amber-500/15 border-l-2 border-l-amber-500" />
                Earnings
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Selected date events */}
            <div className="card">
              <h3 className="font-semibold mb-3 text-sm">
                {selectedDate
                  ? new Date(selectedDate + "T12:00:00").toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" })
                  : "Select a date"}
              </h3>
              {selectedDate ? (
                selectedEvents.length > 0 ? (
                  <div className="space-y-2 max-h-72 overflow-y-auto">
                    {selectedEvents.map((e, i) => {
                      const c = EVENT_COLORS[e.type];
                      return (
                        <div key={i} className={`flex items-start gap-2 text-sm p-2 rounded-md border-l-2 ${c.bg} ${c.border}`}>
                          <div>
                            <div className={`font-medium ${c.text}`}>{e.title}</div>
                            {e.detail && <div className="text-xs text-text-secondary mt-0.5">{e.detail}</div>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-text-secondary">No events on this date.</p>
                )
              ) : (
                <p className="text-sm text-text-secondary">Click a date on the calendar to view events.</p>
              )}
            </div>

            {/* Major recurring events */}
            {data?.major_events?.length > 0 && (
              <div className="card">
                <h3 className="font-semibold mb-3 text-sm">Major Events</h3>
                <div className="space-y-2">
                  {data.major_events.map((e: any, i: number) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span className="font-medium">{e.name}</span>
                      <span className="text-text-secondary text-xs">{e.frequency}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Upcoming events list */}
            <div className="card">
              <h3 className="font-semibold mb-3 text-sm">Upcoming</h3>
              <div className="space-y-1 max-h-80 overflow-y-auto">
                {events.slice(0, 20).map((e, i) => {
                  const c = EVENT_COLORS[e.type];
                  return (
                    <button
                      key={i}
                      onClick={() => setSelectedDate(e.date)}
                      className="w-full flex items-center gap-2 text-sm text-left hover:bg-border/30 rounded p-1.5 transition-colors"
                    >
                      <div className={`w-1 h-6 rounded-full shrink-0 ${e.type === "economic" ? "bg-blue-500" : "bg-amber-500"}`} />
                      <div className="flex-1 min-w-0">
                        <div className="truncate text-xs">{e.title}</div>
                        <div className="text-[10px] text-text-secondary">{e.date.slice(5)}</div>
                      </div>
                    </button>
                  );
                })}
                {events.length === 0 && <p className="text-sm text-text-secondary">No upcoming events.</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
