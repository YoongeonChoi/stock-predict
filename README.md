# Stock Predict

AI 기반 주식 시장 분석 플랫폼 — 미국, 한국, 일본 시장을 커버합니다.

현재 릴리즈: `v2.10.8`

OpenAI API 기반 LLM과 정량 엔진을 함께 사용해 리서치 기관 보고서를 종합 분석하고, 엄격한 루브릭 기반 100점 만점 스코어링 시스템으로 국가/섹터/종목을 평가합니다.

버전 정책:
- 백엔드 앱 버전 기준: `backend/app/version.py`
- 프론트 패키지 버전 기준: `frontend/package.json`
- 릴리즈 변경 사항 기록: [CHANGELOG.md](./CHANGELOG.md)

협업 규칙:
- AI 작업 규칙: [AGENTS.md](./AGENTS.md)
- UI/UX 설계 기준: [DESIGN_BIBLE.md](./DESIGN_BIBLE.md)
- 사람/AI 공통 기여 규칙: [CONTRIBUTING.md](./CONTRIBUTING.md)
- PR 체크리스트: [.github/pull_request_template.md](./.github/pull_request_template.md)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 14)                 │
│  ┌──────────┬──────────┬──────────┬──────────┬────────┐ │
│  │Dashboard │ Country  │ Sector   │  Stock   │Watchlist│ │
│  │+Heatmap  │ Report   │ Analysis │+Candle   │Compare │ │
│  │+Movers   │+Forecast │ +Top10   │+TechAnls │Screener│ │
│  │+ExchRate │+F&G Index│          │+Pivot    │Portfolo│ │
│  │+Search   │          │          │+Analyst  │Archive │ │
│  └────┬─────┴────┬─────┴────┬─────┴────┬─────┴───┬────┘ │
│       └──────────┴──────────┴──────────┴─────────┘      │
│                         ▼ HTTP (port 3000 → 8000)       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                      │
│                                                         │
│  ┌─ API Routers ──────────────────────────────────────┐ │
│  │ /countries  /country/{code}/report  /stock/{ticker} │ │
│  │ /sectors    /sector/{id}/report     /stock/chart    │ │
│  │ /stock/technical-summary  /stock/pivot-points       │ │
│  │ /screener  /portfolio  /portfolio/ideal  /search    │ │
│  │ /watchlist  /compare  /archive  /calendar  /export  │ │
│  └────────────────────────┬───────────────────────────┘ │
│                           ▼                             │
│  ┌─ Services ─────────────────────────────────────────┐ │
│  │ archive_service │ watchlist_service │ export_service│ │
│  │ compare_service │ calendar_service  │ portfolio_svc │ │
│  └────────────────────────┬───────────────────────────┘ │
│                           ▼                             │
│  ┌─ Analysis Engine ──────────────────────────────────┐ │
│  │                                                     │ │
│  │  ┌──────────────┐  ┌───────────────┐               │ │
│  │  │  LLM Client  │  │  Scoring      │               │ │
│  │  │  (GPT-4o)    │  │  Engine       │               │ │
│  │  │  + Prompts   │  │  (rubric.py)  │               │ │
│  │  └──────┬───────┘  └───────┬───────┘               │ │
│  │         ▼                  ▼                        │ │
│  │  country_analyzer  │ sector_analyzer                │ │
│  │  stock_analyzer    │ forecast_engine                │ │
│  │  sentiment         │ fear_greed                     │ │
│  └────────────────────────────┬───────────────────────┘ │
│                               ▼                         │
│  ┌─ Data Layer ───────────────────────────────────────┐ │
│  │ ┌──────────┐ ┌──────┐ ┌──────┐ ┌─────┐ ┌───────┐ │ │
│  │ │ yfinance │ │ FRED │ │ ECOS │ │ BOJ │ │ News  │ │ │
│  │ │ (주가/재무)│ │(미국) │ │(한국) │ │(일본)│ │(Google)│ │ │
│  │ └──────────┘ └──────┘ └──────┘ └─────┘ └───────┘ │ │
│  │                  ┌──────────┐                      │ │
│  │                  │  FMP API │                      │ │
│  │                  │  (Basic) │                      │ │
│  │                  └──────────┘                      │ │
│  └────────────────────────────┬───────────────────────┘ │
│                               ▼                         │
│  ┌─ SQLite Cache + Archive DB ────────────────────────┐ │
│  │ cache │ watchlist │ archive_reports │ forecast_acc  │ │
│  │ portfolio_holdings │ ideal_portfolio_snapshots      │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 데이터 흐름

```
사용자 → 국가 선택 → Backend API 호출
  → 캐시 확인 (TTL 기반, 스테일하면 갱신)
  → Data Sources에서 시장 데이터 / 경제 지표 / 뉴스 수집
  → Scoring Engine이 정량 채점 (rubric.py 기반)
  → LLM이 뉴스+데이터 종합 → 정성 분석 + 매수/매도가 생성
  → Monte Carlo (10,000회) + LLM 보정 → 지수 확률 예측
  → 결과를 Archive DB에 저장 (예측 정확도 추적용)
  → Frontend에 JSON 반환 → 차트/점수/리포트 렌더링
```

---

## Features

### 핵심 분석 기능

