# Route Stability Checklist

이 문서는 공개/로그인 화면 전수 점검을 할 때 같은 기준으로 route를 보도록 고정한 내부 체크리스트입니다. README가 제품 입구 문서라면, 이 문서는 “어떤 route가 왜 깨지는지 구조적으로 분류하는 기준”에 가깝습니다.

## 단계별 종료 기준

### Phase 1. 관측성 / 재현 고정

- 모든 핵심 route와 핵심 API에 같은 trace 메타가 있어야 합니다.
- cold / warm 재현 절차가 verify나 스모크에서 다시 실행 가능해야 합니다.
- hydration 후 실패를 SSR 성공과 분리해서 추적할 수 있어야 합니다.

종료 기준:

- `stock`, `briefing`, `portfolio`에서 실패 1건당 원인 분류 가능
- 같은 증상을 `프론트 timeout`, `백엔드 full path 지연`, `외부 소스 차단`, `세션 복구 실패` 중 어디인지 로그만으로 구분 가능

### Phase 2. quick / full 계약 재설계

- `shell / quick / full` timeout과 역할이 분리돼야 합니다.
- `blank`, `error-only first screen`, raw timeout 문구를 없애야 합니다.
- `partial`, `fallback_reason`, `stale` 표시가 audit strip 기준으로 통일돼야 합니다.

종료 기준:

- `/`, `/stock/[ticker]`, `/radar`에서 cold 진입 시 first usable 보장
- `full` 실패가 `shell` 또는 `quick` 표시를 막지 않음

### Phase 3. 로그인 후 화면 격리

- 세션 복구 실패와 패널 데이터 실패를 다른 문제로 다뤄야 합니다.
- 패널 단위 degrade가 가능해야 합니다.

종료 기준:

- `/portfolio`, `/watchlist`, `/settings`에서 한 패널 실패가 전체 화면 실패로 번지지 않음
- 로그인 복구 실패와 데이터 로드 실패가 서로 다른 안내로 구분됨

### Phase 4. 회귀 자동화

- API smoke와 browser smoke가 모두 있어야 합니다.
- hydration blank / error-only 재발은 배포 검증에서 차단돼야 합니다.

종료 기준:

- 새 배포에서 hydration blank / error-only 재발 시 CI/CD 또는 배포 검증에서 차단

## Route 점검 템플릿

모든 route는 아래 양식으로 점검합니다.

- `Route`
- `Auth required`
- `SSR data`
- `Hydration fetch`
- `Required visible data`
- `Optional upgraded data`
- `External dependencies`
- `Timeout budgets`
- `Fallback policy`
- `Retry policy`
- `Known failure modes`
- `Smoke coverage`
- `Success criteria`

## 사용자 체감 장애 지표

정확도 이전에 먼저 보는 지표는 아래와 같습니다.

- `blank screen rate`
- `error-only screen rate`
- `first usable content p50 / p95`
- `hydration failure rate`
- `fallback served rate`
- `stale served rate`
- `first-request cold failure rate`
- `login session recovery failure rate`

## 현재 우선 순위 route

### `/`

- `Auth required`: no
- `SSR data`: countries, indicators, briefing, country report, heatmap, movers, radar summary
- `Hydration fetch`: briefing refresh, country workspace refresh
- `Required visible data`: 시장 요약 shell, 핵심 수치, 최소 1개 이상의 usable 패널
- `Optional upgraded data`: 최신 briefing, richer country report
- `External dependencies`: Yahoo/FMP/Naver/ECOS/KOSIS
- `Timeout budgets`: SSR public fetch 16초 이내, hydration 브리핑 16초
- `Fallback policy`: stale briefing 유지, SSR usable 패널 유지, `partial + fallback_reason`
- `Retry policy`: 패널별 재시도
- `Known failure modes`: briefing first-request cold timeout, country report slow path
- `Smoke coverage`: HTML 200 + forbidden timeout text 금지 + briefing API
- `Success criteria`: 홈 전체가 error-only screen으로 변하지 않고 first usable 유지

### `/stock/[ticker]`

