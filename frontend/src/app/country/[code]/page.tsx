"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import ErrorBanner, { WarningBanner } from "@/components/ErrorBanner";
import MarketRegimeCard from "@/components/MarketRegimeCard";
import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import PageHeader from "@/components/PageHeader";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import FearGreedGauge from "@/components/charts/FearGreedGauge";
import ForecastBand from "@/components/charts/ForecastBand";
import NextDayForecastCard from "@/components/charts/NextDayForecastCard";
import PriceChart from "@/components/charts/PriceChart";
import ScoreBreakdown from "@/components/charts/ScoreBreakdown";
import ScoreRadial from "@/components/charts/ScoreRadial";
import { api } from "@/lib/api";
import type { CountryReport, MacroClaim, OpportunityRadarResponse, ScoreItem, SectorListItem } from "@/lib/types";
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
  if (value === "bullish") return "bg-positive/10 text-positive";
  if (value === "bearish") return "bg-negative/10 text-negative";
  return "bg-surface-elevated text-text-secondary";
}

function macroClaimTone(direction: MacroClaim["direction"]) {
  if (direction === "up") return "text-positive";
  if (direction === "down") return "text-negative";
  return "text-text";
}

function formatMacroClaimValue(claim: MacroClaim) {
  const showSigned =
    claim.metric.includes("등락률")
    || claim.metric.includes("증가")
    || claim.metric.includes("성장률");
  const prefix = showSigned && claim.value > 0 ? "+" : "";
  return `${prefix}${claim.value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}${claim.unit}`;
}

