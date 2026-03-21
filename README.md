# Stock Predict

AI 기반 주식 시장 분석 플랫폼 — 미국, 한국, 일본 시장을 커버합니다.

OpenAI GPT-4o를 활용하여 리서치 기관 보고서를 종합 분석하고, 엄격한 루브릭 기반 100점 만점 스코어링 시스템으로 국가/섹터/종목을 평가합니다.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 14)                 │
│  ┌──────────┬──────────┬──────────┬──────────┬────────┐ │
│  │Dashboard │ Country  │ Sector   │  Stock   │Watchlist│ │
│  │  (Home)  │ Report   │ Analysis │  Detail  │Compare │ │
│  │          │+Forecast │ +Top10   │+Chart    │Archive │ │
│  │          │+F&G Index│          │+Buy/Sell │Calendar│ │
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
│  │ /watchlist  /compare  /archive  /calendar  /export  │ │
│  └────────────────────────┬───────────────────────────┘ │
│                           ▼                             │
│  ┌─ Services ─────────────────────────────────────────┐ │
│  │ archive_service │ watchlist_service │ export_service│ │
│  │ compare_service │ calendar_service                  │ │
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

| 기능 | 설명 |
|------|------|
| **국가 리포트** | 100점 만점 6항목 채점, 리서치 기관 컨센서스 분석, Top 5 종목 |
| **지수 예측** | Monte Carlo 시뮬레이션 + LLM 보정, 1개월 상단/기본/하단 확률% |
| **섹터 분석** | 섹터별 100점 채점, Top 10 종목 장단점/점수/매수매도가 |
| **종목 상세** | 3개월 차트(MA20/60, RSI, MACD), Buy/Sell Zone, 재무 상세 |
| **Fear & Greed** | 5개 지표 복합 게이지 (모멘텀, 주가강도, 변동성, 안전자산, 센티먼트) |
| **워치리스트** | 관심 종목 CRUD, 실시간 점수/가격 업데이트 |
| **비교 모드** | 2~4개 종목 나란히 비교 테이블 |
| **아카이브** | 과거 리포트 저장, 예측 정확도 추적 |
| **경제 캘린더** | FOMC/BOK금통위/BOJ회의 + 어닝 일정 |
| **PDF/CSV** | 모든 리포트 내보내기 |

---

## Tech Stack

| 영역 | 기술 |
|------|------|
| Backend | Python 3.10+, FastAPI, SQLite, OpenAI GPT-4o |
| Frontend | Next.js 14 (App Router), Tailwind CSS, Recharts |
| Data | yfinance, FRED API, BOK ECOS API, BOJ API, Google News RSS, FMP Basic |

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
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

> **패키지가 추가/변경된 경우에만** `pip install -r backend/requirements.txt`를 다시 실행하세요.

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

**방법 A: PowerShell 원클릭 실행 (Windows)**

```powershell
.\start.ps1
```

**방법 B: 수동 실행 (터미널 2개)**

