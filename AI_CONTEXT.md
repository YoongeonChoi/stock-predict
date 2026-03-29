# AI Context

이 문서는 `GitHub 링크만 받은 AI`가 이 저장소를 빠르게 읽고 평가하기 위한 첫 진입 문서입니다.

목표는 두 가지입니다.

- AI가 `어디부터 읽어야 하는지` 헤매지 않게 한다.
- 코드 리뷰, 구조 평가, 회귀 위험 판단을 `현재 운영 중인 제품` 기준으로 하게 만든다.

## 이 프로젝트를 한 줄로 설명하면

`Stock Predict`는 시장 탐색, 종목 해석, 포트폴리오 운영, 예측 검증을 한 흐름으로 연결한 투자 분석 워크스페이스입니다.

- 프론트 배포: `Vercel`
- 백엔드 배포: `Render`
- 인증 / 사용자 데이터: `Supabase`
- 도메인 / DNS: `Cloudflare`
- 현재 운영 기준선: `KR 시장 중심`, 다만 리서치 아카이브는 `KR / US / EU / JP` 공식 기관 소스를 함께 다룹니다.

## AI가 가장 먼저 읽어야 할 순서

1. `README.md`
2. `AGENTS.md`
3. `DESIGN_BIBLE.md`
4. `ARCHITECTURE.md`
5. `API_CONTRACT.md`
6. `backend/app/version.py`
7. `backend/app/main.py`
8. `frontend/src/lib/api.ts`
9. `frontend/src/components/AuthProvider.tsx`
10. `verify.py`

이 순서를 따르면 제품 설명, 작업 규칙, UI 기준, 시스템 구조, API 계약, 실제 엔트리포인트, 검증 방법을 빠르게 파악할 수 있습니다.

## 현재 제품 지도

### 프론트 주요 화면

- `/`
- `/auth`
- `/radar`
- `/screener`
- `/compare`
- `/portfolio`
- `/watchlist`
- `/calendar`
- `/archive`
- `/lab`
- `/settings`
- `/country/[code]`
- `/country/[code]/sector/[id]`
- `/stock/[ticker]`
- `/archive/export/[id]`

### 백엔드 주요 API 묶음

- 상태 / 시스템: `/api/health`, `/api/diagnostics`
- 계정 / 인증: `/api/account/*`
- 국가 / 시장: `/api/countries`, `/api/country/{code}/*`, `/api/market/*`
- 종목 / 검색: `/api/stock/{ticker}/*`, `/api/search`, `/api/ticker/resolve`
- 포트폴리오 / 관심종목: `/api/watchlist*`, `/api/portfolio*`
- 브리핑 / 캘린더 / 아카이브 / 비교 / 스크리너: `/api/briefing/daily`, `/api/calendar/{code}`, `/api/archive*`, `/api/compare`, `/api/screener`

## 이 저장소에서 가장 중요한 canonical 파일

### 예측 엔진

- `backend/app/analysis/distributional_return_engine.py`
- `backend/app/analysis/learned_fusion.py`
- `backend/app/analysis/stock_graph_context.py`
- `backend/app/scoring/confidence.py`
- `backend/app/services/confidence_calibration_service.py`
- `backend/app/services/learned_fusion_profile_service.py`

규칙:

- 숫자 예측의 canonical backbone은 `distributional_return_engine.py`
- 현재 운영 모델 버전은 `dist-studentt-v3.3-lfgraph`
- learned fusion은 prior backbone을 대체하지 않고, 실측 prediction log가 충분한 horizon만 보강합니다.
- graph context는 full GNN이 아니라 peer / sector / correlation fallback을 이용한 경량 feature builder입니다.
- 표시 confidence의 canonical calibration loop는 `confidence.py + confidence_calibration_service.py`
- `OpenAI / GPT-4o`는 숫자 예측기가 아니라 구조화 이벤트 추출기와 서술 요약기

### 포트폴리오 추천

- `backend/app/services/portfolio_optimizer.py`
- `backend/app/services/portfolio_service.py`
- `backend/app/services/portfolio_recommendation_service.py`
- `backend/app/services/ideal_portfolio_service.py`

