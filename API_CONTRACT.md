# API Contract

이 문서는 `Stock Predict`의 현재 API 계약을 사람이든 AI든 빠르게 읽을 수 있도록 정리한 지도입니다.
자동 생성 OpenAPI를 대체하는 문서는 아니지만, 리뷰와 구현 변경에서 가장 자주 확인해야 할 규칙을 담고 있습니다.

## 기본 규칙

- API base path: `/api`
- 백엔드 프레임워크: `FastAPI`
- 런타임 엔트리: `backend/app/main.py`
- 프론트 호출 중심 파일: `frontend/src/lib/api.ts`

## 에러 응답 형식

모든 API 예외는 `backend/app/errors.py`의 중앙 레지스트리를 따릅니다.

기본 형식:

```json
{
  "error_code": "SP-6014",
  "message": "Authentication required",
  "detail": "Sign in and retry the requested operation.",
  "timestamp": "2026-03-28T21:00:00.000000"
}
```

중요 규칙:

- 보호된 API는 인증 없을 때 `401 / SP-6014`
- 존재하지 않는 API는 `404 / SP-6011`
- 관심종목에 없는 종목으로 심화 추적 detail/toggle을 요청하면 `404 / SP-6017`
- 허용되지 않은 HTTP method는 `405 / SP-6012`
- 입력 검증 실패는 `422 / SP-6010`
- 공개 계정 검증 API 과호출은 `429 / SP-6016`

## 공개 집계형 API의 fallback 규칙

일부 공개 집계형 API는 느린 외부 소스 하나 때문에 전체 실패를 내기보다 아래 형태를 우선합니다.

- `200`
- `partial: true`
- `fallback_reason`
- 사용자에게 보여 줄 수 있는 최소 결과

이 원칙은 아래 영역에서 특히 중요합니다.

- `/api/country/{code}/report`
- `/api/country/{code}/heatmap`
- `/api/market/opportunities/{code}`
- `/api/screener`
- `/api/calendar/{code}`
- `/api/archive/research`

리뷰 시 raw `Failed to fetch` 노출이나, 부분 응답이 가능한 경로를 바로 `504`로 바꾸는 수정은 회귀 후보로 봅니다.

### 공개 audit 필드

공개 SSR과 부분 응답 UI는 아래 공통 메타데이터를 우선 사용합니다.

- `generated_at`
- `partial`
- `fallback_reason`

공개 snapshot 일치성 진단이 필요한 응답은 아래 내부 메타데이터를 함께 가질 수 있습니다.

- `snapshot_id`
- `fallback_tier`
- `request_trace`
  - `request_phase: shell | quick | full`
  - `cache_state: memory_hit | sqlite_hit | miss`
  - `cold_start_suspected`
  - `upstream_source`
  - `elapsed_ms`
  - `timeout_budget_ms`
  - `fallback_reason`
  - `served_state: fresh | partial | stale | degraded`

프론트 표시 규칙:

- 정상: `마지막 갱신 시각`
- partial: `일부 데이터 지연` + `fallback_reason` 한국어 매핑
- stale but usable: `전일 기준`, `기관 동기화 중` 같은 보조 문구

가능한 경우 public page는 raw 브라우저 fetch 에러보다 `200 + partial + fallback_reason`을 먼저 사용자에게 보여 줍니다.

### 공개 숫자 서술 규칙

공개 숫자와 공개 서술은 같은 필드에 섞지 않습니다.

- `macro_claims`
  - 구조화된 숫자 근거
  - 권장 필드: `source`, `published_at`, `metric`, `value`, `unit`, `direction`, `confidence`
- `market_summary`, `summary`
  - 공개 정성 서술
  - 숫자, 퍼센트, 날짜, 목표가, 밸류에이션 숫자를 직접 넣지 않습니다.
- `public_summary`
  - 공개 종목 판단 요약
  - 필드: `summary`, `evidence_for`, `evidence_against`, `why_not_buy_now`, `thesis_breakers`, `data_quality`, `confidence_note`
  - `fair value`, `buy/sell zone`, `analyst target`, 목표가, 가격대 직접 제시는 허용하지 않습니다.

검증 규칙:

- 공개 UI의 숫자 문장은 구조화 claim 필드 기반으로만 렌더합니다.
- 자유 서술에 숫자가 섞이면 프론트 정규식이 아니라 백엔드 validation 단계에서 공개 서술로 승격하지 않습니다.
- 구조화 claim이 비어 있더라도 공개 요약은 숫자 없는 정성 서술로만 남겨야 합니다.

### forecast horizon 확장 메타데이터