| 기능 | 설명 |
|------|------|
| **국가 리포트** | 100점 만점 6항목 채점, 리서치 기관 컨센서스 분석, Top 5 종목 (점수 기반) |
| **지수 예측** | Monte Carlo 시뮬레이션 + LLM 보정, 1개월 상단/기본/하단 확률% |
| **다음 거래일 예측** | 정량 신호 엔진 기반 방향/상승확률/예상 종가/예상 고가·저가와 함께 상방/기준/하방 시나리오, 실행 바이어스, 리스크 플래그를 계산 |
| **과거 유사 국면 예측** | 최근 2년 가격 이력에서 현재와 비슷한 장면을 찾아 5·20·60거래일 기대 수익률, 예상 가격 범위, 유사 사례를 계산 |
| **시장 국면 분석** | 국가별 대표 지수의 추세/변동성/브레드스/단기 확률을 종합해 Risk-On, Rangebound, Risk-Off 같은 실행 컨텍스트 제공 |
| **섹터 분석** | 섹터별 100점 채점, Top 10 종목 장단점/점수/매수매도가 |
| **종목 상세** | 캔들스틱/라인 차트, Buy/Sell Zone, 재무 상세, 52주 범위 |
| **트레이드 플랜** | 종목 상세에서 진입 구간, 손절, 1차/2차 목표가, 무효화 조건, 보유 예상 기간까지 자동 제시 |
| **셋업 백테스트** | 현재 셋업과 닮은 과거 사례의 승률, 평균 수익률, 평균 최대 낙폭, 프로핏 팩터를 한 번에 요약 |
| **Fear & Greed** | 5개 지표 복합 게이지 (모멘텀, 주가강도, 변동성, 안전자산, 센티먼트) |

### 투자 도구 (Investing.com / TradingView / Yahoo Finance 스타일)

| 기능 | 설명 |
|------|------|
| **Technical Analysis Summary** | Investing.com 스타일 — SMA/EMA(5~200), RSI, MACD, Stochastic, CCI, ADX, Williams %R, Bollinger Bands 기반 종합 Buy/Sell 게이지 |
| **Stock Screener** | 국가/섹터/P·E/배당수익률/시총 등 조건 필터링, 정렬 가능한 결과 테이블 |
| **Portfolio Tracker** | 보유 종목 CRUD, 한국/일본 로컬 티커 자동 보정, 실시간 P&L 계산, 섹터·국가별 자산 배분 파이차트 |
| **Portfolio Risk Coach** | 포지션별 위험 점수, 포트폴리오 베타/집중도/변동성, 국가별 시장 국면, 스트레스 테스트, 실행 플레이북, 실행 믹스/우선 액션 큐 제공 |
| **Model Portfolio Builder** | 현재 보유 비중, 다음 거래일 시나리오, 실행 바이어스, Opportunity Radar, 워치리스트를 합쳐 목표 비중·현금 버퍼·리밸런싱 큐·후보 파이프라인을 자동 제안 |
| **Daily Ideal Portfolio** | 한국·미국·일본 레이더를 합쳐 다음 거래일 기준 가장 이상적인 종목 조합과 목표 비중을 매일 생성하고, 이전 추천안의 실제 성과까지 날짜별로 추적 |
| **Candlestick Chart** | TradingView 스타일 OHLC 캔들스틱 + 라인 차트 전환, 기간 선택 (1M/3M/6M/1Y) |
| **Pivot Points** | Classic + Fibonacci Pivot, Support/Resistance 레벨 (S1~S3, R1~R3) |
| **Analyst Consensus** | Buy/Hold/Sell 비율 시각화, 목표가 범위 (Low/Mean/High vs 현재가) |
| **Earnings Surprise** | Yahoo 실적 이력 기반 분기별 EPS Estimate vs Actual 바 차트 |
| **52-Week Range** | 현재가의 52주 범위 내 위치를 프로그레스 바로 표시 |
| **Prediction Overlay** | 라인 차트 위에 다음 거래일 예상 종가/상단/하단과 과거 유사 국면 기반 중기 경로를 함께 오버레이 |
| **Top Gainers/Losers** | 대시보드에 시장별 당일 상승/하락 Top 5 종목 표시 |
| **설정 및 시스템** | `/settings`에서 API 상태, startup 작업, 데이터 소스 readiness, 기관 리서치 동기화 상태를 한 번에 확인 |
| **Opportunity Radar** | 시장별 상위 셋업을 자동 스캔해서 Radar Score, 실행 액션, 진입/손절/목표가, 상방/기준/하방 시나리오와 핵심 리스크 플래그까지 함께 정렬 |
| **예측 연구실** | 예측 방향 적중률, 밴드 적중률, 신뢰도 보정, 국가/모델별 breakdown, 최근 miss audit까지 시각화 |

### 시장 데이터

| 기능 | 설명 |
|------|------|
| **Market Heatmap** | Treemap 기반 종목별 시총/등락률 히트맵 (US/KR/JP) |
| **Global Indicators** | VIX, DXY, Gold, Oil, US 10Y, Bitcoin 실시간 지표 |
| **Diagnostics API** | `/api/system/diagnostics` 에서 예측 엔진 버전, startup 상태, 데이터 소스 readiness 확인 |
| **Radar API** | `/api/market/opportunities/{code}` 에서 국가별 시장 국면과 상위 기회 종목을 한 번에 반환하고, 실시간 유니버스가 막히면 `universe_source`/`universe_note`로 fallback 상태를 함께 알려줌 |
| **Exchange Rates** | USD/KRW, USD/JPY, EUR/USD 환율 위젯 |
| **경제 캘린더** | 월별 일정 보드와 상세 패널을 함께 제공하고, 실제 데이터가 있으면 우선 반영하며 같은 월간 지표는 한 달에 1회만 보이도록 정규화 |
| **한국 우선 기본값** | 홈 대시보드, 레이더, 히트맵, 캘린더가 한국 시장부터 시작 |

### 사용자 기능

| 기능 | 설명 |
|------|------|
| **Global Search** | 네비게이션 상단 검색바, 티커/종목명 자동완성 |
| **워치리스트** | 인라인 추가, 실시간 점수/가격 업데이트, 통화 단위 자동 적용 |
| **비교 모드** | 2~4개 종목 나란히 비교 테이블 (통화 단위 자동) |
| **아카이브** | 과거 리포트 저장, 다음 거래일 예측 정확도 자동 누적, 실패 없는 다운로드 허브 제공 |
| **기관 리서치 아카이브** | Fed, KDI, 한국은행, BOJ, BIS 공식 리포트를 하루 한 번 동기화하고 PDF 또는 원문 링크 제공 |
| **Research API** | `/api/research/predictions` 에서 최근 예측 성과, calibration, breakdown, recent records를 한 번에 반환 |
| **PDF/CSV** | 모든 리포트 내보내기 (CJK 폰트 지원, PDF 응답 안정화 및 브라우저 다운로드 검증 완료) |

