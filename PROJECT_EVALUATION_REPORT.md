# Stock Predict Project Evaluation Report

평가일: 2026-05-14 KST  
대상: 현재 로컬 워크트리 `main...origin/main` + 미커밋 변경 포함  
평가 방식: 100점 가중치, 증거 기반 감점, 신규 백테스트 제외

## 1. Executive Summary

현재 프로젝트는 백엔드 서비스 구조, 예측 엔진 backbone, 공개 API fallback, 계정 검증, 회귀 테스트 기반이 상당히 강합니다. 특히 FastAPI 계층과 예측/포트폴리오 엔진은 문서화된 운영 철학과 대체로 맞고, backend-only 검증은 통과했습니다.

하지만 현재 워크트리는 프론트 production build와 TypeScript typecheck가 실패하므로 운영 배포 가능 상태가 아닙니다. `/portfolio`, 시스템 진단, 기회 레이더, API 타입 re-export 주변에서 컴파일 차단 문제가 확인됐고, API 계약 문서 일부도 실제 라우터와 어긋납니다. 따라서 전체 평가는 "사용 가능하나 주요 리스크 존재"보다 한 단계 낮은 운영 신뢰성 부족 구간으로 판정합니다.

**총점: 64 / 100**

| 영역 | 배점 | 점수 | 판정 |
|---|---:|---:|---|
| 제품/UX/디자인 | 14 | 8 | 디자인 기준은 명확하나 빌드 차단으로 렌더 검증 불가 |
| 프론트 기능 완성도 | 14 | 5 | 주요 route 소스는 있으나 build/typecheck 실패 |
| 백엔드/API 설계 | 13 | 9 | 라우터/서비스 구조와 오류 계약은 강함, 문서-구현 drift 있음 |
| 예측/주식 추천 방법론 | 22 | 14 | 분포형 backbone은 우수, LLM 숫자/검증 한계 리스크 |
| 포트폴리오 최적화 | 10 | 8 | canonical optimizer 공유 구조 양호 |
| 데이터/운영 안정성 | 11 | 9 | timeout/cache/fallback 회귀 테스트 강함 |
| 계정/보안/개인정보 | 8 | 7 | 검증 규칙과 세션 복구 양호, 공개 rate limit 완화는 운영 관찰 필요 |
| 테스트/문서/릴리즈 | 8 | 4 | backend 테스트 강함, frontend build/typecheck와 API 문서 drift 감점 |

점수 해석: 60-69 = 운영 신뢰성 부족. 프론트 빌드 차단을 해소하기 전에는 운영 반영을 보류해야 합니다.

## 2. Verification Results

| 검증 | 결과 | 근거 |
|---|---|---|
| `git status --short --branch` | 미커밋 변경 8개 존재 | `backend/app/services/portfolio_optimizer.py`, `public_rate_limit_service.py`, 계정 테스트, home/stock UI 등 |
| `.\venv\Scripts\python.exe .\verify.py` | 실패 | Backend compile/import/unittest 통과 후 frontend build 실패 |
| Backend unittest | 통과 | 416 tests, OK |
| `.\venv\Scripts\python.exe .\verify.py --skip-frontend` | 통과 | backend-only 검증 완료 |
| `cd frontend; npm run test` | 통과 | 6 files, 67 tests passed |
| `cd frontend; npx tsc --noEmit` | 실패 | API 타입, 중복 변수, 누락 변수 등 다수 |
| Rendered browser QA | 미수행 | frontend build/typecheck 실패로 신뢰 가능한 렌더 기준선 없음 |

## 3. Blocking Findings

### P0. 프론트 production build가 실패해 현재 배포 불가

- `frontend/src/components/pages/PortfolioPageClient.tsx:166-183`에서 `eventRadarError`, `conditionalError`, `optimalError` state가 중복 선언됩니다.
- `next build`는 `/portfolio/page.tsx` import trace에서 webpack error로 중단됩니다.
- 이 상태에서는 Vercel 배포, route-level 브라우저 QA, 디자인 검수가 모두 차단됩니다.

### P0. TypeScript 계약이 다수 깨져 있음

`npx tsc --noEmit`에서 다음 오류가 확인됐습니다.

- `frontend/src/lib/api.ts:58-90`: `export type { ... }`로 re-export한 타입을 같은 파일의 generic 타입 인자로 직접 사용해 `TechSummary`, `PivotPoints`, `ArchiveEntry`, `PredictionLabResponse` 등 이름을 찾지 못합니다.
- `frontend/src/lib/api/types.ts:1307`: `RequestTrace` 타입 참조가 있으나 정의/수입이 없습니다.
- `frontend/src/components/SystemStatusCard.tsx:169-173`: 실제 변수는 `routeStabilityRows`인데 JSX는 `routeStability`를 참조합니다.
- `frontend/src/components/OpportunityRadarBoard.tsx:291`: 타입은 `expected_return_pct_20d`를 제공하지만 UI 복사 로직은 `expected_return_pct`를 읽습니다.
- `frontend/src/__tests__/request-state.test.ts:49`: 테스트 호출부가 현재 함수 시그니처와 맞지 않습니다.

### P1. API 계약 문서 일부가 실제 라우터와 불일치

- `API_CONTRACT.md:247-258`은 `POST /api/watchlist`, `PATCH /api/portfolio/profile`, `GET /api/portfolio/holdings`, `DELETE /api/portfolio/holdings/{ticker}`를 적고 있습니다.
- 실제 구현은 `backend/app/routers/watchlist.py:101`의 `POST /api/watchlist/{ticker}`, `backend/app/routers/portfolio.py:78`의 `PUT /api/portfolio/profile`, `portfolio.py:162/184/211`의 holdings create/update/delete by `holding_id`입니다.
- 프론트 `frontend/src/lib/api/portfolio.ts`는 실제 구현과 맞지만, 문서가 오래된 계약을 말합니다.

### P1. LLM 숫자 의존 경로가 남아 있음

- canonical 원칙은 LLM을 숫자 예측기가 아니라 구조화/서술 보조로 제한합니다.
- 하지만 `backend/app/analysis/stock_analyzer.py:909-920`의 `_build_buy_sell`은 LLM 결과의 `fair_value`, `buy_zone_low`, `sell_zone_low` 등을 직접 가격대 산출에 사용합니다.
- 공개 요약은 숫자 서술을 방어하는 구조가 있으나, 상세 실행 가이드에서는 LLM 숫자 입력이 valuation/buy-sell guide에 들어갈 수 있습니다. 투자 품질 관점에서 엄격 감점 대상입니다.

