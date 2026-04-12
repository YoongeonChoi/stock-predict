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

const PARTIAL_REASON_CHIPS: Record<string, PublicAuditChip> = {
  briefing_partial_snapshot: { label: "요약 스냅샷", tone: "info" },
  country_report_startup_seed: { label: "준비 스냅샷", tone: "info" },
  country_report_startup_guard: { label: "초기 스냅샷", tone: "info" },
  heatmap_startup_guard: { label: "초기 스냅샷", tone: "info" },
  opportunity_startup_guard: { label: "초기 스냅샷", tone: "info" },
  country_report_memory_guard: { label: "보호 스냅샷", tone: "neutral" },
  heatmap_memory_guard: { label: "보호 스냅샷", tone: "neutral" },
  opportunity_memory_guard: { label: "보호 스냅샷", tone: "neutral" },
  live_snapshot_timeout: { label: "대표 스냅샷", tone: "info" },
  opportunity_quick_fallback: { label: "빠른 스냅샷", tone: "info" },
  opportunity_quick_response: { label: "빠른 스냅샷", tone: "info" },
  opportunity_cached_quick_response: { label: "직전 스냅샷", tone: "info" },
  cached_snapshot: { label: "기본 스냅샷", tone: "info" },
  kr_safe_shell_warming: { label: "기본 스냅샷", tone: "info" },
  calendar_refresh_pending: { label: "동기화 진행 중", tone: "info" },
  calendar_live_partial_data: { label: "실시간 일정 보강 중", tone: "info" },
  calendar_startup_warming: { label: "월간 스냅샷", tone: "info" },
  research_sync_pending: { label: "동기화 진행 중", tone: "info" },
  prediction_lab_partial_data: { label: "검증 보강 중", tone: "info" },
  prediction_lab_cache_wait_timeout: { label: "최근 스냅샷", tone: "info" },
  screener_seeded_cache: { label: "기본 스냅샷", tone: "info" },
  kr_representative_snapshot_warming: { label: "대표 스냅샷", tone: "info" },
  stock_cached_detail: { label: "저장 스냅샷", tone: "info" },
  stock_minimal_shell: { label: "기본 상세", tone: "neutral" },
  stock_quick_detail: { label: "빠른 상세", tone: "info" },
};

const FALLBACK_REASON_LABELS: Record<string, string> = {
  briefing_partial_snapshot: "브리핑 요약 스냅샷",
  briefing_timeout: "브리핑 계산 지연",
  public_briefing_timeout: "브리핑 계산 지연",
  country_report_memory_guard: "시장 요약 보호 스냅샷",
  country_report_startup_seed: "시장 요약 준비 스냅샷",
  country_report_startup_guard: "시장 요약 초기 스냅샷",
  country_report_timeout: "시장 요약 지연",
  heatmap_memory_guard: "히트맵 보호 스냅샷",
  heatmap_startup_guard: "히트맵 초기 스냅샷",
  heatmap_timeout: "히트맵 계산 지연",
  live_snapshot_timeout: "대표 시세 스냅샷",
  movers_timeout: "상위 집계 지연",
  radar_timeout: "레이더 계산 지연",
  opportunity_memory_guard: "레이더 보호 스냅샷",
  opportunity_startup_guard: "레이더 초기 스냅샷",
  opportunity_quick_fallback: "대표 후보 기준 빠른 응답",
  opportunity_quick_response: "대표 후보 기준 빠른 응답",
  opportunity_cached_quick_response: "직전 후보 스냅샷",
  opportunity_placeholder_response: "사용 가능 후보 미확보",
  screener_timeout: "스크리너 계산 지연",
  screener_seeded_cache: "전일 종가 기준 기본 캐시",
  kr_safe_shell_warming: "기본 스크리너 스냅샷",
  kr_representative_snapshot_warming: "대표 종목 스냅샷 기준",
  cached_snapshot: "기본 캐시 결과",
  calendar_refresh_pending: "일정 동기화 중",
  calendar_startup_warming: "월간 일정 스냅샷",
  calendar_live_partial_data: "일부 실제 일정 확인 중",
  calendar_external_source_unavailable: "외부 일정 공급 제한",
  research_sync_pending: "기관 리포트 동기화 중",
  prediction_lab_partial_data: "검증 세부 집계 일부 지연",
  prediction_lab_cache_wait_timeout: "검증 스냅샷 준비 중",
  prediction_lab_timeout: "검증 집계 지연",
  stock_cached_detail: "최근 저장 상세 스냅샷 기준",
  stock_minimal_shell: "최소 종목 스냅샷 기준",
  stock_quick_detail: "빠른 종목 스냅샷 기준",
};

