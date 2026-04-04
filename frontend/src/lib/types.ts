export interface IndexInfo {
  ticker: string;
  name: string;
  price?: number;
  current_price?: number;
  change_pct: number;
}

export interface CountryListItem {
  code: string;
  name: string;
  name_local: string;
  currency: string;
  indices: IndexInfo[];
}

export interface ScoreItem {
  name: string;
  score: number;
  max_score: number;
  description: string;
}

export interface CountryScore {
  total: number;
  monetary_policy: ScoreItem;
  economic_growth: ScoreItem;
  market_valuation: ScoreItem;
  earnings_momentum: ScoreItem;
  institutional_consensus: ScoreItem;
  risk_assessment: ScoreItem;
}

export interface ForecastScenario {
  name: string;
  price: number;
  probability: number;
  description: string;
}

export interface IndexForecast {
  index_ticker: string;
  index_name: string;
  current_price: number;
  fair_value: number;
  scenarios: ForecastScenario[];
  confidence_note: string;
}

export interface FlowSignal {
  available: boolean;
  source: string;
  market: string;
  unit: string;
  foreign_net_buy?: number | null;
  institutional_net_buy?: number | null;
  retail_net_buy?: number | null;
}

export interface ForecastDriver {
  name: string;
  value: number;
  signal: "bullish" | "bearish" | "neutral";
  weight: number;
  contribution: number;
  detail: string;
}

export interface NextDayForecast {
  target_date: string;
  reference_date: string;
  reference_price: number;
  direction: "up" | "down" | "flat";
  up_probability: number;
  predicted_open?: number | null;
  predicted_close: number;
  predicted_high: number;
  predicted_low: number;
  predicted_return_pct: number;
  confidence: number;
  raw_confidence?: number | null;
  calibrated_probability?: number | null;
  probability_edge?: number | null;
  analog_support?: number | null;
  regime_support?: number | null;
  agreement_support?: number | null;
  data_quality_support?: number | null;
  volatility_ratio?: number | null;
  confidence_calibrator?: string | null;
  calibration_snapshot?: Record<string, unknown> | null;
  fusion_method?: "prior_only" | "learned_blended" | "learned_blended_graph" | null;
  fusion_profile_sample_count?: number | null;
  fusion_blend_weight?: number | null;
  graph_context_used?: boolean | null;
  graph_context_score?: number | null;
  graph_coverage?: number | null;
  fusion_profile_fitted_at?: string | null;
  confidence_note: string;
  news_sentiment: number;
  raw_signal: number;
  scenarios?: ForecastScenario[];
  risk_flags?: string[];
  execution_bias?:
    | "press_long"
    | "lean_long"
    | "stay_selective"
    | "reduce_risk"
    | "capital_preservation";
  execution_note?: string;
  flow_signal?: FlowSignal | null;
  drivers: ForecastDriver[];
  model_version: string;
}

export interface FreeKrForecastDataSource {
  name: string;
  configured: boolean;
  used: boolean;
  item_count: number;
  note: string;
}

export interface FreeKrForecastEvidence {
  key: string;
  label: string;
  contribution: number;
  signal: "bullish" | "bearish" | "neutral";
  detail: string;
}

export interface FreeKrForecastHorizon {
  horizon_days: number;
  target_date: string;
  mean_return_raw: number;
  mean_return_excess: number;
  q10: number;
  q25: number;
  q50: number;
  q75: number;
  q90: number;
  price_q10: number;
  price_q25: number;
  price_q50: number;
  price_q75: number;
  price_q90: number;
  p_down: number;
  p_flat: number;
  p_up: number;
  vol_forecast: number;
  confidence: number;
  raw_confidence?: number | null;
  calibrated_probability?: number | null;
  probability_edge?: number | null;
  analog_support?: number | null;
  regime_support?: number | null;
  agreement_support?: number | null;
  data_quality_support?: number | null;
  volatility_ratio?: number | null;
  confidence_calibrator?: string | null;
  calibration_snapshot?: Record<string, unknown> | null;
  fusion_method?: "prior_only" | "learned_blended" | "learned_blended_graph" | null;
  fusion_profile_sample_count?: number | null;
  fusion_blend_weight?: number | null;
  graph_context_used?: boolean | null;
  graph_context_score?: number | null;
  graph_coverage?: number | null;
  fusion_profile_fitted_at?: string | null;
}

export interface FreeKrForecast {
  reference_date: string;
  reference_price: number;
  regime: "risk_on" | "neutral" | "risk_off";
  regime_probs: Record<string, number>;
  horizons: FreeKrForecastHorizon[];
  evidence: FreeKrForecastEvidence[];
  data_sources: FreeKrForecastDataSource[];
  confidence_note: string;
  summary: string;
  model_version: string;
}

export interface HistoricalForecastHorizon {
  horizon_days: number;
  sample_size: number;
  up_probability: number;
  expected_return_pct: number;
  median_return_pct: number;
  predicted_price: number;
  range_low: number;
  range_high: number;
  realized_volatility_pct: number;
  avg_max_drawdown_pct: number;
  confidence: number;
  analog_support?: number | null;
  effective_sample_size?: number | null;
  profit_factor?: number | null;
}

