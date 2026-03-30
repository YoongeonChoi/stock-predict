export interface PublicAuditFields {
  snapshot_id?: string | null;
  generated_at?: string | null;
  partial?: boolean | null;
  fallback_reason?: string | null;
  fallback_tier?: "full" | "quick" | "cached_quick" | "placeholder" | null;
}

export interface PublicAuditChip {
  label: string;
  tone: "neutral" | "warning" | "info";
}

const FALLBACK_REASON_LABELS: Record<string, string> = {
  briefing_timeout: "브리핑 계산 지연",
  public_briefing_timeout: "브리핑 계산 지연",
  country_report_timeout: "시장 요약 지연",
  heatmap_timeout: "히트맵 계산 지연",
  movers_timeout: "상위 집계 지연",
  radar_timeout: "레이더 계산 지연",
  opportunity_quick_fallback: "대표 후보 기준 빠른 응답",
  opportunity_quick_response: "대표 후보 기준 빠른 응답",
  opportunity_cached_quick_response: "이전 usable 후보 기준",
  opportunity_placeholder_response: "사용 가능 후보 미확보",
  screener_timeout: "스크리너 계산 지연",
  screener_seeded_cache: "전일 종가 기준 기본 캐시",
  kr_representative_snapshot_warming: "대표 종목 스냅샷 기준",
  cached_snapshot: "기본 캐시 결과",
  calendar_refresh_pending: "일정 동기화 중",
  calendar_live_partial_data: "일부 실제 일정 확인 중",
  calendar_external_source_unavailable: "외부 일정 공급 제한",
  research_sync_pending: "기관 리포트 동기화 중",
  prediction_lab_partial_data: "검증 세부 집계 일부 지연",
  prediction_lab_cache_wait_timeout: "검증 스냅샷 준비 중",
  prediction_lab_timeout: "검증 집계 지연",
  stock_cached_detail: "최근 저장 상세 스냅샷 기준",
  stock_quick_detail: "빠른 종목 스냅샷 기준",
};

function normalizeReason(reason?: string | null) {
  const normalized = String(reason || "").trim();
  if (!normalized) {
    return null;
  }
  return FALLBACK_REASON_LABELS[normalized] || normalized.replace(/_/g, " ");
}

export function formatAuditTimestamp(value?: string | null) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleString("ko-KR");
}

export function buildPublicAuditChips(
  meta?: PublicAuditFields | null,
  options: {
    staleLabel?: string | null;
    includeGeneratedAt?: boolean;
  } = {},
): PublicAuditChip[] {
  const chips: PublicAuditChip[] = [];
  const generated = options.includeGeneratedAt === false ? null : formatAuditTimestamp(meta?.generated_at);
  if (generated) {
    chips.push({ label: `마지막 갱신 ${generated}`, tone: "info" });
  }
  if (meta?.partial) {
    chips.push({ label: "일부 데이터 지연", tone: "warning" });
  }
  const reason = normalizeReason(meta?.fallback_reason);
  if (reason) {
    chips.push({ label: reason, tone: meta?.partial ? "warning" : "neutral" });
  }
  if (options.staleLabel) {
    chips.push({ label: options.staleLabel, tone: "neutral" });
  }
  return chips;
}

export function buildPublicAuditSummary(
  meta?: PublicAuditFields | null,
  options: {
    staleLabel?: string | null;
    defaultSummary?: string;
  } = {},
) {
  if (meta?.partial && meta?.fallback_reason === "opportunity_placeholder_response") {
    return "이번 요청에서는 사용 가능한 후보를 만들지 못해 시장 국면만 먼저 보여주고 있습니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "calendar_external_source_unavailable") {
    return "외부 일정 공급 제한으로 이번 달은 월간 핵심 일정부터 먼저 보여주고 있습니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "prediction_lab_partial_data") {
    return "검증 세부 집계 일부가 늦어도 최근 스냅샷과 fusion 상태부터 먼저 보여주고 있습니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "stock_cached_detail") {
    return "상세 계산이 지연돼 최근 저장 종목 스냅샷을 먼저 보여주고 있습니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "stock_quick_detail") {
    return "정밀 종목 분석을 이어가는 동안 가격 흐름과 기술 신호를 기준으로 빠른 상세 스냅샷을 먼저 보여주고 있습니다.";
  }
  const reason = normalizeReason(meta?.fallback_reason);
  if (meta?.partial && reason) {
    return `일부 데이터가 늦어 ${reason} 기준으로 먼저 보여주고 있습니다.`;
  }
  if (meta?.partial) {
    return "일부 데이터가 늦어 먼저 확보된 결과부터 보여주고 있습니다.";
  }
  if (reason) {
    return `${reason} 기준으로 먼저 정리했습니다.`;
  }
  if (options.staleLabel) {
    return options.staleLabel;
  }
  return options.defaultSummary || null;
}
