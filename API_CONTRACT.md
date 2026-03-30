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

`prediction_records`는 새 SQL 컬럼을 추가하지 않고 기존 `calibration_json`을 확장합니다. top-level calibration 필드는 유지하고, 아래 nested block이 추가될 수 있습니다.

- `fusion_features`
  - `prior_fused_score`, `fundamental_score`, `macro_score`, `event_sentiment`, `event_surprise`, `event_uncertainty`, `flow_score`, `coverage_naver`, `coverage_opendart`, `regime_spread`
- `graph_context`
  - `used`, `coverage`, `peer_count`, `peer_momentum_5d`, `peer_momentum_20d`, `peer_dispersion`, `sector_relative_strength`, `correlation_support`, `news_relation_support`, `graph_context_score`
- `fusion_metadata`
  - `method`, `profile_bucket`, `profile_sample_count`, `blend_weight`, `profile_fitted_at`

old/new record가 섞여 있어도 집계 API와 연구실 UI는 이를 정상적으로 읽어야 합니다.

`/api/market/opportunities/{code}`의 현재 우선순위:

1. full radar response
2. quick radar response + `partial: true` + `fallback_reason=opportunity_quick_response`
3. cached quick response reuse + `fallback_reason=opportunity_cached_quick_response`
4. placeholder partial response + `fallback_reason=opportunity_placeholder_response`

즉 이 경로는 가능한 한 hard `504`보다 `200 + partial`을 먼저 선택합니다. 또한 홈과 `/radar`는 같은 KR 공개 snapshot을 공유할 수 있도록 `snapshot_id`, `fallback_tier`, `generated_at`를 함께 전달합니다.

`/api/archive/research` 공개 목록 계약:

- `summary_plain`이 있으면 공개 카드와 목록은 이 필드만 렌더합니다.
- `summary` HTML 원문은 상세 보기나 내부 처리에서만 사용합니다.

## 인증 관련 계약

### 공개 계정 API

- `POST /api/account/signup/validate`
- `GET /api/account/username-availability`

특징:

- 로그인 전 호출 가능
- 짧은 rate limit 유지
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

용도:

- 배포 상태
- startup task 진행 상태
- 시스템 진단

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
  - `public_summary`
    - 공개 판단 요약 전용 블록
    - UI는 `근거 -> 반대 근거 -> 지금 바로 사지 않는 이유 -> 무효화 조건 -> 데이터 품질 / 신뢰 메모` 순서로 읽습니다.
  - `generated_at`, `partial`, `fallback_reason`
    - freshness / fallback audit 메타
  - `fallback_reason=stock_cached_detail`
    - 상세 계산이 timeout 또는 조합 오류로 끝나지 않을 때 최근 저장 detail snapshot을 먼저 보여줍니다.
  - `analysis_summary`, `buy_sell_guide`
    - 상세 분석과 실행 가이드 전용
    - 목표가/가격대/valuation 설명은 이 상세 레이어에만 남깁니다.
- `GET /api/stock/{ticker}/chart`
- `GET /api/stock/{ticker}/technical-summary`
- `GET /api/stock/{ticker}/pivot-points`
- `GET /api/stock/{ticker}/forecast-delta`
- `GET /api/search`
- `GET /api/ticker/resolve`

### 포트폴리오 / 관심종목

- `GET /api/watchlist`
- `POST /api/watchlist`
- `DELETE /api/watchlist/{ticker}`
- `GET /api/portfolio`
- `GET /api/portfolio/profile`
- `PATCH /api/portfolio/profile`
- `GET /api/portfolio/holdings`
- `POST /api/portfolio/holdings`
- `DELETE /api/portfolio/holdings/{ticker}`
- `GET /api/portfolio/ideal`
- `GET /api/portfolio/event-radar`
- `GET /api/portfolio/recommendations/conditional`
- `GET /api/portfolio/recommendations/optimal`

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
  - `recent_records[]`는 `fusion_method`, `fusion_blend_weight`, `graph_context_used`, `graph_coverage`를 optional로 가질 수 있습니다.
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
