# Stock Predict

한국장 전용 AI 주식 분석 워크스페이스입니다.

현재 릴리즈: `v2.15.2`

이 버전부터 앱은 더 이상 미국/일본 시장을 다루지 않고, 한국 주식과 한국 거시 일정에만 집중합니다. 프론트와 백엔드의 국가 선택, 리서치 아카이브, 캘린더, 포트폴리오 입력 흐름도 모두 `KR` 기준으로 정리했습니다.

## 핵심 방향

- 한국장 전용: `KR`만 지원합니다.
- 무료 스택 우선: 유료 벤더 없이도 돌릴 수 있는 구성부터 다집니다.
- 예측 엔진 병렬화: 기존 규칙식 엔진은 유지하고, 무료 한국 데이터 기반 확률 엔진을 종목 상세에 병렬로 붙였습니다.

## 현재 무료 데이터 스택

지금 앱이 바로 쓰는 축은 아래입니다.

| 소스 | 용도 | 상태 |
|---|---|---|
| `Yahoo Finance` | 가격 이력, 지수, 기본 펀더멘털 | 기본 사용 |
| `PyKRX` | 한국 수급 보조 입력 | best effort |
| `ECOS` | 한국은행 거시 데이터 | API 키 필요 |
| `Google News RSS` | 한국장 뉴스 헤드라인 | 기본 사용 |
| `Naver Search API` | 국내 뉴스 헤드라인 보강 | 선택 |
| `OpenDART` | 최근 공시 이벤트 보강 | 선택 |
| `KOSIS` | 정부 통계 보강 | 선택 |
| `FMP` | 스크리너 보조, 시장 캘린더, 애널리스트 보조 | 선택 |
| `KDI / 한국은행 공식 리서치` | 리서치 아카이브 | 기본 사용 |

## 추가로 붙일 무료 KR API

무료 기준으로 다음 순서가 가장 현실적입니다.

1. `OpenDART`
   - 한국 공시 원문, 정기/수시 보고서, 재무제표, XBRL
   - 무료 KR 멀티모달 확장의 핵심
2. `KOSIS OpenAPI`
   - CPI, 고용, 산업생산 같은 정부 통계
   - ECOS 보강용
3. `Naver News Search API`
   - 한국 뉴스 헤드라인/링크 보강
   - 원문 멀티모달 완성용이라기보다 무료 뉴스 보조 축

정리하면, 무료 한국 확장판의 추천 조합은 `OpenDART + KOSIS + Naver News Search API` 입니다.

## 무료 KR 버전 구현 계획

### 1단계. 지금 바로 구현 가능한 버전

- 입력: 가격, 거래량, 변동성, 상대강도, ECOS 거시, Google/Naver 헤드라인, PyKRX 수급
- 출력: `q10/q25/q50/q75/q90`, `p_down/p_flat/p_up`, `vol_forecast`, `regime_probs`
- 포트폴리오: 한국 롱온리, 종목/섹터 cap 제약

이 단계는 현재 레포 구조와 무료 데이터만으로도 시작 가능합니다. 현재 앱에는 기존 `다음 거래일 예측`과 별도로 `무료 KR 확률 엔진` 카드가 병렬로 표시됩니다.

### 2단계. 무료 KR 멀티모달 확장

- `OpenDART` 공시 원문을 수집해 텍스트 임베딩 추가
- `KOSIS` 정부 통계를 거시 feature에 추가
- `Naver News Search API`로 뉴스 커버리지 보강
- `historical_pattern_forecast.py`는 메인 예측기가 아니라 설명/근거 모듈로 유지

### 3단계. KR 확률모형 전환

- `multi-period normalized encoder`
- `Student-t mixture return head`
- `regime-weighted probability output`
- `KR long-only constrained optimizer`

처음부터 풀 멀티모달로 가지 않고, `numeric-only -> KR text add-on -> portfolio optimizer` 순서로 올리는 것이 안전합니다.

## 현재 사용자 기능

- 한국장 대시보드
- 한국장 Opportunity Radar
- 한국장 스크리너
- 한국 종목 검색 / 워치리스트 / 비교
- 한국장 포트폴리오와 조건 추천 / 최적 추천
- 한국장 월간 캘린더
- 한국장 리서치 아카이브
- 다음 거래일 예측
- 무료 KR 확률 엔진
- 과거 유사 국면 예측

