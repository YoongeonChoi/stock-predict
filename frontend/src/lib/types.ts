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
  confidence_note: string;
  news_sentiment: number;
  raw_signal: number;
  flow_signal?: FlowSignal | null;
  drivers: ForecastDriver[];
  model_version: string;
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
  key_news: NewsItem[];
  institutional_analysis: InstitutionalAnalysis;
  top_stocks: StockSummaryRef[];
  fear_greed: FearGreedIndex;
  forecast: IndexForecast;
  next_day_forecast?: NextDayForecast;
  primary_index_history?: PricePoint[];
  market_data: Record<string, { price: number; change_pct: number }>;
  generated_at: string;
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
  analysis_summary?: string;
  key_risks?: string[];
  key_catalysts?: string[];
  llm_available?: boolean;
  errors?: string[];
}

export interface WatchlistItem {
  id: number;
  ticker: string;
  country_code: string;
  name?: string;
  current_price?: number;
  change_pct?: number;
  score_total?: number;
}
