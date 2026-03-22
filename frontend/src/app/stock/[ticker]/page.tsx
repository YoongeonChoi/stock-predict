"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import ErrorBanner, { WarningBanner } from "@/components/ErrorBanner";
import MarketRegimeCard from "@/components/MarketRegimeCard";
import TradePlanCard from "@/components/TradePlanCard";
import AnalystConsensus from "@/components/charts/AnalystConsensus";
import CandlestickChart from "@/components/charts/CandlestickChart";
import EarningsSurprise from "@/components/charts/EarningsSurprise";
import NextDayForecastCard from "@/components/charts/NextDayForecastCard";
import PriceChart from "@/components/charts/PriceChart";
import ScoreBreakdown from "@/components/charts/ScoreBreakdown";
import ScoreRadial from "@/components/charts/ScoreRadial";
import TechnicalSummary from "@/components/charts/TechnicalSummary";
import { api } from "@/lib/api";
import type { CompositeScore, PivotPoints, TechSummary } from "@/lib/api";
import type { PricePoint, StockDetail } from "@/lib/types";
import { changeColor, formatMarketCap, formatPct, formatPrice } from "@/lib/utils";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "종목 상세를 불러오지 못했습니다.");
}

function valueOrPending(value: number | null | undefined, priceKey: string) {
  return value == null ? "미정" : formatPrice(value, priceKey);
}