## 환경 변수

백엔드 `backend/.env` 예시:

```env
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o
ECOS_API_KEY=...
FMP_API_KEY=...
OPENDART_API_KEY=...
KOSIS_API_KEY=...
KOSIS_CPI_STATS_ID=...
KOSIS_EMPLOYMENT_STATS_ID=...
KOSIS_INDUSTRIAL_PRODUCTION_STATS_ID=...
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
DB_PATH=data/stock_predict.db
FRONTEND_URL=http://localhost:3000
FRONTEND_URLS=
FRONTEND_ORIGIN_REGEX=
STARTUP_PREDICTION_ACCURACY_REFRESH=true
STARTUP_PREDICTION_ACCURACY_REFRESH_TIMEOUT=20
STARTUP_RESEARCH_ARCHIVE_SYNC=true
STARTUP_RESEARCH_ARCHIVE_SYNC_TIMEOUT=35
```

프론트 `frontend/.env.example` 기준 예시:

```env
NEXT_PUBLIC_API_URL=
BACKEND_PROXY_URL=http://localhost:8000
```

메모:

- `OPENAI_API_KEY`가 없어도 앱은 일부 정량 기능이 동작하지만 서술형 설명 품질은 낮아집니다.
- `ECOS_API_KEY`는 한국 거시 입력 품질에 중요합니다.
- `OPENDART_API_KEY`를 넣으면 최근 공시 이벤트가 무료 KR 확률 엔진에 보강 신호로 반영됩니다.
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`를 넣으면 국내 뉴스 헤드라인 커버리지가 보강됩니다.
- `KOSIS_API_KEY`는 KOSIS 공유서비스 인증키입니다.
- `KOSIS_CPI_STATS_ID`, `KOSIS_EMPLOYMENT_STATS_ID`, `KOSIS_INDUSTRIAL_PRODUCTION_STATS_ID`는 별도 API가 아니라 같은 KOSIS 통계자료 API에 넘기는 통계표 ID입니다.
- `FMP_API_KEY`는 선택입니다. 없으면 더 작은 fallback 유니버스와 Yahoo 중심 흐름으로 동작합니다.
- `FRONTEND_URLS`는 쉼표 또는 줄바꿈으로 여러 프론트 도메인을 받을 수 있습니다.
- `FRONTEND_ORIGIN_REGEX`를 쓰면 `https://preview-*.vercel.app` 같은 프리뷰 도메인을 CORS에 같이 허용할 수 있습니다.
- 시작 시 예측 정확도/리서치 동기화는 이제 백그라운드로 돌며, `STARTUP_*` 값으로 부팅 시 동작 여부와 timeout을 조절할 수 있습니다.

## 상시 배포 추천 구성

학생 예산 기준으로 가장 현실적인 기본 구성은 아래입니다.

- 프론트: `Vercel Hobby`
- 백엔드: `Render Starter`
- DB: `SQLite + Render Persistent Disk`
- DNS: `Cloudflare`

이 레포는 아직 로그인/사용자 분리가 없고 SQLite 파일을 직접 사용합니다. 그래서 지금 단계에서는 `Vercel + Render + 디스크 유지`가 가장 적은 수정으로 안정적인 상시 운영에 가깝습니다.

권장 도메인 구조:

- 프론트: `https://example.com`
- 백엔드: `https://api.example.com`

배포 순서:

1. 백엔드부터 Render에 올립니다.
   - 저장소 루트에 포함된 `render.yaml`을 사용하면 `backend` 루트, `uvicorn` 시작 명령, `/api/health` 헬스체크, `/var/data` 디스크 마운트가 한 번에 잡힙니다.
   - Render에서 `New + -> Blueprint`로 이 저장소를 연결합니다.
2. Render 서비스 환경 변수를 채웁니다.
   - `DB_PATH=/var/data/stock_predict.db`
   - `FRONTEND_URL=https://example.com`
   - `FRONTEND_URLS=https://www.example.com`
   - `FRONTEND_ORIGIN_REGEX=^https://.*\.vercel\.app$`
   - 나머지 API 키는 `backend/.env.example` 기준으로 입력합니다.