### P1. 프론트 테스트는 현재 빌드 차단을 잡지 못함

- `npm run test`는 67개 통과했지만 `next build`와 `tsc --noEmit`은 실패합니다.
- 이는 프론트 테스트가 route import, type-only export, 시스템 진단, 포트폴리오 client compile을 충분히 덮지 못한다는 뜻입니다.

## 4. Area-by-Area Evaluation

### 제품/UX/디자인: 8 / 14

강점:

- `DESIGN_BIBLE.md`는 작업형 워크스페이스, page thread, 상태 카드, 모바일 규칙을 구체적으로 정의합니다.
- 주요 page client들이 `WorkspaceStateCard`, `PublicAuditStrip`, `ErrorBanner`, `AuthGateCard`를 사용해 loading/partial/empty/error 상태를 통일하려는 구조가 있습니다.
- 한국어 운영형 문구가 전반적으로 유지됩니다.

감점:

- frontend build 실패로 실제 디자인 렌더, 모바일 겹침, state card 시각 QA를 수행할 수 없습니다.
- `frontend/src/app/stock/[ticker]/page.tsx`의 새 metadata 문구는 `AI가 분석한`, `AI 예측 리포트`를 반복해 AGENTS의 AI 과장 카피 금지 원칙과 충돌할 여지가 있습니다.
- `SystemStatusCard.tsx`에는 route stability 블록이 중복/오류 상태로 남아 진단 UI 신뢰도를 떨어뜨립니다.

### 프론트 기능 완성도: 5 / 14

강점:

- App Router 기준 주요 화면은 존재합니다: `/`, `/auth`, `/radar`, `/screener`, `/compare`, `/portfolio`, `/watchlist`, `/calendar`, `/archive`, `/lab`, `/settings`, `/stock/[ticker]`.
- 대시보드, 레이더, 캘린더, 아카이브, 종목 상세는 partial/fallback 메타를 표시하는 흔적이 있습니다.
- 계정/관심종목/포트폴리오는 인증 gate와 client-side timeout을 고려합니다.

감점:

- `/portfolio`가 build를 차단합니다.
- API facade 타입 깨짐 때문에 여러 화면이 TypeScript 기준으로 신뢰 불가합니다.
- `OpportunityRadarBoard`의 복사 기능이 타입상 없는 필드를 읽습니다.
- build가 막혀 route별 실제 동작, 검색/필터/저장/다운로드/browser fallback은 확인하지 못했습니다.

Route별 요약:

| Route | 평가 |
|---|---|
| `/` | SSR timebox와 client retry가 있으나 최근 변경으로 서버 초기 timebox가 모두 1초로 줄어 first usable은 좋아질 수 있어도 빈 패널 가능성이 증가 |
| `/radar` | quick/placeholder partial 구조는 좋음, field mismatch 리스크 존재 |
| `/screener` | audit strip과 timeout 구조 양호, build 성공 후 실제 필터 검증 필요 |
| `/compare` | 단순 client flow, build 차단 해소 후 empty/error UX 확인 필요 |
| `/portfolio` | 현재 build 차단 route |
| `/watchlist` | 인증 gate와 tracking detail 구조 양호 |
| `/calendar` | partial state 표현 양호 |
| `/archive` | research sync pending/fallback 표현 양호 |
| `/lab` | prediction/fusion/calibration 메타 표시 의도 양호 |
| `/settings` | draft 보호, beforeunload, reset, reauth nonce 흐름 양호 |
| `/stock/[ticker]` | quick/full upgrade 구조 양호, metadata 문구와 LLM 숫자 guide 리스크 |

### 백엔드/API 설계: 9 / 13

강점:

- 58개 API route가 FastAPI router로 분리되어 있고, `main.py`에서 모듈별 router 등록이 명확합니다.
- 보호 API 인증, 공개 계정 rate limit, watchlist missing item 등 에러 계약 테스트가 존재합니다.
- backend-only verify와 416개 unittest가 통과합니다.
- stock detail, briefing, market opportunities에 `200 + partial + fallback_reason` 방어가 폭넓게 있습니다.

감점:

- `API_CONTRACT.md`와 실제 router가 일부 다릅니다.
- 프론트 타입 계약이 깨져 백엔드 응답과 프론트 facade의 단일 계약점 역할이 약해졌습니다.
- 일부 라우터는 예외를 광범위하게 잡아 `500`으로 내리므로 원인 분류와 사용자 안내 정밀도는 더 높일 수 있습니다.

### 예측/주식 추천 방법론: 14 / 22

강점:

- `distributional_return_engine.py`는 가격 시계열을 backbone으로 사용하고, horizon별 분포, 분위수, 방향 확률, confidence를 생성합니다.
- `confidence.py`는 raw support를 만들고 empirical profile이 있으면 적용하며, 없으면 bootstrap sigmoid로 fallback합니다.
- `confidence_calibration_service.py`는 Brier score, reliability bin, class balance, regularized sigmoid, isotonic curve 조건을 갖추고 있습니다.
- learned fusion은 최소 표본/클래스 수를 요구하고, prior보다 Brier가 나빠질 때 soft blend로 후퇴합니다.
- graph context, macro/fundamental/event/flow feature가 calibration snapshot에 저장되어 lab/diagnostics 확장성이 있습니다.

감점:

- 상세 `buy_sell_guide`는 여전히 LLM 숫자 필드를 직접 사용할 수 있습니다.
- 신규 백테스트나 out-of-sample 성과 검증은 이번 범위에서 확인되지 않았고, 실제 prediction log의 표본 품질은 런타임 데이터에 의존합니다.
- `_build_horizon_distribution`에는 계수형 tilt/mixture 파라미터가 많아, 경험적 calibration이 충분히 쌓이지 않은 horizon에서는 수치 설득력이 bootstrap prior에 크게 의존합니다.
- recommendation UX가 confidence와 expected return을 투자 판단처럼 보이게 할 위험이 있으므로 "조건부 확률/검증 대기" 고지가 계속 필요합니다.

### 포트폴리오 최적화: 8 / 10