분포형 forecast의 horizon 단위 응답은 기존 `q10 / q25 / q50 / q75 / q90`, `p_up / p_flat / p_down`, confidence 흐름을 유지한 채 아래 optional 메타데이터를 함께 가질 수 있습니다.

- `fusion_method`
- `fusion_profile_sample_count`
- `fusion_blend_weight`
- `graph_context_used`
- `graph_context_score`
- `graph_coverage`
- `fusion_profile_fitted_at`

이 필드는 backward-compatible optional 필드이며, 값이 없으면 프론트는 기존 prior backbone 결과만으로 계속 동작해야 합니다.

### calibration_json 내부 확장 규칙

`prediction_records`는 top-level calibration 필드를 유지하면서 nested block을 확장합니다. v2.66.0의 5거래일 실행안 검증부터는 실제 target-date OHLC와 별개로 실행 기간 고저 범위와 평가 결과도 저장할 수 있습니다.

- `fusion_features`
  - `prior_fused_score`, `fundamental_score`, `macro_score`, `event_sentiment`, `event_surprise`, `event_uncertainty`, `flow_score`, `coverage_naver`, `coverage_opendart`, `regime_spread`
- `graph_context`
  - `used`, `coverage`, `peer_count`, `peer_momentum_5d`, `peer_momentum_20d`, `peer_dispersion`, `sector_relative_strength`, `correlation_support`, `news_relation_support`, `graph_context_score`
- `fusion_metadata`
  - `method`, `profile_bucket`, `profile_sample_count`, `blend_weight`, `profile_fitted_at`
- `weekly_trade_plan`
  - `distributional_5d` row에 optional로 저장되는 5거래일 실행안입니다.
  - `action`, `buy_price`, `buy_zone_low/high`, `sell_price`, `sell_zone_low/high`, `stop_loss`, `p_up`, `confidence`, `risk_reward_estimate`, `evidence_keys`, `source_statuses`를 포함할 수 있습니다.

### prediction_records 실행 평가 확장

- `actual_window_low`, `actual_window_high`
  - `reference_date` 다음 거래일부터 `target_date`까지의 실제 저가/고가 범위입니다.
- `execution_json`
  - `weekly_trade_plan`이 있는 5D row에서 target date 이후 채워지는 실행 평가 결과입니다.
  - 주요 필드: `buy_zone_touched`, `sell_zone_touched`, `stop_loss_touched`, `outcome`, `actual_return_pct`, `window_low`, `window_high`
  - 일중 선후관계는 확정하지 않고, 5거래일 범위 안에서 접촉 여부만 평가합니다.

old/new record가 섞여 있어도 집계 API와 연구실 UI는 이를 정상적으로 읽어야 합니다.

`/api/market/opportunities/{code}`의 현재 우선순위:

1. full radar response
2. quick radar response + `partial: true` + `fallback_reason=opportunity_quick_response`
3. cached quick response reuse + `fallback_reason=opportunity_cached_quick_response`
4. placeholder partial response + `fallback_reason=opportunity_placeholder_response`

즉 이 경로는 가능한 한 hard `504`보다 `200 + partial`을 먼저 선택합니다. 또한 홈과 `/radar`는 같은 KR 공개 snapshot을 공유할 수 있도록 `snapshot_id`, `fallback_tier`, `generated_at`를 함께 전달합니다.

v2.65.0부터 `opportunities[]`와 `next_day_focus`는 다음 품질 필드를 optional로 가질 수 있습니다. 오래된 캐시나 fallback 응답에는 없을 수 있으므로 프론트는 `null`/미표시로 처리합니다.

- `quality_score`
- `chase_risk_score`
- `volume_quality_score`
- `flow_accumulation_score`
- `sector_catalyst_score`
- `score_breakdown`
- `flow_data_status`: `eod_pending`, `fresh_eod`, `flow_unavailable` 등
- `quality_data_status`: `complete`, `partial_flow`, `quote_screen` 등
- `entry_style`
- `recommended_entry_condition`

기회 레이더 1차 후보 정렬은 당일 `change_pct` 자체가 아니라 섹터 강도, 유동성, 거래량 품질, 추격 위험 감점을 조합한 quick score를 사용합니다. KRX 투자자별 수급은 장중 실시간 데이터가 아니라 EOD 보조 신호입니다. 18시 전에는 `eod_pending`으로 표시하고, 확보 실패 시에도 `200 + partial` 후보를 유지합니다.

