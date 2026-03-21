export interface IndexInfo {
  ticker: string;
  name: string;
  price: number;
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

export interface CountryReport {
  country: { code: string; name: string; name_local: string };
  score: CountryScore;
  market_summary: string;
  key_news: NewsItem[];
  institutional_analysis: InstitutionalAnalysis;
  top_stocks: StockSummaryRef[];
  fear_greed: FearGreedIndex;
  forecast: IndexForecast;
  market_data: Record<string, { price: number; change_pct: number }>;
  generated_at: string;
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
  buy_price?: number;
  sell_price?: number;
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

export interface PricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
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
  financials: { period: string; revenue?: number; operating_income?: number; net_income?: number; ebitda?: number; free_cash_flow?: number }[];
  pe_ratio?: number;
  pb_ratio?: number;
  ev_ebitda?: number;
  peg_ratio?: number;
  peer_comparisons: { metric: string; company_value?: number; peer_avg?: number }[];
  dividend: { dividend_yield?: number; payout_ratio?: number };
  analyst_ratings: { buy: number; hold: number; sell: number; target_mean?: number; target_median?: number };
  earnings_history: { date: string; eps_estimate?: number; eps_actual?: number; surprise_pct?: number }[];
  price_history: PricePoint[];
  technical: { ma_20: (number | null)[]; ma_60: (number | null)[]; rsi_14: (number | null)[]; macd: (number | null)[]; dates: string[] };
  score: StockScore;
  buy_sell_guide: BuySellGuide;
  analysis_summary?: string;
  key_risks?: string[];
  key_catalysts?: string[];
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