- `Auth required`: no
- `SSR data`: ticker 유효성, quick snapshot, 공개 판단 요약
- `Hydration fetch`: prefer_full detail, chart, technical summary, pivot, forecast delta
- `Required visible data`: 종목명, 현재가, quick 판단 요약, 기본 audit
- `Optional upgraded data`: full analysis summary, richer guide, 보조 통계
- `External dependencies`: Yahoo/FMP/OpenAI/Naver
- `Timeout budgets`: quick 18초, prefer_full 24초, SSR 9초
- `Fallback policy`: `quick -> cached quick -> cached full -> structured error`
- `Retry policy`: quick 먼저 재시도, full upgrade는 화면 유지 상태에서만
- `Known failure modes`: full path timeout, detached background full refresh로 인한 backend instability, cold start
- `Smoke coverage`: stock detail API, stock detail prefer_full API, frontend stock HTML, health-post-stock
- `Success criteria`: uncached 종목이라도 first usable quick snapshot 보장, full 실패가 UI 전체를 막지 않음

### `/radar`

- `Auth required`: no
- `SSR data`: market regime, quick/full opportunities snapshot
- `Hydration fetch`: fresh quick retry, optional full refresh
- `Required visible data`: 최소 하나의 usable snapshot 또는 last usable snapshot + 실패 사유
- `Optional upgraded data`: full detailed candidates
- `External dependencies`: Yahoo/Naver/FMP
- `Timeout budgets`: route full wait 분리, quick 우선
- `Fallback policy`: stale usable snapshot > quick > cached quick > placeholder
- `Retry policy`: placeholder면 fresh quick 우선 재시도
- `Known failure modes`: quick miss + placeholder 고정, cold start sampled quote delay
- `Smoke coverage`: opportunities API, radar HTML forbidden text 금지
- `Success criteria`: placeholder보다 usable snapshot 우선, first screen blank 금지

### `/portfolio`

- `Auth required`: yes, 익명 preview 있음
- `SSR data`: 익명 preview 또는 세션 shell
- `Hydration fetch`: profile, holdings, recommendations, event radar
- `Required visible data`: 익명 preview 또는 로그인 shell
- `Optional upgraded data`: 패널별 실제 계정 데이터
- `External dependencies`: Supabase session, backend portfolio APIs
- `Timeout budgets`: 패널별 분리
- `Fallback policy`: panel isolation, 세션 실패와 데이터 실패 분리
- `Retry policy`: 패널별 재시도
- `Known failure modes`: session recovery delay, holdings panel timeout, recommendation panel failure
- `Smoke coverage`: HTML 200, 401 contract, preview visibility
- `Success criteria`: 한 패널 실패가 전체 페이지 실패로 번지지 않음

### `/watchlist`

- `Auth required`: yes, 익명 preview 있음
- `SSR data`: 익명 preview 또는 세션 shell
- `Hydration fetch`: watchlist API
- `Required visible data`: preview list 또는 로그인 shell
- `Optional upgraded data`: 실제 사용자 관심종목 목록
- `External dependencies`: Supabase session, watchlist API
- `Timeout budgets`: 세션 복구와 API 응답 분리
- `Fallback policy`: preview 유지, 목록 패널만 degrade
- `Retry policy`: 목록 패널 재시도
- `Known failure modes`: authLoading skeleton이 first paint를 덮음, 401 복구 실패
- `Smoke coverage`: HTML 200, 401 contract
- `Success criteria`: 익명 first paint는 preview로 시작, 로그인 사용자는 세션 실패와 목록 실패를 구분

### `/settings`

- `Auth required`: yes
- `SSR data`: 세션 shell
- `Hydration fetch`: account, diagnostics, session info
- `Required visible data`: 계정 관리 shell, 버전/진단 기본 정보
- `Optional upgraded data`: email/password/session/pending state
- `External dependencies`: Supabase auth, backend account APIs
- `Timeout budgets`: 패널별 분리
- `Fallback policy`: panel isolation
- `Retry policy`: 저장 액션과 조회 액션 분리
- `Known failure modes`: 진단 패널 failure가 전체 설정 화면 붕괴
- `Smoke coverage`: settings HTML, account auth contract
- `Success criteria`: profile/email/password/session/diagnostics 중 하나 실패가 전체 화면 실패로 번지지 않음

## 운영 점검 메모

- cold start 의심 시 같은 route를 `첫 요청 / 직후 두 번째 요청`으로 나눠 측정합니다.
- 공개 route는 가능하면 `200 + partial + fallback_reason`을 우선합니다.
- `prefer_full=true`는 blocking flag가 아니라 upgrade hint입니다.
- hydration 실패가 SSR usable 데이터를 지워서는 안 됩니다.