export interface HistoricalAnalogCase {
  date: string;
  similarity: number;
  return_5d?: number | null;
  return_20d?: number | null;
  return_60d?: number | null;
}

export interface HistoricalPathPoint {
  offset: number;
  target_date: string;
  expected_price: number;
  band_low: number;
  band_high: number;
}

export interface HistoricalPatternForecast {
  reference_date: string;
  reference_price: number;
  lookback_window_days: number;
  analog_count: number;
  feature_regime: string;
  summary: string;
  horizons: HistoricalForecastHorizon[];
  analog_cases: HistoricalAnalogCase[];
  projected_path: HistoricalPathPoint[];
  model_version: string;
}

export interface SetupBacktest {
  setup_label: string;
  forward_horizon_days: number;
  sample_size: number;
  win_rate: number;
  avg_return_pct: number;
  median_return_pct: number;
  avg_max_drawdown_pct: number;
  best_return_pct: number;
  worst_return_pct: number;
  profit_factor?: number | null;
  confidence: number;
  summary: string;
}

export interface MarketRegimeSignal {
  name: string;
  value: number;
  signal: "bullish" | "bearish" | "neutral";
  detail: string;
}

export interface MarketRegime {
  label: string;
  stance: "risk_on" | "neutral" | "risk_off";
  trend: "uptrend" | "range" | "downtrend";
  volatility: "low" | "normal" | "high";
  breadth: "strong" | "mixed" | "weak";
  score: number;
  conviction: number;
  summary: string;
  playbook: string[];
  warnings: string[];
  signals: MarketRegimeSignal[];
}

export interface TradePlan {
  setup_label: string;
  action: "accumulate" | "breakout_watch" | "wait_pullback" | "reduce_risk" | "avoid";
  conviction: number;
  entry_low?: number | null;
  entry_high?: number | null;
  stop_loss?: number | null;
  take_profit_1?: number | null;
  take_profit_2?: number | null;
  expected_holding_days: number;
  risk_reward_estimate: number;
  thesis: string[];
  invalidation: string;
}

export interface OpportunityItem {
  rank: number;
  ticker: string;
  name: string;
  sector: string;
  country_code: string;
  current_price: number;
  change_pct: number;
  opportunity_score: number;
  quant_score: number;
  up_probability: number;
  confidence: number;
  predicted_return_pct: number;
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
  raw_confidence_20d?: number | null;
  calibrated_probability_20d?: number | null;
  probability_edge_20d?: number | null;
  analog_support_20d?: number | null;
  regime_support_20d?: number | null;
  agreement_support_20d?: number | null;
  data_quality_support_20d?: number | null;
  volatility_ratio_20d?: number | null;
  confidence_calibrator_20d?: string | null;
  price_q25_20d?: number | null;
  price_q50_20d?: number | null;
  price_q75_20d?: number | null;
  bull_case_price?: number | null;
  base_case_price?: number | null;
  bear_case_price?: number | null;
  bull_probability?: number | null;
  base_probability?: number | null;
  bear_probability?: number | null;
  setup_label: string;
  action: string;
  execution_bias?: "press_long" | "lean_long" | "stay_selective" | "reduce_risk" | "capital_preservation";
  execution_note?: string;
  regime_tailwind: string;
  entry_low?: number | null;
  entry_high?: number | null;
  stop_loss?: number | null;
  take_profit_1?: number | null;
  take_profit_2?: number | null;
  risk_reward_estimate: number;
  thesis: string[];
  risk_flags: string[];
  forecast_date: string;
}

export interface OpportunityRadarResponse {
  country_code: string;
  snapshot_id: string;
  generated_at: string;
  partial?: boolean;
  fallback_reason?: string | null;
  fallback_tier?: "full" | "quick" | "cached_quick" | "placeholder";
  market_regime: MarketRegime;
  universe_size: number;
  total_scanned: number;
  quote_available_count?: number;
  detailed_scanned_count: number;
  actionable_count: number;
  bullish_count: number;
  universe_source?: "dynamic" | "fallback" | "krx_listing";
  universe_note?: string;
  opportunities: OpportunityItem[];
}

export interface FearGreedComponent {
  name: string;
  value: number;
  signal: string;
  weight: number;
}

export interface FearGreedIndex {
  score: number;
  label: string;
  components: FearGreedComponent[];
  country_code: string;
}

export interface StockSummaryRef {
  rank: number;
  ticker: string;
  name: string;
  score: number;
  current_price: number;
  change_pct: number;
  reason: string;
}

export interface InstitutionView {
  name: string;
  stance: string;
  key_points: string[];
}

export interface InstitutionalAnalysis {
  policy_institutions: InstitutionView[];
  sell_side: InstitutionView[];
  policy_sellside_aligned: boolean;
  consensus_count: number;
  consensus_summary: string;
}

export interface NewsItem {
  title: string;
  source: string;
  url: string;
  published: string;
  sentiment?: string;
}