v2.66.0부터 `opportunities[]`는 optional `weekly_trade_plan`을 가질 수 있습니다. 상세 계산이 끝난 후보에만 붙으며, 오래된 캐시·quote-only·placeholder 응답에는 없을 수 있습니다. 프론트는 필드가 없으면 기존 20거래일 후보 카드만 표시하고, 있으면 5거래일 매수·매도 요약을 보조로 표시합니다.

`/api/archive/research` 공개 목록 계약:

- `summary_plain`이 있으면 공개 카드와 목록은 이 필드만 렌더합니다.
- `summary` HTML 원문은 상세 보기나 내부 처리에서만 사용합니다.

## 인증 관련 계약

### 공개 계정 API

- `POST /api/account/signup/validate`
- `GET /api/account/username-availability`

특징:

- 로그인 전 호출 가능
- 짧은 rate limit 유지: 아이디 중복 확인은 클라이언트별 60초 60회, 회원가입 사전 검증은 60초 20회
- 초과 시 `429 / SP-6016`과 `Retry-After` 기준 재시도 안내를 반환
- 회원가입 직전 서버 사전 검증에 사용

### 보호된 계정 API

- `GET /api/account/me`
- `PATCH /api/account/me`
- `DELETE /api/account/me`

프론트 계약:

- `401 / SP-6014`가 오면 페이지마다 따로 처리하지 말고 `AuthProvider`의 세션 재검증 흐름을 우선 사용

## 주요 API 그룹

### 상태 / 시스템

- `GET /api/health`
- `GET /api/diagnostics`
- `POST /api/diagnostics/event`

용도:

- 배포 상태
- startup task 진행 상태
- 시스템 진단
- route 안정성 요약, first usable 지표, hydration/session recovery 실패 요약

### 계정 / 인증

- `GET /api/account/me`
- `PATCH /api/account/me`
- `DELETE /api/account/me`
- `POST /api/account/signup/validate`
- `GET /api/account/username-availability`

### 시장 / 국가

- `GET /api/countries`
- `GET /api/country/{code}/report`
- `GET /api/country/{code}/heatmap`
- `GET /api/country/{code}/forecast`
- `GET /api/country/{code}/sector-performance`
- `GET /api/country/{code}/sectors`
- `GET /api/market/indicators`
- `GET /api/market/movers/{code}`
- `GET /api/market/opportunities/{code}`

`GET /api/country/{code}/report` 공개 응답 메모:

- `market_summary`
  - 정성 요약
- `macro_claims`
  - 공개 숫자 근거 배열
- `generated_at`, `partial`, `fallback_reason`
  - freshness / fallback audit 메타

### 섹터 / 종목 / 검색

