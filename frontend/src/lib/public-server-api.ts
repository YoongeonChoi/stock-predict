import "server-only";

import type {
  ArchiveEntry,
  CalendarResponse,
  DailyBriefingResponse,
  HeatmapData,
  MarketMovers,
  PredictionAccuracyStats,
  ResearchArchiveEntry,
  ResearchArchiveStatus,
  ScreenerResponse,
} from "@/lib/api";
import type { CountryListItem, CountryReport, OpportunityRadarResponse } from "@/lib/types";

const API_BASE_URL = (process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

async function getPublicJson<T>(path: string, revalidate: number): Promise<T> {
  const response = await fetch(apiUrl(path), {
    next: { revalidate },
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`${path} -> ${response.status}`);
  }
  return response.json();
}

export function getPublicCountries() {
  return getPublicJson<CountryListItem[]>("/api/countries", 60);
}

export function getPublicMarketIndicators() {
  return getPublicJson<Array<{ name: string; price: number; change_pct: number }>>("/api/market/indicators", 60);
}

export function getPublicDailyBriefing() {
  return getPublicJson<DailyBriefingResponse>("/api/briefing/daily", 60);
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
  return getPublicJson<PredictionAccuracyStats>("/api/archive/accuracy/stats", 300);
}

export function getPublicResearchArchive(region: "KR" | "US" | "EU" | "JP" = "KR", limit = 24) {
  return getPublicJson<ResearchArchiveEntry[]>(`/api/archive/research?region=${region}&limit=${limit}`, 300);
}

export function getPublicResearchStatus() {
  return getPublicJson<ResearchArchiveStatus>("/api/archive/research/status?cached=true", 300);
}

export function getPublicScreenerSeed(country = "KR", limit = 10) {
  return getPublicJson<ScreenerResponse & { generated_at?: string; partial?: boolean; fallback_reason?: string | null }>(
    `/api/screener?country=${encodeURIComponent(country)}&limit=${limit}`,
    90,
  );
}
