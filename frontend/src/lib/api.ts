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

export interface AccountProfile {
  user_id: string;
  email?: string | null;
  pending_email?: string | null;
  email_verified: boolean;
  email_confirmed_at?: string | null;
  email_change_sent_at?: string | null;
  username?: string | null;
  full_name?: string | null;
  phone_number?: string | null;
  phone_masked?: string | null;
  birth_date?: string | null;
}

export interface AccountProfileUpdateRequest {
  username: string;
  full_name: string;
  phone_number: string;
  birth_date: string;
}

export interface AccountDeleteRequest {
  confirmation_text: string;
}

export interface AccountDeleteResponse {
  status: "deleted";
  message: string;
}

export interface SignUpValidationRequest {
  username: string;
  email: string;
  full_name: string;
  phone_number: string;
  birth_date: string;
  password: string;
  password_confirm: string;
}

export interface SignUpValidationResponse {
  email: string;
  normalized_username: string;
  normalized_full_name: string;
  normalized_phone_number: string;
  birth_date: string;
  ready: boolean;
  message: string;
}

export interface UsernameAvailabilityResponse {
  username: string;
  normalized_username: string;
  valid: boolean;
  available: boolean;
  message: string;
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
  revenue_growth: number | null;
  roe: number | null;
  debt_to_equity: number | null;
  avg_volume: number;
  profit_margins: number | null;
  score: number | null; country_code: string;
}

