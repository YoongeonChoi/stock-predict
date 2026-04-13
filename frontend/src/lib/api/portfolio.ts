"use client";

import { del, get, post, put } from "@/lib/api/client";
import type { RequestOptions } from "@/lib/api/shared";
import type {
  DailyIdealPortfolio,
  PortfolioConditionalRecommendationResponse,
  PortfolioData,
  PortfolioEventRadarResponse,
  PortfolioHoldingCreateResponse,
  PortfolioOptimalRecommendationResponse,
  PortfolioProfile,
  PortfolioRecommendationStyle,
} from "@/lib/api";

export const portfolioApi = {
  getPortfolio: (options?: RequestOptions) => get<PortfolioData>("/api/portfolio", options),
  getPortfolioProfile: (options?: RequestOptions) => get<PortfolioProfile>("/api/portfolio/profile", options),
  updatePortfolioProfile: (data: PortfolioProfile) => put<PortfolioProfile>("/api/portfolio/profile", data),
  getPortfolioConditionalRecommendation: (
    params: {
      country_code?: string;
      sector?: string;
      style?: PortfolioRecommendationStyle;
      max_items?: number;
      min_up_probability?: number;
      exclude_holdings?: boolean;
      watchlist_only?: boolean;
    },
    options?: RequestOptions,
  ) => {
    const search = new URLSearchParams();
    if (params.country_code) search.set("country_code", params.country_code);
    if (params.sector) search.set("sector", params.sector);
    if (params.style) search.set("style", params.style);
    if (params.max_items != null) search.set("max_items", String(params.max_items));
    if (params.min_up_probability != null) search.set("min_up_probability", String(params.min_up_probability));
    if (params.exclude_holdings != null) search.set("exclude_holdings", String(params.exclude_holdings));
    if (params.watchlist_only != null) search.set("watchlist_only", String(params.watchlist_only));
    return get<PortfolioConditionalRecommendationResponse>(
      `/api/portfolio/recommendations/conditional?${search.toString()}`,
      options,
    );
  },
  getPortfolioOptimalRecommendation: (options?: RequestOptions) =>
    get<PortfolioOptimalRecommendationResponse>("/api/portfolio/recommendations/optimal", options),
  getPortfolioEventRadar: (days = 14, options?: RequestOptions) =>
    get<PortfolioEventRadarResponse>(`/api/portfolio/event-radar?days=${days}`, options),
  getDailyIdealPortfolio: (refresh = false, historyLimit = 10) =>
    get<DailyIdealPortfolio>(`/api/portfolio/ideal?refresh=${refresh}&history_limit=${historyLimit}`),
  addPortfolioHolding: (data: { ticker: string; buy_price: number; quantity: number; buy_date: string; country_code?: string }) =>
    post<PortfolioHoldingCreateResponse>("/api/portfolio/holdings", data),
  updatePortfolioHolding: (
    id: number,
    data: { ticker: string; buy_price: number; quantity: number; buy_date: string; country_code?: string },
  ) => put<PortfolioHoldingCreateResponse>(`/api/portfolio/holdings/${id}`, data),
  removePortfolioHolding: (id: number) => del<{ status: "ok" }>(`/api/portfolio/holdings/${id}`),
};
