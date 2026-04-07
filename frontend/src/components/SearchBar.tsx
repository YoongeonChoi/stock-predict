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
    <div ref={ref} className="relative w-full max-w-3xl" role="search" aria-label="사이트 검색">
      <label htmlFor="global-search-input" className="sr-only">
        티커 또는 종목명 검색
      </label>
      <div
        className={cn(
          "flex min-h-[var(--control-height-md)] items-center gap-3 rounded-[24px] border px-3 py-2.5 transition-[border-color,box-shadow,background-color] sm:min-h-[var(--control-height-lg)] sm:px-4 sm:py-3",
          focused || open
            ? "border-accent/35 bg-surface shadow-[0_22px_45px_-34px_rgba(37,99,235,0.22)]"
            : "border-border bg-surface/92"
        )}
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[18px] bg-accent/10 text-accent sm:h-11 sm:w-11">
          <Search size={18} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="hidden text-[10px] font-semibold uppercase tracking-[0.18em] text-text-secondary sm:block">
            빠른 종목 검색
          </div>
          <input
            id="global-search-input"
            type="search"
            name="global_search"
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
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="search"
            aria-expanded={open}
            aria-controls="global-search-results"
            placeholder="티커 또는 종목명 검색…"
            className="mt-0.5 w-full bg-transparent text-[0.94rem] text-text outline-none placeholder:text-text-secondary sm:text-[0.95rem]"
          />
        </div>
        <div className="hidden shrink-0 rounded-full border border-border px-3 py-1.5 text-[11px] text-text-secondary xl:inline-flex">
          Enter로 첫 결과 열기
        </div>
      </div>

      {loading && (
        <div className="absolute right-4 top-1/2 -translate-y-1/2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {open && query.length > 0 && (
        <div
          id="global-search-results"
          className="absolute top-full z-50 mt-2 w-full overflow-hidden rounded-[24px] border border-border bg-surface shadow-[0_20px_42px_-30px_rgba(15,23,42,0.24)]"
        >
          <div className="border-b border-border/70 px-4 py-3.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-text-secondary">
            검색 결과
          </div>

          {results.length > 0 ? (
            <div className="max-h-72 overflow-y-auto py-1">
              {results.map((r) => (
                <button
                  key={r.ticker}
                  onClick={() => select(r.ticker)}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left transition-[background-color,color] hover:bg-border/20 focus-visible:bg-border/20"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-text">{r.ticker}</span>
                      <span className="rounded-full border border-border px-2 py-0.5 text-[10px] text-text-secondary">
                        {r.country_code}
                      </span>
                    </div>
                    <div className="mt-1 truncate text-xs text-text-secondary">{r.name}</div>
                    {r.resolution_note ? <div className="mt-1 truncate text-[11px] text-text-secondary">{r.resolution_note}</div> : null}
                  </div>
                  <span className="text-[11px] text-text-secondary">{r.match_basis === "partial_ticker" ? "검색" : "해석"}</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="px-4 py-5 text-[0.95rem] text-text-secondary">
              일치하는 종목을 찾지 못했습니다. 티커나 종목명을 조금 더 구체적으로 입력해 보세요.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

