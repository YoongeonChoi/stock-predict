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
  type: "economic" | "earnings" | "major";
  title: string;
  date: string;
  detail?: string;
}

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay();
}

function formatMonthYear(year: number, month: number) {
  return new Date(year, month).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });
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
    <div className="max-w-5xl mx-auto space-y-6">
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
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Calendar Grid */}
          <div className="lg:col-span-2 card">
            <div className="flex items-center justify-between mb-4">
              <button onClick={goToPrevMonth} className="p-2 rounded-lg hover:bg-border/50 transition-colors text-text-secondary hover:text-text">&larr;</button>
              <h2 className="font-semibold text-lg">{formatMonthYear(viewYear, viewMonth)}</h2>
              <button onClick={goToNextMonth} className="p-2 rounded-lg hover:bg-border/50 transition-colors text-text-secondary hover:text-text">&rarr;</button>
            </div>

            {/* Day headers */}
            <div className="grid grid-cols-7 gap-1 mb-1">
              {DAYS.map((d) => (
                <div key={d} className="text-center text-xs font-medium text-text-secondary py-1">{d}</div>
              ))}
            </div>

            {/* Calendar cells */}
            <div className="grid grid-cols-7 gap-1">
              {calendarCells.map((day, idx) => {
                if (day === null) return <div key={idx} className="aspect-square" />;

                const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                const dayEvents = eventsByDate[dateStr] || [];
                const isToday = dateStr === todayStr;
                const isSelected = dateStr === selectedDate;
                const hasEconomic = dayEvents.some((e) => e.type === "economic");
                const hasEarnings = dayEvents.some((e) => e.type === "earnings");

                return (
                  <button
                    key={idx}
                    onClick={() => setSelectedDate(isSelected ? null : dateStr)}
                    className={`aspect-square rounded-lg flex flex-col items-center justify-center relative transition-all text-sm
                      ${isToday ? "ring-2 ring-accent" : ""}
                      ${isSelected ? "bg-accent/20 border border-accent" : "hover:bg-border/40"}
                      ${dayEvents.length > 0 ? "font-medium" : "text-text-secondary"}
                    `}
                  >
                    <span>{day}</span>
                    {dayEvents.length > 0 && (
                      <div className="flex gap-0.5 mt-0.5">
                        {hasEconomic && <span className="w-1.5 h-1.5 rounded-full bg-accent" />}
                        {hasEarnings && <span className="w-1.5 h-1.5 rounded-full bg-warning" />}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Legend */}
            <div className="flex gap-4 mt-4 text-xs text-text-secondary">
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-accent" />Economic</div>
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-warning" />Earnings</div>
            </div>
          </div>

          {/* Sidebar: selected date events + major events */}
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
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {selectedEvents.map((e, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm">
                        <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${e.type === "economic" ? "bg-accent" : "bg-warning"}`} />
                        <div>
                          <div className="font-medium">{e.title}</div>
                          {e.detail && <div className="text-xs text-text-secondary">{e.detail}</div>}
                        </div>
                      </div>
                    ))}
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
                <h3 className="font-semibold mb-3 text-sm">Major Recurring Events</h3>
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
              <h3 className="font-semibold mb-3 text-sm">Upcoming Events</h3>
              <div className="space-y-1.5 max-h-72 overflow-y-auto">
                {events.slice(0, 15).map((e, i) => (
                  <button
                    key={i}
                    onClick={() => setSelectedDate(e.date)}
                    className="w-full flex items-center gap-2 text-sm text-left hover:bg-border/30 rounded p-1 transition-colors"
                  >
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${e.type === "economic" ? "bg-accent" : "bg-warning"}`} />
                    <span className="flex-1 truncate">{e.title}</span>
                    <span className="text-xs text-text-secondary shrink-0">{e.date.slice(5)}</span>
                  </button>
                ))}
                {events.length === 0 && <p className="text-sm text-text-secondary">No upcoming events.</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