### UX

| 기능 | 설명 |
|------|------|
| **모바일 반응형** | 모바일 햄버거 메뉴 + 데스크톱 사이드바 |
| **워크스페이스 네비게이션** | 메뉴를 시장 탐색·운영·리서치 흐름으로 재구성하고, 상단 검색/빠른 이동/공통 페이지 헤더를 정리해 중구난방하던 정보 구조를 더 선명하게 개선 |
| **UI 셸 안정화** | Tailwind 토큰의 투명도 클래스를 전역 색상 변수와 다시 연결해 헤더, 사이드바, 카드, 테이블 배경이 깨지지 않도록 정리 |
| **투명 스크롤바 트랙** | 스크롤이 생기는 패널과 표, 드롭다운 전반에서 흰 트랙 배경을 제거하고 thumb만 남는 형태로 통일 |
| **대시보드 상단 재구성** | 추천 포트폴리오와 강한 셋업을 카드형 워크스페이스 셸로 다시 묶고, 대시보드에서는 넓은 비중 테이블 대신 폭에 맞는 요약 카드로 보여줘 정렬 깨짐과 잘림을 줄임 |
| **포트폴리오 입력 UX 보강** | 한국 `005930`, 일본 `7203`, 미국 `AAPL`처럼 입력해도 국가별 Yahoo 형식으로 자동 저장하고, 추가 실패 시 에러 코드와 함께 즉시 안내 |
| **다크/라이트 모드** | 시스템 테마 연동, 수동 전환 |
| **Toast 알림** | Watchlist/Portfolio 추가·삭제 등 사용자 액션 피드백 |
| **데이터 갱신 시각** | 대시보드에 마지막 업데이트 시각 표시 |
| **통화 단위 자동** | US($), KR(₩), JP(¥) 국가별 통화 기호 자동 적용 |

---

## Tech Stack

| 영역 | 기술 |
|------|------|
| Backend | Python 3.10+, FastAPI, SQLite, OpenAI GPT-4o |
| Frontend | Next.js 14 (App Router), Tailwind CSS, Recharts |
| Data | yfinance, pykrx, FRED API, BOK ECOS API, BOJ API, Google News RSS, FMP Basic, lxml |
| Forecast Infra | pandas-market-calendars, ta, SQLite prediction history |

### 다음 거래일 예측 엔진

- LLM이 가격을 직접 찍는 방식이 아니라, 기술 지표와 수급/뉴스를 정량화한 `signal-v2.4` 엔진을 사용합니다.
- 사용 신호:
  - 최근 5일 / 1개월 모멘텀
  - EMA 정렬 + 장기 추세 괴리
  - RSI 과열/되돌림
  - MACD histogram
  - 캔들 주도권 + 거래량 확인 신호
  - 한국어/영어 혼합 뉴스 헤드라인 감성 점수
  - 애널리스트 목표가/컨센서스
  - 한국 시장의 경우 pykrx 기반 외국인/기관 순매수 신호를 우선 시도
  - 시장 체제 오버레이(변동성 체제 + 컨텍스트 바이어스)
- 출력:
  - `direction`
  - `up_probability`
  - `predicted_close`
  - `predicted_high`
  - `predicted_low`
  - `confidence`
  - `scenarios` (상방 / 기준 / 하방)
  - `risk_flags`
  - `execution_bias`
  - `execution_note`
  - `drivers`

### 과거 데이터 기반 유사 국면 엔진

- `analog-v1.0` 엔진은 최근 2년 가격 이력에서 현재와 가장 비슷한 장면을 찾아 미래 분포를 계산합니다.
- 입력 신호:
  - 5일 / 20일 / 60일 모멘텀
  - RSI(14)
  - 20일 이격도와 20/60일 이동평균 정렬
  - 20일 변동성, ATR%
  - 거래량 Z-Score
  - 60일 고점 대비 돌파/이탈 정도
  - 동일 국가 대표 지수 대비 20일 상대강도
- 출력:
  - `5 / 20 / 60 거래일` 상승 확률
  - 기대 수익률 / 중간값 수익률
  - 예상 가격과 신뢰 구간
  - 과거 유사 사례 5건
  - 미래 경로 밴드
  - 현재 셋업에 대한 미니 백테스트

### Yahoo Finance 안정화

- `Ticker.info` 단일 의존을 줄이고 `fast_info`, `history_metadata`, 최근 가격 이력 fallback을 함께 사용하도록 정리했습니다.
- 지수(`^GSPC`, `^KS11`, `^N225` 등)는 원천적으로 없는 재무/실적 데이터를 요청하지 않도록 분기 처리해 불필요한 404 노이즈를 줄였습니다.
- 실적 이력 파싱을 위해 `lxml`을 의존성에 포함했고, 없을 경우에도 캘린더 fallback으로 최대한 조용하게 처리합니다.

### 정확도 추적

- `prediction_records` 테이블에 다음 거래일 예측을 저장합니다.
- 앱 시작 시와 정확도 조회 시점에 미평가 예측을 자동 재평가합니다.
- 집계 항목:
  - 방향 적중률
  - 예상 밴드 내 적중률
  - 평균 절대 오차율
  - 평균 confidence

---

## 실행 방법

### 사전 요구사항

- Python 3.10 이상
- Node.js 18 이상
- Git

### 1. 레포지토리 클론 (최초 1회)

```bash
git clone https://github.com/YoongeonChoi/stock-predict.git
cd stock-predict
```

### 2. 백엔드 설정 (최초 1회)

