"use client";

import { get } from "@/lib/api/client";
import type { RequestOptions } from "@/lib/api/shared";
import type {
  CalendarResponse,
  HeatmapData,
  MarketMovers,
  ScreenerResponse,
} from "@/lib/api";
import type {
  CountryListItem,
  CountryReport,
  IndexForecast,
  OpportunityRadarResponse,
  SectorListItem,
  SectorReport,
} from "@/lib/types";

export const marketApi = {
  getCountries: () => get<CountryListItem[]>("/api/countries"),
  getMarketIndicators: () => get<{ name: string; price: number; change_pct: number }[]>("/api/market/indicators"),
  getSectorPerformance: (code: string) =>
    get<{ sector: string; ticker: string; price: number; change_pct: number }[]>(
      `/api/country/${code}/sector-performance`,
    ),
  getHeatmap: (code: string, options?: RequestOptions) => get<HeatmapData>(`/api/country/${code}/heatmap`, options),
  getCountryReport: (code: string, options?: RequestOptions) => get<CountryReport>(`/api/country/${code}/report`, options),
  getCountryForecast: (code: string) => get<IndexForecast>(`/api/country/${code}/forecast`),
  getSectors: (code: string) => get<SectorListItem[]>(`/api/country/${code}/sectors`),
  getSectorReport: (code: string, sectorId: string) => get<SectorReport>(`/api/country/${code}/sector/${sectorId}/report`),
  getMarketOpportunities: (code: string, limit = 12, options?: RequestOptions) =>
    get<OpportunityRadarResponse>(`/api/market/opportunities/${code}?limit=${limit}`, options),
  getCalendar: (code: string, year?: number, month?: number, options?: RequestOptions) => {
    const qs = new URLSearchParams();
    if (year) qs.set("year", String(year));
    if (month) qs.set("month", String(month));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return get<CalendarResponse>(`/api/calendar/${code}${suffix}`, options);
  },
  getScreener: (params: Record<string, string>, options?: RequestOptions) => {
    const qs = new URLSearchParams(params).toString();
    return get<ScreenerResponse>(`/api/screener?${qs}`, options);
  },
  getMarketMovers: (code: string, options?: RequestOptions) => get<MarketMovers>(`/api/market/movers/${code}`, options),
};