- `GET /api/country/{code}/sector/{sector_id}/report`
- `GET /api/stock/{ticker}/detail`
  - `weekly_trade_plan`
    - 5거래일 조건부 분포 기반 실행 판단 블록입니다.
    - 주요 필드: `horizon_days=5`, `target_date`, `reference_price`, `action`, `buy_price`, `buy_zone_low/high`, `sell_price`, `sell_zone_low/high`, `stop_loss`, `expected_return_pct`, `expected_excess_return_pct`, `p_up`, `p_flat`, `p_down`, `confidence`, `risk_reward_estimate`, `evidence[]`, `source_freshness[]`, `partial`, `fallback_reason`, `data_quality`
    - 숫자는 canonical `distributional_return_engine.py`의 5거래일 분포와 ATR, 기존 `buy_sell_guide` 교차로 산정합니다. LLM 응답의 가격 숫자는 이 필드에 반영하지 않습니다.
    - v2.66.1부터 quick 응답도 6개월 가격·시장 시계열만으로 5거래일 분포를 먼저 계산할 수 있습니다. 이 경우 `weekly_trade_plan.partial=true`, `fallback_reason=stock_quick_distributional`일 수 있지만 `buy_price`, `sell_price`, `stop_loss`, `p_up/p_flat/p_down`은 가능한 한 채워서 내려보냅니다.
    - v2.66.2부터 Render memory-safe cold start에서 최소 shell을 먼저 반환하더라도, 메모리 압박이 높지 않으면 같은 종목의 quick 분포 warm을 응답 뒤 예약합니다. 이 warm은 full 분석이 아니라 quick snapshot 캐시를 채우는 경로입니다.
    - v2.66.3부터 `stock_memory_guard` shell이 quick cache에 남아 있어도 다음 조회에서 다시 quick 분포 warm을 예약합니다. shell cache는 30초 TTL로 유지되며, warm 성공 후에는 같은 key가 `stock_quick_distributional` 숫자 응답으로 교체됩니다.
    - `evidence[]`에는 가격·분포·시장 국면·수급·뉴스/공시 외에, 매칭된 경우 `official_research`가 포함될 수 있습니다. 이 항목은 `archive/research`의 공식/허용 메타데이터만 사용하며 PDF 본문 무단 수집을 전제로 하지 않습니다.
    - 프론트는 `source_freshness[]`를 최신성 UI로 모두 소비할 수 있어야 하며, 공식 리서치·IB 메타데이터와 PyKRX 수급처럼 사용자의 판단에 직접 영향을 주는 소스는 배열 뒤쪽에 있어도 숨기지 않습니다.
    - quick/shell fallback도 빈 카드가 되지 않도록 `partial=true` 또는 대기 상태를 내려보냅니다.
  - `public_summary`
    - 공개 판단 요약 전용 블록
    - UI는 `근거 -> 반대 근거 -> 지금 바로 사지 않는 이유 -> 무효화 조건 -> 데이터 품질 / 신뢰 메모` 순서로 읽습니다.
  - `generated_at`, `partial`, `fallback_reason`, `fallback_tier`, `request_trace`
    - freshness / fallback audit 메타
  - query `prefer_full=true`
    - partial quick snapshot 뒤에 full detail 업그레이드를 우선 시도할 때 사용하는 힌트입니다.
    - 응답 최상위 `partial=false`라도 `weekly_trade_plan.partial=true`이면 프론트는 한 번 더 full detail 업그레이드를 시도할 수 있습니다.
    - quick snapshot이 이미 있으면 먼저 즉시 서빙하고, full detail은 bounded 예산 안에서만 업그레이드합니다.
    - full detail이 timeout 또는 조합 오류로 끝나지 않으면 quick/cached partial로 안전하게 되돌아갑니다.
  - `fallback_reason=stock_quick_detail`
    - uncached 종목 상세에서 full detail을 기다리기 전에 가격 흐름, 기술 신호, 시장 국면을 기준으로 빠른 stock snapshot을 먼저 반환합니다.
    - stock page는 이 partial을 server-first initial snapshot으로 first HTML에 먼저 실을 수 있어야 합니다.
    - Render memory-safe 운영에서는 quick snapshot 뒤 detached full refresh를 남기지 않고, `prefer_full=true` follow-up request 안에서만 bounded full analyze와 archive save를 수행합니다.
  - `fallback_reason=stock_cached_detail`
    - 상세 계산이 timeout 또는 조합 오류로 끝나지 않을 때 최근 저장 detail snapshot을 먼저 보여줍니다.
  - `analysis_summary`, `buy_sell_guide`
    - 상세 분석과 실행 가이드 전용
    - 목표가/가격대/valuation 설명은 이 상세 레이어에만 남깁니다.
- `GET /api/stock/{ticker}/chart`
- `GET /api/stock/{ticker}/technical-summary`
- `GET /api/stock/{ticker}/pivot-points`
- `GET /api/stock/{ticker}/forecast-delta`
  - 기존 next-day 예측 변화 요약에 더해 optional `weekly_plan` 블록을 반환할 수 있습니다.
  - `weekly_plan.history[]`는 5거래일 실행안의 매수가, 매도가, 손절가, 실제 5거래일 범위, 매수/목표/손절 접촉 여부, `outcome_label`을 포함합니다.
- `GET /api/search`
- `GET /api/ticker/resolve`

### 포트폴리오 / 관심종목

- `GET /api/watchlist`
- `POST /api/watchlist/{ticker}`
- `DELETE /api/watchlist/{ticker}`
- `POST /api/watchlist/{ticker}/tracking`
- `DELETE /api/watchlist/{ticker}/tracking`
- `GET /api/watchlist/{ticker}/tracking-detail`
- `GET /api/portfolio`
- `GET /api/portfolio/profile`
- `PUT /api/portfolio/profile`
- `POST /api/portfolio/holdings`
- `PUT /api/portfolio/holdings/{holding_id}`
- `DELETE /api/portfolio/holdings/{holding_id}`
- `GET /api/portfolio/ideal`
- `GET /api/portfolio/event-radar`
- `GET /api/portfolio/recommendations/conditional`
- `GET /api/portfolio/recommendations/optimal`

`GET /api/watchlist` additive fields:

- `tracking_enabled`
- `tracking_started_at`
- `last_prediction_at`
- `last_outlook_label`
- `last_confidence`

`GET /api/watchlist/{ticker}/tracking-detail` response blocks:

- `watchlist_meta`
- `tracking_state`
- `latest_snapshot`
- `prediction_change_summary`
- `prediction_history`
- `realized_accuracy_summary`
- `current_context_summary`
- `partial`
- `fallback_reason`
- `panel_states`