export interface MacroClaim {
  source: string;
  published_at: string;
  metric: string;
  value: number;
  unit: string;
  direction: "up" | "down" | "flat";
  confidence: number;
}

export interface PricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface CountryReport {
  country: {
    code: string;
    name: string;
    name_local: string;
    currency?: string;
    indices?: IndexInfo[];
  };
  score: CountryScore;
  market_summary: string;
  macro_claims: MacroClaim[];
  key_news: NewsItem[];
  institutional_analysis: InstitutionalAnalysis;
  top_stocks: StockSummaryRef[];
  fear_greed: FearGreedIndex;
  forecast: IndexForecast;
  next_day_forecast?: NextDayForecast;
  market_regime?: MarketRegime;
  primary_index_history?: PricePoint[];
  market_data: Record<string, { price: number; change_pct: number }>;
  generated_at: string;
  partial?: boolean;
  fallback_reason?: string | null;
  llm_available?: boolean;
  errors?: string[];
}

export interface SectorListItem {
  id: string;
  name: string;
  country_code: string;
  stock_count: number;
}

export interface SectorStockItem {
  rank: number;
  ticker: string;
  name: string;
  score: number;
  current_price: number;
  change_pct: number;
  pros: string[];
  cons: string[];
  buy_price?: number | null;
  sell_price?: number | null;
}

export interface SectorScore {
  total: number;
  earnings_growth: ScoreItem;
  institutional_consensus: ScoreItem;
  valuation_attractiveness: ScoreItem;
  policy_impact: ScoreItem;
  technical_momentum: ScoreItem;
  risk_adjusted_return: ScoreItem;
}

export interface SectorReport {
  sector: SectorListItem;
  score: SectorScore;
  summary: string;
  top_stocks: SectorStockItem[];
  generated_at: string;
  llm_available?: boolean;
  errors?: string[];
}

export interface BuySellGuide {
  buy_zone_low: number;
  buy_zone_high: number;
  fair_value: number;
  sell_zone_low: number;
  sell_zone_high: number;
  risk_reward_ratio: number;
  confidence_grade: string;
  methodology: { name: string; value: number; weight: number; details: string }[];
  summary: string;
}

export interface PublicStockSummary {
  summary: string;
  evidence_for: string[];
  evidence_against: string[];
  why_not_buy_now: string[];
  thesis_breakers: string[];
  data_quality: string;
  confidence_note: string;
}

export interface StockScoreDetail {
  total: number;
  max_score: number;
  items: ScoreItem[];
}

export interface StockScore {
  total: number;
  fundamental: StockScoreDetail;
  valuation: StockScoreDetail;
  growth_momentum: StockScoreDetail;
  analyst: StockScoreDetail;
  risk: StockScoreDetail;
}

export interface StockDetail {
  ticker: string;
  name: string;
  country_code: string;
  sector: string;
  industry: string;
  market_cap: number;
  current_price: number;
  change_pct: number;
  financials: {
    period: string;
    revenue?: number;
    operating_income?: number;
    net_income?: number;
    ebitda?: number;
    free_cash_flow?: number;
  }[];
  pe_ratio?: number;
  pb_ratio?: number;
  ev_ebitda?: number;
  peg_ratio?: number;
  week52_high?: number | null;
  week52_low?: number | null;
  peer_comparisons: { metric: string; company_value?: number; peer_avg?: number }[];
  dividend: { dividend_yield?: number; payout_ratio?: number };
  analyst_ratings: {
    buy: number;
    hold: number;
    sell: number;
    target_mean?: number;
    target_median?: number;
    target_high?: number | null;
    target_low?: number | null;
  };
  earnings_history: { date: string; eps_estimate?: number | null; eps_actual?: number | null; surprise_pct?: number | null }[];
  price_history: PricePoint[];
  technical: {
    ma_20: (number | null)[];
    ma_60: (number | null)[];
    rsi_14: (number | null)[];
    macd: (number | null)[];
    macd_signal?: (number | null)[];
    macd_hist?: (number | null)[];
    dates: string[];
  };
  score: StockScore;
  buy_sell_guide: BuySellGuide;
  next_day_forecast?: NextDayForecast;
  free_kr_forecast?: FreeKrForecast | null;
  historical_pattern_forecast?: HistoricalPatternForecast | null;
  setup_backtest?: SetupBacktest | null;
  market_regime?: MarketRegime;
  trade_plan?: TradePlan;
  public_summary?: PublicStockSummary;
  analysis_summary?: string;
  key_risks?: string[];
  key_catalysts?: string[];
  llm_available?: boolean;
  errors?: string[];
  historical_pattern_warning?: string;
  generated_at?: string | null;
  partial?: boolean | null;
  fallback_reason?: string | null;
}

export interface WatchlistItem {
  id: number;
  ticker: string;
  country_code: string;
  name?: string;
  current_price?: number;
  change_pct?: number;
  score_total?: number;
  resolution_note?: string;
  tracking_enabled?: boolean;
  tracking_started_at?: string | null;
  tracking_updated_at?: string | null;
  last_prediction_at?: string | null;
  last_outlook_label?: string | null;
  last_confidence?: number | null;
}