강점:

- `portfolio_optimizer.py`는 expected return, expected excess return, EWMA+shrinkage covariance, turnover penalty, cap projection을 사용합니다.
- `portfolio_service.py`와 `portfolio_recommendation_service.py`가 같은 optimizer를 호출합니다.
- `test_portfolio_optimizer.py`, `test_portfolio_recommendations.py`가 canonical optimizer 흐름을 고정합니다.

감점:

- 현재 미커밋 변경은 `_fill_weights` 성능 최적화와 cap skip을 추가했지만, 포트폴리오 optimizer는 작은 수치 변화도 사용자 추천 비중에 직접 영향을 줍니다. 기존 테스트는 통과했지만 stress case를 더 늘려야 합니다.
- 문서의 holdings/profile API 계약이 오래되어 portfolio 관련 변경 시 혼선을 만들 수 있습니다.

### 데이터/운영 안정성: 9 / 11

강점:

- public dashboard, stock detail, opportunity radar, briefing에 timeout/cache/partial fallback 설계가 촘촘합니다.
- Render memory/startup guard, quick snapshot, placeholder response, route trace 회귀 테스트가 많습니다.
- backend-only verify가 성공하고, `.env` 없음도 warning으로 처리됩니다.

감점:

- frontend build 실패로 운영 배포 체인은 최종 실패입니다.
- 홈 SSR timebox를 1초로 줄인 미커밋 변경은 cold start에서 partial/empty 빈도를 늘릴 수 있으므로 실제 deployed smoke 전까지 위험합니다.

### 계정/보안/개인정보: 7 / 8

강점:

- 프론트와 백엔드가 username/password/profile 검증 규칙을 대부분 같은 의미로 유지합니다.
- settings는 pending email, reauth nonce, cooldown, beforeunload, reset 흐름을 갖춥니다.
- `AuthProvider`가 `SP-6014` 이벤트 기반 세션 재검증 흐름을 가집니다.
- backend tests가 public account rate limit과 protected route 계약을 검증합니다.

감점:

- 미커밋 변경으로 공개 계정 API rate limit이 `username_availability 12 -> 60`, `signup_validate 6 -> 20`으로 완화됐습니다. UX에는 좋지만 abuse 관점에서는 운영 로그와 Cloudflare/Render rate layer까지 함께 봐야 합니다.

### 테스트/문서/릴리즈 거버넌스: 4 / 8

강점:

- backend test 수와 품질은 강합니다.
- version은 `backend/app/version.py`, `frontend/package.json`, `frontend/package-lock.json`, `README.md` 모두 `2.62.0`으로 동기화되어 있습니다.
- `verify.py --skip-frontend`는 정상 동작합니다.

감점:

- 전체 `verify.py`는 실패합니다.
- `tsc --noEmit` 실패가 많습니다.
- frontend unit test가 compile/type contract 파손을 막지 못했습니다.
- API 문서 일부가 실제 route와 다릅니다.

## 5. Recommended Roadmap

### 1주 이내: 배포 차단 해소

1. `PortfolioPageClient.tsx` 중복 state 선언 제거.
2. `frontend/src/lib/api.ts`의 type re-export와 local generic 타입 사용을 분리해 `tsc --noEmit` 통과.
3. `SystemStatusCard.tsx`의 `routeStability` 참조를 `routeStabilityRows` 또는 의도한 derived variable로 정리.
4. `OpportunityRadarBoard.tsx`의 `expected_return_pct` 참조를 `expected_return_pct_20d` 또는 fallback helper로 교체.
5. `RequestTrace` 타입 정의/수입 정리.
6. `npm run build`, `npx tsc --noEmit`, `npm run test`, `verify.py` 재실행.

### 2주 이내: 계약/문서/테스트 강화

1. `API_CONTRACT.md`의 watchlist/portfolio route를 실제 구현과 동기화.
2. frontend test에 route import smoke 또는 `tsc --noEmit` CI gate를 명시.
3. `/portfolio`, `/settings`, `/stock/[ticker]`, `/radar`의 browser smoke를 추가해 build만 통과하는 회귀를 막기.
4. 공개 계정 API rate limit 완화가 운영상 안전한지 로그/429 비율/abuse 시나리오를 점검.
5. 새 metadata 문구에서 `AI가 분석한` 반복을 줄이고 실제 기능 중심 문구로 조정.

### 장기: 추천/예측 신뢰성 강화

1. `_build_buy_sell`에서 LLM 숫자 필드를 직접 쓰지 않고, 구조화된 valuation/price/fundamental engine 결과만 가격대에 사용.
2. Prediction Lab에 horizon별 표본 수, class balance, Brier delta, reliability gap을 더 직접적으로 노출.
3. Opportunity Radar와 portfolio recommendation의 실제 realized return 평가를 cohort 단위로 정기 리포팅.
4. calibration profile이 없는 horizon에서는 confidence copy를 더 보수적으로 표시.

## 6. Final Verdict

이 프로젝트는 백엔드와 예측 엔진의 구조적 의도는 좋은 편입니다. 공개 경로 fallback, route trace, calibration, optimizer 공유처럼 운영형 제품에 필요한 설계가 실제 코드에 많이 반영되어 있습니다.

다만 현재 상태는 프론트가 빌드되지 않습니다. 따라서 엄격 평가 기준에서는 "좋은 설계가 있는 미완성 운영 빌드"로 봐야 하며, 배포 전 최우선 작업은 기능 추가가 아니라 compile/type/API 계약 복구입니다.

## 7. Remediation Update - 2026-05-14

이번 패치는 위 평가에서 확인한 배포 차단, LLM 숫자 의존, 계약 문서 불일치, 검증 공백을 우선 닫는 범위로 진행했습니다. 최초 평가 점수는 당시 스냅샷으로 유지하되, 아래 항목은 수정 완료 상태입니다.

### 완료 항목