### 브리핑 / 캘린더 / 아카이브 / 비교 / 스크리너

- `GET /api/briefing/daily`
- `GET /api/market/sessions`
- `GET /api/calendar/{code}`
- `GET /api/archive`
- `GET /api/archive/accuracy/stats`
  - 기존 정확도 요약은 유지하고, 필요 시 learned fusion 상태를 보조 summary 수준으로 함께 실을 수 있습니다.
- `GET /api/archive/research`
- `GET /api/archive/research/status`
- `POST /api/archive/research/refresh`
- `GET /api/archive/{report_id}`
- `GET /api/research/predictions`
  - 현재 Prediction Lab의 canonical API입니다.
  - top-level 확장 필드:
    - `fusion_profiles[]`
    - `graph_context_summary`
    - `fusion_status_summary`
  - `horizon_accuracy[]`는 `current_method`, `fusion_profile_sample_count`, `avg_blend_weight`, `graph_coverage`, `graph_context_used_rate`, `prior_brier_delta`, `fusion_status`를 optional로 가질 수 있습니다.
  - `return_cohorts[]`는 `prediction_type`, `label`, `target_date`, `evaluated_total`, `avg_predicted_return_pct`, `avg_realized_return_pct`, `avg_return_error_pct`, `avg_error_pct`, `confidence_brier_score`를 포함해 목표일별 예상/실현 수익률과 표시 confidence Brier를 대조합니다.
  - `recent_records[]`와 `review_queue[]`는 `fusion_method`, `fusion_blend_weight`, `graph_context_used`, `graph_coverage` 외에도 `confidence_cap`, `confidence_cap_reason`, `empirical_profile_available`, `empirical_sample_count`, `empirical_max_reliability_gap`, `empirical_brier_delta`를 optional로 가질 수 있습니다.
- `GET /api/compare`
- `GET /api/screener`
- `GET /api/export/{fmt}/{report_id}`

## 프론트와 백엔드가 같이 바뀌어야 하는 곳

아래 종류의 변경은 프론트와 백엔드를 반드시 같이 봐야 합니다.

### 응답 필드 변경

- 백엔드 router / service
- `frontend/src/lib/api.ts`
- 해당 페이지 / 패널 컴포넌트

### 계정 검증 규칙 변경

- `frontend/src/lib/account.ts`
- `frontend/src/app/auth/page.tsx`
- `frontend/src/components/AuthProvider.tsx`
- `backend/app/services/account_service.py`
- `backend/app/routers/account.py`
- `backend/app/auth.py`

### 포트폴리오 응답 변경

- `backend/app/services/portfolio_optimizer.py`
- `backend/app/services/portfolio_service.py`
- `backend/app/services/portfolio_recommendation_service.py`
- `backend/app/services/ideal_portfolio_service.py`
- `frontend/src/lib/api.ts`
- 포트폴리오 관련 패널

## 현재 제품에서 중요한 세부 계약

### 1. 회원가입

필수 입력:

- 아이디
- 이메일
- 이름
- 전화번호
- 생년월일
- 비밀번호
- 비밀번호 재확인

아이디 규칙:

- 영문 소문자 시작
- 영문 소문자 / 숫자 / 밑줄
- 4~20자

비밀번호 규칙:

- 10자 이상
- 대문자 포함
- 소문자 포함
- 숫자 포함
- 특수문자 포함
- 재확인 일치

### 2. 보호된 API 인증

- 보호된 API는 익명 호출 시 `401 / SP-6014`
- 공개 저장성 API smoke는 이 계약을 유지해야 함

### 3. 공개 경로 안정성

- 집계형 API는 timeout과 partial fallback을 함께 설계
- Render free 환경에서 cold start를 고려
- 공개 읽기 경로는 server-first fetch와 `revalidate` 캐시를 우선 사용
- 브라우저 인증 호출, 저장성 호출, 계정 설정 호출은 계속 `no-store`를 유지

### 4. 리서치 아카이브 범위

현재 운영 기준 공식 기관 소스:

- 한국 `KDI`, `한국은행`
- 미국 `Federal Reserve`
- 유로존 `ECB`
- 일본 `BOJ`

## 런타임 OpenAPI

앱을 실행한 뒤 FastAPI 기본 스펙으로도 확인할 수 있습니다.

- `GET /openapi.json`
- `GET /docs`

다만 코드 리뷰와 변경 영향 판단은 이 문서와 `frontend/src/lib/api.ts`를 함께 보는 편이 더 빠릅니다.