가상환경을 생성하고 패키지를 설치합니다. **이 단계는 최초 1번만** 실행하면 됩니다.

```powershell
# Windows PowerShell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

> **패키지가 추가/변경된 경우에만** `pip install -r backend/requirements.txt`를 다시 실행하세요.

### 검증 명령어

개발 후 가장 먼저 아래 원클릭 검증을 권장합니다.

```powershell
& .\venv\Scripts\python.exe .\verify.py
```

프론트만 잠시 건너뛰고 백엔드만 빠르게 검증하려면:

```powershell
& .\venv\Scripts\python.exe .\verify.py --skip-frontend
```

실제 주요 API 기능을 한 번 더 전수 스모크 점검하려면:

```powershell
& .\venv\Scripts\python.exe .\verify.py --live-api-smoke
```

실행 정책이나 `cmd` 자동 실행 훅, `\\?\C:\...` 확장 경로 때문에 래퍼가 불안정한 환경이면 위 Python 직접 실행 방식을 우선 사용하세요. `verify.cmd`와 `verify.ps1`는 같은 검증 런처를 감싸는 편의용 래퍼입니다.

개별 명령으로 확인할 때는 아래 순서를 사용합니다.

```powershell
# Backend
.\venv\Scripts\python.exe -m compileall backend\app
.\venv\Scripts\python.exe -m unittest discover -s backend\tests -v

# Frontend
cd frontend
npx tsc --noEmit
npm run build
```

> `npx tsc --noEmit` 는 `npm run build` 와 동시에 돌리면 `.next/types` 재생성 타이밍 때문에 false negative가 날 수 있습니다. 순차적으로 실행하세요.

### 3. API 키 설정 (최초 1회)

```powershell
# .env 파일 생성 (최초 1회)
Copy-Item backend\.env.example backend\.env
```

`backend/.env` 파일을 열고 아래 키를 입력합니다. **한 번 설정하면 다시 할 필요 없습니다.**

| 키 | 필수 여부 | 무료 여부 | 발급처 |
|----|----------|----------|--------|
| `OPENAI_API_KEY` | **필수** | 유료 | https://platform.openai.com/api-keys |
| `FRED_API_KEY` | **필수** | 무료 | https://fred.stlouisfed.org/docs/api/api_key.html |
| `ECOS_API_KEY` | **필수** | 무료 | https://ecos.bok.or.kr/api/ |
| `FMP_API_KEY` | 선택 | 무료 | https://financialmodelingprep.com/developer/docs/ |

> `OPENAI_API_KEY`가 없으면 AI 분석 기능(리포트, 추천 종목, 매수/매도 가이드)이 비활성화됩니다.
> 시장 데이터, 차트, Fear & Greed 지수 등은 정상 작동합니다. (에러코드: SP-1001)

### 4. 프론트엔드 설정 (최초 1회)

```powershell
cd frontend
npm install
cd ..
```

> `package.json`이 변경된 경우에만 `npm install`을 다시 실행하세요.

### 5. 실행 (매번)

아래 단계는 **서버를 켤 때마다** 실행합니다.

**방법 A: Python 직접 실행 (Windows, 권장)**

```powershell
& .\venv\Scripts\python.exe .\start.py
```

PowerShell 실행 정책 때문에 `.\start.ps1` 가 막히는 환경에서도 위 Python 직접 실행 방식은 그대로 사용할 수 있습니다.
단, `.\start.ps1` 를 직접 입력하는 방식은 로컬 PC의 실행 정책이 막고 있으면 계속 차단될 수 있습니다. 이 경우는 코드 문제가 아니라 Windows 보안 정책이므로 `start.py`, `start.cmd`, 또는 `powershell -ExecutionPolicy Bypass -File .\start.ps1` 경로를 사용해야 합니다.

**방법 B: CMD 래퍼 실행**

```powershell
.\start.cmd
```

**방법 C: PowerShell 실행 (정책 우회 포함)**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

빠르게 환경만 점검하려면:

```powershell
& .\venv\Scripts\python.exe .\start.py --check
```

필요하면 `.\start.cmd --check` 도 같은 점검을 실행합니다.

`start.py`는 현재 터미널을 유지한 채 백엔드와 프론트를 백그라운드로 띄우고, 실행 로그를 `.run/backend.log`, `.run/frontend.log`에 기록합니다. 서버가 실제로 뜨기 전에 상태 확인을 먼저 하기 때문에, 포트가 안 열렸는데 URL만 먼저 출력되는 문제를 줄였습니다.

**방법 D: 수동 실행 (터미널 2개)**

터미널 1 — 백엔드:
```powershell
cd backend
..\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

터미널 2 — 프론트엔드:
```powershell
cd frontend
npm run dev
```

### 6. 접속

| URL | 설명 |
|-----|------|
| http://localhost:3000 | 웹 UI |
| http://localhost:8000/docs | API 문서 (Swagger) |
| http://localhost:8000/api/health | 서버 상태 확인 |

### 요약: 최초 vs 매번

| 단계 | 최초 설치 | 매번 실행 |
|------|-----------|-----------|
| `git clone` | O | X |
| `python -m venv venv` | O | X |
| `pip install -r requirements.txt` | O | 패키지 변경 시만 |
| `.env` 파일 생성 + API 키 입력 | O | X |
| `npm install` | O | package.json 변경 시만 |
| `python .\start.py` 또는 래퍼 실행 | - | **O (매번)** |
| `uvicorn` 백엔드 실행 | - | **O (매번)** |
| `npm run dev` 프론트엔드 실행 | - | **O (매번)** |

---

## Error Codes Reference

모든 에러는 `SP-XYYY` 형식의 코드를 가집니다. 로그와 프론트엔드 UI 모두에 표시됩니다.

코드 정의: `backend/app/errors.py`

### 1xxx — 설정 (Configuration)

