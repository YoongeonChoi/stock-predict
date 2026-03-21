"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const COUNTRIES = [
  { code: "US", label: "🇺🇸 US" },
  { code: "KR", label: "🇰🇷 KR" },
  { code: "JP", label: "🇯🇵 JP" },
];

export default function CalendarPage() {
  const [country, setCountry] = useState("US");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getCalendar(country).then(setData).catch(console.error).finally(() => setLoading(false));
  }, [country]);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
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
      ) : data ? (
        <div className="space-y-6">
          <div className="card">
            <h2 className="font-semibold mb-3">Major Recurring Events</h2>
            <div className="space-y-2">
              {data.major_events?.map((e: any, i: number) => (
                <div key={i} className="flex justify-between text-sm">
                  <span>{e.name}</span>
                  <span className="text-text-secondary">{e.frequency}</span>
                </div>
              ))}
            </div>
          </div>

          {data.economic_events?.length > 0 && (
            <div className="card">
              <h2 className="font-semibold mb-3">Upcoming Economic Events</h2>
              <div className="space-y-2">
                {data.economic_events.slice(0, 20).map((e: any, i: number) => (
                  <div key={i} className="flex justify-between text-sm border-b border-border/30 pb-1">
                    <span>{e.event || e.name || "Event"}</span>
                    <span className="text-text-secondary">{e.date}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <p className="text-text-secondary">No calendar data available.</p>
      )}
    </div>
  );
}