터미널 1 — 백엔드:
```powershell
.\venv\Scripts\Activate.ps1          # 가상환경 활성화 (매번 필요)
cd backend
uvicorn app.main:app --reload --port 8000
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
| 가상환경 활성화 (`Activate.ps1`) | - | **O (매번)** |
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

### 6xxx — 요청 검증 (Validation)

| 코드 | 설명 | 해결 방법 |
|------|------|----------|
| SP-6001 | 미지원 국가 | US, KR, JP만 지원 |
| SP-6002 | 미존재 섹터 | 유효한 GICS 섹터 ID 확인 |
| SP-6003 | 잘못된 기간 파라미터 | 1mo, 3mo, 6mo, 1y, 2y 중 선택 |
| SP-6004 | 비교 티커 부족 | 최소 2개, 최대 4개 |
| SP-6005 | 아카이브 리포트 미발견 | 유효한 report_id 확인 |
| SP-6006 | 잘못된 내보내기 형식 | pdf 또는 csv |
| SP-9999 | 예상치 못한 서버 오류 | 서버 로그 확인 |

> 프론트엔드에서는 에러 발생 시 **에러 코드 + 한국어 가이드**가 함께 표시됩니다.
> 백엔드 로그에는 `[SP-XXXX] 메시지 | 상세` 형식으로 기록됩니다.

---

## Scoring Rubric

모든 점수는 `backend/app/scoring/rubric.py`에 정의된 단일 진실의 원천(Single Source of Truth)을 따릅니다.

### Country Score (100점)

| 카테고리 | 배점 | 평가 기준 |
|---------|------|----------|
| 통화정책 방향 | 20점 | 중앙은행 스탠스, 금리 경로, QT/QE |
| 경제성장 모멘텀 | 20점 | GDP vs 컨센서스, PMI, 고용 |
| 시장 밸류에이션 | 15점 | P/E vs 역사 평균, 버핏지표, ERP |
| 이익 모멘텀 | 15점 | EPS 추정치 변경, 매출/이익 트렌드 |
| 기관 컨센서스 | 15점 | 3곳+ 동일 결론, 정책-셀사이드 정렬 |
| 리스크 평가 | 15점 | VIX, 환율, 지정학, 신용스프레드 |

### Sector Score (100점)

| 카테고리 | 배점 | 평가 기준 |
|---------|------|----------|
| 이익성장 전망 | 20점 | 섹터 EPS 성장, 마진 추세 |
| 기관 컨센서스 | 20점 | 비중확대/축소, 리서치 방향 |
| 밸류에이션 매력 | 15점 | 섹터 P/E vs 역사/시장 |
| 정책 순풍/역풍 | 15점 | 규제, 보조금, 금리 민감도 |
| 기술적 모멘텀 | 15점 | 상대강도, 자금흐름, MA |
| 위험조정수익 | 15점 | 베타, 하방 변동성 |

### Stock Score (100점)

| 카테고리 | 배점 | 세부 (각 5점) |
|---------|------|-------------|
| 펀더멘탈 | 25점 | 매출 성장, 영업마진, ROE, 부채비율, FCF |
| 밸류에이션 | 20점 | P/E, P/B, EV/EBITDA vs 동종, PEG |
| 성장/모멘텀 | 20점 | EPS 성장, 매출 성장, 어닝서프라이즈, 가격 |
| 애널리스트 | 15점 | 매수비율, 목표가 괴리율, 추정치 변경 |
| 리스크 | 20점 | 베타, 변동성, 최대낙폭, 유동성 |

### 매수/매도 가이드

- **Buy Zone**: Fair Value -12% (안전마진 반영)
- **Fair Value**: DCF(35%) + 동종 멀티플(35%) + 애널리스트 목표가(30%) 가중평균
- **Sell Zone**: Fair Value +18%
- **신뢰도**: A(3개 방법론 수렴), B(2개 수렴), C(괴리 큼)

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
│   │   │   ├── forecast_engine.py  # Monte Carlo + LLM 보정
│   │   │   └── sentiment.py        # 뉴스 감성 분석
│   │   ├── services/               # 비즈니스 로직
│   │   │   ├── archive_service.py  # 리포트 아카이빙/정확도
│   │   │   ├── watchlist_service.py
│   │   │   ├── compare_service.py
│   │   │   ├── calendar_service.py
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
│   │   ├── app/                    # Next.js App Router (8 routes)
│   │   │   ├── page.tsx            # 대시보드 (국가 선택)
│   │   │   ├── country/[code]/     # 국가 리포트 + 지수 예측
│   │   │   │   └── sector/[id]/    # 섹터 분석
│   │   │   ├── stock/[ticker]/     # 종목 상세 (차트 + 매수/매도가)
│   │   │   ├── watchlist/          # 워치리스트
│   │   │   ├── compare/            # 비교 모드
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
├── start.ps1                       # 원클릭 실행 스크립트 (Windows)
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