- 프론트 빌드 차단을 해소했습니다.
  - `PortfolioPageClient.tsx` 중복 state 선언을 제거했습니다.
  - `RequestTrace`를 `frontend/src/lib/api/types.ts`의 canonical 타입으로 두고 `frontend/src/lib/types.ts`가 재사용하도록 정리했습니다.
  - `api.ts`, `api/account.ts`, `api/market.ts`, `api/portfolio.ts`, `api/system.ts`의 타입 import 경계를 정리했습니다.
  - `SystemStatusCard.tsx`의 잘못된 route stability 참조와 중복 블록을 제거했습니다.
  - `OpportunityRadarBoard.tsx`의 복사 문구는 `expected_return_pct_20d ?? predicted_return_pct` 기준으로 맞췄습니다.
  - `request-state.test.ts`의 `ApiTimeoutError` 생성자를 실제 시그니처와 맞췄습니다.

- LLM 숫자 의존을 제거했습니다.
  - `stock_analyzer._build_buy_sell()`은 LLM 응답의 가격대, fair value, confidence 숫자 필드를 읽지 않고 `build_quick_buy_sell(info)` 기반 deterministic guide만 사용합니다.
  - `stock_detail_analysis_prompt`, `sector_report_prompt`, `index_forecast_prompt`에서 목표가, 매수가, 매도가, valuation 숫자 요구를 제거하고 narrative-only schema로 줄였습니다.
  - LLM이 극단적인 숫자를 반환해도 buy/sell guide가 바뀌지 않는 회귀 테스트를 추가했습니다.

- 문서, 문구, 운영 계약을 정리했습니다.
  - `API_CONTRACT.md`의 watchlist/portfolio route를 실제 라우터와 맞췄습니다.
  - `CHANGELOG.md`의 conflict marker를 제거했습니다.
  - PDF export title, stock metadata, ErrorBanner의 "AI 분석/AI 예측" 표현을 "분석 요약/예측 분포/종목 해석" 중심으로 정리했습니다.
  - 홈 SSR timebox를 route별 차등 budget으로 복구했습니다.
  - 공개 계정 API rate limit `60/min`, `20/min`과 `429 / SP-6016` 재시도 안내를 README/API 계약에 명시했습니다.

- 테스트와 릴리즈 관리를 보강했습니다.
  - `backend/tests/test_portfolio_optimizer.py`에 cap skip 최적화가 target fill, single cap, country cap, sector cap을 깨지 않는 stress case를 추가했습니다.
  - frontend `package.json`에 `npm run check`를 추가해 `test + build + typecheck`를 한 번에 실행할 수 있게 했습니다.
  - 릴리즈 버전을 `v2.62.1`로 동기화했습니다.

### 재검증 결과

| 검증 | 결과 |
| --- | --- |
| `cd frontend; npm run test` | 통과, 6 files / 67 tests |
| `cd frontend; npm run build` | 통과, Next.js production build 완료 |
| `cd frontend; npx tsc --noEmit` | 통과 |
| `cd backend; ..\venv\Scripts\python.exe -m compileall app` | 통과 |
| `cd backend; ..\venv\Scripts\python.exe -m unittest discover -s tests -v` | 통과, 418 tests |
| `.\venv\Scripts\python.exe .\verify.py` | 통과 |
| conflict marker 정적 검색 | 결과 없음 |
| `rg -n "AI가|AI 예측|AI 분석|AI analysis" README.md frontend backend\app -S` | 결과 없음 |
| `rg -n "fair_value|buy_zone|sell_zone|valuation_methods" backend\app\analysis\prompts.py backend\app\analysis\stock_analyzer.py -S` | 결과 없음 |

### 남은 리스크

- 이번 패치는 신규 백테스트나 모델 재학습을 포함하지 않았습니다. 예측/추천 방법론의 장기 신뢰성은 기존 calibration log, prediction log, out-of-sample 평가 체계에 계속 의존합니다.
- `--live-api-smoke`와 `--deployed-site-smoke`는 이번 로컬 패치 검증 범위에서 필수로 실행하지 않았습니다. 배포 직전에는 운영 URL 기준으로 한 번 더 확인해야 합니다.
- 공개 계정 API rate limit 완화는 문서와 테스트에 반영됐지만, 실제 abuse 내성은 Cloudflare/Render 로그와 함께 운영 관찰이 필요합니다.

## 8. Remediation Loop 2 - 2026-05-14

이번 추가 루프는 최초 점수표의 감점 항목이 다시 들어오지 않도록 검증 루프 자체를 강화하고, 추천/예측 화면의 사용자 고지를 더 보수적으로 맞추는 데 집중했습니다.

### 추가 완료 항목

- 점수 보고서 정적 게이트를 `verify.py`에 연결했습니다.
  - `scripts/evaluation_gate.py`는 conflict marker, 과장된 AI 문구, LLM 숫자 prompt, stale API 계약, frontend `check` script, 릴리즈 버전 drift를 한 번에 검사합니다.
  - `backend/tests/test_evaluation_gate.py`로 게이트가 빈 실패 목록을 유지하는지 고정했습니다.

- 추천/포트폴리오 화면의 오해 위험을 낮췄습니다.
  - `ModelOutputNotice`를 추가하고 기회 레이더, 포트폴리오 추천, 일일 이상적 포트폴리오에 공통으로 노출했습니다.
  - 문구는 "수익 보장"이나 "즉시 매수 지시"가 아니라 조건부 분포와 제약 기반 참고 신호임을 분명히 말합니다.
  - `frontend/src/__tests__/model-output-notice.test.tsx`로 핵심 고지가 사라지지 않게 했습니다.

- 브라우저 스모크의 Windows/Edge 안정성을 보강했습니다.
  - Edge headless가 Crashpad/lockfile을 늦게 정리해도 검증이 예외로 깨지지 않도록 browser profile temp cleanup을 방어했습니다.
  - Edge `--dump-dom`이 빈 stdout을 반환하는 경우에도 HTTP HTML fallback으로 route text를 검증하고, 별도 screenshot으로 렌더링 산출물을 남기도록 했습니다.
  - screenshot 파일이 실제로 생성되고 비어 있지 않을 때만 route smoke를 성공으로 처리합니다.
  - `backend/tests/test_browser_smoke_runtime.py`에 cleanup race, empty DOM fallback, non-empty screenshot 회귀 테스트를 추가했습니다.

- 릴리즈 버전을 `v2.62.2`로 다시 동기화했습니다.
  - `backend/app/version.py`, `frontend/package.json`, `frontend/package-lock.json`, `README.md`, `CHANGELOG.md`를 같은 버전으로 맞췄습니다.

### 재평가 점수

