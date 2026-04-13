import { apiPath, del, get, post, put, request } from "@/lib/api/client";
import { accountApi } from "@/lib/api/account";
import { marketApi } from "@/lib/api/market";
import { portfolioApi } from "@/lib/api/portfolio";
import type { RequestOptions, StockDetailRequestOptions } from "@/lib/api/shared";
import { systemApi } from "@/lib/api/system";
export { apiPath };
export {
  AUTH_REQUIRED_EVENT,
  ApiError,
  ApiTimeoutError,
  getApiRetryAfterSeconds,
  isApiErrorCode,
  isAuthRequiredError,
} from "@/lib/api/errors";
export type { ApiErrorInfo, AuthRequiredEventDetail } from "@/lib/api/errors";
export type { RequestOptions, StockDetailRequestOptions } from "@/lib/api/shared";
export type {
  AccountProfile, AccountProfileUpdateRequest, AccountDeleteRequest, AccountDeleteResponse,
  SignUpValidationRequest, SignUpValidationResponse, UsernameAvailabilityResponse, CompositeScoreItem,
  CompositeScoreDetail, CompositeScore, HeatmapStock, HeatmapSector,
  HeatmapData, TechSignalItem, TechSummaryGroup, TechSummary,
  PivotLevel, PivotPoints, ScreenerResult, ScreenerResponse,
  PortfolioHolding, PortfolioStressScenario, PortfolioRiskRegime, PortfolioExecutionMixItem,
  PortfolioActionQueueItem, PortfolioRiskSnapshot, PortfolioModelBudget, PortfolioModelSummary,
  PortfolioModelAllocationItem, PortfolioModelItem, PortfolioModelPortfolio, PortfolioRecommendationStyle,
  PortfolioRecommendationBudget, PortfolioRecommendationSummary, PortfolioRecommendationMarketView, PortfolioRecommendationItem,
  PortfolioConditionalRecommendationFilters, PortfolioConditionalRecommendationResponse, PortfolioOptimalRecommendationResponse, DailyIdealPortfolioTargetDate,
  DailyIdealPortfolioMarketView, DailyIdealPortfolioPosition, DailyIdealPortfolioHistoryEntry, DailyIdealPortfolio,
  PortfolioData, PortfolioProfile, PortfolioSummary, PortfolioHoldingCreateResponse,
  WatchlistAddResponse, MarketMovers, PredictionAccuracyStats, ArchiveEntry,
  ResearchRegionCode, ResearchArchiveSourceResult, ResearchArchiveSourceCount, ResearchArchiveRegionCount,
  ResearchArchiveStatus, ResearchArchiveEntry, PredictionBreakdownRow, PredictionCalibrationBucket,
  PredictionTrendPoint, PredictionRecentRecord, PredictionLabActionItem, PredictionLabFailurePattern,
  PredictionLabReviewItem, PredictionLabRadarTagStat, PredictionLabRadarCohort, PredictionLabRadarReviewItem,
  PredictionLabRadarProfile, PredictionLabRadarSummary, PredictionLabResponse, StartupTaskStatus,
  DataSourceStatus, ForecastModelSummary, RouteStabilitySummaryRow, RouteStabilityFirstUsableMetrics,
  RouteStabilityFailureSummary, RouteStabilityFailureClassSummary, SystemDiagnostics, CalendarMajorEvent,
  CalendarSummary, CalendarEvent, CalendarResponse, SearchResult,
  TickerResolution, MarketSessionItem, MarketSessionsResponse, DailyBriefingMarketView,
  DailyBriefingFocusCard, DailyBriefingEvent, DailyBriefingResponse, PortfolioEventRadarEvent,
  PortfolioEventRadarResponse, ForecastDeltaHistoryItem, ForecastDeltaResponse, WatchlistTrackingState,
  WatchlistTrackingSnapshot, WatchlistTrackingAccuracySummary, WatchlistCurrentContextSummary, WatchlistTrackingDetailResponse,
  WatchlistTrackingToggleResponse,
} from "@/lib/api/types";

export const api = {
  ...accountApi,
  ...marketApi,
  ...portfolioApi,
  getStockDetail: (ticker: string, options: StockDetailRequestOptions = {}) => {
    const { preferFull = false, ...requestOptions } = options;
    const query = preferFull ? "?prefer_full=true" : "";
    return get<import("./types").StockDetail>(`/api/stock/${encodeURIComponent(ticker)}/detail${query}`, requestOptions);
  },
  getStockChart: (ticker: string, period = "3mo") =>
    get<{ data: import("./types").PricePoint[] }>(`/api/stock/${encodeURIComponent(ticker)}/chart?period=${period}`),
  getTechSummary: (ticker: string) => get<TechSummary>(`/api/stock/${encodeURIComponent(ticker)}/technical-summary`),
  getPivotPoints: (ticker: string) => get<PivotPoints>(`/api/stock/${encodeURIComponent(ticker)}/pivot-points`),
  getWatchlist: (options?: RequestOptions) => get<import("./types").WatchlistItem[]>("/api/watchlist", options),
  addWatchlist: (ticker: string, country_code = "KR") => post<WatchlistAddResponse>(`/api/watchlist/${ticker}?country_code=${country_code}`),
  removeWatchlist: (ticker: string) => del(`/api/watchlist/${ticker}`),
  enableWatchlistTracking: (ticker: string, countryCode = "KR") =>
    post<WatchlistTrackingToggleResponse>(`/api/watchlist/${encodeURIComponent(ticker)}/tracking?country_code=${encodeURIComponent(countryCode)}`),
  disableWatchlistTracking: (ticker: string, countryCode = "KR") =>
    del<WatchlistTrackingToggleResponse>(`/api/watchlist/${encodeURIComponent(ticker)}/tracking?country_code=${encodeURIComponent(countryCode)}`),
  getWatchlistTrackingDetail: (ticker: string, countryCode = "KR", options?: RequestOptions) =>
    get<WatchlistTrackingDetailResponse>(
      `/api/watchlist/${encodeURIComponent(ticker)}/tracking-detail?country_code=${encodeURIComponent(countryCode)}`,
      options,
    ),
  compare: (tickers: string[]) => get<unknown[]>(`/api/compare?tickers=${tickers.join(",")}`),
  getArchive: () => get<ArchiveEntry[]>("/api/archive"),
  getArchiveDetail: (id: number) => get<unknown>(`/api/archive/${id}`),
  getPredictionAccuracy: () => get<PredictionAccuracyStats>("/api/archive/accuracy/stats"),
  getResearchArchive: (regionCode?: ResearchRegionCode, limit = 40, autoRefresh = true) => {
    const qs = new URLSearchParams();
    if (regionCode) qs.set("region_code", regionCode);
    qs.set("limit", String(limit));
    qs.set("auto_refresh", String(autoRefresh));
    return get<ResearchArchiveEntry[]>(`/api/archive/research?${qs.toString()}`);
  },
  ...systemApi,
  getPredictionLab: (limitRecent = 40, refresh = true) =>
    get<PredictionLabResponse>(`/api/research/predictions?limit_recent=${limitRecent}&refresh=${refresh}`),
  search: (q: string) => get<SearchResult[]>(`/api/search?q=${encodeURIComponent(q)}`),
  resolveTicker: (query: string, countryCode = "KR") =>
    get<TickerResolution>(`/api/ticker/resolve?query=${encodeURIComponent(query)}&country_code=${countryCode}`),
  getStockForecastDelta: (ticker: string, limit = 8) =>
    get<ForecastDeltaResponse>(`/api/stock/${encodeURIComponent(ticker)}/forecast-delta?limit=${limit}`),
};