| 코드 | 설명 | 해결 방법 |
|------|------|----------|
| SP-1001 | OpenAI API 키 미설정 | `backend/.env`에 `OPENAI_API_KEY` 설정 |
| SP-1002 | OpenAI API 키 무효 | platform.openai.com에서 키 재발급 |
| SP-1003 | FRED API 키 미설정 | `backend/.env`에 `FRED_API_KEY` 설정 (무료) |
| SP-1004 | ECOS API 키 미설정 | `backend/.env`에 `ECOS_API_KEY` 설정 (무료) |
| SP-1005 | FMP API 키 미설정 | `backend/.env`에 `FMP_API_KEY` 설정 (무료, 선택) |

### 2xxx — 데이터 소스 (Data Sources)

| 코드 | 설명 | 해결 방법 |
|------|------|----------|
| SP-2001 | FRED API 요청 실패 | API 키 확인, 시리즈 ID 유효성 확인 |
| SP-2002 | ECOS (BOK) API 요청 실패 | 네트워크/키 확인 |
| SP-2003 | BOJ API 요청 실패 | 네트워크 확인 (키 불필요) |
| SP-2004 | 티커 미발견/상장폐지 | 유효한 Yahoo Finance 티커인지 확인 |
| SP-2005 | 가격 데이터 불가 | 장 개장 여부 / 티커 유효성 확인 |
| SP-2006 | FMP API 요청 실패 | FMP 키 확인, 일일 250콜 한도 확인 |
| SP-2007 | 뉴스 피드 불가 | 네트워크 확인, Google News 접근 가능 확인 |
| SP-2008 | 재무 데이터 불가 | yfinance에서 해당 종목 재무제표 미제공 |

### 3xxx — 분석 파이프라인 (Analysis)

| 코드 | 설명 | 해결 방법 |
|------|------|----------|
| SP-3001 | 국가 분석 실패 | 로그에서 하위 에러 코드 확인 |
| SP-3002 | 섹터 분석 실패 | 로그에서 하위 에러 코드 확인 |
| SP-3003 | 종목 분석 실패 | 티커 유효성 확인 |
| SP-3004 | 지수 예측 실패 | 가격 데이터 확인 |
| SP-3005 | 감성 분석 실패 | LLM 에러 코드 확인 |
| SP-3006 | 스코어링 계산 실패 | 입력 데이터 확인 |
| SP-3007 | 과거 유사 국면 예측 실패 | 장기 가격 이력 또는 지수 비교 데이터 확인 |

### 4xxx — LLM / OpenAI

| 코드 | 설명 | 해결 방법 |
|------|------|----------|
| SP-4001 | OpenAI 쿼터 초과 | platform.openai.com에서 결제/플랜 확인 |
| SP-4002 | OpenAI 인증 실패 | API 키 재발급 |
| SP-4003 | LLM 응답 파싱 오류 | 자동 재시도 또는 캐시 삭제 후 재요청 |
| SP-4004 | LLM 요청 타임아웃 | 네트워크 확인, 재시도 |
| SP-4005 | LLM 기타 오류 | 로그 상세 메시지 확인 |

### 5xxx — 서비스 / 데이터베이스

| 코드 | 설명 | 해결 방법 |
|------|------|----------|
| SP-5001 | DB 연결 실패 | SQLite 파일 경로/권한 확인 |
| SP-5002 | 리포트 저장 실패 | DB 용량/권한 확인 |
| SP-5003 | 워치리스트 작업 실패 | DB 확인 |
| SP-5004 | 내보내기 생성 실패 | fpdf2 패키지 설치 확인 |
| SP-5005 | 캐시 작업 실패 | DB 확인 |
| SP-5006 | 시스템 진단 조회 실패 | `/api/system/diagnostics` 로그 확인 |
| SP-5007 | 예측 연구실 조회 실패 | `/api/research/predictions` 로그 확인 |
| SP-5008 | 포트폴리오 분석 실패 | `/api/portfolio` 로그 확인 |
| SP-5009 | 외부 기관 리서치 동기화 실패 | `/api/archive/research/status` 로그 확인 |

### 6xxx — 요청 검증 (Validation)

| 코드 | 설명 | 해결 방법 |
|------|------|----------|
| SP-6001 | 미지원 국가 | US, KR, JP만 지원 |
| SP-6002 | 미존재 섹터 | 유효한 GICS 섹터 ID 확인 |
| SP-6003 | 잘못된 기간 파라미터 | 1mo, 3mo, 6mo, 1y, 2y 중 선택 |
| SP-6004 | 비교 티커 부족 | 최소 2개, 최대 4개 |
| SP-6005 | 아카이브 리포트 미발견 | 유효한 report_id 확인 |
| SP-6006 | 잘못된 내보내기 형식 | pdf 또는 csv |
| SP-6007 | 잘못된 캘린더 기간 파라미터 | month는 1~12, year는 2000~2100 범위 |
| SP-6008 | 잘못된 기관 리서치 아카이브 파라미터 | region_code는 US, KR, JP, GLOBAL만 허용 |
| SP-6009 | 잘못된 포트폴리오 입력값 | 티커, 양수 매수가/수량, 올바른 매수일 형식 확인 |
| SP-6010 | 잘못된 요청 파라미터/본문 형식 | 요청 필드 이름, 타입, 필수값 누락 여부 확인 |
| SP-6011 | 존재하지 않는 API 경로 | 경로 오타 또는 프론트 호출 경로 확인 |
| SP-6012 | 허용되지 않은 HTTP 메서드 | GET/POST/DELETE 등 지원 메서드 확인 |
| SP-9999 | 예상치 못한 서버 오류 | 서버 로그 확인 |

> 프론트엔드에서는 에러 발생 시 **에러 코드 + 한국어 가이드**가 함께 표시됩니다.
> 백엔드 로그에는 `[SP-XXXX] 메시지 | 상세` 형식으로 기록됩니다.
> FastAPI 기본 422/404/405도 구조화된 에러 코드(`SP-6009`, `SP-6010`, `SP-6011`, `SP-6012`)로 통일해 반환합니다.