최초 평가는 당시 broken build 상태를 기록한 기준선으로 보존합니다. 이번 루프 이후 로컬 검증 기준 재평가 점수는 아래와 같습니다.

| 영역 | 배점 | 재평가 점수 | 변경 근거 |
| --- | ---: | ---: | --- |
| 제품/UX/디자인 | 14 | 12 | AI 과장 문구 제거, 추천 고지 추가, 5개 viewport browser smoke 통과 |
| 프론트 기능 완성도 | 14 | 13 | `npm run check`, build/typecheck/test, 주요 route browser smoke 통과 |
| 백엔드/API 설계 | 13 | 12 | API 계약 정리, `SP-6014`, partial fallback, live smoke 확인 |
| 예측/주식 추천 방법론 | 22 | 18 | LLM 숫자 의존 제거, calibration backbone 유지, 단 신규 백테스트 없음 |
| 포트폴리오 최적화 | 10 | 9 | canonical optimizer 공유와 cap stress 회귀 테스트 추가 |
| 데이터/운영 안정성 | 11 | 10 | timeout/fallback, browser smoke 안정화, live API smoke 통과 |
| 계정/보안/개인정보 | 8 | 7 | rate limit 문서화와 protected API 계약 확인, 운영 abuse 관찰은 남음 |
| 테스트/문서/릴리즈 거버넌스 | 8 | 8 | evaluation gate, frontend `check`, 버전 동기화, README/CHANGELOG 갱신 |
| **총점** | **100** | **89** | 운영 품질에 가까운 상태이나 배포 URL smoke와 신규 out-of-sample 검증은 남음 |

점수 해석: 80-89 = 견고하지만 개선 여지 있음. 이번 루프에서는 broken build와 계약 drift 리스크를 닫았고, 90점 이상으로 올리려면 운영 배포 반영 확인과 추천/예측의 신규 out-of-sample 검증이 필요합니다.

### 추가 재검증 결과

| 검증 | 결과 |
| --- | --- |
| `.\venv\Scripts\python.exe .\scripts\evaluation_gate.py` | 통과 |
| `cd backend; ..\venv\Scripts\python.exe -m unittest tests.test_browser_smoke_runtime -v` | 통과, 6 tests |
| `cd frontend; npm run check` | 통과, 7 files / 68 tests + production build + typecheck |
| `.\venv\Scripts\python.exe .\verify.py --live-api-smoke --browser-smoke` | 통과, backend 422 tests + frontend build/typecheck + 5 viewport browser smoke + live API smoke |
| `.\venv\Scripts\python.exe .\scripts\browser_smoke.py --viewport 360x800 ...` | 통과, strict screenshot 성공 조건 재확인 |

참고: Codex 인앱 Browser 런타임은 이번 세션에서 `node_repl` transport가 닫혀 직접 세션 확인까지 이어지지 않았습니다. 대신 로컬 Edge 기반 browser smoke가 `360x800`, `390x844`, `768x1024`, `1024x768`, `1440x900` 전체 매트릭스에서 route별 screenshot과 HTML 검증을 남겼습니다.

### 현재 남은 리스크

- 운영 배포 URL이 `v2.62.2`로 실제 반영됐는지는 `--deployed-site-smoke` 또는 `scripts/wait_for_deployed_version.py`로 별도 확인해야 합니다.
- 신규 백테스트/모델 재학습은 여전히 이번 범위 밖입니다. 90점 이상을 위해서는 horizon별 realized return cohort, Brier delta, calibration drift를 새 데이터로 한 번 더 닫아야 합니다.
- 공개 계정 API rate limit 완화는 문서와 테스트에 고정했지만, 실제 abuse 내성은 Cloudflare/Render 로그 기반 운영 관찰이 필요합니다.

## 9. Remediation Loop 3 - 2026-05-14

이번 루프는 점수표의 장기 리스크였던 "calibration profile이 없는 horizon의 confidence 과신"을 직접 줄이는 데 집중했습니다.

### 추가 완료 항목

- bootstrap fallback confidence를 horizon별로 더 보수적으로 제한했습니다.
  - empirical profile이 없는 경우 표시 confidence 상한은 `1D 78%`, `5D 74%`, `20D 70%`입니다.
  - calibrator 이름도 `bootstrap_conservative_sigmoid_{bucket}d`로 남겨 fallback 상태를 더 명확히 구분합니다.

- empirical profile 품질 guard를 추가했습니다.
  - 표본 수가 `60건` 미만이면 표시 confidence를 최대 `86%`로 제한합니다.
  - reliability gap이 `0.12` 이상이면 표시 confidence를 최대 `84%`로 제한합니다.
  - `calibration_snapshot`에는 `confidence_cap`, `confidence_cap_reason`, empirical 표본 수, reliability gap, Brier delta가 함께 남습니다.

- 회귀 테스트와 문서를 동기화했습니다.
  - bootstrap profile 부재와 큰 reliability gap에서 confidence가 다시 과도하게 올라가지 않는 테스트를 추가했습니다.
  - README와 CHANGELOG를 새 confidence cap 계약에 맞췄고, 릴리즈 버전은 `v2.63.0`으로 동기화했습니다.

### 재평가 점수

| 영역 | 배점 | 재평가 점수 | 변경 근거 |
| --- | ---: | ---: | --- |
| 제품/UX/디자인 | 14 | 12 | 추천 고지와 과장 문구 정리 유지 |
| 프론트 기능 완성도 | 14 | 13 | `npm run check` 통과 |
| 백엔드/API 설계 | 13 | 12 | `SP-6014`, partial fallback, live smoke 계약 유지 |
| 예측/주식 추천 방법론 | 22 | 19 | LLM 숫자 의존 제거에 더해 profile 부재/품질 부족 confidence cap 추가 |
| 포트폴리오 최적화 | 10 | 9 | canonical optimizer와 stress 회귀 유지 |
| 데이터/운영 안정성 | 11 | 10 | live API smoke 통과, fallback 계약 유지 |
| 계정/보안/개인정보 | 8 | 7 | rate limit과 보호 API 계약 유지 |
| 테스트/문서/릴리즈 거버넌스 | 8 | 8 | evaluation gate, 버전 동기화, README/CHANGELOG 갱신 |
| **총점** | **100** | **90** | 로컬 검증 기준 운영 품질 우수 초입. 배포 반영과 신규 out-of-sample 검증은 별도 과제 |