function formatMacroClaimDate(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ko-KR");
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
      .catch((caught) => setError(toError(caught)));

    const loadSectors = api.getSectors(code).then(setSectors).catch(() => setSectors([]));
    const loadOpportunities = api.getMarketOpportunities(code, 8).then(setOpportunities).catch(() => setOpportunities(null));

    Promise.all([loadReport, loadSectors, loadOpportunities]).finally(() => setLoading(false));
  }, [code]);

  if (loading) {
    return (
      <div className="page-shell">
        <WorkspaceLoadingCard
          title="국가 리포트를 불러오고 있습니다"
          message="시장 요약, 지수 흐름, 기관 컨센서스를 같은 흐름으로 다시 정리하는 중입니다."
          className="min-h-[220px]"
        />
      </div>
    );
  }

  if (!report && error) {
    return (
      <div className="page-shell">
        <Link href="/" className="ui-button-ghost w-fit px-0">
          홈으로 돌아가기
        </Link>
        <ErrorBanner error={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="page-shell">
        <WorkspaceStateCard
          kind="empty"
          title="국가 리포트를 찾지 못했습니다"
          message="지원 중인 시장 코드인지 다시 확인해 주세요."
        />
      </div>
    );
  }

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
  const countryTitle = report.country?.name_local || report.country?.name || "국가";

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="시장 탐색"
        title={`${countryTitle} 국가 리포트`}
        description={`시장 요약, 주요 지수, 기관 컨센서스, 상위 종목을 한 흐름으로 정리합니다. 생성 시각 ${new Date(report.generated_at).toLocaleString("ko-KR")}`}
        meta={
          <>
            <span className="info-chip">{code}</span>
            {primaryIndex?.ticker ? <span className="info-chip">{primaryIndex.ticker}</span> : null}
          </>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Link href="/" className="ui-button-secondary px-4">
              홈으로
            </Link>
            <a href={`/api/country/${code}/report/pdf`} className="ui-button-primary px-4">
              PDF
            </a>
            <a href={`/api/country/${code}/report/csv`} className="ui-button-secondary px-4">
              CSV
            </a>
          </div>
        }
      />

      {report.errors && report.errors.length > 0 ? <WarningBanner codes={report.errors} /> : null}

      {report.country.indices && report.country.indices.length > 0 ? (
        <section className="card !p-5">
          <div className="section-heading">
            <div>
              <h2 className="section-title">대표 지수 스냅샷</h2>
              <p className="section-copy">가격과 등락률을 먼저 보고, 아래에서 차트와 예측 밴드를 이어서 확인합니다.</p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {report.country.indices.map((index) => (
              <div key={index.ticker} className="metric-card">
                <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-secondary">{index.name}</div>
                <div className="mt-2 font-mono text-[1.45rem] font-semibold text-text">
                  {formatPrice(index.price ?? index.current_price, priceKey)}
                </div>
                <div className={`mt-2 text-sm font-medium ${changeColor(index.change_pct ?? 0)}`}>
                  {formatPct(index.change_pct ?? 0)}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="card !p-5 space-y-5">
        <div className="section-heading">
          <div>
            <h2 className="section-title">시장 요약</h2>
            <p className="section-copy">긴 설명은 박스 안에 또 가두지 않고, 핵심 주장만 아래에 이어서 배치합니다.</p>
          </div>
        </div>
        <div className="max-w-5xl whitespace-pre-line text-[0.98rem] leading-8 text-text">
          {report.market_summary || "시장 요약이 아직 준비되지 않았습니다."}
        </div>
        {report.macro_claims && report.macro_claims.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {report.macro_claims.slice(0, 4).map((claim) => (
              <div key={`${claim.source}-${claim.metric}`} className="metric-card">
                <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-secondary">{claim.metric}</div>
                <div className={`mt-2 text-lg font-semibold ${macroClaimTone(claim.direction)}`}>
                  {formatMacroClaimValue(claim)}
                </div>
                <div className="mt-2 text-[12px] leading-6 text-text-secondary">
                  {claim.source}
                  {formatMacroClaimDate(claim.published_at) ? ` · ${formatMacroClaimDate(claim.published_at)}` : ""}
                  {` · 근거 ${Math.round((claim.confidence ?? 0) * 100)}%`}
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <div className="workspace-grid-balanced">
        <section className="card !p-5">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center">
            <ScoreRadial score={score.total || 0} label="종합" />
            <div className="min-w-0 flex-1">
              <ScoreBreakdown items={scoreItems} />
            </div>
          </div>
        </section>
        {report.fear_greed ? (
          <section className="card !p-5">
            <div className="section-heading">
              <div>
                <h2 className="section-title">공포 / 탐욕</h2>
              </div>
            </div>
            <div className="mt-4 flex justify-center">
              <FearGreedGauge data={report.fear_greed} />
            </div>
          </section>
        ) : null}
      </div>

      {report.primary_index_history && report.primary_index_history.length > 0 ? (
        <section className="card !p-5 space-y-4">
          <div className="section-heading">
            <div>
              <h2 className="section-title">{primaryIndex?.name || "대표 지수"} 추이</h2>
              <p className="section-copy">
                {primaryIndex?.ticker || code} · 최근 기준가 {formatPrice(report.next_day_forecast?.reference_price ?? primaryIndex?.price ?? primaryIndex?.current_price, priceKey)}
              </p>
            </div>
          </div>
          <PriceChart data={report.primary_index_history} nextDayForecast={report.next_day_forecast} />
          <div className="flex flex-wrap gap-2 text-[12px] text-text-secondary">
            <span className="status-token">종가</span>
            <span className="status-token">예상 경로</span>
          </div>
        </section>
      ) : null}

      {report.next_day_forecast ? (
        <NextDayForecastCard
          forecast={report.next_day_forecast}
          assetLabel={primaryIndex?.name || countryTitle}
          priceKey={priceKey}
        />
      ) : null}

      {report.market_regime ? (
        <MarketRegimeCard regime={report.market_regime} title={`${primaryIndex?.name || countryTitle} 국면`} />
      ) : null}

      {report.forecast && report.forecast.scenarios?.length > 0 ? (
        <section className="card !p-5">
          <div className="section-heading">
            <div>
              <h2 className="section-title">1개월 시나리오 예측</h2>
            </div>
          </div>
          <div className="mt-4">
            <ForecastBand forecast={report.forecast} />
          </div>
        </section>
      ) : null}

      {opportunities ? <OpportunityRadarBoard data={opportunities} compact /> : null}

      {sectors.length > 0 ? (
        <section className="card !p-5">
          <div className="section-heading">
            <div>
              <h2 className="section-title">주요 섹터</h2>
              <p className="section-copy">총 {sectors.length}개 섹터 중 대표 흐름부터 바로 이동합니다.</p>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {sectors.slice(0, 12).map((sector) => (
              <Link key={sector.id} href={`/country/${code}/sector/${sector.id}`} className="ui-button-secondary px-4">
                {sector.name}
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {news.length > 0 ? (
        <section className="card !p-5">
          <div className="section-heading">
            <div>
              <h2 className="section-title">주요 뉴스</h2>
            </div>
          </div>
          <div className="mt-4 divide-y divide-border/10">
            {news.slice(0, 8).map((item, index) => (
              <a
                key={index}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="grid gap-2 py-3 transition-colors hover:text-accent"
              >
                <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-secondary">{item.source}</span>
                <span className="text-sm leading-7 text-text">{item.title}</span>
              </a>
            ))}
          </div>
        </section>
      ) : null}

      {(institutions.policy_institutions?.length > 0 || institutions.sell_side?.length > 0) ? (
        <section className="card !p-5 space-y-5">
          <div className="section-heading">
            <div>
              <h2 className="section-title">기관 컨센서스</h2>
            </div>
          </div>
          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-4">
              <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-secondary">정책 기관</div>
              {institutions.policy_institutions.map((institution, index) => (
                <div key={index} className="section-slab-subtle">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-text">{institution.name}</span>
                    <span className={`status-token ${stanceTone(institution.stance)}`}>{stanceLabel(institution.stance)}</span>
                  </div>
                  <ul className="mt-3 space-y-2 text-sm leading-7 text-text-secondary">
                    {institution.key_points.map((point, pointIndex) => (
                      <li key={pointIndex}>· {point}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <div className="space-y-4">
              <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-secondary">증권사 / IB</div>
              {institutions.sell_side.map((institution, index) => (
                <div key={index} className="section-slab-subtle">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-text">{institution.name}</span>
                    <span className={`status-token ${stanceTone(institution.stance)}`}>{stanceLabel(institution.stance)}</span>
                  </div>
                  <ul className="mt-3 space-y-2 text-sm leading-7 text-text-secondary">
                    {institution.key_points.map((point, pointIndex) => (
                      <li key={pointIndex}>· {point}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
          {institutions.consensus_summary ? (
            <div className="max-w-4xl text-sm leading-7 text-text-secondary">{institutions.consensus_summary}</div>
          ) : null}
        </section>
      ) : null}

      {topStocks.length > 0 ? (
        <section className="card !p-5">
          <div className="section-heading">
            <div>
              <h2 className="section-title">상위 대표 종목</h2>
            </div>
          </div>
          <div className="mt-4 divide-y divide-border/10">
            {topStocks.map((stock) => (
              <Link key={stock.ticker} href={`/stock/${stock.ticker}`} className="grid gap-3 py-4 md:grid-cols-[72px_minmax(0,1fr)_140px]">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-lg font-semibold text-accent">#{stock.rank}</span>
                  <span className="status-token">{stock.score.toFixed(1)}</span>
                </div>
                <div className="min-w-0">
                  <div className="font-semibold text-text">{stock.name}</div>
                  <div className="mt-1 font-mono text-[12px] text-text-secondary">{stock.ticker}</div>
                  <div className="mt-2 text-sm leading-7 text-text-secondary">{stock.reason}</div>
                </div>
                <div className="text-left md:text-right">
                  <div className="font-mono text-[1rem] font-semibold text-text">
                    {formatPrice(stock.current_price, priceKey)}
                  </div>
                  <div className={`mt-1 text-sm ${changeColor(stock.change_pct ?? 0)}`}>{formatPct(stock.change_pct ?? 0)}</div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
