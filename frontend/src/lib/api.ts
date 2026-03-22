const API = process.env.NEXT_PUBLIC_API_URL || "";

export function apiPath(path: string): string {
  return `${API}${path}`;
}

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
  const res = await fetch(apiPath(path), { cache: "no-store" });
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
  const res = await fetch(apiPath(path), {
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
  const res = await fetch(apiPath(path), { method: "DELETE" });
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
  weight_pct: number;
  realized_volatility_pct: number;
  max_drawdown_pct: number;
  beta?: number | null;
  risk_score: number;
  risk_level: "low" | "medium" | "high";
  up_probability?: number | null;
  predicted_return_pct?: number | null;
  forecast_date?: string | null;
  trade_action?: string | null;
  trade_setup?: string | null;
  trade_conviction?: number | null;
  entry_low?: number | null;
  entry_high?: number | null;
  stop_loss?: number | null;
  take_profit_1?: number | null;
  take_profit_2?: number | null;
  market_regime_label?: string | null;
  market_regime_stance?: string | null;
  thesis: string[];
}

export interface PortfolioStressScenario {
  name: string;
  description: string;
  projected_portfolio_pct: number;
  projected_pnl: number;
}

export interface PortfolioRiskRegime {
  country_code: string;
  weight: number;
  label: string;
  stance: "risk_on" | "neutral" | "risk_off";
  conviction: number;
}

export interface PortfolioRiskSnapshot {
  overall_label: "empty" | "balanced" | "moderate" | "elevated" | "aggressive";
  score: number;
  diversification_score: number;
  concentration_hhi: number;
  top_holding_weight: number;
  avg_volatility_pct: number;
  portfolio_beta: number;
  portfolio_up_probability: number;
  projected_next_day_return_pct: number;
  warning_count: number;
  warnings: string[];
  playbook: string[];
  regimes: PortfolioRiskRegime[];
}

export interface PortfolioData {
  holdings: PortfolioHolding[];
  summary: { total_invested: number; total_current: number; total_pnl: number; total_pnl_pct: number; holding_count: number };
  allocation: { by_sector: { name: string; value: number }[]; by_country: { name: string; value: number }[] };
  risk: PortfolioRiskSnapshot;
  stress_test: PortfolioStressScenario[];
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

export interface ArchiveEntry {
  id: number;
  report_type: string;
  country_code?: string | null;
  sector_id?: string | null;
  ticker?: string | null;
  created_at: number;
  preview: string;
}

export interface ResearchArchiveSourceResult {
  source_id: string;
  source_name: string;
  region_code: "US" | "KR" | "JP" | "GLOBAL";
  count: number;
}

export interface ResearchArchiveSourceCount {
  source_id: string;
  source_name: string;
  total: number;
}

export interface ResearchArchiveRegionCount {
  region_code: "US" | "KR" | "JP" | "GLOBAL";
  total: number;
}

export interface ResearchArchiveStatus {
  refreshed_on?: string | null;
  refreshed_at?: string | null;
  processed_total: number;
  error_count: number;
  total_reports: number;
  source_count: number;
  todays_reports: number;
  last_synced_at?: number | null;
  source_results: ResearchArchiveSourceResult[];
  sources: ResearchArchiveSourceCount[];
  regions: ResearchArchiveRegionCount[];
  errors: { source_id: string; source_name: string; detail: string }[];
}

export interface ResearchArchiveEntry {
  id: number;
  source_id: string;
  source_name: string;
  region_code: "US" | "KR" | "JP" | "GLOBAL";
  organization_type: string;
  language: string;
  category?: string | null;
  title: string;
  summary?: string | null;
  published_at: string;
  report_url: string;
  pdf_url?: string | null;
  has_pdf: boolean;
  is_new_today: boolean;
  metadata: Record<string, unknown>;
  created_at: number;
  updated_at: number;
}

export interface PredictionBreakdownRow {
  label: string;
  total: number;
  direction_accuracy: number;
  within_range_rate: number;
  avg_error_pct: number;
  avg_confidence: number;
}

export interface PredictionCalibrationBucket {
  bucket: string;
  total: number;
  avg_confidence: number;
  realized_up_rate: number;
  direction_accuracy: number;
  avg_error_pct: number;
}

export interface PredictionTrendPoint {
  target_date: string;
  total: number;
  evaluated_total: number;
  direction_accuracy: number;
  within_range_rate: number;
  avg_error_pct: number;
}

export interface PredictionRecentRecord {
  id: number;
  scope: string;
  symbol: string;
  country_code?: string | null;
  target_date: string;
  reference_date?: string | null;
  reference_price: number;
  predicted_close: number;
  predicted_low?: number | null;
  predicted_high?: number | null;
  actual_close?: number | null;
  direction: "up" | "down" | "flat";
  direction_hit?: boolean | null;
  within_range?: boolean | null;
  abs_error_pct?: number | null;
  confidence: number;
  up_probability: number;
  model_version: string;
  created_at: number;
  evaluated_at?: number | null;
}

export interface PredictionLabResponse {
  generated_at: string;
  accuracy: PredictionAccuracyStats;
  breakdown: {
    by_country: PredictionBreakdownRow[];
    by_scope: PredictionBreakdownRow[];
    by_model: PredictionBreakdownRow[];
  };
  calibration: PredictionCalibrationBucket[];
  recent_trend: PredictionTrendPoint[];
  recent_records: PredictionRecentRecord[];
  insights: string[];
}

export interface StartupTaskStatus {
  name: string;
  status: "ok" | "warning" | "error" | "running";
  detail: string;
  updated_at: string;
}

export interface DataSourceStatus {
  name: string;
  configured: boolean;
  status: string;
  purpose: string;
  note: string;
}

export interface ForecastModelSummary {
  name: string;
  version: string;
  markets: string[];
  signals: string[];
  notes: string[];
}

export interface SystemDiagnostics {
  status: "ok" | "degraded" | "starting";
  version: string;
  started_at: string;
  startup_tasks: StartupTaskStatus[];
  data_sources: DataSourceStatus[];
  forecast_models: ForecastModelSummary[];
  prediction_accuracy?: PredictionAccuracyStats | null;
  prediction_accuracy_error?: string | null;
  research_archive?: ResearchArchiveStatus | null;
  research_archive_error?: string | null;
}

export interface CalendarMajorEvent {
  name: string;
  name_local: string;
  frequency: string;
  description: string;
  impact: "high" | "medium" | "low";
  color: string;
}

export interface CalendarSummary {
  total_events: number;
  high_impact_count: number;
  policy_count: number;
  earnings_count: number;
  economic_count: number;
  note: string;
}

export interface CalendarEvent {
  id: string;
  date: string;
  type: "policy" | "economic" | "earnings";
  category: string;
  title: string;
  title_en: string;
  subtitle?: string | null;
  description: string;
  impact: "high" | "medium" | "low";
  color: string;
  source: string;
  all_day: boolean;
  time?: string | null;
  symbol?: string | null;
  country_code: string;
}

export interface CalendarResponse {
  country_code: string;
  year: number;
  month: number;
  month_label: string;
  range_start: string;
  range_end: string;
  generated_at: string;
  summary: CalendarSummary;
  major_events: CalendarMajorEvent[];
  events: CalendarEvent[];
  upcoming_events: CalendarEvent[];
  economic_events: CalendarEvent[];
  earnings_events: CalendarEvent[];
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
  getArchive: () => get<ArchiveEntry[]>("/api/archive"),
  getArchiveDetail: (id: number) => get<unknown>(`/api/archive/${id}`),
  getPredictionAccuracy: () => get<PredictionAccuracyStats>("/api/archive/accuracy/stats"),
  getResearchArchive: (regionCode?: "US" | "KR" | "JP" | "GLOBAL", limit = 40, autoRefresh = true) => {
    const qs = new URLSearchParams();
    if (regionCode) qs.set("region_code", regionCode);
    qs.set("limit", String(limit));
    qs.set("auto_refresh", String(autoRefresh));
    return get<ResearchArchiveEntry[]>(`/api/archive/research?${qs.toString()}`);
  },
  getResearchArchiveStatus: (refreshIfMissing = false) =>
    get<ResearchArchiveStatus>(`/api/archive/research/status?refresh_if_missing=${refreshIfMissing}`),
  refreshResearchArchive: () => post("/api/archive/research/refresh"),
  getPredictionLab: (limitRecent = 40, refresh = true) =>
    get<PredictionLabResponse>(`/api/research/predictions?limit_recent=${limitRecent}&refresh=${refresh}`),
  getDiagnostics: () => get<SystemDiagnostics>("/api/system/diagnostics"),
  getMarketOpportunities: (code: string, limit = 12) =>
    get<import("./types").OpportunityRadarResponse>(`/api/market/opportunities/${code}?limit=${limit}`),
  getCalendar: (code: string, year?: number, month?: number) => {
    const qs = new URLSearchParams();
    if (year) qs.set("year", String(year));
    if (month) qs.set("month", String(month));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return get<CalendarResponse>(`/api/calendar/${code}${suffix}`);
  },
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