### 추가 재검증 결과

| 검증 | 결과 |
| --- | --- |
| `cd backend; ..\venv\Scripts\python.exe -m unittest tests.test_confidence_scoring -v` | 통과, 10 tests |
| `cd backend; ..\venv\Scripts\python.exe -m unittest tests.test_confidence_scoring tests.test_confidence_calibration_service -v` | 통과, 12 tests |
| `.\venv\Scripts\python.exe .\scripts\evaluation_gate.py` | 통과 |
| `.\venv\Scripts\python.exe .\verify.py --skip-frontend` | 통과, backend 424 tests + compileall + evaluation gate |
| `cd frontend; npm run check` | 통과, 7 files / 68 tests + production build + typecheck |
| `cd backend; ..\venv\Scripts\python.exe scripts/live_api_smoke.py` | 통과, route registry 전체 smoke |

### 현재 남은 리스크

- 운영 배포 URL이 `v2.63.0`으로 실제 반영됐는지는 아직 확인하지 않았습니다. 배포 후 `--deployed-site-smoke` 또는 `scripts/wait_for_deployed_version.py`로 닫아야 합니다.
- 신규 백테스트/모델 재학습은 여전히 이번 범위 밖입니다. 다음 품질 점프는 horizon별 realized return cohort와 Brier delta 추적을 새 데이터로 닫는 쪽입니다.

## 10. Remediation Loop 4 - 2026-05-14

이번 루프는 Loop 3에서 추가한 confidence cap이 실제 사용자 화면과 API 계약에서 보이도록 닫았습니다. 수치가 낮아졌다는 사실만으로는 충분하지 않기 때문에, Prediction Lab에서 어떤 표본이 bootstrap fallback 또는 품질 guard로 제한됐는지 바로 확인할 수 있게 했습니다.

### 추가 완료 항목

- Prediction Lab 최근 로그와 리뷰 큐에 confidence cap 메타데이터를 노출했습니다.
  - `recent_records[]`와 `review_queue[]`는 `confidence_cap`, `confidence_cap_reason`, `empirical_profile_available`, `empirical_sample_count`, `empirical_max_reliability_gap`, `empirical_brier_delta`를 optional field로 가질 수 있습니다.
  - 화면에서는 `bootstrap 보수 cap`, `표본 부족 cap`, `reliability gap cap` 같은 한국어 라벨로 표시합니다.

- API 계약과 프론트 타입을 함께 동기화했습니다.
  - `API_CONTRACT.md`에 Prediction Lab 확장 필드를 반영했습니다.
  - `frontend/src/lib/api/types.ts`와 `PredictionLabDashboard`가 같은 필드 의미를 공유합니다.

- 검증 안정성도 같이 보강했습니다.
  - `test_prediction_lab_auto_refreshes_due_records_on_default_load`의 0.1초 타임박스가 묶음 실행에서 흔들리는 것을 확인하고, 테스트 의도는 유지한 채 0.5초로 조정했습니다.
  - 새 프론트 렌더 테스트로 cap 사유 문구가 사라지지 않게 했습니다.

### 재평가 점수

| 영역 | 배점 | 재평가 점수 | 변경 근거 |
| --- | ---: | ---: | --- |
| 제품/UX/디자인 | 14 | 13 | Prediction Lab에서 confidence cap 사유를 직접 표시 |
| 프론트 기능 완성도 | 14 | 13 | `npm run check` 통과, 신규 렌더 테스트 추가 |
| 백엔드/API 설계 | 13 | 12 | API 계약과 타입 동기화, live smoke 통과 |
| 예측/주식 추천 방법론 | 22 | 19 | cap 적용뿐 아니라 표본별 cap 사유를 검증 화면에 노출 |
| 포트폴리오 최적화 | 10 | 9 | 기존 optimizer 회귀 유지 |
| 데이터/운영 안정성 | 11 | 10 | backend 전체 검증과 live smoke 통과 |
| 계정/보안/개인정보 | 8 | 7 | 보호 API 계약 유지 |
| 테스트/문서/릴리즈 거버넌스 | 8 | 8 | README/CHANGELOG/API 계약/테스트 동기화 |
| **총점** | **100** | **91** | 로컬 검증 기준 운영 품질 우수. 배포 반영과 신규 out-of-sample 검증은 별도 과제 |

### 추가 재검증 결과

| 검증 | 결과 |
| --- | --- |
| `cd backend; ..\venv\Scripts\python.exe -m unittest tests.test_research_and_portfolio.ResearchAndPortfolioTests.test_prediction_lab_normalizes_breakdowns -v` | 통과 |
| `cd frontend; npm run test -- prediction-lab-dashboard.test.tsx` | 통과, 1 test |
| `cd backend; ..\venv\Scripts\python.exe -m unittest tests.test_research_and_portfolio tests.test_confidence_scoring tests.test_confidence_calibration_service -v` | 통과, 24 tests |
| `cd frontend; npm run check` | 통과, 8 files / 69 tests + production build + typecheck |
| `.\venv\Scripts\python.exe .\verify.py --skip-frontend` | 통과, backend 424 tests + compileall + evaluation gate |
| `cd backend; ..\venv\Scripts\python.exe scripts/live_api_smoke.py` | 통과, route registry 전체 smoke |

### 현재 남은 리스크

- 운영 배포 URL이 `v2.63.0`으로 실제 반영됐는지는 아직 확인하지 않았습니다.
- confidence cap은 과신 노출을 낮추지만, 모델 자체의 수익률 예측력을 증명하지는 않습니다. 다음 단계는 신규 기간 기준 realized return cohort와 Brier delta를 실제 운영 데이터로 닫는 것입니다.

## 11. Remediation Loop 5 - 2026-05-14

이번 루프는 Loop 4의 남은 리스크였던 `실현 수익률 cohort와 Brier 추적`을 Prediction Lab의 실제 응답과 화면에 연결했습니다. 목표는 예측 숫자를 적중/미스뿐 아니라 `예상 수익률 대비 실제 수익률`과 `표시 confidence Brier`로도 계속 감사할 수 있게 만드는 것입니다.

### 추가 완료 항목

