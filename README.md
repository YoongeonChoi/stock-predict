# Stock Predict

투자 판단과 포트폴리오 운영을 위한 AI 분석 워크스페이스입니다.

현재 릴리즈: `v2.17.0`

현재 서비스는 한국 시장 중심으로 운영되며, 로그인한 사용자별로 워치리스트와 포트폴리오를 분리해 저장합니다. 프론트는 `Vercel`, 백엔드는 `Render`, 사용자 데이터와 인증은 `Supabase`, 도메인은 `Cloudflare` 기준으로 운영 흐름을 정리했습니다.

## 핵심 방향

- 판단 지원형 워크스페이스: 시장 탐색, 포트폴리오 운영, 검증 흐름이 한 제품 안에서 이어집니다.
- 무료 스택 우선: 학생 예산에서도 시작 가능한 `Vercel Hobby + Render Free + Supabase Free + Cloudflare Free` 조합을 기본값으로 둡니다.
- 사용자 분리: 워치리스트, 포트폴리오 보유 종목, 포트폴리오 프로필은 계정별로 따로 저장합니다.
- 근거 중심 분석: 가격·변동성·상대강도 같은 숫자 시계열을 주신호로 쓰고, 뉴스·공시·거시는 보조 신호로 결합해 차트/리포트/레이더를 같은 흐름으로 읽을 수 있게 구성합니다.

## 현재 무료 데이터 스택

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

## 현재 사용자 기능

- 대시보드
- Opportunity Radar
- 스크리너
- 종목 검색 / 비교
- 이메일 회원가입 / 로그인
- 사용자별 워치리스트
- 사용자별 포트폴리오 / 자산 프로필
- 포트폴리오 조건 추천 / 최적 추천
- 월간 캘린더
- 리서치 아카이브
- 다음 거래일 예측
- 무료 KR 확률 엔진
- 과거 유사 국면 예측

## 현재 예측 엔진

- 공통 백본: 다중 기간 가격 인코더 + 공개시차 안전 거시 압축 + 숫자 주도 게이트 결합 + regime-aware Student-t mixture 분포 헤드
- 가격 출력: `q10/q25/q50/q75/q90` 분위수
- 방향 출력: 같은 분포에서 파생한 `up / flat / down` 확률
- 증시/지수 출력: 동일한 공식에 지수 가격, breadth, dispersion, 금리 프록시를 적용한 분포 예측
- 뉴스/공시 역할: 주신호가 아니라 구조화 이벤트 보조 신호
- `OpenAI / GPT-4o` 역할: 수익률이나 가격을 직접 예측하지 않고, Naver 뉴스·FMP 보도자료·OpenDART 공시를 구조화 이벤트 벡터로 추출하는 용도

현재 구현 메모:

- `next_day` 예측은 공통 분포 엔진에서 다음 거래일 시나리오와 실행 바이어스를 파생합니다.
- `free_kr_probabilistic` 예측은 같은 분포 엔진을 1·5·20거래일 horizon으로 확장해 사용합니다.
- 포트폴리오 추천은 분포 기반 기대수익/확률 시그널을 반영하지만, 완전한 공분산 최적화 포트폴리오까지는 아직 아닙니다.

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
SUPABASE_URL=
SUPABASE_SERVER_KEY=
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
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
BACKEND_PROXY_URL=http://localhost:8000
```

메모:

- `SUPABASE_URL`은 프로젝트 URL입니다.
- `SUPABASE_SERVER_KEY`는 백엔드 전용입니다. Supabase의 `Secret key` 또는 레거시 `service_role`을 사용합니다.
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`는 프론트 로그인 세션에 필요합니다.
- `DB_PATH`는 이제 사용자 데이터 저장소가 아니라 로컬 캐시, 리서치 아카이브, 보조 SQLite 작업 경로입니다.
- `OPENAI_API_KEY`가 없어도 숫자 예측은 동작하지만 이벤트 구조화와 서술형 설명 품질은 낮아집니다.
- `ECOS_API_KEY`는 한국 거시 입력 품질에 중요합니다.
- `KOSIS_API_KEY`는 KOSIS 공유서비스 인증키입니다.
- `KOSIS_CPI_STATS_ID`, `KOSIS_EMPLOYMENT_STATS_ID`, `KOSIS_INDUSTRIAL_PRODUCTION_STATS_ID`는 별도 API가 아니라 같은 KOSIS 통계자료 API에 넘기는 통계표 ID입니다.
- `FRONTEND_URLS`는 쉼표 또는 줄바꿈으로 여러 프론트 도메인을 받을 수 있습니다.
- `FRONTEND_ORIGIN_REGEX`를 쓰면 `https://preview-*.vercel.app` 같은 프리뷰 도메인을 CORS에 같이 허용할 수 있습니다.

## 무료 배포 추천 구성

학생 예산 기준으로 가장 현실적인 기본 구성은 아래입니다.