규칙:

- 포트폴리오 비중 계산의 canonical optimizer는 `portfolio_optimizer.py`
- 조건 추천, 최적 추천, 일일 이상적 포트폴리오는 같은 optimizer를 공유

### 프론트 계약

- `frontend/src/lib/api.ts`
- `frontend/src/lib/account.ts`
- `frontend/src/components/AuthProvider.tsx`
- `frontend/src/components/Navigation.tsx`
- `frontend/src/components/WorkspaceStateCard.tsx`

## AI가 리뷰할 때 꼭 지켜야 할 기준

- `예전에 구상한 앱`이 아니라 `지금 운영 중인 서비스`를 기준으로 평가합니다.
- UI/UX 평가는 반드시 `DESIGN_BIBLE.md`를 먼저 읽고 진행합니다.
- 집계형 공개 경로는 `빠른 실패`보다 `200 + partial + fallback_reason`을 우선합니다.
- raw `Failed to fetch` 같은 브라우저 에러를 그대로 노출하는 것은 회귀로 봅니다.
- `401 / SP-6014`는 보호된 API의 인증 필요 계약입니다.
- 설정 화면은 프론트 / 백엔드 버전 불일치와 시스템 상태를 한 곳에서 보여주는 운영 패널입니다.

## 빠른 평가 체크리스트

아래 질문에 답할 수 있으면 이 프로젝트를 꽤 정확하게 읽은 상태입니다.

1. 현재 제품의 Depth 1 화면은 무엇인가
2. 예측 숫자 backbone은 무엇인가
3. learned fusion profile은 어디서 다시 맞춰지는가
4. confidence는 어디서 보정되는가
5. 포트폴리오 비중 계산은 어디서 하는가
6. 공개 집계형 API의 timeout / partial fallback 원칙은 무엇인가
7. 계정 검증 규칙은 프론트와 백엔드에서 어디가 맞물리는가
8. 버전 동기화는 어떤 파일 묶음을 함께 바꿔야 하는가

## 빠른 실행 경로

### Windows 권장 검증

```powershell
& .\venv\Scripts\python.exe .\verify.py
```

### 백엔드만 빠르게

```powershell
& .\venv\Scripts\python.exe .\verify.py --skip-frontend
```

### 운영 배포 확인

```powershell
& .\venv\Scripts\python.exe .\verify.py --deployed-site-smoke
```

## 환경 변수와 실행 전제

- 백엔드 예시는 `backend/.env.example`
- 프론트 예시는 `frontend/.env.example`
- 비밀 키가 없어도 `구조 평가`, `코드 품질 평가`, `라우트 / 계약 검토`, `테스트 체계 검토`는 가능합니다.
- 다만 `인증 실동작`, `외부 데이터 품질`, `운영 배포와 로컬의 차이`, `실제 API 응답 일관성`은 예시 환경 변수나 preview URL이 있어야 평가 정확도가 더 높아집니다.

## GitHub 링크만으로 어디까지 가능한가

아래 조건을 만족하면 AI는 `GitHub 링크만으로도` 이 프로젝트를 상당히 정확하게 평가할 수 있습니다.

- 저장소가 공개되어 있거나 접근 권한이 있음
- `README.md`, `AGENTS.md`, `DESIGN_BIBLE.md`, `ARCHITECTURE.md`, `API_CONTRACT.md`가 최신 상태
- `.env.example`가 실제 실행 전제를 반영
- `verify.py` 같은 원클릭 검증 경로가 유지됨

다만 아래는 링크만으로 100% 확정하기 어렵습니다.

- 실제 배포 환경 변수 누락
- Render cold start 체감 시간
- Supabase 프로젝트 설정 오차
- 외부 API 키 품질과 quota 상태
- 브라우저 체감 UX와 시각적 미세 결함

즉, `링크만으로 구조 / 품질 / 위험 평가`는 가능하고, `실운영 체감 검증`까지 완전히 대신하려면 preview 또는 배포 URL이 추가로 있으면 더 좋습니다.
