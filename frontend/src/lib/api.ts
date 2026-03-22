const API = process.env.NEXT_PUBLIC_API_URL || "";

export interface ApiErrorInfo {
  error_code: string;
  message: string;
  detail?: string;
}

export class ApiError extends Error {
  status: number;
  errorCode: string;
  detail: string;

  constructor(status: number, info: ApiErrorInfo) {
    super(info.message);
    this.status = status;
    this.errorCode = info.error_code || `HTTP-${status}`;
    this.detail = info.detail || "";
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) {
    let info: ApiErrorInfo;
    try {
      info = await res.json();
    } catch {
      info = { error_code: `HTTP-${res.status}`, message: res.statusText };
    }
    throw new ApiError(res.status, info);
  }
  return res.json();
}

async function post(path: string, body?: unknown) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let info: ApiErrorInfo;
    try {
      info = await res.json();
    } catch {
      info = { error_code: `HTTP-${res.status}`, message: res.statusText };
    }
    throw new ApiError(res.status, info);
  }
  return res.json();
}

async function del(path: string) {
  const res = await fetch(`${API}${path}`, { method: "DELETE" });
  if (!res.ok) {
    let info: ApiErrorInfo;
    try {
      info = await res.json();
    } catch {
      info = { error_code: `HTTP-${res.status}`, message: res.statusText };
    }
    throw new ApiError(res.status, info);
  }
  return res.json();
}

export interface CompositeScoreItem {
  name: string;
  score: number;
  max_score: number;
  description: string;
}

export interface CompositeScoreDetail {
  total: number;
  max_score: number;
  items: CompositeScoreItem[];
}

export interface CompositeScore {
  total: number;
  total_raw: number;
  max_raw: number;
  fundamental: CompositeScoreDetail;
  valuation: CompositeScoreDetail;
  growth_momentum: CompositeScoreDetail;
  analyst: CompositeScoreDetail;
  risk: CompositeScoreDetail;
  technical: CompositeScoreDetail;
}

export interface HeatmapStock {
  name: string;
  ticker: string;
  fullName: string;
  size: number;
  change: number;
}

export interface HeatmapSector {
  name: string;
  children: HeatmapStock[];
}

export interface HeatmapData {
  children: HeatmapSector[];
}

export interface TechSignalItem {
  name: string;
  value: number | null;
  signal: "Buy" | "Neutral" | "Sell";
}

export interface TechSummaryGroup {
  buy: number;
  neutral: number;
  sell: number;
  signal: string;
}

export interface TechSummary {
  ticker: string;
  summary: { overall: TechSummaryGroup; moving_averages: TechSummaryGroup; oscillators: TechSummaryGroup };
  moving_averages: TechSignalItem[];
  oscillators: TechSignalItem[];
}

export interface PivotLevel {
  pivot: number; r1: number; r2: number; r3: number; s1: number; s2: number; s3: number;
}

export interface PivotPoints {
  ticker: string;
  classic: PivotLevel;
  fibonacci: PivotLevel;
}

export interface ScreenerResult {
  ticker: string; name: string; sector: string; industry: string;
  market_cap: number; current_price: number; change_pct: number;
  pe_ratio: number | null; pb_ratio: number | null;
  dividend_yield: number | null; beta: number | null;
  week52_high: number; week52_low: number; pct_from_52w_high: number;
  score: number | null; country_code: string;
}

export interface ScreenerResponse {
  results: ScreenerResult[];
  total: number;
  sectors: string[];
}

export interface PortfolioHolding {
  id: number; ticker: string; name: string; country_code: string; sector: string;
  buy_price: number; current_price: number; quantity: number; buy_date: string;
  invested: number; current_value: number; pnl: number; pnl_pct: number;
}

export interface PortfolioData {
  holdings: PortfolioHolding[];
  summary: { total_invested: number; total_current: number; total_pnl: number; total_pnl_pct: number; holding_count: number };
  allocation: { by_sector: { name: string; value: number }[]; by_country: { name: string; value: number }[] };
}

export interface MarketMovers {
  gainers: { ticker: string; name: string; price: number; change_pct: number }[];
  losers: { ticker: string; name: string; price: number; change_pct: number }[];
}

export interface PredictionAccuracyStats {
  stored_predictions: number;
  pending_predictions: number;
  total_predictions: number;
  within_range: number;
  within_range_rate: number;
  direction_hits: number;
  direction_accuracy: number;
  avg_error_pct: number;
  avg_confidence: number;
}

export interface SearchResult {
  ticker: string; name: string; country_code: string; sector: string;
}

export const api = {
  getCountries: () => get<import("./types").CountryListItem[]>("/api/countries"),
  getMarketIndicators: () => get<{ name: string; price: number; change_pct: number }[]>("/api/market/indicators"),
  getSectorPerformance: (code: string) => get<{ sector: string; ticker: string; price: number; change_pct: number }[]>(`/api/country/${code}/sector-performance`),
  getHeatmap: (code: string) => get<HeatmapData>(`/api/country/${code}/heatmap`),
  getCountryReport: (code: string) => get<import("./types").CountryReport>(`/api/country/${code}/report`),
  getCountryForecast: (code: string) => get<import("./types").IndexForecast>(`/api/country/${code}/forecast`),
  getSectors: (code: string) => get<import("./types").SectorListItem[]>(`/api/country/${code}/sectors`),
  getSectorReport: (code: string, sectorId: string) =>
    get<import("./types").SectorReport>(`/api/country/${code}/sector/${sectorId}/report`),
  getStockDetail: (ticker: string) => get<import("./types").StockDetail>(`/api/stock/${ticker}/detail`),
  getStockChart: (ticker: string, period = "3mo") =>
    get<{ data: import("./types").PricePoint[] }>(`/api/stock/${ticker}/chart?period=${period}`),
  getTechSummary: (ticker: string) => get<TechSummary>(`/api/stock/${ticker}/technical-summary`),
  getPivotPoints: (ticker: string) => get<PivotPoints>(`/api/stock/${ticker}/pivot-points`),
  getWatchlist: () => get<import("./types").WatchlistItem[]>("/api/watchlist"),
  addWatchlist: (ticker: string, country_code = "US") => post(`/api/watchlist/${ticker}?country_code=${country_code}`),
  removeWatchlist: (ticker: string) => del(`/api/watchlist/${ticker}`),
  compare: (tickers: string[]) => get<unknown[]>(`/api/compare?tickers=${tickers.join(",")}`),
  getArchive: () => get<unknown[]>("/api/archive"),
  getArchiveDetail: (id: number) => get<unknown>(`/api/archive/${id}`),
  getPredictionAccuracy: () => get<PredictionAccuracyStats>("/api/archive/accuracy/stats"),
  getCalendar: (code: string) => get<unknown>(`/api/calendar/${code}`),
  getScreener: (params: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString();
    return get<ScreenerResponse>(`/api/screener?${qs}`);
  },
  getPortfolio: () => get<PortfolioData>("/api/portfolio"),
  addPortfolioHolding: (data: { ticker: string; buy_price: number; quantity: number; buy_date: string; country_code?: string }) =>
    post("/api/portfolio/holdings", data),
  removePortfolioHolding: (id: number) => del(`/api/portfolio/holdings/${id}`),
  getMarketMovers: (code: string) => get<MarketMovers>(`/api/market/movers/${code}`),
  search: (q: string) => get<SearchResult[]>(`/api/search?q=${encodeURIComponent(q)}`),
};