- 프론트: `Vercel Hobby`
- 백엔드: `Render Free Web Service`
- 인증/사용자 데이터: `Supabase Free`
- DNS / SSL: `Cloudflare Free`

권장 도메인 구조:

- 프론트: `https://yoongeon.xyz`
- 백엔드: `https://api.yoongeon.xyz`

이 구성에서 중요한 점:

- 워치리스트, 포트폴리오 보유 종목, 포트폴리오 프로필은 `Supabase`에 저장됩니다.
- `DB_PATH`는 Render free에서 영구 디스크를 붙일 수 없으므로 `/tmp/stock_predict.db`처럼 임시 경로를 사용합니다.
- Render free는 유휴 시간이 길면 서비스가 잠시 내려갔다가 다시 올라올 수 있습니다. 완전한 always-on 보장은 아닙니다.
- 무료 호스팅 환경에서는 집계형 공개 API가 느려질 수 있으므로, 대시보드는 섹션별 timeout과 fallback 메시지를 사용해 한 패널 지연이 전체 화면 무한 로딩으로 이어지지 않도록 설계합니다.

## 배포 순서

1. Supabase 프로젝트를 먼저 준비합니다.
   - `Authentication -> URL Configuration`
   - `Site URL=https://yoongeon.xyz`
   - `Redirect URLs`에 `http://localhost:3000/**`, `https://yoongeon.xyz/**`, `https://www.yoongeon.xyz/**` 추가
   - SQL Editor에서 `watchlist`, `portfolio_holdings`, `portfolio_profile` 테이블과 RLS 정책을 적용합니다.
2. Render에 백엔드를 배포합니다.
   - 저장소 루트의 `render.yaml`을 사용합니다.
   - `rootDir=backend`
   - `plan=free`
   - `DB_PATH=/tmp/stock_predict.db`
   - `SUPABASE_URL`, `SUPABASE_SERVER_KEY`, `FRONTEND_URL`, `FRONTEND_URLS`, `FRONTEND_ORIGIN_REGEX`와 나머지 API 키를 입력합니다.
   - 헬스체크는 `/api/health`입니다.
3. Render 기본 도메인으로 먼저 확인합니다.
   - `https://<your-render-service>.onrender.com/api/health`
4. Vercel에 프론트를 배포합니다.
   - 프로젝트 Root Directory는 `frontend`
   - `NEXT_PUBLIC_API_URL=https://api.yoongeon.xyz`
   - `NEXT_PUBLIC_SUPABASE_URL=<your-supabase-url>`
   - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<your-supabase-publishable-key>`
5. Cloudflare에서 도메인을 연결합니다.
   - `yoongeon.xyz`는 Vercel이 제시하는 레코드로 연결합니다.
   - `api.yoongeon.xyz`는 Render가 제시하는 `CNAME` 값으로 연결합니다.
6. 도메인 검증 후 각 서비스 환경 변수를 최종 도메인 기준으로 다시 확인하고 재배포합니다.

운영 메모:

- Render free는 영구 디스크가 없으므로 `render.yaml`에 `/var/data` 같은 경로를 두면 배포가 실패합니다.
- 사용자의 핵심 데이터는 모두 Supabase에 있으므로, Render free 재기동 시에도 계정 데이터는 유지됩니다.
- 부팅 직후에도 `/api/health`가 먼저 살아나도록 외부 동기화 작업은 백그라운드로 실행됩니다.

## 실행

저장소 루트 `C:\clone_repo\stock-predict` 기준입니다.

```powershell
& .\venv\Scripts\python.exe .\start.py
```

같은 명령을 다시 실행하면 기존 백엔드/프론트 개발 서버를 자동으로 종료한 뒤 새로 띄웁니다. 수동 종료가 필요할 때만 `--stop`을 사용하시면 됩니다.

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
| `SP-1006` | Supabase 서버 키 미설정 |
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
| `SP-5018` | 공개 집계 API timeout |
| `SP-6001`~`SP-6013` | 잘못된 파라미터 또는 요청 형식 |
| `SP-6014` | 로그인 필요 |
| `SP-9999` | 예기치 못한 서버 오류 |

상세 정의는 `backend/app/errors.py`를 기준으로 관리합니다.

운영 메모:

- 공개 대시보드가 `불러오는 중` 상태로 오래 멈추면, 브라우저 Network 탭과 Render 로그에서 `504`와 `SP-5018` 응답이 있는지 먼저 확인합니다.
- 이 경우 프론트는 섹션별 fallback 문구를 보여주고, 사용자는 잠시 후 재시도할 수 있어야 합니다.

## 버전 정책

- 백엔드와 프론트 버전은 함께 올립니다.
- 사용자 동작이 바뀌면 `README.md`, `CHANGELOG.md`, 관련 테스트를 같이 갱신합니다.
- API 응답이 바뀌면 프론트 타입과 호출부를 함께 수정합니다.
