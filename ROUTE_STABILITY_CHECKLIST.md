# Route Stability Checklist

이 문서는 전체 워크스페이스 안정성 패스를 전수 점검할 때 사용하는 실제 체크리스트입니다. README 요약이 아니라, route별 재현과 smoke 기준을 같은 양식으로 고정하기 위한 작업 문서입니다.

## 단계별 종료 기준

### Phase 1. 관측성 / 재현 고정

- 모든 핵심 route와 핵심 API에 동일한 진단 메타를 붙입니다.
- cold / warm 재현 절차를 고정합니다.
- hydration 이후 실패도 별도로 추적합니다.

종료 기준:

- `stock`, `briefing`, `portfolio`에서 실패 1건당 원인 분류가 가능해야 합니다.
- 같은 증상을 로그만으로 `프론트 timeout`, `백엔드 full path 지연`, `외부 소스 차단`, `세션 복구 실패` 중 어디인지 판별할 수 있어야 합니다.

### Phase 2. quick / full 계약 재설계

- `shell / quick / full` 예산을 route별로 분리합니다.
- first usable을 막는 blocking full path를 없앱니다.
- `partial`, `fallback_reason`, `stale served`, `generated_at` 노출 규칙을 통일합니다.

종료 기준:

- `/`, `/stock/[ticker]`, `/radar`에서 cold 진입 시 first usable이 항상 보여야 합니다.
- `full` 경로 실패가 `shell` 또는 `quick` 노출을 막지 않아야 합니다.

### Phase 3. 로그인 후 화면 격리

- 세션 복구 실패와 패널 데이터 실패를 분리합니다.
- 패널 단위 degrade를 기본값으로 합니다.

종료 기준:

- `/portfolio`, `/watchlist`, `/settings`에서 한 패널 실패가 전체 화면 실패로 번지지 않아야 합니다.
- 로그인 복구 실패와 데이터 로드 실패가 서로 다른 안내로 구분되어야 합니다.

### Phase 4. 회귀 자동화

- API smoke + browser smoke를 배포 게이트로 묶습니다.
- hydration blank/error-only를 재발 조건으로 차단합니다.

종료 기준:

- 새 배포에서 hydration blank/error-only가 재발하면 검증 단계에서 실패해야 합니다.

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

정확도보다 먼저 보는 지표는 아래로 고정합니다.

- `blank screen rate`
- `error-only screen rate`
- `first usable content p50 / p95`
- `hydration failure rate`
- `fallback served rate`
- `stale served rate`
- `first-request cold failure rate`
- `login session recovery failure rate`

## 우선 점검 route

### `/`

- Auth required: 아니오
- SSR data: countries, market indicators, briefing, heatmap, movers, radar, country report
- Hydration fetch: briefing, heatmap, movers, radar, country report 재호출
- Required visible data: `대시보드`, 핵심 수치 또는 stale shell
- Optional upgraded data: 최신 브리핑, 레이더 요약, 뉴스
- External dependencies: Render backend, Naver, Yahoo/FMP, OpenAI summary
- Timeout budgets: shell 2~4s, briefing/summary는 partial 허용
- Fallback policy: home shell 유지, briefing은 stale summary로 degrade
- Retry policy: hydration에서 개별 패널만 재시도
- Known failure modes: briefing timeout, country report slow path, hydration 후 timeout 배너
- Smoke coverage: HTML smoke + browser smoke
- Success criteria: 홈 전체가 blank/error-only로 무너지지 않음

### `/stock/[ticker]`

- Auth required: 아니오
- SSR data: quick snapshot, 기본 판단 요약
- Hydration fetch: 보조 차트, prefer_full detail
- Required visible data: 종목명, 현재가 또는 quick partial, 판단 요약
- Optional upgraded data: full detail, 리포트 보강, 차트
- External dependencies: Yahoo, Naver, OpenAI summary, archive save
- Timeout budgets: shell 즉시, quick 8~12s, full은 bounded upgrade
- Fallback policy: cached full -> cached quick -> fresh quick -> bounded full
- Retry policy: partial일 때만 background upgrade
- Known failure modes: full timeout이 quick 표시를 막는 구조, background refresh가 backend를 흔드는 구조
- Smoke coverage: API smoke + browser smoke
- Success criteria: full 실패가 first usable을 막지 않음

### `/radar`

- Auth required: 아니오
- SSR data: cached/quick opportunities
- Hydration fetch: fresh quick 또는 upgraded snapshot
- Required visible data: `기회 레이더`, first usable 후보 또는 stale usable snapshot
- Optional upgraded data: 최신 후보 board
- External dependencies: KR quote sources, yfinance/Naver, Render warm cache
- Timeout budgets: shell 4s 내외, quick 우선
- Fallback policy: stale usable snapshot 우선, placeholder는 마지막 수단
- Retry policy: 사용자 재시도는 fresh quick 재시도
- Known failure modes: quick timeout, placeholder 고정, stale snapshot 미재사용
- Smoke coverage: API smoke + browser smoke
- Success criteria: placeholder가 first screen 기본값이 되지 않음

### `/portfolio`

- Auth required: 예
- SSR data: 로그인 전 preview, 로그인 후 shell
- Hydration fetch: profile, holdings, recommendation, event radar
- Required visible data: `포트폴리오`, 세션 상태 또는 preview
- Optional upgraded data: 추천, event radar, 최적 포트폴리오
- External dependencies: Supabase session, portfolio APIs
- Timeout budgets: 세션 복구와 데이터 패널 분리
- Fallback policy: 패널 단위 degrade
- Retry policy: 패널별 재시도
- Known failure modes: 세션 복구 실패가 전체 화면 실패처럼 보임, recommendation 한 패널 실패가 workspace 전체를 무너뜨림
- Smoke coverage: browser smoke
- Success criteria: 한 패널 실패가 전체 화면 실패로 번지지 않음

### `/watchlist`

- Auth required: 예
- SSR data: 로그인 전 preview
- Hydration fetch: watchlist items
- Required visible data: `관심종목`
- Optional upgraded data: 실 watchlist 목록
- External dependencies: Supabase session, watchlist API
- Timeout budgets: preview 즉시, account data는 hydration 이후
- Fallback policy: 목록 패널 degrade
- Retry policy: 목록 패널만 재시도
- Known failure modes: auth loading만 먼저 보임, empty와 failure 구분 불가
- Smoke coverage: browser smoke
- Success criteria: 로그인/비로그인 모두 first usable 보장

### `/settings`

- Auth required: 예
- SSR data: 로그인 유도 shell
- Hydration fetch: profile, email, password, session, diagnostics
- Required visible data: `설정 및 시스템` 또는 로그인 유도
- Optional upgraded data: 시스템 진단, 운영 상태
- External dependencies: Supabase, backend diagnostics
- Timeout budgets: 세션 복구와 diagnostics 분리
- Fallback policy: 패널 단위 degrade
- Retry policy: 패널별 재시도
- Known failure modes: profile 저장 실패가 diagnostics까지 같이 무너뜨림
- Smoke coverage: browser smoke
- Success criteria: 세션 복구 실패와 패널 실패가 구분됨
