"use client";

import Link from "next/link";

import PublicAuditStrip from "@/components/PublicAuditStrip";
import type { OpportunityRadarResponse } from "@/lib/types";
import { cn, changeColor, formatPct, formatPrice } from "@/lib/utils";

interface Props {
  data: OpportunityRadarResponse;
  compact?: boolean;
  embedded?: boolean;
}

const OPERATIONAL_FALLBACK_PATTERNS = [
  "1차 시세 스캔 후보",
  "시세 스냅샷",
  "fresh quick",
  "사용 가능한 후보",
  "정밀 시장 국면 계산",
  "정밀 국면 계산",
  "대표 후보",
  "다시 열어",
];

function isOperationalFallbackCopy(text?: string | null) {
  if (!text) return false;
  return OPERATIONAL_FALLBACK_PATTERNS.some((pattern) => text.includes(pattern));
}

function actionTone(action: string) {
  if (action === "accumulate" || action === "breakout_watch") return "text-positive bg-positive/10";
  if (action === "reduce_risk" || action === "avoid") return "text-negative bg-negative/10";
  return "text-warning bg-warning/10";
}

function actionLabel(action: string) {
  if (action === "accumulate") return "분할 매수";
  if (action === "breakout_watch") return "돌파 감시";
  if (action === "reduce_risk") return "리스크 축소";
  if (action === "wait_pullback") return "눌림 대기";
  if (action === "avoid") return "관망";
  return action.replaceAll("_", " ");
}

function executionBiasLabel(bias?: string) {
  if (bias === "press_long") return "추세 대응";
  if (bias === "lean_long") return "상방 우세";
  if (bias === "reduce_risk") return "리스크 관리";
  if (bias === "capital_preservation") return "방어 우선";
  return "선별 대응";
}

function executionBiasTone(bias?: string) {
  if (bias === "press_long") return "text-positive bg-positive/10";
  if (bias === "lean_long") return "text-emerald-500 bg-emerald-500/10";
  if (bias === "reduce_risk") return "text-amber-500 bg-amber-500/10";
  if (bias === "capital_preservation") return "text-negative bg-negative/10";
  return "text-text-secondary bg-border/40";
}

function opportunityScoreLabel(data: OpportunityRadarResponse, setupLabel: string) {
  if (data.detailed_scanned_count <= 0 || setupLabel === "전수 1차 스캔") {
    return "1차 스캔 점수";
  }
  return "레이더 점수";
}

function priceRange(low?: number | null, high?: number | null, key = "KR") {
  if (low == null && high == null) return "미정";
  if (low != null && high != null) return `${formatPrice(low, key)} - ${formatPrice(high, key)}`;
  return formatPrice(low ?? high, key);
}