export default function StockPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const [stock, setStock] = useState<StockDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [techSummary, setTechSummary] = useState<TechSummary | null>(null);
  const [pivotPoints, setPivotPoints] = useState<PivotPoints | null>(null);
  const [chartPeriod, setChartPeriod] = useState("3mo");
  const [chartType, setChartType] = useState<"line" | "candle">("line");
  const [chartData, setChartData] = useState<PricePoint[]>([]);

  useEffect(() => {
    if (!ticker) return;
    const decodedTicker = decodeURIComponent(ticker);
    setLoading(true);
    setError(null);

    api.getStockDetail(decodedTicker)
      .then(setStock)
      .catch((err) => {
        console.error(err);
        setError(toError(err));
      })
      .finally(() => setLoading(false));

    api.getTechSummary(decodedTicker).then(setTechSummary).catch(console.error);
    api.getPivotPoints(decodedTicker).then(setPivotPoints).catch(console.error);
  }, [ticker]);

  const changeChartPeriod = async (period: string) => {
    if (!ticker) return;
    setChartPeriod(period);
    try {
      const response = await api.getStockChart(decodeURIComponent(ticker), period);
      setChartData(response.data);
    } catch {
      setChartData([]);
    }
  };

  const addToWatchlist = () => {
    if (stock) {
      api.addWatchlist(stock.ticker, stock.country_code).catch(console.error);
    }
  };

  const composite = (stock as (StockDetail & { composite_score?: CompositeScore }) | null)?.composite_score ?? null;

  const week52Progress = useMemo(() => {
    if (!stock?.week52_low || !stock?.week52_high || stock.week52_high <= stock.week52_low) return null;
    return ((stock.current_price - stock.week52_low) / (stock.week52_high - stock.week52_low)) * 100;
  }, [stock]);

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-border rounded w-64" />
        <div className="h-72 bg-border rounded" />
        <div className="h-48 bg-border rounded" />
      </div>
    );
  }

  if (!stock && error) {
    return (
      <div className="max-w-5xl mx-auto space-y-4">
        <Link href="/" className="text-text-secondary hover:text-text">&larr; 홈으로</Link>
        <ErrorBanner error={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }

  if (!stock) return <div className="text-text-secondary">종목 정보를 찾을 수 없습니다.</div>;

  const priceKey = stock.country_code;
  const bsg = stock.buy_sell_guide;
  const displayedData = chartData.length > 0 ? chartData : stock.price_history;
  const ma20 = chartData.length === 0 ? stock.technical?.ma_20 : undefined;
  const ma60 = chartData.length === 0 ? stock.technical?.ma_60 : undefined;
  const scoreCategories = [
    { label: "기초체력", data: stock.score.fundamental },
    { label: "밸류에이션", data: stock.score.valuation },
    { label: "성장과 모멘텀", data: stock.score.growth_momentum },
    { label: "애널리스트", data: stock.score.analyst },
    { label: "리스크", data: stock.score.risk },
  ];
  const compositeCategories = composite
    ? [
        { label: "기초체력", data: composite.fundamental, color: "bg-blue-500" },
        { label: "밸류에이션", data: composite.valuation, color: "bg-indigo-500" },
        { label: "성장과 모멘텀", data: composite.growth_momentum, color: "bg-emerald-500" },
        { label: "애널리스트", data: composite.analyst, color: "bg-amber-500" },
        { label: "리스크", data: composite.risk, color: "bg-rose-500" },
        { label: "기술 지표", data: composite.technical, color: "bg-cyan-500" },
      ]
    : [];

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-text-secondary hover:text-text">&larr;</Link>
          <div>
            <h1 className="text-2xl font-bold">{stock.name}</h1>
            <span className="text-text-secondary text-sm">{stock.ticker} · {stock.sector} · {stock.industry}</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={addToWatchlist} className="text-sm px-4 py-2 rounded-lg border border-border hover:border-accent transition-colors">워치리스트 추가</button>
          <div className="text-right">
            <div className="text-2xl font-bold font-mono">{formatPrice(stock.current_price, priceKey)}</div>
            <div className={`text-lg ${changeColor(stock.change_pct)}`}>{formatPct(stock.change_pct)}</div>
          </div>
        </div>
      </div>

      {stock.errors && stock.errors.length > 0 ? <WarningBanner codes={stock.errors} /> : null}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card !p-4"><div className="text-xs text-text-secondary">시가총액</div><div className="font-bold mt-2">{formatMarketCap(stock.market_cap, priceKey)}</div></div>
        <div className="card !p-4"><div className="text-xs text-text-secondary">P/E</div><div className="font-bold mt-2">{stock.pe_ratio?.toFixed(2) ?? "없음"}</div></div>
        <div className="card !p-4"><div className="text-xs text-text-secondary">P/B</div><div className="font-bold mt-2">{stock.pb_ratio?.toFixed(2) ?? "없음"}</div></div>
        <div className="card !p-4"><div className="text-xs text-text-secondary">EV/EBITDA</div><div className="font-bold mt-2">{stock.ev_ebitda?.toFixed(2) ?? "없음"}</div></div>
      </div>

      {stock.analysis_summary ? (
        <div className="card">
          <h2 className="font-semibold mb-3">분석 요약</h2>
          <p className="text-sm leading-relaxed whitespace-pre-line">{stock.analysis_summary}</p>
        </div>
      ) : null}

      <div className="card">
        <div className="flex items-center justify-between mb-3 gap-4 flex-wrap">
          <h2 className="font-semibold">가격 차트</h2>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex gap-1">
              {[{ label: "1M", value: "1mo" }, { label: "3M", value: "3mo" }, { label: "6M", value: "6mo" }, { label: "1Y", value: "1y" }].map((period) => (
                <button key={period.value} onClick={() => changeChartPeriod(period.value)} className={`px-2 py-0.5 text-xs rounded ${chartPeriod === period.value ? "bg-accent text-white" : "bg-border text-text-secondary hover:text-text"}`}>{period.label}</button>
              ))}
            </div>
            <div className="flex gap-1 ml-2 border-l border-border pl-2">
              <button onClick={() => setChartType("line")} className={`px-2 py-0.5 text-xs rounded ${chartType === "line" ? "bg-accent text-white" : "bg-border text-text-secondary hover:text-text"}`}>라인</button>
              <button onClick={() => setChartType("candle")} className={`px-2 py-0.5 text-xs rounded ${chartType === "candle" ? "bg-accent text-white" : "bg-border text-text-secondary hover:text-text"}`}>캔들</button>
            </div>
          </div>
        </div>

        {chartType === "candle" ? (
          <CandlestickChart data={displayedData} />
        ) : (
          <PriceChart
            data={displayedData}
            ma20={ma20}
            ma60={ma60}
            buyZone={{ low: bsg.buy_zone_low, high: bsg.buy_zone_high }}
            sellZone={{ low: bsg.sell_zone_low, high: bsg.sell_zone_high }}
            fairValue={bsg.fair_value}
            nextDayForecast={stock.next_day_forecast}
          />
        )}

        <div className="flex gap-4 mt-2 text-xs text-text-secondary flex-wrap">
          <span><span className="inline-block w-3 h-0.5 bg-accent mr-1" /> 종가</span>
          <span><span className="inline-block w-3 h-0.5 bg-yellow-500 mr-1" /> MA20</span>
          <span><span className="inline-block w-3 h-0.5 bg-purple-500 mr-1" /> MA60</span>
          <span><span className="inline-block w-3 h-0.5 bg-emerald-500 mr-1" /> 매수 구간</span>
        </div>
      </div>

      {stock.next_day_forecast ? <NextDayForecastCard forecast={stock.next_day_forecast} assetLabel={stock.name} priceKey={priceKey} /> : null}

      {(stock.market_regime || stock.trade_plan) ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {stock.market_regime ? <MarketRegimeCard regime={stock.market_regime} title="시장 국면" /> : null}
          {stock.trade_plan ? <TradePlanCard plan={stock.trade_plan} priceKey={priceKey} /> : null}
        </div>
      ) : null}

      <div className="card">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div>
            <h2 className="font-semibold">매수 / 매도 가이드</h2>
            <p className="text-sm text-text-secondary mt-1">{bsg.summary}</p>
          </div>
          <span className={`text-sm px-3 py-1 rounded-full font-medium ${bsg.confidence_grade === "A" ? "bg-emerald-500/20 text-emerald-500" : bsg.confidence_grade === "B" ? "bg-yellow-500/20 text-yellow-500" : "bg-red-500/20 text-red-500"}`}>신뢰 등급 {bsg.confidence_grade}</span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
          <div className="p-3 rounded-lg bg-blue-500/10"><div className="text-xs text-text-secondary">매수 하단</div><div className="font-bold text-blue-500">{formatPrice(bsg.buy_zone_low, priceKey)}</div></div>
          <div className="p-3 rounded-lg bg-blue-500/10"><div className="text-xs text-text-secondary">매수 상단</div><div className="font-bold text-blue-500">{formatPrice(bsg.buy_zone_high, priceKey)}</div></div>
          <div className="p-3 rounded-lg bg-emerald-500/10"><div className="text-xs text-text-secondary">적정가</div><div className="font-bold text-emerald-500">{formatPrice(bsg.fair_value, priceKey)}</div></div>
          <div className="p-3 rounded-lg bg-red-500/10"><div className="text-xs text-text-secondary">매도 하단</div><div className="font-bold text-red-500">{formatPrice(bsg.sell_zone_low, priceKey)}</div></div>
          <div className="p-3 rounded-lg bg-red-500/10"><div className="text-xs text-text-secondary">매도 상단</div><div className="font-bold text-red-500">{formatPrice(bsg.sell_zone_high, priceKey)}</div></div>
        </div>

        <div className="text-sm text-text-secondary">손익비: <strong>{bsg.risk_reward_ratio.toFixed(2)}</strong></div>
        {bsg.methodology.length > 0 ? (
          <div className="mt-3 text-xs text-text-secondary space-y-1">
            {bsg.methodology.map((method, index) => (
              <div key={index}>• {method.name}: {formatPrice(method.value, priceKey)} (가중치 {(method.weight * 100).toFixed(0)}%) - {method.details}</div>
            ))}
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {techSummary ? (
          <div className="card">
            <h2 className="font-semibold mb-3">기술적 요약</h2>
            <TechnicalSummary data={techSummary} />
          </div>
        ) : null}

        {pivotPoints ? (
          <div className="card">
            <h2 className="font-semibold mb-3">피벗 포인트</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h4 className="text-xs text-text-secondary mb-2">클래식</h4>
                <div className="space-y-1 text-xs">
                  {(["r3", "r2", "r1", "pivot", "s1", "s2", "s3"] as const).map((key) => (
                    <div key={key} className="flex justify-between"><span className={key.startsWith("r") ? "text-positive" : key.startsWith("s") ? "text-negative" : "font-bold"}>{key.toUpperCase()}</span><span className="font-mono">{pivotPoints.classic[key]?.toFixed(2)}</span></div>
                  ))}
                </div>
              </div>
              <div>
                <h4 className="text-xs text-text-secondary mb-2">피보나치</h4>
                <div className="space-y-1 text-xs">
                  {(["r3", "r2", "r1", "pivot", "s1", "s2", "s3"] as const).map((key) => (
                    <div key={key} className="flex justify-between"><span className={key.startsWith("r") ? "text-positive" : key.startsWith("s") ? "text-negative" : "font-bold"}>{key.toUpperCase()}</span><span className="font-mono">{pivotPoints.fibonacci[key]?.toFixed(2)}</span></div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {(stock.analyst_ratings.buy + stock.analyst_ratings.hold + stock.analyst_ratings.sell) > 0 ? (
          <div className="card">
            <h2 className="font-semibold mb-3">애널리스트 의견</h2>
            <AnalystConsensus
              buy={stock.analyst_ratings.buy}
              hold={stock.analyst_ratings.hold}
              sell={stock.analyst_ratings.sell}
              targetLow={stock.analyst_ratings.target_low ?? null}
              targetMean={stock.analyst_ratings.target_mean ?? null}
              targetHigh={stock.analyst_ratings.target_high ?? null}
              currentPrice={stock.current_price}
            />
          </div>
        ) : null}

        {stock.earnings_history.length > 0 ? (
          <div className="card">
            <h2 className="font-semibold mb-3">실적 서프라이즈</h2>
            <EarningsSurprise data={stock.earnings_history.map((item) => ({ date: item.date, eps_estimate: item.eps_estimate ?? null, eps_actual: item.eps_actual ?? null, surprise_pct: item.surprise_pct ?? null }))} />
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="font-semibold mb-3">52주 범위</h2>
          {stock.week52_low != null && stock.week52_high != null ? (
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span>{formatPrice(stock.week52_low, priceKey)}</span>
                <span>{formatPrice(stock.week52_high, priceKey)}</span>
              </div>
              <div className="h-2 rounded-full bg-border relative overflow-hidden">
                <div className="absolute inset-y-0 left-0 bg-accent rounded-full" style={{ width: `${Math.min(100, Math.max(0, week52Progress ?? 0))}%` }} />
              </div>
              <div className="text-sm text-text-secondary">현재가 {formatPrice(stock.current_price, priceKey)} · 범위 내 위치 {week52Progress != null ? `${week52Progress.toFixed(1)}%` : "없음"}</div>
            </div>
          ) : (
            <div className="text-sm text-text-secondary">52주 범위를 계산할 데이터가 부족합니다.</div>
          )}
        </div>

        <div className="card">
          <h2 className="font-semibold mb-3">재무와 배당</h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg bg-border/30 p-3"><div className="text-xs text-text-secondary">PEG</div><div className="font-semibold mt-1">{stock.peg_ratio?.toFixed(2) ?? "없음"}</div></div>
            <div className="rounded-lg bg-border/30 p-3"><div className="text-xs text-text-secondary">배당수익률</div><div className="font-semibold mt-1">{stock.dividend.dividend_yield != null ? `${(stock.dividend.dividend_yield * 100).toFixed(2)}%` : "없음"}</div></div>
            <div className="rounded-lg bg-border/30 p-3"><div className="text-xs text-text-secondary">배당성향</div><div className="font-semibold mt-1">{stock.dividend.payout_ratio != null ? `${(stock.dividend.payout_ratio * 100).toFixed(2)}%` : "없음"}</div></div>
            <div className="rounded-lg bg-border/30 p-3"><div className="text-xs text-text-secondary">최근 분기 수</div><div className="font-semibold mt-1">{stock.financials.length}</div></div>
          </div>
        </div>
      </div>

      {stock.financials.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-3">최근 재무 스냅샷</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead>
                <tr className="text-left text-text-secondary border-b border-border">
                  <th className="pb-2 pr-4">기간</th>
                  <th className="pb-2 pr-4 text-right">매출</th>
                  <th className="pb-2 pr-4 text-right">영업이익</th>
                  <th className="pb-2 pr-4 text-right">순이익</th>
                  <th className="pb-2 pr-4 text-right">EBITDA</th>
                  <th className="pb-2 pr-4 text-right">FCF</th>
                </tr>
              </thead>
              <tbody>
                {stock.financials.slice(0, 4).map((row) => (
                  <tr key={row.period} className="border-b border-border/30">
                    <td className="py-2 pr-4 font-medium">{row.period}</td>
                    <td className="py-2 pr-4 text-right">{row.revenue?.toLocaleString() ?? "없음"}</td>
                    <td className="py-2 pr-4 text-right">{row.operating_income?.toLocaleString() ?? "없음"}</td>
                    <td className="py-2 pr-4 text-right">{row.net_income?.toLocaleString() ?? "없음"}</td>
                    <td className="py-2 pr-4 text-right">{row.ebitda?.toLocaleString() ?? "없음"}</td>
                    <td className="py-2 pr-4 text-right">{row.free_cash_flow?.toLocaleString() ?? "없음"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {stock.peer_comparisons.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-3">피어 비교</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            {stock.peer_comparisons.map((item) => (
              <div key={item.metric} className="rounded-lg border border-border px-3 py-3">
                <div className="text-xs text-text-secondary">{item.metric}</div>
                <div className="font-semibold mt-1">우리 종목 {item.company_value?.toFixed(2) ?? "없음"}</div>
                <div className="text-sm text-text-secondary mt-1">피어 평균 {item.peer_avg?.toFixed(2) ?? "없음"}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {(stock.key_catalysts?.length || stock.key_risks?.length) ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {stock.key_catalysts && stock.key_catalysts.length > 0 ? (
            <div className="card">
              <h2 className="font-semibold mb-3">상승 촉매</h2>
              <div className="space-y-2 text-sm text-text-secondary">{stock.key_catalysts.map((item) => <div key={item}>• {item}</div>)}</div>
            </div>
          ) : null}
          {stock.key_risks && stock.key_risks.length > 0 ? (
            <div className="card">
              <h2 className="font-semibold mb-3">핵심 리스크</h2>
              <div className="space-y-2 text-sm text-text-secondary">{stock.key_risks.map((item) => <div key={item}>• {item}</div>)}</div>
            </div>
          ) : null}
        </div>
      ) : null}

      {composite ? (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">복합 점수</h2>
            <div className="flex items-center gap-3">
              <div className={`text-3xl font-bold ${composite.total >= 70 ? "text-positive" : composite.total >= 50 ? "text-warning" : "text-negative"}`}>{composite.total.toFixed(1)}</div>
              <span className="text-xs text-text-secondary">/ 100</span>
            </div>
          </div>

          <div className="space-y-3 mb-5">
            {compositeCategories.map((category) => (
              <div key={category.label}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium">{category.label}</span>
                  <span className="text-text-secondary">{category.data.total}/{category.data.max_score}</span>
                </div>
                <div className="h-2 bg-border rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${category.color}`} style={{ width: `${(category.data.total / category.data.max_score) * 100}%` }} />
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1">
                  {category.data.items.map((item) => (
                    <div key={item.name} className="flex items-center gap-1 text-[10px] text-text-secondary">
                      <span>{item.name}</span>
                      <span className="font-mono font-medium">{item.score.toFixed(1)}/{item.max_score}</span>
                      <span className="opacity-60">({item.description})</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="text-[10px] text-text-secondary border-t border-border pt-2">Raw {composite.total_raw}/{composite.max_raw}를 100점 기준으로 정규화한 점수입니다.</div>
        </div>
      ) : null}

      <div className="card">
        <h2 className="font-semibold mb-4">세부 점수</h2>
        <div className="flex items-center gap-6 mb-5 flex-wrap">
          <ScoreRadial score={stock.score.total || 0} label="종합" />
          <div className="flex gap-3 flex-wrap">
            {scoreCategories.map((category) => (
              <ScoreRadial key={category.label} score={category.data.total} max={category.data.max_score} size={84} label={category.label} />
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {scoreCategories.map((category) => (
            <div key={category.label} className="rounded-xl border border-border px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <div className="font-medium">{category.label}</div>
                <div className="text-xs text-text-secondary">{category.data.total}/{category.data.max_score}</div>
              </div>
              <ScoreBreakdown items={category.data.items} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}