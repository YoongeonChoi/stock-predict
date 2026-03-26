"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import ErrorBanner, { WarningBanner } from "@/components/ErrorBanner";
import MarketRegimeCard from "@/components/MarketRegimeCard";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import FearGreedGauge from "@/components/charts/FearGreedGauge";
import ForecastBand from "@/components/charts/ForecastBand";
import NextDayForecastCard from "@/components/charts/NextDayForecastCard";
import PriceChart from "@/components/charts/PriceChart";
import ScoreBreakdown from "@/components/charts/ScoreBreakdown";
import ScoreRadial from "@/components/charts/ScoreRadial";
import { api } from "@/lib/api";
import type { CountryReport, OpportunityRadarResponse, ScoreItem, SectorListItem } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "국가 리포트를 불러오지 못했습니다.");
}

function stanceLabel(value: string) {
  if (value === "bullish") return "강세";
  if (value === "bearish") return "약세";
  if (value === "neutral") return "중립";
  return value;
}

function stanceTone(value: string) {
  if (value === "bullish") return "bg-positive/20 text-positive";
  if (value === "bearish") return "bg-negative/20 text-negative";
  return "bg-border text-text-secondary";
}

export default function CountryPage() {
  const { code } = useParams<{ code: string }>();
  const [report, setReport] = useState<CountryReport | null>(null);
  const [sectors, setSectors] = useState<SectorListItem[]>([]);
  const [opportunities, setOpportunities] = useState<OpportunityRadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!code) return;
    setLoading(true);
    setError(null);

    const loadReport = api.getCountryReport(code)
      .then(setReport)
      .catch((err) => {
        console.error(err);
        setError(toError(err));
      });

    const loadSectors = api.getSectors(code).then(setSectors).catch(console.error);
    const loadOpportunities = api.getMarketOpportunities(code, 8).then(setOpportunities).catch(console.error);

    Promise.all([loadReport, loadSectors, loadOpportunities]).finally(() => setLoading(false));
  }, [code]);

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-border rounded w-48" />
        <div className="h-96 bg-border rounded" />
      </div>
    );
  }

  if (!report && error) {
    return (
      <div className="max-w-5xl mx-auto space-y-4">
        <Link href="/" className="text-text-secondary hover:text-text">&larr; 홈으로</Link>
        <ErrorBanner error={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }

  if (!report) return <div className="text-text-secondary">국가 리포트를 찾을 수 없습니다.</div>;

  const defaultScore: ScoreItem = { name: "", score: 0, max_score: 0, description: "" };
  const score = report.score;
  const scoreItems = [
    score.monetary_policy || defaultScore,
    score.economic_growth || defaultScore,
    score.market_valuation || defaultScore,
    score.earnings_momentum || defaultScore,
    score.institutional_consensus || defaultScore,
    score.risk_assessment || defaultScore,
  ];
  const institutions = report.institutional_analysis;
  const news = report.key_news || [];
  const topStocks = report.top_stocks || [];
  const primaryIndex = report.country.indices?.[0];
  const priceKey = report.country.code || code || "KR";

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-text-secondary hover:text-text">&larr;</Link>
          <div>
            <h1 className="text-2xl font-bold">{report.country?.name_local || report.country?.name || "국가"} 국가 리포트</h1>
            <div className="text-sm text-text-secondary mt-1">생성 시각 {new Date(report.generated_at).toLocaleString("ko-KR")}</div>
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          <a href={`/api/country/${code}/report/pdf`} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:opacity-90 transition-opacity">PDF</a>
          <a href={`/api/country/${code}/report/csv`} className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:border-accent/50 transition-colors">CSV</a>
        </div>
      </div>

      {report.errors && report.errors.length > 0 ? <WarningBanner codes={report.errors} /> : null}

      {report.country.indices && report.country.indices.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {report.country.indices.map((index) => (
            <div key={index.ticker} className="card !p-4">
              <div className="text-xs text-text-secondary">{index.name}</div>
              <div className="text-xl font-bold mt-2">{formatPrice(index.price ?? index.current_price, priceKey)}</div>
              <div className={`text-sm mt-1 ${changeColor(index.change_pct ?? 0)}`}>{formatPct(index.change_pct ?? 0)}</div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="card">
        <h2 className="font-semibold mb-3">시장 요약</h2>
        <div className="text-sm leading-relaxed whitespace-pre-line">{report.market_summary || "시장 요약이 아직 준비되지 않았습니다."}</div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="card lg:col-span-2">
          <div className="flex items-center gap-6 mb-4">
            <ScoreRadial score={score.total || 0} label="종합" />
            <div className="flex-1">
              <ScoreBreakdown items={scoreItems} />
            </div>
          </div>
        </div>
        {report.fear_greed ? (
          <div className="card flex flex-col items-center justify-center">
            <h3 className="font-semibold mb-3">공포 / 탐욕</h3>
            <FearGreedGauge data={report.fear_greed} />
          </div>
        ) : null}
      </div>

      {report.primary_index_history && report.primary_index_history.length > 0 ? (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="font-semibold">{primaryIndex?.name || "대표 지수"} 추이</h2>
              <p className="text-xs text-text-secondary mt-1">{primaryIndex?.ticker || code} · 최근 기준가 {formatPrice(report.next_day_forecast?.reference_price ?? primaryIndex?.price ?? primaryIndex?.current_price, priceKey)}</p>
            </div>
          </div>
          <PriceChart data={report.primary_index_history} nextDayForecast={report.next_day_forecast} />
          <div className="flex gap-4 mt-2 text-xs text-text-secondary flex-wrap">
            <span><span className="inline-block w-3 h-0.5 bg-accent mr-1" /> 종가</span>
            <span><span className="inline-block w-3 h-0.5 bg-emerald-500 mr-1" /> 예상 경로</span>
          </div>
        </div>
      ) : null}

      {report.next_day_forecast ? (
        <NextDayForecastCard forecast={report.next_day_forecast} assetLabel={primaryIndex?.name || report.country?.name_local || report.country?.name || "대표 지수"} priceKey={priceKey} />
      ) : null}

      {report.market_regime ? (
        <MarketRegimeCard regime={report.market_regime} title={`${primaryIndex?.name || report.country?.name_local || report.country?.name || "시장"} 국면`} />
      ) : null}

      {report.forecast && report.forecast.scenarios?.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-3">1개월 시나리오 예측</h2>
          <ForecastBand forecast={report.forecast} />
        </div>
      ) : null}

      {opportunities ? <OpportunityRadarBoard data={opportunities} compact /> : null}

      {sectors.length > 0 ? (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">주요 섹터</h2>
            <span className="text-xs text-text-secondary">총 {sectors.length}개</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {sectors.slice(0, 12).map((sector) => (
              <Link key={sector.id} href={`/country/${code}/sector/${sector.id}`} className="px-3 py-1.5 rounded-full border border-border text-sm hover:border-accent/50 hover:text-accent transition-colors">
                {sector.name}
              </Link>
            ))}
          </div>
        </div>
      ) : null}

      {news.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-3">주요 뉴스</h2>
          <div className="space-y-2">
            {news.slice(0, 8).map((item, index) => (
              <a key={index} href={item.url} target="_blank" rel="noopener noreferrer" className="block text-sm hover:text-accent transition-colors">
                <span className="text-text-secondary mr-2">{item.source}</span>
                {item.title}
              </a>
            ))}
          </div>
        </div>
      ) : null}

      {(institutions.policy_institutions?.length > 0 || institutions.sell_side?.length > 0) ? (
        <div className="card">
          <h2 className="font-semibold mb-3">기관 컨센서스</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <h3 className="text-sm font-medium text-text-secondary mb-2">정책 기관</h3>
              {institutions.policy_institutions.map((institution, index) => (
                <div key={index} className="mb-3 text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium">{institution.name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${stanceTone(institution.stance)}`}>{stanceLabel(institution.stance)}</span>
                  </div>
                  <ul className="space-y-1 text-text-secondary">
                    {institution.key_points.map((point, pointIndex) => <li key={pointIndex}>• {point}</li>)}
                  </ul>
                </div>
              ))}
            </div>
            <div>
              <h3 className="text-sm font-medium text-text-secondary mb-2">증권사 / IB</h3>
              {institutions.sell_side.map((institution, index) => (
                <div key={index} className="mb-3 text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium">{institution.name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${stanceTone(institution.stance)}`}>{stanceLabel(institution.stance)}</span>
                  </div>
                  <ul className="space-y-1 text-text-secondary">
                    {institution.key_points.map((point, pointIndex) => <li key={pointIndex}>• {point}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          </div>
          {institutions.consensus_summary ? <p className="text-sm text-text-secondary">{institutions.consensus_summary}</p> : null}
        </div>
      ) : null}

      {topStocks.length > 0 ? (
        <div className="card">
          <h2 className="font-semibold mb-3">상위 5개 대표 종목</h2>
          <div className="space-y-3">
            {topStocks.map((stock) => (
              <Link key={stock.ticker} href={`/stock/${stock.ticker}`} className="flex items-center justify-between p-3 rounded-lg hover:bg-border/30 transition-colors">
                <div className="flex items-center gap-3">
                  <div className="flex flex-col items-center w-12 shrink-0">
                    <span className="text-lg font-bold text-accent">#{stock.rank}</span>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${stock.score >= 70 ? "bg-positive/20 text-positive" : stock.score >= 50 ? "bg-warning/20 text-warning" : "bg-negative/20 text-negative"}`}>{stock.score.toFixed(1)}</span>
                  </div>
                  <div>
                    <div className="font-medium">{stock.name}</div>
                    <div className="text-xs text-text-secondary mt-1">{stock.ticker}</div>
                    <div className="text-sm text-text-secondary mt-1">{stock.reason}</div>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="font-mono font-semibold">{formatPrice(stock.current_price, priceKey)}</div>
                  <div className={`text-sm mt-1 ${changeColor(stock.change_pct ?? 0)}`}>{formatPct(stock.change_pct ?? 0)}</div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
