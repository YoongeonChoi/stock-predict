"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { SearchResult } from "@/lib/api";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (query.length < 1) { setResults([]); return; }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await api.search(query);
        setResults(r);
        setOpen(true);
      } catch { setResults([]); }
      setLoading(false);
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  const select = (ticker: string) => {
    setOpen(false);
    setQuery("");
    router.push(`/stock/${encodeURIComponent(ticker)}`);
  };

  return (
    <div ref={ref} className="relative w-full max-w-sm">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder="Search ticker..."
        className="w-full px-3 py-1.5 rounded-lg bg-surface border border-border text-sm focus:outline-none focus:border-accent"
      />
      {loading && (
        <div className="absolute right-2 top-1/2 -translate-y-1/2">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      )}
      {open && results.length > 0 && (
        <div className="absolute z-50 top-full mt-1 w-full bg-surface border border-border rounded-lg shadow-lg max-h-64 overflow-y-auto">
          {results.map((r) => (
            <button
              key={r.ticker}
              onClick={() => select(r.ticker)}
              className="w-full text-left px-3 py-2 hover:bg-border/30 transition-colors text-sm flex justify-between"
            >
              <div>
                <span className="font-medium">{r.ticker}</span>
                <span className="text-text-secondary ml-2 text-xs">{r.name}</span>
              </div>
              <span className="text-[10px] text-text-secondary">{r.country_code}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