function normalizeReasonKey(reason?: string | null) {
  const normalized = String(reason || "").trim();
  return normalized || null;
}

function normalizeReason(reason?: string | null) {
  const normalized = normalizeReasonKey(reason);
  if (!normalized) {
    return null;
  }
  return FALLBACK_REASON_LABELS[normalized] || normalized.replace(/_/g, " ");
}

function resolvePartialChip(reason?: string | null): PublicAuditChip {
  const normalized = normalizeReasonKey(reason);
  if (normalized && PARTIAL_REASON_CHIPS[normalized]) {
    return PARTIAL_REASON_CHIPS[normalized];
  }
  return { label: "일부 데이터 지연", tone: "warning" };
}

function resolveReasonTone(meta?: PublicAuditFields | null): PublicAuditChip["tone"] {
  if (!meta?.partial) {
    return "neutral";
  }
  const normalized = normalizeReasonKey(meta?.fallback_reason);
  if (normalized && PARTIAL_REASON_CHIPS[normalized]) {
    return PARTIAL_REASON_CHIPS[normalized].tone === "warning" ? "warning" : "neutral";
  }
  return "warning";
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
    chips.push(resolvePartialChip(meta?.fallback_reason));
  }
  const reason = normalizeReason(meta?.fallback_reason);
  if (reason) {
    chips.push({ label: reason, tone: resolveReasonTone(meta) });
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
  if (meta?.partial && meta?.fallback_reason === "briefing_partial_snapshot") {
    return "시장 브리핑은 먼저 정리했고, 레이더와 포커스 카드는 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "opportunity_placeholder_response") {
    return "이번 요청에서는 사용 가능한 후보를 만들지 못해 시장 국면만 먼저 보여주고 있습니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "calendar_external_source_unavailable") {
    return "외부 일정 공급 제한으로 이번 달은 월간 핵심 일정부터 먼저 보여주고 있습니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "prediction_lab_partial_data") {
    return "검증 세부 집계 일부가 늦어도 최근 스냅샷과 fusion 상태부터 먼저 보여주고 있습니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "country_report_startup_guard") {
    return "처음 진입에서는 대표 시장 스냅샷을 먼저 정리했고, 정밀 시장 요약은 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "country_report_startup_seed") {
    return "처음 진입에서는 준비된 시장 스냅샷을 먼저 보여주고, 정밀 시장 요약은 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "country_report_memory_guard") {
    return "서버 보호 구간에서는 대표 시장 스냅샷을 먼저 정리하고, 정밀 계산은 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "heatmap_startup_guard") {
    return "처음 진입에서는 대표 종목 기준 히트맵을 먼저 정리했고, 정밀 히트맵은 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "heatmap_memory_guard") {
    return "서버 보호 구간에서는 대표 종목 기준 히트맵을 먼저 정리하고, 정밀 계산은 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "live_snapshot_timeout") {
    return "대표 시세 스냅샷을 먼저 보여주고, 세부 히트맵 계산은 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "opportunity_startup_guard") {
    return "처음 진입에서는 대표 후보 기준 기회 레이더를 먼저 정리했고, 정밀 후보 계산은 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "opportunity_memory_guard") {
    return "서버 보호 구간에서는 대표 후보 기준 기회 레이더를 먼저 정리하고, 정밀 계산은 이어서 보강합니다.";
  }
  if (
    meta?.partial &&
    (meta?.fallback_reason === "opportunity_quick_fallback" ||
      meta?.fallback_reason === "opportunity_quick_response")
  ) {
    return "대표 후보 기준 빠른 레이더를 먼저 정리했고, 정밀 후보 계산은 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "opportunity_cached_quick_response") {
    return "직전 후보 스냅샷을 먼저 보여주고, 최신 후보 계산은 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "screener_seeded_cache") {
    return "기본 스냅샷을 먼저 보여주고, 최신 조건 계산은 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "kr_safe_shell_warming") {
    return "기본 스크리너 스냅샷을 먼저 보여주고, 최신 조건 계산은 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "prediction_lab_cache_wait_timeout") {
    return "최근 검증 스냅샷을 먼저 보여주고, 최신 집계는 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "calendar_startup_warming") {
    return "월간 핵심 일정 스냅샷을 먼저 보여주고, 실제 일정 동기화는 이어서 보강합니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "stock_cached_detail") {
    return "상세 계산이 지연돼 최근 저장 종목 스냅샷을 먼저 보여주고 있습니다.";
  }
  if (meta?.partial && meta?.fallback_reason === "stock_minimal_shell") {
    return "상세 계산을 완료하지 못해 티커와 기본 메타데이터 중심 최소 스냅샷을 먼저 보여주고 있습니다.";
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
