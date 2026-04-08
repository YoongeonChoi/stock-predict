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
    const handler = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
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

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const response = await api.search(query);
        setResults(response);
        setOpen(true);
      } catch {
        setResults([]);
        setOpen(true);
      } finally {
        setLoading(false);
      }
    }, 260);

    return () => clearTimeout(timer);
  }, [query]);

  const select = (ticker: string) => {
    setOpen(false);
    setQuery("");
    router.push(`/stock/${encodeURIComponent(ticker)}`);
  };

  return (
    <div ref={ref} className="relative w-full max-w-3xl" role="search" aria-label="종목 검색">
      <label htmlFor="global-search-input" className="sr-only">
        티커 또는 종목명 검색
      </label>
      <div
        className={cn(
          "flex min-h-[var(--control-height-lg)] items-center gap-3 border px-4 py-3 transition-colors",
          focused || open
            ? "rounded-[14px] border-accent/30 bg-surface"
            : "rounded-[12px] border-border/15 bg-surface",
        )}
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center text-text-secondary">
          <Search size={18} />
        </div>
        <input
          id="global-search-input"
          type="search"
          name="global_search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onFocus={() => {
            setFocused(true);
            if (query.length > 0) setOpen(true);
          }}
          onBlur={() => setFocused(false)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && results[0]) {
              event.preventDefault();
              select(results[0].ticker);
            }
          }}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="search"
          aria-expanded={open}
          aria-controls="global-search-results"
          placeholder="티커 또는 종목명을 입력하세요"
          className="w-full bg-transparent text-[0.98rem] text-text outline-none placeholder:text-text-secondary"
        />
        <div className="hidden shrink-0 font-mono text-[11px] uppercase tracking-[0.08em] text-text-secondary xl:block">
          Enter
        </div>
      </div>

      {loading ? (
        <div className="absolute right-4 top-1/2 -translate-y-1/2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      ) : null}

      {open && query.length > 0 ? (
        <div
          id="global-search-results"
          className="absolute top-full z-50 mt-2 w-full overflow-hidden rounded-[14px] border border-border/15 bg-surface"
        >
          {results.length > 0 ? (
            <div className="max-h-72 overflow-y-auto">
              {results.map((result, index) => (
                <button
                  key={result.ticker}
                  onClick={() => select(result.ticker)}
                  className={cn(
                    "grid w-full grid-cols-[minmax(0,1fr)_auto] gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-muted focus-visible:bg-surface-muted",
                    index < results.length - 1 ? "border-b border-border/10" : "",
                  )}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[0.9rem] font-semibold text-text">{result.ticker}</span>
                      <span className="status-token">{result.country_code}</span>
                    </div>
                    <div className="mt-1 truncate text-sm text-text">{result.name}</div>
                    {result.resolution_note ? (
                      <div className="mt-1 truncate text-[12px] text-text-secondary">{result.resolution_note}</div>
                    ) : null}
                  </div>
                  <span className="self-start font-mono text-[11px] uppercase tracking-[0.08em] text-text-secondary">
                    {result.match_basis === "partial_ticker" ? "검색" : "해석"}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="px-4 py-5 text-[0.94rem] leading-7 text-text-secondary">
              일치하는 종목을 찾지 못했습니다. 티커나 종목명을 조금 더 구체적으로 입력해 주세요.
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