---

## Scoring Methodology (점수 산정 방법론)

모든 점수는 `backend/app/scoring/rubric.py`에 정의된 **단일 진실의 원천(Single Source of Truth)**을 따릅니다.
점수는 크게 두 가지 방식으로 산출됩니다:

- **정량 채점 (Quantitative)**: 재무 데이터에 미리 정의된 임계값(Threshold)을 적용하여 결정론적으로 계산
- **정성 채점 (Qualitative)**: LLM(GPT-4o)에 구조화된 루브릭을 전달하여 분석 기반 점수 생성

> 두 방식 모두 동일한 `rubric.py` 파일의 기준을 따르며, LLM에도 정확한 점수 구간이 프롬프트로 전달됩니다.

---

### 종목 점수 (Stock Score) — 100점, 완전 정량

종목 점수는 100% 정량적으로 계산됩니다. yfinance에서 가져온 재무 데이터를 아래 Threshold 테이블에 대입합니다.
각 지표는 값의 크기에 따라 1~5점이 부여되며, `None`(데이터 없음)인 경우 중간값(2.5점)이 부여됩니다.

#### 1. 펀더멘탈 (Fundamental) — 25점

| 지표 | 5점 | 4점 | 3점 | 2점 | 1점 | 방향 |
|------|-----|-----|-----|-----|-----|------|
| 매출 성장률 (YoY%) | ≥20% | ≥10% | ≥5% | ≥0% | <0% | 높을수록 좋음 |
| 영업이익률 (%) | ≥25% | ≥15% | ≥10% | ≥5% | <5% | 높을수록 좋음 |
| ROE (%) | ≥20% | ≥15% | ≥10% | ≥5% | <5% | 높을수록 좋음 |
| 부채비율 (D/E %) | ≤30% | ≤60% | ≤100% | ≤200% | >200% | 낮을수록 좋음 |
| FCF Yield (%) | ≥8% | ≥5% | ≥3% | ≥1% | <1% | 높을수록 좋음 |

#### 2. 밸류에이션 (Valuation) — 20점

| 지표 | 5점 | 4점 | 3점 | 2점 | 1점 | 방향 |
|------|-----|-----|-----|-----|-----|------|
| P/E vs 동종업계 (% 차이) | ≤-20% | ≤-10% | ≤+10% | ≤+20% | >+20% | 낮을수록 좋음 |
| P/B vs 동종업계 (% 차이) | ≤-20% | ≤-10% | ≤+10% | ≤+20% | >+20% | 낮을수록 좋음 |
| EV/EBITDA vs 동종 (% 차이) | ≤-20% | ≤-10% | ≤+10% | ≤+20% | >+20% | 낮을수록 좋음 |
| PEG Ratio | ≤0.5 | ≤1.0 | ≤1.5 | ≤2.5 | >2.5 | 낮을수록 좋음 |

> 동종업계 평균은 FMP API의 Peers에서 가져옵니다. Peers 데이터 미제공 시 중간값 처리됩니다.

#### 3. 성장/모멘텀 (Growth & Momentum) — 20점

| 지표 | 5점 | 4점 | 3점 | 2점 | 1점 | 방향 |
|------|-----|-----|-----|-----|-----|------|
| EPS 성장률 (YoY%) | ≥25% | ≥15% | ≥5% | ≥0% | <0% | 높을수록 좋음 |
| 매출 성장 모멘텀 (%) | ≥20% | ≥10% | ≥5% | ≥0% | <0% | 높을수록 좋음 |
| 어닝 서프라이즈 (%) | ≥5% | ≥2% | ≥0% | ≥-2% | <-2% | 높을수록 좋음 |
| 3개월 가격 수익률 (%) | ≥15% | ≥5% | ≥0% | ≥-10% | <-10% | 높을수록 좋음 |

#### 4. 애널리스트 (Analyst) — 15점

| 지표 | 5점 | 4점 | 3점 | 2점 | 1점 | 방향 |
|------|-----|-----|-----|-----|-----|------|
| 매수 비율 (%) | ≥80% | ≥60% | ≥40% | ≥20% | <20% | 높을수록 좋음 |
| 목표가 괴리율 (%) | ≥30% | ≥15% | ≥5% | ≥-5% | <-5% | 높을수록 좋음 |
| 추정치 변경 (0-5) | LLM 정성 평가 | — | — | — | — | 높을수록 좋음 |

> 추정치 변경(Estimate Revision)은 유일하게 LLM이 정성적으로 채점하는 항목입니다 (0~5점).

#### 5. 리스크 (Risk) — 20점

| 지표 | 5점 | 4점 | 3점 | 2점 | 1점 | 방향 |
|------|-----|-----|-----|-----|-----|------|
| 베타 | ≤1.0 | ≤1.2 | ≤1.5 | ≤2.0 | >2.0 | 낮을수록 좋음 |
| 연간 변동성 (%) | ≤15% | ≤25% | ≤35% | ≤50% | >50% | 낮을수록 좋음 |
| 3개월 최대낙폭 (%) | ≤5% | ≤10% | ≤20% | ≤30% | >30% | 낮을수록 좋음 |
| 유동성 (거래량 비율) | ≥120% | ≥100% | ≥80% | ≥50% | <50% | 높을수록 좋음 |

#### Top 5 종목 선정 방식

국가 리포트의 **Top 5 Recommended Stocks**는 아래 프로세스로 선정됩니다:

1. 해당 국가 전 섹터에서 상위 종목을 샘플링 (섹터당 8개, 총 ~88개)
2. 각 종목을 위 100점 기준으로 정량 채점
3. 점수 내림차순 정렬 후 상위 5개 선정
4. LLM이 가용한 경우, LLM의 추천 이유가 함께 표시됨

