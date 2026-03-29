# Architecture

이 문서는 `현재 운영 중인 Stock Predict`의 시스템 구조를 빠르게 설명합니다.
코드 리뷰나 신규 작업 전에 이 문서를 먼저 읽으면, 각 폴더와 서비스가 왜 존재하는지 더 빨리 이해할 수 있습니다.

## 시스템 한눈에 보기

```text
Next.js frontend (Vercel)
  -> FastAPI backend (/api, Render)
     -> SQLite cache / runtime data
     -> Supabase Auth + user data
     -> Public market data / macro data / research sources
     -> Distributional prior backbone + learned fusion + lightweight graph context
     -> OpenAI for structured extraction and narrative summaries
```

## 운영 기준선

- 프론트: `Next.js App Router`
- 백엔드: `FastAPI`
- 인증 / 사용자 데이터: `Supabase`
- 로컬 캐시 / 연구 기록 / 런타임 데이터: `SQLite`
- 외부 데이터: `ECOS`, `KOSIS`, `OpenDART`, `Naver`, `FMP`, `Yahoo Finance`, 공식 기관 리서치

## 저장소 구조

### 루트

- `README.md`
  - 제품 설명과 운영 가정
- `AGENTS.md`
  - AI 작업 규칙과 canonical 파일
- `DESIGN_BIBLE.md`
  - UI/UX 구조 기준
- `AI_CONTEXT.md`
  - AI 리뷰어용 빠른 입구
- `ARCHITECTURE.md`
  - 현재 문서
- `API_CONTRACT.md`
  - API 규칙과 라우트 지도
- `verify.py`
  - 원클릭 검증
- `start.py`
  - 로컬 개발 런처

### 프론트

- `frontend/src/app`
  - App Router 페이지 엔트리
- `frontend/src/components`
  - 공통 패널, 차트, 인증, 상태 카드
- `frontend/src/lib/api.ts`
  - 프론트-백엔드 API 계약의 중심
- `frontend/src/lib/account.ts`
  - 가입 / 계정 입력 규칙
- `frontend/src/lib/supabase-browser.ts`
  - 브라우저 Supabase 클라이언트 설정

### 백엔드

- `backend/app/main.py`
  - FastAPI 엔트리포인트, middleware, 예외 처리, startup task
- `backend/app/routers`
  - HTTP API 계층
- `backend/app/services`
  - 비즈니스 로직 계층
- `backend/app/analysis`
  - 예측 / 분석 엔진
- `backend/app/scoring`
  - score / confidence / selection 규칙
- `backend/app/data`
  - 외부 데이터 클라이언트와 유니버스 / 시세 조회
- `backend/app/errors.py`
  - 중앙 에러 코드 레지스트리
- `backend/tests`
  - 회귀 테스트

## 프론트 구조

### 화면 계층

`frontend/src/app`은 현재 아래 Depth 1 화면을 가집니다.

- `page.tsx`
- `auth/page.tsx`
- `radar/page.tsx`
- `screener/page.tsx`
- `compare/page.tsx`
- `portfolio/page.tsx`
- `watchlist/page.tsx`
- `calendar/page.tsx`
- `archive/page.tsx`
- `lab/page.tsx`
- `settings/page.tsx`

### 공통 프론트 계약

- 모든 API 호출은 우선 `frontend/src/lib/api.ts`를 통해 이뤄집니다.
- 인증 세션 복구와 `401 / SP-6014` 대응은 `frontend/src/components/AuthProvider.tsx`가 중심입니다.
- 페이지별 로딩 / 지연 / 부분 fallback 상태는 `frontend/src/components/WorkspaceStateCard.tsx`가 공통 표현을 담당합니다.
- 전역 내비게이션 구조와 메뉴 용어는 `frontend/src/components/Navigation.tsx`와 `DESIGN_BIBLE.md`를 함께 봐야 정확합니다.

## 백엔드 구조

### 엔트리와 라우팅

- `backend/app/main.py`
  - router 등록
  - CORS
  - 글로벌 예외 처리
  - startup task 실행
  - `/api/health`

### Router -> Service 구조

라우터는 HTTP 계약을 담당하고, 실제 계산은 서비스 계층으로 위임합니다.

예:

- `routers/portfolio.py` -> `services/portfolio_service.py`
- `routers/account.py` -> `services/account_service.py`
- `routers/screener.py` -> `services/market_service.py` 및 data 계층
- `routers/archive.py` -> `services/archive_service.py`, `services/research_archive_service.py`

