"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

import { api } from "@/lib/api";
import type { SearchResult } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [focused, setFocused] = useState(false);
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
    if (query.length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }

    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await api.search(query);
        setResults(r);
        setOpen(true);
      } catch {
        setResults([]);
        setOpen(true);
      }
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
    <div ref={ref} className="relative w-full max-w-2xl">
      <div
        className={cn(
          "flex items-center gap-3 rounded-[22px] border px-4 py-3 transition-all",
          focused || open
            ? "border-accent/35 bg-white/75 shadow-[0_22px_45px_-34px_rgba(56,189,248,0.65)] dark:bg-slate-900/70"
            : "border-border bg-white/58 dark:bg-slate-900/52"
        )}
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
          <Search size={18} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="hidden text-[10px] font-semibold uppercase tracking-[0.22em] text-text-secondary sm:block">
            빠른 종목 검색
          </div>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => {
              setFocused(true);
              if (query.length > 0) setOpen(true);
            }}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && results[0]) {
                e.preventDefault();
                select(results[0].ticker);
              }
            }}
            placeholder="티커, 종목명, 한국·미국·일본 종목 검색"
            className="mt-0.5 w-full bg-transparent text-sm text-text outline-none placeholder:text-text-secondary"
          />
        </div>
        <div className="hidden shrink-0 rounded-full border border-border px-2.5 py-1 text-[11px] text-text-secondary md:inline-flex">
          Enter로 첫 결과 열기
        </div>
      </div>

      {loading && (
        <div className="absolute right-4 top-1/2 -translate-y-1/2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {open && query.length > 0 && (
        <div className="absolute top-full z-50 mt-2 w-full overflow-hidden rounded-[22px] border border-border bg-surface/96 shadow-[0_28px_60px_-36px_rgba(15,23,42,0.5)] backdrop-blur-2xl">
          <div className="border-b border-border/70 px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-text-secondary">
            검색 결과
          </div>

          {results.length > 0 ? (
            <div className="max-h-72 overflow-y-auto py-1">
              {results.map((r) => (
                <button
                  key={r.ticker}
                  onClick={() => select(r.ticker)}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-border/20"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-text">{r.ticker}</span>
                      <span className="rounded-full border border-border px-2 py-0.5 text-[10px] text-text-secondary">
                        {r.country_code}
                      </span>
                    </div>
                    <div className="mt-1 truncate text-xs text-text-secondary">{r.name}</div>
                  </div>
                  <span className="text-[11px] text-text-secondary">열기</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="px-4 py-5 text-sm text-text-secondary">
              일치하는 종목을 찾지 못했습니다. 티커나 종목명을 조금 더 구체적으로 입력해 보세요.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