---

### 국가 점수 (Country Score) — 100점, LLM 정성 채점

국가 점수는 GPT-4o가 경제 데이터 + 리서치 기관 뉴스를 분석하여 아래 루브릭에 따라 채점합니다.
각 항목에 대해 LLM은 반드시 점수와 1-2문장의 근거를 함께 반환해야 합니다.

| 카테고리 | 배점 | 최고점 조건 | 최저점 조건 |
|---------|------|-----------|-----------|
| 통화정책 방향 | 20점 | 적극 완화 (금리 인하, QE 진행) | 적극 긴축 (금리 인상, QT) |
| 경제성장 모멘텀 | 20점 | GDP 추세 상회, PMI 확장, 고용 강세 | 경기침체 신호, 실업 증가 |
| 시장 밸류에이션 | 15점 | P/E 역사 평균 크게 하회, 버핏지표 <100% | P/E 역사 평균 크게 상회, 버블 영역 |
| 이익 모멘텀 | 15점 | 광범위한 상향 수정, 어닝 비트율 높음 | 광범위한 하향 수정, 이익 붕괴 |
| 기관 컨센서스 | 15점 | 3곳+ 동일 결론, 정책-셀사이드 정렬 | 상반된 견해, 정책 vs 셀사이드 괴리 |
| 리스크 평가 | 15점 | 낮은 VIX, 안정 환율, 지정학 리스크 없음 | 위기 수준 변동성, 심각한 지정학 리스크 |

**교차검증 규칙**: LLM은 아래 3가지를 반드시 확인합니다:
- ① 3곳 이상의 기관이 같은 결론을 내리는가?
- ② 정책기관 방향과 sell-side 방향이 일치하는가?
- ③ 기관의 금리/이익 가정이 최신 데이터와 부합하는가?

---

### 섹터 점수 (Sector Score) — 100점, LLM 정성 채점

| 카테고리 | 배점 | 최고점 조건 | 최저점 조건 |
|---------|------|-----------|-----------|
| 이익성장 전망 | 20점 | 섹터 EPS 성장 >15%, 마진 확대 | 심각한 이익 감소 |
| 기관 컨센서스 | 20점 | 3곳+ 강한 비중확대 | 강한 비중축소 컨센서스 |
| 밸류에이션 매력 | 15점 | 섹터 P/E가 5년 평균 및 시장 평균 하회 | 현저히 고평가 |
| 정책 순풍/역풍 | 15점 | 보조금, 규제 완화, 정부 지출 | 규제 강화, 과세, 금지 |
| 기술적 모멘텀 | 15점 | 강한 상승 추세, 모든 MA 위, 자금 유입 | 강한 하락 추세, 자금 유출 |
| 위험조정수익 | 15점 | 베타 0.5~1.0, 낮은 하방 변동성 | 매우 높은 리스크, 최대낙폭 영역 |

---

### 매수/매도 가이드 (Buy/Sell Guide)

```
Buy Zone Low ← Buy Zone High ← Fair Value → Sell Zone Low → Sell Zone High
  (-12%)          (-6%)         (기준)        (+11%)          (+18%)
```

| 항목 | 산출 방식 |
|------|----------|
| **Fair Value** | DCF(35%) + 동종 멀티플(35%) + 애널리스트 목표가(30%) 가중평균 |
| **Buy Zone** | Fair Value × (1 - 12%) ~ Fair Value × (1 - 6%) |
| **Sell Zone** | Fair Value × (1 + 11%) ~ Fair Value × (1 + 18%) |
| **Risk/Reward Ratio** | (Sell Zone Low - 현재가) / (현재가 - Buy Zone High) |

| 신뢰도 등급 | 조건 |
|------------|------|
| **A** | 3개 밸류에이션 방법론의 결과 편차 ≤10% |
| **B** | 편차 ≤20% |
| **C** | 편차 >20% |

---

### Fear & Greed Index

5개 구성 지표의 가중평균으로 0~100 점수를 산출합니다.

| 구간 | 레이블 |
|------|--------|
| 80-100 | Extreme Greed |
| 60-79 | Greed |
| 40-59 | Neutral |
| 20-39 | Fear |
| 0-19 | Extreme Fear |

구성 지표: 시장 모멘텀 (MA200 이격), 주가 강도 (52주 고저), 시장 변동성 (VIX), 안전자산 수요 (국채 스프레드), 뉴스 센티먼트 (LLM 분석)

---

### 티커 유니버스 (Stock Universe)

분석 대상 종목은 두 가지 방식으로 결정됩니다:

1. **동적 (FMP Stock Screener API)**: FMP API 키가 있으면 시총 상위 종목을 섹터별로 자동 수집 (24시간 캐시)
2. **정적 (하드코딩)**: API 미사용 시 아래 수준의 사전 정의 목록으로 fallback

| 국가 | 정적 목록 수준 | 섹터당 종목 수 |
|------|-------------|--------------|
| US | S&P 500 | ~40-50개 |
| KR | KOSPI 200 | ~20-25개 |
| JP | Nikkei 225 / TOPIX | ~20-25개 |

정의: `backend/app/data/universe_data.py`

---

## 리서치 기관

### 미국 (US)
1. Federal Reserve
2. Goldman Sachs Research
3. J.P. Morgan Global Research
4. Morgan Stanley Research
5. BofA Global Research

### 한국 (KR)
1. 한국은행(BOK)
2. 삼성증권 리서치
3. NH투자증권 리서치본부
4. 미래에셋증권 리서치센터
5. 자본시장연구원(KCMI)
6. KDI

### 일본 (JP)
1. Bank of Japan
2. 野村證券 / Nomura Reports
3. Daiwa Institute of Research
4. Mizuho Research & Technologies
5. ニッセイ基礎研究所 / NLI Research Institute
6. Japan Research Institute

---

## Project Structure