- `prediction_records` 기반 읽기 전용 cohort 집계를 추가했습니다.
  - `db.prediction_return_cohorts(prediction_type, limit)`는 target date별 평가 완료 표본을 묶어 예상 수익률, 실제 수익률, 수익률 차이, 평균 절대 오차, 방향 적중률, 밴드 적중률, confidence Brier를 계산합니다.
  - SQLite lock 상황에서는 다른 public read 집계처럼 빈 리스트로 안전하게 fallback합니다.

- `/api/research/predictions` 응답에 `return_cohorts[]`를 추가했습니다.
  - `1D / 5D / 20D` horizon별 cohort를 같은 top-level 배열로 반환합니다.
  - API 계약과 프론트 타입을 함께 갱신했습니다.

- Prediction Lab에 `실현 수익률 cohort` 표를 추가했습니다.
  - 목표일, horizon, 평가 표본 수, 예상 수익률, 실제 수익률, 수익률 차이, 방향/밴드 적중률, Brier를 한 data frame에서 대조합니다.
  - 검증 표본이 없으면 큰 빈 차트 대신 표본 축적 상태를 설명하는 empty frame으로 내려갑니다.

### 재평가 점수

| 영역 | 배점 | 재평가 점수 | 변경 근거 |
| --- | ---: | ---: | --- |
| 제품/UX/디자인 | 14 | 13 | Prediction Lab에 검증용 data frame을 추가하고 모바일 smoke 통과 |
| 프론트 기능 완성도 | 14 | 13 | 신규 UI 테스트, build, typecheck 통과 |
| 백엔드/API 설계 | 13 | 12 | additive `return_cohorts[]` 계약과 public read fallback 추가 |
| 예측/주식 추천 방법론 | 22 | 20 | 적중률뿐 아니라 실현 수익률 편향과 confidence Brier를 horizon별로 추적 |
| 포트폴리오 최적화 | 10 | 9 | 기존 optimizer 회귀 유지 |
| 데이터/운영 안정성 | 11 | 10 | live API smoke와 브라우저 smoke 통과 |
| 계정/보안/개인정보 | 8 | 7 | 보호 API `401 / SP-6014` 계약 유지 |
| 테스트/문서/릴리즈 거버넌스 | 8 | 8 | README/CHANGELOG/API 계약/버전/테스트 동기화 |
| **총점** | **100** | **92** | 로컬 검증 기준 운영 품질 우수. 다음 큰 점프는 배포 반영 확인과 장기 out-of-sample cohort 누적 |

### 추가 재검증 결과

| 검증 | 결과 |
| --- | --- |
| `cd backend; ..\venv\Scripts\python.exe -m unittest tests.test_research_and_portfolio tests.test_database_cache_resilience -v` | 통과, 18 tests |
| `cd frontend; npm run test -- prediction-lab-dashboard.test.tsx` | 통과, 2 tests |
| `cd frontend; npm run check` | 통과, 8 files / 70 tests + production build + typecheck |
| `.\venv\Scripts\python.exe .\verify.py --skip-frontend` | 통과, backend 424 tests + compileall + evaluation gate |
| `cd backend; ..\venv\Scripts\python.exe scripts\live_api_smoke.py` | 통과, route registry 전체 smoke |
| `.\venv\Scripts\python.exe .\scripts\browser_smoke.py --base-url http://127.0.0.1:3000 --viewport 1440x900 --viewport 390x844 --attempts 2 --command-timeout-seconds 30 --max-total-seconds 240` | 통과, `/lab` 포함 주요 화면 desktop/mobile screenshot 생성 |
| `GET /api/research/predictions?limit_recent=20&refresh=false` | `return_cohorts[]` 실측 payload 반환 확인 |

### 현재 남은 리스크

- 운영 배포 URL이 `v2.64.0`으로 실제 반영됐는지는 아직 확인하지 않았습니다.
- cohort 집계는 운영 prediction log를 더 투명하게 보여 주지만, 표본 자체가 작으면 결론도 보수적으로 읽어야 합니다. 장기적으로는 기간별 out-of-sample holdout과 모델 버전별 cohort 비교를 더 촘촘히 쌓아야 합니다.

## 12. Remediation Loop 6 - 2026-05-14

Loop 5에서 cohort 표는 생겼지만, 사용자가 표를 직접 읽어야만 수익률 과대/과소 추정 편향을 발견할 수 있었습니다. 이번 루프에서는 같은 데이터를 Prediction Lab 액션 큐로 승격해, 큰 편향이 있는 horizon을 먼저 복기하도록 만들었습니다.

### 추가 완료 항목

- `return_cohorts[]` 기반 액션 큐 진단을 추가했습니다.
  - 평가 표본이 3건 이상이고 실현-예상 평균 수익률 차이가 `2.0%p` 이상이면 `수익률 과대/과소 추정 점검` 액션으로 올립니다.
  - `3.0%p` 이상이면 high severity로 올립니다.
  - 한 horizon에서 여러 날짜가 동시에 흔들려도 가장 큰 편향 1개만 표시해 액션 큐가 같은 유형으로 도배되지 않게 했습니다.

- cache key를 `prediction_lab:v10`으로 올렸습니다.
  - 액션 큐 의미가 바뀌었기 때문에 기존 `v9` 캐시가 남아 새 진단이 보이지 않는 경로를 차단했습니다.

- 문서와 회귀 테스트를 갱신했습니다.
  - README와 CHANGELOG에 수익률 편향 액션 큐 동작을 반영했습니다.
  - `test_prediction_lab_normalizes_breakdowns`가 return-bias action을 확인합니다.

### 재평가 점수

| 영역 | 배점 | 재평가 점수 | 변경 근거 |
| --- | ---: | ---: | --- |
| 제품/UX/디자인 | 14 | 13 | 표를 읽기 전에도 액션 큐에서 수익률 편향을 먼저 발견 |
| 프론트 기능 완성도 | 14 | 13 | 기존 UI 계약 유지, frontend check 통과 |
| 백엔드/API 설계 | 13 | 12 | additive action queue 진단과 cache key 갱신 |
| 예측/주식 추천 방법론 | 22 | 20 | 실현 수익률 편향을 자동 우선순위화 |
| 포트폴리오 최적화 | 10 | 9 | 기존 optimizer 회귀 유지 |
| 데이터/운영 안정성 | 11 | 10 | backend 전체 검증 통과 |
| 계정/보안/개인정보 | 8 | 7 | 보호 API 계약 유지 |
| 테스트/문서/릴리즈 거버넌스 | 8 | 8 | README/CHANGELOG/테스트 동기화 |
| **총점** | **100** | **92** | 점수는 유지하되, 예측 검증 UX와 운영 triage 품질 개선 |

