import "server-only";

import type {
  ArchiveEntry,
  CalendarResponse,
  DailyBriefingResponse,
  HeatmapData,
  MarketMovers,
  PredictionLabResponse,
  PredictionAccuracyStats,
  ResearchArchiveEntry,
  ResearchArchiveStatus,
  ScreenerResponse,
} from "@/lib/api";
import type { CountryListItem, CountryReport, OpportunityRadarResponse, StockDetail } from "@/lib/types";

const API_BASE_URL = (process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const DEFAULT_PUBLIC_FETCH_TIMEOUT_MS = Number.parseInt(process.env.PUBLIC_SERVER_FETCH_TIMEOUT_MS || "8000", 10);
const HIBERNATE_WAKE_RETRY_DELAY_MS = Number.parseInt(process.env.PUBLIC_SERVER_HIBERNATE_RETRY_DELAY_MS || "900", 10);

function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

async function getPublicJson<T>(path: string, revalidate: number, timeoutMs = DEFAULT_PUBLIC_FETCH_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const requestInit = {
      next: { revalidate },
      headers: { Accept: "application/json" },
      signal: controller.signal,
    };
    let response = await fetch(apiUrl(path), requestInit);
    const renderRouting = response.headers.get("x-render-routing") || "";
    if (response.status === 503 && renderRouting.startsWith("hibernate-") && HIBERNATE_WAKE_RETRY_DELAY_MS > 0) {
      await new Promise((resolve) => setTimeout(resolve, HIBERNATE_WAKE_RETRY_DELAY_MS));
      response = await fetch(apiUrl(path), requestInit);
    }
    if (!response.ok) {
      throw new Error(`${path} -> ${response.status}`);
    }
    return response.json();
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(`${path} -> timeout ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function getPublicCountries() {
  return getPublicJson<CountryListItem[]>("/api/countries", 60);
}

export function getPublicMarketIndicators() {
  return getPublicJson<Array<{ name: string; price: number; change_pct: number }>>("/api/market/indicators", 60);
}

export interface SectorPerformanceItem {
  sector: string;
  ticker: string;
  price: number;
  change_pct: number;
  breadth: number;
  leader_name: string;
}

export function getPublicSectorPerformance(code = "KR") {
  return getPublicJson<SectorPerformanceItem[]>(`/api/country/${code}/sector-performance`, 120);
}

export function getPublicDailyBriefing() {
  return getPublicJson<DailyBriefingResponse>("/api/briefing/daily", 60, 16000);
}

export function getPublicCountryReport(code = "KR") {
  return getPublicJson<CountryReport>(`/api/country/${encodeURIComponent(code)}/report`, 60);
}

export function getPublicHeatmap(code = "KR") {
  return getPublicJson<HeatmapData & { generated_at?: string; partial?: boolean; fallback_reason?: string | null }>(
    `/api/country/${encodeURIComponent(code)}/heatmap`,
    90,
  );
}

export function getPublicMarketMovers(code = "KR") {
  return getPublicJson<MarketMovers & { generated_at?: string; partial?: boolean; fallback_reason?: string | null }>(
    `/api/market/movers/${encodeURIComponent(code)}`,
    90,
  );
}

export function getPublicOpportunities(code = "KR", limit = 12) {
  return getPublicJson<OpportunityRadarResponse & { partial?: boolean; fallback_reason?: string | null }>(
    `/api/market/opportunities/${encodeURIComponent(code)}?limit=${limit}`,
    90,
    18000,
  );
}

export function getPublicStockDetail(ticker: string) {
  return getPublicJson<StockDetail & { partial?: boolean; fallback_reason?: string | null }>(
    `/api/stock/${encodeURIComponent(ticker)}/detail`,
    120,
    18000,
  );
}

export function getPublicPredictionLab(limitRecent = 40, refresh = false) {
  return getPublicJson<PredictionLabResponse>(
    `/api/research/predictions?limit_recent=${limitRecent}&refresh=${refresh}`,
    180,
    10000,
  );
}

export function getPublicCalendar(code = "KR", year?: number, month?: number) {
  const today = new Date();
  const resolvedYear = year ?? today.getFullYear();
  const resolvedMonth = month ?? today.getMonth() + 1;
  return getPublicJson<CalendarResponse & { partial?: boolean; fallback_reason?: string | null }>(
    `/api/calendar/${encodeURIComponent(code)}?year=${resolvedYear}&month=${resolvedMonth}`,
    300,
  );
}

export function getPublicArchive() {
  return getPublicJson<ArchiveEntry[]>("/api/archive", 300);
}

export function getPublicPredictionAccuracy() {
  return getPublicJson<PredictionAccuracyStats>("/api/archive/accuracy/stats?refresh=false", 300);
}

export function getPublicResearchArchive(region?: "KR" | "US" | "EU" | "JP", limit = 40) {
  const searchParams = new URLSearchParams({
    limit: String(limit),
    auto_refresh: "false",
  });
  if (region) {
    searchParams.set("region_code", region);
  }
  return getPublicJson<ResearchArchiveEntry[]>(
    `/api/archive/research?${searchParams.toString()}`,
    300,
    10000,
  );
}

export function getPublicResearchStatus() {
  return getPublicJson<ResearchArchiveStatus>("/api/archive/research/status?refresh_if_missing=false", 300, 10000);
}

export function getPublicScreenerSeed(country = "KR", limit = 10) {
  return getPublicJson<ScreenerResponse & { generated_at?: string; partial?: boolean; fallback_reason?: string | null }>(
    `/api/screener?country=${encodeURIComponent(country)}&limit=${limit}`,
    90,
    12000,
  );
}