```
stock-predict/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 엔트리포인트 + CORS
│   │   ├── config.py               # pydantic-settings 기반 설정
│   │   ├── database.py             # SQLite (캐시 + 아카이브 + 예측 정확도)
│   │   ├── models/                 # Pydantic 데이터 모델
│   │   │   ├── score.py            # CountryScore, SectorScore, StockScore
│   │   │   ├── country.py          # CountryInfo, CountryReport, 국가 레지스트리
│   │   │   ├── sector.py           # SectorReport, SectorStockItem
│   │   │   ├── stock.py            # StockDetail, BuySellGuide, Technicals
│   │   │   ├── forecast.py         # IndexForecast, FearGreedIndex
│   │   │   ├── watchlist.py        # WatchlistItem
│   │   │   └── archive.py          # ArchiveEntry, AccuracyStats
│   │   ├── data/                   # 외부 데이터 소스 클라이언트
│   │   │   ├── cache.py            # TTL 기반 캐시 헬퍼
│   │   │   ├── yfinance_client.py  # 주가, 재무제표, 기술 지표
│   │   │   ├── fred_client.py      # 미국 경제지표 (FRED API)
│   │   │   ├── ecos_client.py      # 한국 경제지표 (BOK ECOS API)
│   │   │   ├── boj_client.py       # 일본 경제지표 (BOJ API)
│   │   │   ├── fmp_client.py       # FMP Basic (피어, DCF, 캘린더)
│   │   │   └── news_client.py      # Google News RSS 수집
│   │   ├── scoring/                # 루브릭 기반 스코어링 엔진
│   │   │   ├── rubric.py           # 모든 임계값 + 채점 기준 (SSOT)
│   │   │   ├── country_scorer.py   # 국가 점수 조립
│   │   │   ├── sector_scorer.py    # 섹터 점수 조립
│   │   │   ├── stock_scorer.py     # 정량 종목 채점
│   │   │   └── fear_greed.py       # Fear & Greed 복합지표
│   │   ├── analysis/               # LLM 분석 엔진
│   │   │   ├── llm_client.py       # OpenAI GPT-4o 래퍼
│   │   │   ├── prompts.py          # 구조화된 JSON 프롬프트
│   │   │   ├── country_analyzer.py # 국가 리포트 생성
│   │   │   ├── sector_analyzer.py  # 섹터 리포트 생성
│   │   │   ├── stock_analyzer.py   # 종목 분석 + 매수/매도가
│   │   │   ├── historical_pattern_forecast.py # 과거 유사 국면 예측 + 셋업 백테스트
│   │   │   ├── forecast_engine.py  # Monte Carlo + LLM 보정
│   │   │   └── sentiment.py        # 뉴스 감성 분석
│   │   ├── services/               # 비즈니스 로직
│   │   │   ├── archive_service.py  # 리포트 아카이빙/정확도
│   │   │   ├── ideal_portfolio_service.py # 일일 추천 포트폴리오 생성/추적
│   │   │   ├── market_service.py   # Opportunity Radar
│   │   │   ├── portfolio_service.py# Portfolio risk coach + model portfolio
│   │   │   ├── research_service.py # 예측 연구실 / 검증 분석
│   │   │   ├── system_service.py   # Diagnostics / readiness
│   │   │   └── export_service.py   # PDF/CSV 생성
│   │   └── routers/                # FastAPI 라우터 (14개 엔드포인트)
│   │       ├── country.py
│   │       ├── sector.py
│   │       ├── stock.py
│   │       ├── watchlist.py
│   │       ├── compare.py
│   │       ├── archive.py
│   │       ├── calendar.py
│   │       └── export.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js App Router
│   │   │   ├── page.tsx            # 대시보드 (국가 선택)
│   │   │   ├── country/[code]/     # 국가 리포트 + 지수 예측
│   │   │   │   └── sector/[id]/    # 섹터 분석
│   │   │   ├── radar/              # Opportunity Radar
│   │   │   ├── lab/                # 예측 연구실
│   │   │   ├── stock/[ticker]/     # 종목 상세 (차트 + 매수/매도가)
│   │   │   ├── portfolio/          # 포트폴리오 리스크 코치 + 모델 포트폴리오
│   │   │   ├── archive/            # 아카이브
│   │   │   └── calendar/           # 경제 캘린더
│   │   ├── components/             # React 컴포넌트
│   │   │   ├── charts/             # ScoreRadial, PriceChart, ForecastBand, FearGreed
│   │   │   └── Navigation.tsx      # 사이드바 네비게이션
│   │   └── lib/
│   │       ├── api.ts              # 백엔드 API 클라이언트
│   │       ├── types.ts            # TypeScript 타입 정의
│   │       └── utils.ts            # 포맷팅 유틸
│   ├── package.json
│   └── tailwind.config.ts
├── start.cmd                       # Windows 편의용 런처
├── start.ps1                       # PowerShell 래퍼
├── dev_runtime.py                  # Windows 경로/Node 런타임 공용 헬퍼
├── start.py                        # 공용 개발 서버 런처
├── verify.cmd                      # Windows 편의용 검증 래퍼
├── verify.py                       # 공용 검증 런처
├── .gitignore
└── README.md
```

---

## 캐싱 전략

| 데이터 | TTL | 이유 |
|--------|-----|------|
| 주가 | 15분 | yfinance 지연 감안 |
| 차트 (3개월) | 1시간 | 갱신 빈도 낮음 |
| 재무제표 | 24시간 | 분기 업데이트 |
| 경제지표 | 24시간 | 월간/분기 발표 |
| 뉴스 | 1시간 | 빠른 갱신 필요 |
| FMP 데이터 | 1시간 | 250콜/일 제한 |
| LLM 리포트 | 6시간 | 비용 최적화 |
| 지수 예측 | 6시간 | 비용 최적화 |
| Fear & Greed | 1시간 | 시장 심리 변화 반영 |

---

## License

MIT