export interface ScreenerResponse {
  results: ScreenerResult[];
  total: number;
  sectors: string[];
  generated_at?: string;
  partial?: boolean;
  fallback_reason?: string | null;
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
  target_horizon_days?: number | null;
  target_date_20d?: string | null;
  expected_return_pct_20d?: number | null;
  expected_excess_return_pct_20d?: number | null;
  median_return_pct_20d?: number | null;
  forecast_volatility_pct_20d?: number | null;
  up_probability_20d?: number | null;
  flat_probability_20d?: number | null;
  down_probability_20d?: number | null;
  distribution_confidence_20d?: number | null;
  price_q25_20d?: number | null;
  price_q50_20d?: number | null;
  price_q75_20d?: number | null;
  execution_bias?: "press_long" | "lean_long" | "stay_selective" | "reduce_risk" | "capital_preservation" | null;
  execution_note?: string | null;
  risk_flags: string[];
  bull_case_price?: number | null;
  base_case_price?: number | null;
  bear_case_price?: number | null;
  bull_probability?: number | null;
  base_probability?: number | null;
  bear_probability?: number | null;
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

export interface PortfolioExecutionMixItem {
  bias: "press_long" | "lean_long" | "stay_selective" | "reduce_risk" | "capital_preservation";
  count: number;
  weight: number;
}

export interface PortfolioActionQueueItem {
  ticker: string;
  name: string;
  action: string;
  execution_bias: "press_long" | "lean_long" | "stay_selective" | "reduce_risk" | "capital_preservation";
  weight_pct: number;
  reason: string;
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
  downside_watch_weight: number;
  bearish_scenario_exposure: number;
  warning_count: number;
  warnings: string[];
  playbook: string[];
  regimes: PortfolioRiskRegime[];
  execution_mix: PortfolioExecutionMixItem[];
  action_queue: PortfolioActionQueueItem[];
}

export interface PortfolioModelBudget {
  style: "defensive" | "balanced" | "offensive";
  style_label: string;
  recommended_equity_pct: number;
  cash_buffer_pct: number;
  target_position_count: number;
  max_single_weight_pct: number;
  max_country_weight_pct: number;
  max_sector_weight_pct: number;
}

export interface PortfolioModelSummary {
  selected_count: number;
  new_position_count: number;
  trim_count: number;
  watchlist_focus_count: number;
  model_up_probability: number;
  model_predicted_return_pct: number;
  expected_return_pct_20d: number;
  expected_excess_return_pct_20d: number;
  forecast_volatility_pct_20d: number;
  up_probability_20d: number;
  down_probability_20d: number;
  turnover_pct: number;
}

export interface PortfolioModelAllocationItem {
  name: string;
  value: number;
}

export interface PortfolioModelItem {
  ticker: string;
  name: string;
  country_code: string;
  sector: string;
  source: "holding" | "radar" | "watchlist";
  in_watchlist: boolean;
  current_weight_pct: number;
  target_weight_pct: number;
  delta_weight_pct: number;
  model_score: number;
  action: "new" | "add" | "hold" | "trim" | "exit" | "watch";
  priority: "high" | "medium" | "low";
  target_horizon_days?: number | null;
  target_date_20d?: string | null;
  expected_return_pct_20d?: number | null;
  expected_excess_return_pct_20d?: number | null;
  median_return_pct_20d?: number | null;
  forecast_volatility_pct_20d?: number | null;
  up_probability_20d?: number | null;
  flat_probability_20d?: number | null;
  down_probability_20d?: number | null;
  distribution_confidence_20d?: number | null;
  price_q25_20d?: number | null;
  price_q50_20d?: number | null;
  price_q75_20d?: number | null;
  up_probability?: number | null;
  predicted_return_pct?: number | null;
  base_probability?: number | null;
  bull_probability?: number | null;
  bear_probability?: number | null;
  bull_case_price?: number | null;
  base_case_price?: number | null;
  bear_case_price?: number | null;
  execution_bias?: "press_long" | "lean_long" | "stay_selective" | "reduce_risk" | "capital_preservation" | null;
  setup_label?: string | null;
  rationale: string[];
  risk_flags: string[];
}

export interface PortfolioModelPortfolio {
  as_of: string;
  objective: string;
  risk_budget: PortfolioModelBudget;
  summary: PortfolioModelSummary;
  allocation: {
    by_country: PortfolioModelAllocationItem[];
    by_sector: PortfolioModelAllocationItem[];
  };
  recommended_holdings: PortfolioModelItem[];
  rebalance_actions: PortfolioModelItem[];
  candidate_pipeline: PortfolioModelItem[];
  notes: string[];
}

export type PortfolioRecommendationStyle = "defensive" | "balanced" | "offensive";

export interface PortfolioRecommendationBudget {
  style: PortfolioRecommendationStyle;
  style_label: string;
  recommended_equity_pct: number;
  cash_buffer_pct: number;
  target_position_count: number;
  max_single_weight_pct: number;
  max_country_weight_pct: number;
  max_sector_weight_pct: number;
}

export interface PortfolioRecommendationSummary {
  selected_count: number;
  candidate_count: number;
  watchlist_focus_count: number;
  existing_overlap_count: number;
  model_up_probability: number;
  model_predicted_return_pct: number;
  expected_return_pct_20d: number;
  expected_excess_return_pct_20d: number;
  forecast_volatility_pct_20d: number;
  up_probability_20d: number;
  down_probability_20d: number;
  turnover_pct: number;
  focus_country?: string | null;
  focus_sector?: string | null;
}

export interface PortfolioRecommendationMarketView {
  country_code: string;
  label?: string | null;
  stance?: "risk_on" | "neutral" | "risk_off" | null;
  actionable_count: number;
  universe_note?: string | null;
}

export interface PortfolioRecommendationItem {
  key: string;
  ticker: string;
  name: string;
  country_code: string;
  sector: string;
  source: "holding" | "watchlist" | "radar";
  in_watchlist: boolean;
  current_weight_pct: number;
  current_country_exposure_pct: number;
  current_sector_exposure_pct: number;
  target_weight_pct: number;
  delta_weight_pct: number;
  model_score: number;
  opportunity_score: number;
  target_horizon_days?: number | null;
  target_date_20d?: string | null;
  expected_return_pct_20d?: number | null;
  expected_excess_return_pct_20d?: number | null;
  median_return_pct_20d?: number | null;
  forecast_volatility_pct_20d?: number | null;
  up_probability_20d?: number | null;
  flat_probability_20d?: number | null;
  down_probability_20d?: number | null;
  distribution_confidence_20d?: number | null;
  price_q25_20d?: number | null;
  price_q50_20d?: number | null;
  price_q75_20d?: number | null;
  up_probability: number;
  predicted_return_pct: number;
  confidence: number;
  bull_probability?: number | null;
  base_probability?: number | null;
  bear_probability?: number | null;
  bull_case_price?: number | null;
  base_case_price?: number | null;
  bear_case_price?: number | null;
  execution_bias?: "press_long" | "lean_long" | "stay_selective" | "reduce_risk" | "capital_preservation" | null;
  setup_label?: string | null;
  action?: string | null;
  entry_low?: number | null;
  entry_high?: number | null;
  stop_loss?: number | null;
  take_profit_1?: number | null;
  take_profit_2?: number | null;
  risk_reward_estimate?: number | null;
  rationale: string[];
  risk_flags: string[];
  priority?: "high" | "medium" | "low";
}

export interface PortfolioConditionalRecommendationFilters {
  country_code: string;
  sector: string;
  style: PortfolioRecommendationStyle;
  max_items: number;
  min_up_probability: number;
  exclude_holdings: boolean;
  watchlist_only: boolean;
}

export interface PortfolioConditionalRecommendationResponse {
  generated_at: string;
  filters: PortfolioConditionalRecommendationFilters;
  options: {
    countries: string[];
    sectors: string[];
    styles: PortfolioRecommendationStyle[];
  };
  budget: PortfolioRecommendationBudget;
  summary: PortfolioRecommendationSummary;
  recommendations: PortfolioRecommendationItem[];
  notes: string[];
  market_view: PortfolioRecommendationMarketView[];
}

export interface PortfolioOptimalRecommendationResponse {
  generated_at: string;
  objective: string;
  style: PortfolioRecommendationStyle;
  budget: PortfolioRecommendationBudget;
  summary: PortfolioRecommendationSummary;
  recommendations: PortfolioRecommendationItem[];
  notes: string[];
  market_view: PortfolioRecommendationMarketView[];
}

export interface DailyIdealPortfolioTargetDate {
  country_code: string;
  target_date: string;
}

export interface DailyIdealPortfolioMarketView {
  country_code: string;
  label: string;
  stance: "risk_on" | "neutral" | "risk_off";
  conviction: number;
  actionable_count: number;
  bullish_count: number;
  summary: string;
}

export interface DailyIdealPortfolioPosition {
  rank: number;
  ticker: string;
  name: string;
  country_code: string;
  sector: string;
  reference_price: number;
  target_date: string;
  target_horizon_days?: number | null;
  target_date_20d?: string | null;
  target_weight_pct: number;
  selection_score: number;
  opportunity_score: number;
  expected_return_pct_20d?: number | null;
  expected_excess_return_pct_20d?: number | null;
  median_return_pct_20d?: number | null;
  forecast_volatility_pct_20d?: number | null;
  up_probability_20d?: number | null;
  flat_probability_20d?: number | null;
  down_probability_20d?: number | null;
  distribution_confidence_20d?: number | null;
  price_q25_20d?: number | null;
  price_q50_20d?: number | null;
  price_q75_20d?: number | null;
  up_probability: number;
  confidence: number;
  predicted_return_pct: number;
  bull_case_price?: number | null;
  base_case_price?: number | null;
  bear_case_price?: number | null;
  bull_probability?: number | null;
  base_probability?: number | null;
  bear_probability?: number | null;
  setup_label?: string | null;
  action?: string | null;
  execution_bias?: "press_long" | "lean_long" | "stay_selective" | "reduce_risk" | "capital_preservation" | null;
  execution_note?: string | null;
  entry_low?: number | null;
  entry_high?: number | null;
  stop_loss?: number | null;
  take_profit_1?: number | null;
  take_profit_2?: number | null;
  risk_reward_estimate?: number | null;
  thesis: string[];
  risk_flags: string[];
  market_stance: "risk_on" | "neutral" | "risk_off";
}

export interface DailyIdealPortfolioHistoryEntry {
  reference_date: string;
  generated_at: string;
  predicted_portfolio_return_pct: number;
  expected_excess_return_pct_20d?: number | null;
  realized_portfolio_return_pct?: number | null;
  evaluated: boolean;
  hit_rate?: number | null;
  direction_accuracy?: number | null;
  selected_count: number;
  top_tickers: string[];
}

export interface DailyIdealPortfolio {
  reference_date: string;
  generated_at: string;
  objective: string;
  target_dates: DailyIdealPortfolioTargetDate[];
  risk_budget: PortfolioModelBudget;
  market_view: DailyIdealPortfolioMarketView[];
  summary: {
    selected_count: number;
    predicted_portfolio_return_pct: number;
    expected_return_pct_20d: number;
    expected_excess_return_pct_20d: number;
    forecast_volatility_pct_20d: number;
    portfolio_up_probability: number;
    portfolio_down_probability: number;
    turnover_pct: number;
  };
  allocation: {
    by_country: PortfolioModelAllocationItem[];
    by_sector: PortfolioModelAllocationItem[];
  };
  positions: DailyIdealPortfolioPosition[];
  playbook: string[];
  history: DailyIdealPortfolioHistoryEntry[];
}

export interface PortfolioData {
  profile: PortfolioProfile;
  holdings: PortfolioHolding[];
  summary: PortfolioSummary;
  allocation: { by_sector: { name: string; value: number }[]; by_country: { name: string; value: number }[] };
  risk: PortfolioRiskSnapshot;
  stress_test: PortfolioStressScenario[];
  model_portfolio: PortfolioModelPortfolio;
}

export interface PortfolioProfile {
  total_assets: number;
  cash_balance: number;
  monthly_budget: number;
  updated_at?: string | null;
}

export interface PortfolioSummary {
  total_invested: number;
  total_current: number;
  total_pnl: number;
  total_pnl_pct: number;
  holding_count: number;
  total_assets: number;
  cash_balance: number;
  other_assets: number;
  stock_ratio_pct: number;
  cash_ratio_pct: number;
  other_assets_ratio_pct: number;
  monthly_budget: number;
  deployable_cash: number;
  asset_gap: number;
  unrealized_pnl_pct_of_assets: number;
}

export interface PortfolioHoldingCreateResponse {
  status: "ok";
  ticker: string;
  name: string;
  country_code: string;
  buy_date: string;
}

export interface WatchlistAddResponse {
  status: "added";
  ticker: string;
  country_code: string;
  note: string;
}

export interface MarketMovers {
  gainers: { ticker: string; name: string; price: number; change_pct: number }[];
  losers: { ticker: string; name: string; price: number; change_pct: number }[];
  generated_at?: string;
  partial?: boolean;
  fallback_reason?: string | null;
}

export interface PredictionAccuracyStats {
  generated_at?: string;
  partial?: boolean;
  fallback_reason?: string | null;
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

export type ResearchRegionCode = "KR" | "US" | "EU" | "JP";

export interface ResearchArchiveSourceResult {
  source_id: string;
  source_name: string;
  region_code: ResearchRegionCode;
  count: number;
}

export interface ResearchArchiveSourceCount {
  source_id: string;
  source_name: string;
  total: number;
}

export interface ResearchArchiveRegionCount {
  region_code: ResearchRegionCode;
  total: number;
}

export interface ResearchArchiveStatus {
  refreshed_on?: string | null;
  refreshed_at?: string | null;
  partial?: boolean;
  fallback_reason?: string | null;
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
  region_code: ResearchRegionCode;
  organization_type: string;
  language: string;
  category?: string | null;
  title: string;
  summary?: string | null;
  summary_plain?: string | null;
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
  partial?: boolean;
  fallback_reason?: string | null;
  accuracy: PredictionAccuracyStats;
  horizon_accuracy: {
    prediction_type: string;
    label: string;
    stored_predictions: number;
    pending_predictions: number;
    total_predictions: number;
    direction_accuracy: number;
    within_range_rate: number;
    avg_error_pct: number;
    avg_confidence: number;
    current_method: "prior_only" | "learned_blended" | "learned_blended_graph";
    fusion_profile_sample_count: number;
    avg_blend_weight: number;
    graph_coverage: number;
    graph_context_used_rate: number;
    prior_brier_delta?: number | null;
    fusion_status: string;
  }[];
  empirical_calibration: {
    prediction_type: string;
    label: string;
    method: string;
    sample_count: number;
    positive_rate: number;
    brier_score: number;
    prior_brier_score: number;
    max_reliability_gap: number;
    reliability_bins: {
      lower: number;
      upper: number;
      sample_count: number;
      predicted_mean: number;
      empirical_rate: number;
      gap: number;
    }[];
    fitted_at?: string | null;
  }[];
  breakdown: {
    by_country: PredictionBreakdownRow[];
    by_scope: PredictionBreakdownRow[];
    by_model: PredictionBreakdownRow[];
  };
  fusion_profiles: {
    prediction_type: string;
    label: string;
    method: string;
    sample_count: number;
    positive_rate: number;
    brier_score?: number | null;
    prior_brier_score?: number | null;
    prior_brier_delta?: number | null;
    fitted_at?: string | null;
    profile_bucket?: string | null;
    status: string;
  }[];
  graph_context_summary: {
    coverage_available: boolean;
    used_rate: number;
    avg_coverage: number;
    avg_score: number;
    avg_peer_count: number;
    records: number;
    by_horizon: {
      prediction_type: string;
      label: string;
      used_rate: number;
      avg_coverage: number;
      avg_score: number;
      avg_peer_count: number;
      records: number;
    }[];
  };
  fusion_status_summary: {
    active_model_version: string;
    last_refresh_time?: string | null;
    graph_coverage_available: boolean;
    avg_blend_weight: number;
    method_mix: {
      prior_only: number;
      learned_blended: number;
      learned_blended_graph: number;
    };
    horizons: {
      prediction_type: string;
      label: string;
      current_method: string;
      profile_sample_count: number;
      avg_blend_weight: number;
      graph_coverage: number;
      prior_brier_delta?: number | null;
      status: string;
    }[];
  };
  calibration: PredictionCalibrationBucket[];
  recent_trend: PredictionTrendPoint[];
  recent_records: (PredictionRecentRecord & {
    fusion_method?: string;
    fusion_blend_weight?: number;
    graph_context_used?: boolean;
    graph_coverage?: number;
  })[];
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

export interface RouteStabilitySummaryRow {
  route: string;
  total: number;
  p50_elapsed_ms: number;
  p95_elapsed_ms: number;
  fallback_served_rate: number;
  partial_rate: number;
  stale_rate: number;
  degraded_rate: number;
  cold_start_suspected_rate: number;
  request_phase_mix: Record<string, number>;
  operation_kind_mix: Record<string, number>;
  cache_state_mix: Record<string, number>;
  failure_class_mix: Record<string, number>;
  recovered_failure_rate: number;
}

export interface RouteStabilityFirstUsableMetrics {
  tracked_routes: number;
  total_requests: number;
  p50_elapsed_ms: number;
  p95_elapsed_ms: number;
  fallback_served_rate: number;
  stale_served_rate: number;
  first_request_cold_failure_rate: number;
  blank_screen_rate: number;
  error_only_screen_rate: number;
}

export interface RouteStabilityFailureSummary {
  tracked: boolean;
  total: number;
  failure_count: number;
  failure_rate: number;
  by_route: {
    route: string;
    total: number;
    failure_count: number;
    failure_rate: number;
  }[];
}

export interface RouteStabilityFailureClassSummary {
  tracked: boolean;
  total: number;
  by_class: Record<string, number>;
  recovered_count: number;
  recovered_rate: number;
}

export interface SystemDiagnostics {
  status: "ok" | "degraded" | "starting";
  version: string;
  started_at: string;
  startup_tasks: StartupTaskStatus[];
  data_sources: DataSourceStatus[];
  forecast_models: ForecastModelSummary[];
  confidence_calibration_profiles?: {
    prediction_type: string;
    method: string;
    sample_count: number;
    positive_rate: number;
    brier_score: number;
    prior_brier_score: number;
    max_reliability_gap: number;
    reliability_bins: {
      lower: number;
      upper: number;
      sample_count: number;
      predicted_mean: number;
      empirical_rate: number;
      gap: number;
    }[];
    fitted_at?: string | null;
  }[] | null;
  learned_fusion_status?: {
    active_model_version: string;
    last_refresh_time?: string | null;
    graph_coverage_available: boolean;
    horizons: {
      prediction_type: string;
      label: string;
      method: string;
      status: string;
      sample_count: number;
      prior_brier_delta?: number | null;
      fitted_at?: string | null;
    }[];
  } | null;
  prediction_accuracy?: PredictionAccuracyStats | null;
  prediction_accuracy_error?: string | null;
  research_archive?: ResearchArchiveStatus | null;
  research_archive_error?: string | null;
  route_stability_summary?: RouteStabilitySummaryRow[];
  first_usable_metrics?: RouteStabilityFirstUsableMetrics | null;
  hydration_failure_summary?: RouteStabilityFailureSummary | null;
  session_recovery_summary?: RouteStabilityFailureSummary | null;
  failure_class_summary?: RouteStabilityFailureClassSummary | null;
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
  partial?: boolean;
  fallback_reason?: string | null;
  summary: CalendarSummary;
  major_events: CalendarMajorEvent[];
  events: CalendarEvent[];
  upcoming_events: CalendarEvent[];
  economic_events: CalendarEvent[];
  earnings_events: CalendarEvent[];
}

export interface SearchResult {
  ticker: string;
  name: string;
  country_code: string;
  sector: string;
  match_basis?: string;
  resolution_note?: string;
}

export interface TickerResolution {
  input_ticker: string;
  normalized_input: string;
  ticker: string;
  country_code: string;
  sector: string;
  match_basis: string;
  confidence: "low" | "medium" | "high";
  matched: boolean;
  note: string;
  name?: string;
}

export interface MarketSessionItem {
  country_code: string;
  name: string;
  name_local: string;
  currency: string;
  phase: string;
  is_open: boolean;
  trading_day_today: boolean;
  latest_closed_date: string;
  next_trading_day: string;
  session_token: string;
  opened_at?: string | null;
  closed_at?: string | null;
  next_open_at?: string | null;
  next_close_at?: string | null;
  after_hours_supported: boolean;
  provider_note: string;
  forecast_ready_note: string;
}

export interface MarketSessionsResponse {
  generated_at: string;
  sessions: MarketSessionItem[];
}

export interface DailyBriefingMarketView {
  country_code: string;
  label: string;
  stance: "risk_on" | "neutral" | "risk_off";
  conviction: number;
  actionable_count: number;
  bullish_count: number;
  summary: string;
}

export interface DailyBriefingFocusCard {
  country_code: string;
  ticker: string;
  name: string;
  sector: string;
  action: string;
  up_probability: number;
  confidence: number;
  predicted_return_pct: number;
  execution_note?: string | null;
}

export interface DailyBriefingEvent {
  date: string;
  country_code: string;
  title: string;
  subtitle?: string | null;
  impact: "high" | "medium" | "low";
  type: string;
  summary: string;
}

export interface DailyBriefingResponse {
  generated_at: string;
  partial?: boolean;
  fallback_reason?: string | null;
  sessions: MarketSessionItem[];
  market_view: DailyBriefingMarketView[];
  focus_cards: DailyBriefingFocusCard[];
  upcoming_events: DailyBriefingEvent[];
  research_archive: {
    todays_reports: number;
    total_reports: number;
    source_count: number;
    last_synced_at?: string | null;
  };
  priorities: string[];
}

export interface PortfolioEventRadarEvent {
  id: string;
  date: string;
  country_code: string;
  title: string;
  subtitle?: string | null;
  impact: "high" | "medium" | "low";
  type: string;
  portfolio_weight: number;
  country_weight: number;
  affected_holdings: {
    ticker: string;
    name: string;
    weight_pct: number;
  }[];
  summary: string;
}

export interface PortfolioEventRadarResponse {
  generated_at: string;
  window_days: number;
  events: PortfolioEventRadarEvent[];
}

export interface ForecastDeltaHistoryItem {
  target_date: string;
  reference_date?: string | null;
  reference_price: number;
  predicted_close: number;
  predicted_low?: number | null;
  predicted_high?: number | null;
  up_probability: number;
  confidence: number;
  direction?: string | null;
  direction_label: string;
  actual_close?: number | null;
  direction_hit?: boolean | null;
  model_version: string;
  created_at: number;
}

export interface ForecastDeltaResponse {
  generated_at: string;
  ticker: string;
  summary: {
    available: boolean;
    current_direction?: string | null;
    current_direction_label?: string;
    up_probability_delta?: number;
    confidence_delta?: number;
    predicted_close_delta_pct?: number;
    direction_changed?: boolean;
    hit_rate?: number | null;
    message: string;
  };
  history: ForecastDeltaHistoryItem[];
}

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