export default function OpportunityRadarBoard({ data, compact = false, embedded = false }: Props) {
  const items = compact ? data.opportunities.slice(0, 4) : data.opportunities;
  const usingFallbackUniverse = data.universe_source === "fallback";
  const usingKrxListingUniverse = data.universe_source === "krx_listing";
  const usingTop200Universe = data.universe_source === "kr_top200";
  const quoteAvailableCount = data.quote_available_count ?? data.total_scanned;
  const visibleCandidateCount = Math.max(data.opportunities.length, data.actionable_count);
  const hasItems = items.length > 0;
  const universeLabel = usingTop200Universe ? "대표 유니버스" : "전체 유니버스";
  const radarUniverseSummary = usingTop200Universe
    ? `코스피 상위 190개와 코스닥 상위 10개, 총 ${data.universe_size}개 대표 종목`
    : `KR 유니버스 ${data.universe_size}개`;
  const liveUniverseBadge = usingTop200Universe ? "대표 200종목 유니버스 기반 추천" : "실시간 유니버스 기반 추천";
  const listingUniverseNote = usingTop200Universe
    ? data.universe_note || "코스피 190개와 코스닥 10개 대표 종목 기준 1차 스캔 결과입니다."
    : data.universe_note || "KRX 상장사 목록 기준 전종목 1차 스캔 결과입니다.";
  const quoteCoverageNote =
    quoteAvailableCount < data.total_scanned
      ? `실제 시세를 확보한 종목은 ${quoteAvailableCount}개입니다. 일부 종목은 데이터 원본 제한이나 거래 상태에 따라 1차 점수 계산에서 제외될 수 있습니다.`
      : "";
  const emptyMessage =
    quoteAvailableCount > 0
      ? "1차 시세 스캔은 끝났지만 이번 응답에서 정밀 후보 정리가 비어 있습니다. 잠시 뒤 다시 열면 상위 후보가 채워질 수 있습니다."
      : "실시간 시세 확보가 지연돼 대표 후보를 아직 만들지 못했습니다. 잠시 뒤 다시 열어 주세요.";
  const radarSummary =
    data.detailed_scanned_count > 0
      ? `아래 후보 보드는 20거래일 기대 수익 분포 기준입니다. ${radarUniverseSummary}를 1차 스캔했고, 실제 시세를 확보한 ${quoteAvailableCount}개 중 상위 ${data.detailed_scanned_count}개를 정밀 분석해 ${visibleCandidateCount}개 후보를 표시합니다.`
      : `아래 후보 보드는 20거래일 기대 수익 분포 기준입니다. ${radarUniverseSummary}를 1차 스캔했고, 실제 시세를 확보한 ${quoteAvailableCount}개 중 상위 ${visibleCandidateCount}개 후보를 먼저 표시합니다.`;
  const operationalFallbackNote =
    data.partial && hasItems
      ? "정밀 국면 계산이 길어져 이번 화면은 먼저 확보된 usable 후보와 핵심 수치 중심으로 정리했습니다."
      : null;
  const universeBadgeLabel = usingFallbackUniverse
    ? "기본 유니버스 응답"
    : usingKrxListingUniverse || usingTop200Universe
      ? (usingTop200Universe ? "대표 200종목 기준" : "KRX 전종목 기준")
      : "실시간 유니버스 기준";

  if (compact) {
    return (
      <div className={cn("min-w-0 space-y-4", embedded ? "" : "card !p-5")}>
        <div className="space-y-3">
          {!embedded ? (
            <div>
              <h2 className="font-semibold">기회 레이더</h2>
              <p className="mt-1 text-sm text-text-secondary">{radarSummary}</p>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <div className="info-chip">{universeBadgeLabel}</div>
            <Link href="/lab" className="rounded-full border border-border/70 bg-surface/70 px-3 py-1 text-xs text-text-secondary transition-colors hover:border-accent/40 hover:text-text">
              유사 셋업 검증 보기
            </Link>
          </div>
          <div className="ui-panel-muted text-sm leading-6 text-text-secondary">
            {usingFallbackUniverse
              ? data.universe_note || "실시간 유니버스 연결이 제한돼 기본 종목군으로 먼저 추천하고 있습니다."
              : usingKrxListingUniverse || usingTop200Universe
                ? listingUniverseNote
                : liveUniverseBadge}
          </div>
          <div className="workspace-metric-grid">
            <div className="rounded-2xl border border-border/70 bg-surface/70 px-3 py-3">
              <div className="text-[11px] text-text-secondary">{universeLabel}</div>
              <div className="mt-2 text-xl font-semibold text-text">{data.universe_size}</div>
              <div className="mt-1 text-[11px] text-text-secondary">오늘 레이더 기준 종목군</div>
            </div>
            <div className="rounded-2xl border border-border/70 bg-surface/70 px-3 py-3">
              <div className="text-[11px] text-text-secondary">1차 스캔</div>
              <div className="mt-2 text-xl font-semibold text-text">{data.total_scanned}</div>
              <div className="mt-1 text-[11px] text-text-secondary">대표 후보 정렬 기준</div>
            </div>
            <div className="rounded-2xl border border-border/70 bg-accent/10 px-3 py-3">
              <div className="text-[11px] text-text-secondary">시세 확보</div>
              <div className="mt-2 text-xl font-semibold text-accent">{quoteAvailableCount}</div>
              <div className="mt-1 text-[11px] text-text-secondary">정밀 계산 가능 종목</div>
            </div>
            <div className="rounded-2xl border border-border/70 bg-positive/10 px-3 py-3">
              <div className="text-[11px] text-text-secondary">표시 후보</div>
              <div className="mt-2 text-xl font-semibold text-positive">{visibleCandidateCount}</div>
              <div className="mt-1 text-[11px] text-text-secondary">상위 보드 우선 표시</div>
            </div>
          </div>
          <PublicAuditStrip meta={data} />
          {operationalFallbackNote ? (
            <div className="rounded-2xl border border-border/70 bg-surface/55 px-4 py-3 text-sm text-text-secondary">
              {operationalFallbackNote}
            </div>
          ) : null}
          {quoteCoverageNote ? (
            <p className="text-xs text-text-secondary">{quoteCoverageNote}</p>
          ) : null}
        </div>

        {hasItems ? (
          <div className="space-y-3">
            {items.map((item) => (
              <Link
                key={item.ticker}
                href={`/stock/${encodeURIComponent(item.ticker)}`}
                className="block rounded-[22px] border border-border/80 bg-surface/65 px-4 py-4 transition-colors hover:border-accent/45"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-text-secondary">#{item.rank}</span>
                      <span className="truncate font-semibold text-text">{item.name}</span>
                      <span className="text-xs text-text-secondary">{item.ticker}</span>
                    </div>
                    <div className="mt-1 truncate text-xs text-text-secondary">{item.sector}</div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-lg font-bold">{item.opportunity_score.toFixed(1)}</div>
                    <div className="text-[11px] text-text-secondary">{opportunityScoreLabel(data, item.setup_label)}</div>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                  <span className={`rounded-full px-2 py-1 font-semibold uppercase tracking-wide ${actionTone(item.action)}`}>
                    {actionLabel(item.action)}
                  </span>
                  <span className={`rounded-full px-2 py-1 ${executionBiasTone(item.execution_bias)}`}>
                    {executionBiasLabel(item.execution_bias)}
                  </span>
                  <span className="rounded-full bg-border/35 px-2 py-1 text-text-secondary">{item.setup_label}</span>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
                    <div className="text-[11px] text-text-secondary">현재가</div>
                    <div className="mt-1 font-semibold">{formatPrice(item.current_price, item.country_code)}</div>
                    <div className={`text-[11px] ${changeColor(item.change_pct)}`}>{formatPct(item.change_pct)}</div>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
                    <div className="text-[11px] text-text-secondary">20거래일 상승 확률</div>
                    <div className="mt-1 font-semibold">{item.up_probability.toFixed(1)}%</div>
                    <div className="text-[11px] text-text-secondary">신뢰도 {item.confidence.toFixed(0)}</div>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
                    <div className="text-[11px] text-text-secondary">20거래일 예상 수익률</div>
                    <div className={`mt-1 font-semibold ${changeColor(item.predicted_return_pct)}`}>
                      {formatPct(item.predicted_return_pct)}
                    </div>
                    <div className="text-[11px] text-text-secondary">손익비 {item.risk_reward_estimate.toFixed(2)}</div>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-surface/70 px-3 py-2">
                    <div className="text-[11px] text-text-secondary">진입 구간</div>
                    <div className="mt-1 font-semibold">{priceRange(item.entry_low, item.entry_high, item.country_code)}</div>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-text-secondary">
                  {item.calibrated_probability_20d != null ? (
                    <span className="rounded-full border border-border/70 bg-surface/70 px-2 py-1">
                      보정 확률 {item.calibrated_probability_20d.toFixed(1)}%
                    </span>
                  ) : null}
                  {item.probability_edge_20d != null ? (
                    <span className="rounded-full border border-border/70 bg-surface/70 px-2 py-1">
                      확률 격차 {item.probability_edge_20d.toFixed(1)}pt
                    </span>
                  ) : null}
                  {item.analog_support_20d != null ? (
                    <span className="rounded-full border border-border/70 bg-surface/70 px-2 py-1">
                      유사 셋업 {item.analog_support_20d.toFixed(0)}
                    </span>
                  ) : null}
                  {item.data_quality_support_20d != null ? (
                    <span className="rounded-full border border-border/70 bg-surface/70 px-2 py-1">
                      데이터 품질 {item.data_quality_support_20d.toFixed(0)}
                    </span>
                  ) : null}
                </div>

                <div className="mt-3 text-sm leading-6 text-text-secondary line-clamp-2">
                  {item.thesis[0] || "핵심 메모가 아직 없습니다."}
                </div>

                {item.risk_flags.find((flag) => !isOperationalFallbackCopy(flag)) ? (
                  <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-600">
                    {item.risk_flags.find((flag) => !isOperationalFallbackCopy(flag))}
                  </div>
                ) : null}
              </Link>
            ))}
          </div>
        ) : (
          <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-5 text-sm text-text-secondary">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">후보 준비 중</div>
            <div className="mt-2 leading-6">{emptyMessage}</div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={cn("min-w-0", embedded ? "" : "card")}>
      <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="font-semibold">기회 레이더</h2>
          <p className="mt-1 text-sm text-text-secondary">{radarSummary}</p>
          {quoteCoverageNote ? (
            <p className="mt-2 text-xs text-text-secondary">{quoteCoverageNote}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <div className="info-chip">{universeBadgeLabel}</div>
            <Link href="/lab" className="rounded-full border border-border/70 bg-surface/70 px-3 py-1 text-xs text-text-secondary transition-colors hover:border-accent/40 hover:text-text">
              유사 셋업 검증 보기
            </Link>
          </div>
          <div className="ui-panel-muted mt-3 text-sm leading-6 text-text-secondary">
            {usingFallbackUniverse
              ? data.universe_note || "실시간 유니버스 연결이 제한돼 기본 종목군으로 먼저 추천하고 있습니다."
              : usingKrxListingUniverse || usingTop200Universe
                ? listingUniverseNote
                : liveUniverseBadge}
          </div>
        </div>
        <div className="grid shrink-0 grid-cols-2 gap-2 text-center sm:grid-cols-4">
          <div className="rounded-lg bg-border/40 px-3 py-2">
            <div className="text-[11px] text-text-secondary">{universeLabel}</div>
            <div className="font-bold">{data.universe_size}</div>
          </div>
          <div className="rounded-lg bg-border/40 px-3 py-2">
            <div className="text-[11px] text-text-secondary">1차 스캔</div>
            <div className="font-bold">{data.total_scanned}</div>
          </div>
          <div className="rounded-lg bg-accent/10 px-3 py-2">
            <div className="text-[11px] text-text-secondary">시세 확보</div>
            <div className="font-bold text-accent">{quoteAvailableCount}</div>
          </div>
          <div className="rounded-lg bg-positive/10 px-3 py-2">
            <div className="text-[11px] text-text-secondary">표시 후보</div>
            <div className="font-bold text-positive">{visibleCandidateCount}</div>
          </div>
        </div>
      </div>
      <PublicAuditStrip meta={data} className="mb-4" />
      {operationalFallbackNote ? (
        <div className="mb-4 rounded-2xl border border-border/70 bg-surface/55 px-4 py-3 text-sm text-text-secondary">
          {operationalFallbackNote}
        </div>
      ) : null}

      {hasItems ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {items.map((item) => (
            <Link
              key={item.ticker}
              href={`/stock/${encodeURIComponent(item.ticker)}`}
              className="rounded-xl border border-border p-4 transition-colors hover:border-accent/50"
            >
              <div className="mb-3 flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-text-secondary">#{item.rank}</span>
                    <span className="font-semibold">{item.name}</span>
                    <span className="text-xs text-text-secondary">{item.ticker}</span>
                  </div>
                  <div className="mt-1 text-xs text-text-secondary">{item.sector}</div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold">{item.opportunity_score.toFixed(1)}</div>
                  <div className="text-[11px] text-text-secondary">{opportunityScoreLabel(data, item.setup_label)}</div>
                </div>
              </div>

              <div className="mb-3 flex flex-wrap gap-2 text-[11px]">
                <span className={`rounded-full px-2 py-1 font-semibold uppercase tracking-wide ${actionTone(item.action)}`}>
                  {actionLabel(item.action)}
                </span>
                <span className="rounded-full bg-border/40 px-2 py-1 text-text-secondary">{item.setup_label}</span>
                <span className="rounded-full bg-border/40 px-2 py-1 text-text-secondary">{item.regime_tailwind}</span>
                <span className={`rounded-full px-2 py-1 ${executionBiasTone(item.execution_bias)}`}>
                  {executionBiasLabel(item.execution_bias)}
                </span>
              </div>

              <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
                <div>
                  <div className="text-[11px] text-text-secondary">현재가</div>
                  <div className="font-semibold">{formatPrice(item.current_price, item.country_code)}</div>
                  <div className={`text-[11px] ${changeColor(item.change_pct)}`}>{formatPct(item.change_pct)}</div>
                </div>
                <div>
                  <div className="text-[11px] text-text-secondary">20거래일 상승 확률</div>
                  <div className="font-semibold">{item.up_probability.toFixed(1)}%</div>
                  <div className="text-[11px] text-text-secondary">신뢰도 {item.confidence.toFixed(0)}</div>
                </div>
                <div>
                  <div className="text-[11px] text-text-secondary">진입 구간</div>
                  <div className="font-semibold">{priceRange(item.entry_low, item.entry_high, item.country_code)}</div>
                </div>
                <div>
                  <div className="text-[11px] text-text-secondary">20거래일 손익비</div>
                  <div className="font-semibold">{item.risk_reward_estimate.toFixed(2)}</div>
                  <div className={`text-[11px] ${changeColor(item.predicted_return_pct)}`}>{formatPct(item.predicted_return_pct)}</div>
                </div>
              </div>

              <div className="mb-3 flex flex-wrap gap-2 text-[11px] text-text-secondary">
                {item.calibrated_probability_20d != null ? (
                  <span className="rounded-full border border-border/70 bg-surface/70 px-2 py-1">
                    보정 확률 {item.calibrated_probability_20d.toFixed(1)}%
                  </span>
                ) : null}
                {item.probability_edge_20d != null ? (
                  <span className="rounded-full border border-border/70 bg-surface/70 px-2 py-1">
                    확률 격차 {item.probability_edge_20d.toFixed(1)}pt
                  </span>
                ) : null}
                {item.analog_support_20d != null ? (
                  <span className="rounded-full border border-border/70 bg-surface/70 px-2 py-1">
                    유사 셋업 {item.analog_support_20d.toFixed(0)}
                  </span>
                ) : null}
                {item.data_quality_support_20d != null ? (
                  <span className="rounded-full border border-border/70 bg-surface/70 px-2 py-1">
                    데이터 품질 {item.data_quality_support_20d.toFixed(0)}
                  </span>
                ) : null}
              </div>

              {(item.bull_case_price != null || item.bear_case_price != null) ? (
                <div className="mb-3 grid grid-cols-3 gap-2 text-[11px]">
                  <div className="rounded-lg bg-positive/5 px-2 py-2">
                    <div className="text-text-secondary">상방</div>
                    <div className="font-semibold text-positive">
                      {item.bull_case_price != null ? formatPrice(item.bull_case_price, item.country_code) : "미정"}
                    </div>
                    <div className="text-text-secondary">{item.bull_probability?.toFixed(1) ?? "-"}%</div>
                  </div>
                  <div className="rounded-lg bg-border/30 px-2 py-2">
                    <div className="text-text-secondary">기준</div>
                    <div className="font-semibold">
                      {item.base_case_price != null ? formatPrice(item.base_case_price, item.country_code) : "미정"}
                    </div>
                    <div className="text-text-secondary">{item.base_probability?.toFixed(1) ?? "-"}%</div>
                  </div>
                  <div className="rounded-lg bg-negative/5 px-2 py-2">
                    <div className="text-text-secondary">하방</div>
                    <div className="font-semibold text-negative">
                      {item.bear_case_price != null ? formatPrice(item.bear_case_price, item.country_code) : "미정"}
                    </div>
                    <div className="text-text-secondary">{item.bear_probability?.toFixed(1) ?? "-"}%</div>
                  </div>
                </div>
              ) : null}

              <div className="space-y-2 text-sm">
                {item.thesis.map((point) => (
                  <div key={point} className="text-text-secondary">
                    {point}
                  </div>
                ))}
              </div>
              {item.execution_note && !isOperationalFallbackCopy(item.execution_note) ? (
                <div className="mt-3 text-xs text-text-secondary">{item.execution_note}</div>
              ) : null}
              {item.risk_flags.find((flag) => !isOperationalFallbackCopy(flag)) ? (
                <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-600">
                  {item.risk_flags.find((flag) => !isOperationalFallbackCopy(flag))}
                </div>
              ) : null}
            </Link>
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-border/70 bg-surface/45 px-4 py-5 text-sm text-text-secondary">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">후보 준비 중</div>
          <div className="mt-2 leading-6">{emptyMessage}</div>
        </div>
      )}
    </div>
  );
}
