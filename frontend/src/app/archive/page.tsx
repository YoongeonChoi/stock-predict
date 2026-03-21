"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function ArchivePage() {
  const [archives, setArchives] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getArchive().then(setArchives).catch(console.error).finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Report Archive</h1>

      {loading ? (
        <div className="animate-pulse space-y-3">{[1, 2, 3].map((i) => <div key={i} className="h-20 bg-border rounded" />)}</div>
      ) : archives.length === 0 ? (
        <p className="text-text-secondary">No archived reports yet. Reports are saved automatically when generated.</p>
      ) : (
        <div className="space-y-2">
          {archives.map((a: any) => (
            <div key={a.id} className="card flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    a.report_type === "country" ? "bg-blue-500/20 text-blue-500" :
                    a.report_type === "sector" ? "bg-purple-500/20 text-purple-500" : "bg-emerald-500/20 text-emerald-500"
                  }`}>{a.report_type}</span>
                  {a.country_code && <span className="text-xs text-text-secondary">{a.country_code}</span>}
                  {a.ticker && <span className="text-xs font-mono">{a.ticker}</span>}
                </div>
                <p className="text-sm text-text-secondary mt-1">{a.preview}</p>
              </div>
              <div className="text-right shrink-0 ml-4">
                <div className="text-xs text-text-secondary">{new Date(a.created_at * 1000).toLocaleDateString()}</div>
                <a href={`/api/export/pdf/${a.id}`} className="text-xs text-accent hover:underline">PDF</a>
                <span className="text-text-secondary mx-1">·</span>
                <a href={`/api/export/csv/${a.id}`} className="text-xs text-accent hover:underline">CSV</a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