### 분석 / 스코어링 계층

중요 파일:

- `backend/app/analysis/distributional_return_engine.py`
- `backend/app/analysis/learned_fusion.py`
- `backend/app/analysis/stock_graph_context.py`
- `backend/app/analysis/next_day_forecast.py`
- `backend/app/analysis/free_kr_forecast.py`
- `backend/app/analysis/historical_pattern_forecast.py`
- `backend/app/scoring/confidence.py`
- `backend/app/scoring/selection.py`

규칙:

- 숫자 예측 backbone은 `distributional_return_engine.py`
- learned fusion profile은 `learned_fusion_profile_service.py`가 `prediction_records` 기반으로 다시 맞춥니다.
- graph context는 `stock_graph_context.py`에서 피어 / 섹터 / 상관관계 fallback 순서로 구성합니다.
- confidence calibration은 `confidence.py + confidence_calibration_service.py`
- LLM은 구조화와 서술 보조이며, 숫자 backbone이 아닙니다

### 포트폴리오 계층

중요 파일:

- `backend/app/services/portfolio_optimizer.py`
- `backend/app/services/portfolio_service.py`
- `backend/app/services/portfolio_recommendation_service.py`
- `backend/app/services/ideal_portfolio_service.py`
- `backend/app/services/portfolio_event_service.py`

규칙:

- 추천 / 최적 / 이상적 포트폴리오는 같은 optimizer를 공유합니다.

## 저장 계층

### SQLite

주요 용도:

- 캐시
- 연구 기록
- `prediction_records.calibration_json` 내부의 fusion / graph context snapshot 저장
- startup 보강 작업의 로컬 저장
- 운영 진단용 데이터

설정 위치:

- `backend/app/config.py`
- 기본 경로: `data/stock_predict.db`

### Supabase

주요 용도:

- Auth
- 사용자별 `watchlist`
- 사용자별 `portfolio_holdings`
- 사용자별 `portfolio_profile`
- `user_metadata`

## 외부 데이터와 AI 보조 역할

### 외부 데이터

- `ECOS`
- `KOSIS`
- `OpenDART`
- `Yahoo Finance`
- `FMP`
- `Naver`
- 각국 공식 기관 리서치 소스

### OpenAI 역할

- 구조화 이벤트 추출
- 서술형 요약

하지 않는 역할:

- 숫자 예측 backbone 대체
- learned fusion profile 입력 대체
- 포트폴리오 비중의 ad-hoc 결정기

## 공개 경로 설계 원칙

공개 대시보드나 집계형 API는 느린 외부 소스 하나 때문에 전체 화면이 멈추지 않게 설계합니다.

핵심 원칙:

- timeout을 둔다
- 가능하면 `504`보다 `200 + partial`을 우선한다
- `fallback_reason`과 사용자 안내 문구를 함께 준다
- 프론트는 raw fetch error 대신 상태 카드와 재시도 흐름을 보여 준다

주로 영향을 받는 영역:

- 대시보드
- 기회 레이더
- 스크리너
- 캘린더
- 아카이브
- 설정 및 시스템

## Startup task 구조

`backend/app/main.py`는 서버 시작 시 아래 보강 작업을 백그라운드로 다룹니다.

- learned fusion profile refresh
- prediction accuracy refresh
- research archive sync
- market opportunity prewarm

중요한 점:

- startup time budget을 넘겨도 서비스 전체를 바로 실패시키지 않습니다
- learned fusion refresh가 timeout이나 예외를 내도 엔진은 자동으로 `prior_only`로 계속 동작합니다.
- 헬스와 런타임 상태는 `degraded / partial` 맥락을 포함해 해석해야 합니다

## 검증 구조

### 로컬 원클릭

```powershell
& .\venv\Scripts\python.exe .\verify.py
```

### 세부 검증

- 백엔드 compileall
- 백엔드 unittest
- 프론트 build
- 프론트 typecheck
- 선택적 live API smoke
- 선택적 deployed site smoke

## 구조 평가할 때 자주 보는 포인트

- 프론트와 백엔드 계약이 `frontend/src/lib/api.ts`와 라우터 응답에서 어긋나지 않는가
- 새 기능이 기존 Depth 1 화면에 흡수 가능한데도 새 route를 불필요하게 늘리지 않았는가
- 공개 경로에 timeout / partial fallback이 빠지지 않았는가
- `OpenAI`를 숫자 backbone처럼 오해한 로직이 들어오지 않았는가
- 포트폴리오 추천이 optimizer를 우회하지 않았는가