3. Render 기본 도메인으로 백엔드가 뜨는지 먼저 확인합니다.
   - `https://<your-render-service>.onrender.com/api/health`
4. 프론트를 Vercel에 올립니다.
   - 프로젝트 Root Directory는 `frontend`
   - 환경 변수 `NEXT_PUBLIC_API_URL=https://api.example.com`
5. Cloudflare에서 커스텀 도메인을 붙입니다.
   - `example.com`은 Vercel이 제시하는 값으로 연결합니다.
   - `api.example.com`은 Render가 제시하는 `CNAME` 값으로 연결합니다.
6. 도메인 검증이 끝나면 Render의 `FRONTEND_URL`, `FRONTEND_URLS`를 최종 도메인 기준으로 다시 확인하고 재배포합니다.

운영 메모:

- 현재 구조는 단일 워크스페이스 DB입니다. 여러 사용자가 동시에 접속하면 워치리스트, 포트폴리오, 프로필 데이터가 함께 공유됩니다.
- Render Starter + 디스크 조합은 “항상 켜지는 개인 서비스”에는 잘 맞지만, 멀티유저 SaaS로 가려면 이후 `Postgres + 사용자 인증` 분리가 필요합니다.
- 부팅 직후에도 `/api/health`가 먼저 살아나도록 외부 동기화 작업은 백그라운드로 실행됩니다.

## 실행

저장소 루트 `C:\clone_repo\stock-predict` 기준입니다.

```powershell
& .\venv\Scripts\python.exe .\start.py
```

상태 확인:

```powershell
& .\venv\Scripts\python.exe .\start.py --status
```

중지:

```powershell
& .\venv\Scripts\python.exe .\start.py --stop
```

## 검증

전체 검증:

```powershell
& .\venv\Scripts\python.exe .\verify.py
```

프론트 제외 빠른 검증:

```powershell
& .\venv\Scripts\python.exe .\verify.py --skip-frontend
```

실호출 스모크:

```powershell
& .\venv\Scripts\python.exe .\verify.py --live-api-smoke
```

## 주요 파일

- 백엔드 버전: `backend/app/version.py`
- 프론트 버전: `frontend/package.json`
- 변경 이력: `CHANGELOG.md`
- 에이전트 작업 규칙: `AGENTS.md`
- UI 기준: `DESIGN_BIBLE.md`

## 에러 코드

현재 앱이 주로 반환하는 에러 코드는 아래입니다.

| 코드 | 의미 |
|---|---|
| `SP-1001` | OpenAI API 키 미설정 |
| `SP-1003` | 추가 공공데이터 API 키 미설정 |
| `SP-1004` | ECOS API 키 미설정 |
| `SP-1005` | FMP API 키 미설정 |
| `SP-2001` | 추가 공공데이터 API 호출 실패 |
| `SP-2002` | ECOS 호출 실패 |
| `SP-2003` | 추가 통계 API 호출 실패 |
| `SP-2004` | 티커 없음 또는 상장폐지 |
| `SP-2005` | 가격 데이터 없음 |
| `SP-2006` | FMP 호출 실패 |
| `SP-2007` | 뉴스 피드 실패 |
| `SP-2008` | 재무 데이터 없음 |
| `SP-3001`~`SP-3007` | 분석 파이프라인 실패 |
| `SP-4001`~`SP-4005` | OpenAI/LLM 호출 실패 |
| `SP-5001`~`SP-5009` | DB / 아카이브 / 캐시 / 시스템 실패 |
| `SP-5010`~`SP-5017` | 티커 해석, 브리핑, 세션, 포트폴리오 추천/프로필 실패 |
| `SP-6001`~`SP-6013` | 잘못된 파라미터 또는 요청 형식 |
| `SP-9999` | 예기치 못한 서버 오류 |

상세 정의는 `backend/app/errors.py`를 기준으로 관리합니다.

## 버전 정책

- 백엔드와 프론트 버전은 함께 올립니다.
- 사용자 동작이 바뀌면 `README.md`, `CHANGELOG.md`, 관련 테스트를 같이 갱신합니다.
- API 응답이 바뀌면 프론트 타입과 호출부를 함께 수정합니다.