### 추가 재검증 결과

| 검증 | 결과 |
| --- | --- |
| `cd backend; ..\venv\Scripts\python.exe -m unittest tests.test_research_and_portfolio.ResearchAndPortfolioTests.test_prediction_lab_normalizes_breakdowns -v` | 통과 |
| `cd backend; ..\venv\Scripts\python.exe -m unittest tests.test_research_and_portfolio -v` | 통과, 12 tests |
| `.\venv\Scripts\python.exe .\scripts\evaluation_gate.py` | 통과 |
| `.\venv\Scripts\python.exe .\verify.py --skip-frontend` | 통과, backend 424 tests + compileall + evaluation gate |
| `cd frontend; npm run check` | 통과, 8 files / 70 tests + production build + typecheck |
| `GET /api/research/predictions?limit_recent=20&refresh=false` | action queue에 `1D 수익률 과소 추정 점검`, `20D 수익률 과소 추정 점검` 대표 항목 확인 |

### 현재 남은 리스크

- 수익률 편향 액션은 표본 수 3건부터 보수적으로 표시하므로, 초기 표본에서는 “경고”보다 “복기 후보”로 읽어야 합니다.
- 다음 개선은 모델 버전별 cohort 비교를 추가해 새 엔진/가중치가 실제로 좋아졌는지 더 직접적으로 보는 쪽입니다.

## 13. Remediation Loop 7 - 2026-05-16

이번 루프는 기회 레이더가 이미 오른 종목을 추격 후보로 올리는 문제를 1차 후보 스캔부터 줄이는 데 집중했습니다. 리서치 근거는 “중기 모멘텀은 유효하지만 초단기 급등 추격은 반전 위험이 커지고, 거래량/수급/섹터 breadth가 지속 가능성을 가르는 필터”라는 가정으로 정리했습니다.

### 추가 완료 항목

- 1차 quote screen을 `change_pct` 중심 quick score에서 `섹터 강도 + 유동성 + 거래량 품질 + 추격 위험 감점` 기반으로 바꿨습니다.
- `OpportunityQuality` 점수표를 추가해 메인 레이더와 `NextDayFocus`가 같은 품질 기준을 공유합니다.
- 새 optional API 필드를 추가했습니다: `quality_score`, `chase_risk_score`, `volume_quality_score`, `flow_accumulation_score`, `sector_catalyst_score`, `score_breakdown`, `flow_data_status`, `quality_data_status`, `entry_style`, `recommended_entry_condition`.
- KRX 수급은 EOD 성격으로 고정했습니다. 장중은 `eod_pending`, 18시 이후 확보는 `fresh_eod`, 실패는 `flow_unavailable`로 표시합니다.
- 레이더 capture 기준일을 UTC today가 아니라 KST payload 생성일/마지막 가격일 기준으로 맞췄습니다.
- `support_json`과 `evaluation_json`에 품질 신호, 1D/5D/20D 수익률, 최대 역행폭, 맞은 근거/틀린 근거를 남기도록 확장했습니다.
- 레이더 캡처 뒤 pending radar 평가 refresh를 백그라운드로 예약해 `/archive/accuracy/stats?refresh=true` 호출에만 의존하지 않게 했습니다.
- `/radar`와 다음 거래일 포커스 UI에 추격 위험, 거래량, 수급, 섹터, 진입 조건 strip을 추가했습니다.
- README, API_CONTRACT, DESIGN_BIBLE, CHANGELOG, 버전을 `v2.65.0`으로 동기화했습니다.

### 재평가 점수

| 영역 | 배점 | 재평가 점수 | 변경 근거 |
| --- | ---: | ---: | --- |
| 제품/UX/디자인 | 14 | 13 | 레이더 카드에서 추격 위험/수급/거래량/진입 조건을 바로 읽을 수 있게 개선 |
| 프론트 기능 완성도 | 14 | 13 | optional 필드 fallback 유지, typecheck 통과 |
| 백엔드/API 설계 | 13 | 12 | additive API 확장과 캐시 호환 유지 |
| 예측/주식 추천 방법론 | 22 | 21 | 급등 추격 감점, 수급/거래량/섹터 품질 점수, 사후 평가 루프 보강 |
| 포트폴리오 최적화 | 10 | 9 | 기존 optimizer 회귀 유지 |
| 데이터/운영 안정성 | 11 | 10 | KST 기준일, EOD 수급 상태, background pending 평가 보강 |
| 계정/보안/개인정보 | 8 | 7 | 계정 계약 영향 없음 |
| 테스트/문서/릴리즈 거버넌스 | 8 | 8 | 신규 회귀 테스트와 문서/버전 동기화 |
| **총점** | **100** | **93** | 레이더 추천 방법론의 핵심 리스크였던 초단기 추격 매수 편향을 구조적으로 낮춤 |

### 추가 재검증 결과

| 검증 | 결과 |
| --- | --- |
| `cd backend; ..\venv\Scripts\python.exe -m compileall app` | 통과 |
| `cd frontend; npx tsc --noEmit` | 통과 |
| `cd backend; ..\venv\Scripts\python.exe -m unittest tests.test_opportunity_quality tests.test_investor_flow_client tests.test_opportunity_radar_lab_service tests.test_prediction_capture_service -v` | 통과, 10 tests |

### 현재 남은 리스크

- 실시간 Level 2/order book, 실제 IB 내부 flow, 체결 주체 실시간 식별은 무료 KR-first 데이터 범위 밖입니다. 현재 구현은 일봉 OHLCV, 상대 거래량, KRX EOD 수급, 섹터 breadth 프록시 기준입니다.
- KRX EOD 수급은 18시 이후에도 원천 지연이나 pykrx 장애가 있으면 `flow_unavailable`로 내려갈 수 있습니다. 이 경우 후보는 가격/거래량/섹터 기준으로 유지됩니다.
- 품질 가중치의 empirical 조정은 평가된 cohort가 충분히 쌓여야 안정화됩니다. 표본 수 gate와 `±6점` cap은 유지했습니다.
