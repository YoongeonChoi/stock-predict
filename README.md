# Stock Predict

투자 판단과 포트폴리오 운영을 위한 AI 분석 워크스페이스입니다.

현재 릴리즈: `v2.27.0`

이 프로젝트는 단순한 종목 조회 앱이 아니라 `시장 탐색 -> 종목 해석 -> 포트폴리오 운영 -> 예측 검증` 흐름을 한 제품 안에서 연결하는 것을 목표로 합니다. 프론트는 `Vercel`, 백엔드는 `Render`, 인증과 사용자 데이터는 `Supabase`, 도메인과 DNS는 `Cloudflare`를 기준으로 운영합니다.

현재 서비스는 한국 시장 중심으로 운영되지만, 제품 설명의 중심은 `제약`보다 `지금 실제로 할 수 있는 일`에 둡니다. 로그인 후 계정별 포트폴리오와 관심종목을 분리 관리할 수 있고, 가격·변동성·거시·공시·뉴스 구조화 신호를 결합한 분포형 예측을 기반으로 종목과 비중 추천을 받을 수 있습니다.

## 핵심 가치

- `판단 지원형 워크스페이스`
  - 대시보드, 레이더, 포트폴리오, 리서치가 서로 이어집니다.
- `확률 기반 예측`
  - 점 하나를 찍는 대신 미래 로그수익률의 조건부 분포를 예측합니다.
- `계정별 데이터 분리`
  - 워치리스트, 보유 종목, 자산 기준은 로그인 사용자별로 저장됩니다.
- `무료 스택 우선`
  - 학생 예산에서도 시작 가능한 `Vercel Hobby + Render Free + Supabase Free + Cloudflare Free` 조합을 기본 운영 가정으로 둡니다.

## 현재 사용자 기능

- 대시보드
- Opportunity Radar
- 스크리너
- 종목 검색 / 비교
- 이메일 회원가입 / 로그인
- 계정 프로필 수정 / 이메일 변경 / 이메일 인증 재전송 / 비밀번호 변경 / 비밀번호 재설정 / 세션 종료 / 회원 탈퇴
- 사용자별 관심종목
- 사용자별 포트폴리오 / 자산 프로필
- 포트폴리오 조건 추천 / 최적 추천
- 일일 이상적 포트폴리오
- 월간 캘린더
- 리서치 아카이브
- 다음 거래일 예측
- 무료 KR 확률 엔진
- 과거 유사 국면 예측

## 운영 아키텍처

### 프론트

- 호스팅: `Vercel`
- 런타임: `Next.js`
- 주요 역할:
  - 대시보드, 포트폴리오, 레이더, 인증 UI
  - Supabase 브라우저 세션 유지
  - Render API 호출

### 백엔드

- 호스팅: `Render`
- 런타임: `FastAPI`
- 주요 역할:
  - 분석 엔진 실행
  - 포트폴리오 최적화
  - 대시보드 집계 응답
  - Supabase 토큰 검증

### 인증 / 사용자 데이터

- 서비스: `Supabase`
- 현재 저장 위치:
  - `watchlist`
  - `portfolio_holdings`
  - `portfolio_profile`
- 계정 메타데이터:
  - `username`
  - `full_name`
  - `phone_number`
  - `birth_date`

### DNS / 도메인

- 서비스: `Cloudflare`
- 권장 구조:
  - 프론트: `https://yoongeon.xyz`
  - 백엔드: `https://api.yoongeon.xyz`

## 회원가입 / 로그인 / 계정 보안

현재 인증과 계정 관리는 `/auth`, `/settings`, `/api/account/*` 흐름으로 연결되어 있습니다.

- `/auth`
  - 이메일 회원가입
  - 이메일 로그인
  - 인증 메일 재전송
  - 비밀번호 재설정 메일 요청
  - 복구 세션 기반 새 비밀번호 설정
- `/settings`
  - 아이디, 이름, 전화번호, 생년월일 수정
  - 새 이메일 변경 요청 / 변경 대기 이메일 확인
  - 이메일 인증 상태 확인
  - 현재 세션 정보 확인
  - 이 기기 로그아웃 / 모든 기기 로그아웃
  - 인증 메일 재전송
  - 로그인 상태에서 새 비밀번호 바로 변경
  - 비밀번호 재설정 메일 발송
  - 회원 탈퇴

회원가입 화면은 다음 요구사항을 모두 만족해야 통과하도록 구성되어 있습니다.

- 아이디 중복 확인
- 서버 사전 검증 통과
- 비밀번호 보안 강도 실시간 표시
- 비밀번호 확인 입력
- 이름, 전화번호, 생년월일 필수 입력
- 이메일 인증 기반 가입

회원가입 제출 직전에는 프론트가 `POST /api/account/signup/validate`를 먼저 호출해 아래 항목을 서버에서도 다시 확인합니다.

- 아이디 형식과 중복 여부
- 이메일 형식
- 이름 / 전화번호 / 생년월일 형식
- 비밀번호 강도
- 비밀번호 재확인 일치

### 아이디 규칙

- 영문 소문자로 시작
- 영문 소문자, 숫자, `_`만 허용
- 길이 `4~20`
- 중복 확인 통과 필요

관련 경로:

- 프론트 유틸: `frontend/src/lib/account.ts`
- 백엔드 검증: `backend/app/services/account_service.py`
- 공개 확인 API: `GET /api/account/username-availability`

### 비밀번호 규칙

- 10자 이상
- 영문 대문자 포함
- 영문 소문자 포함
- 숫자 포함
- 특수문자 포함
- 재확인 입력과 일치

프론트는 조건을 모두 만족해야 회원가입 버튼을 활성화합니다.

### 개인정보 처리 흐름

- 이메일 인증과 로그인 세션은 `Supabase Auth`
- 이름 / 전화번호 / 생년월일은 가입 시 `user_metadata`에 저장
- 백엔드는 인증 토큰을 검증한 뒤 `/api/account/me`에서 마스킹된 전화번호, 이메일 인증 상태, 변경 대기 이메일을 함께 반환
- 프로필 수정은 `PATCH /api/account/me`를 통해 서버 검증 후 반영
- 이메일 변경은 로그인 세션에서 새 주소 인증 메일을 발송하는 방식으로 처리하며, 확인 전까지는 기존 이메일이 유지됩니다.
- 회원 탈퇴는 `DELETE /api/account/me`를 통해 현재 아이디 또는 이메일 재입력을 확인한 뒤 진행

운영 주의:

- 현재 `username`은 사용자 경험상 중복 확인을 거치고 서버에서도 조회 검증을 하지만, DB-level unique constraint 기반 별도 프로필 테이블까지는 아직 아닙니다.
- 즉 `회원가입 UX와 현재 운영 안전성`은 확보했지만, 장기적으로는 `user_profiles` 전용 테이블 + unique index + RLS`로 한 단계 더 강화하는 것이 이상적입니다.
- 로그인 전 공개 계정 API(`아이디 중복 확인`, `회원가입 사전 검증`)는 봇성 반복 호출을 줄이기 위해 IP 기준의 짧은 rate limit을 적용합니다.

### 계정 API 계약

- `GET /api/account/me`
  - 현재 로그인 계정 프로필 반환
  - `email_verified`, `email_confirmed_at`, `pending_email`, `email_change_sent_at`, 마스킹된 전화번호 포함
- `PATCH /api/account/me`
  - `username`, `full_name`, `phone_number`, `birth_date` 수정
  - 아이디 형식과 중복 여부를 서버에서 다시 검증
- `DELETE /api/account/me`
  - 현재 아이디가 있으면 아이디, 없으면 이메일을 다시 입력해야 탈퇴 가능
  - `Supabase Auth` 계정을 삭제하며 `watchlist`, `portfolio_holdings`, `portfolio_profile`도 함께 정리
- `POST /api/account/signup/validate`
  - 로그인 전 공개 회원가입 사전 검증
  - 이메일, 아이디, 이름, 전화번호, 생년월일, 비밀번호 규칙을 서버에서 확인
  - 프론트는 이 응답의 정규화 값을 사용해 Supabase 가입을 진행
- `GET /api/account/username-availability`
  - 로그인 전에도 사용 가능한 아이디인지 확인
  - 공개 엔드포인트이므로 짧은 rate limit이 적용됩니다.
  - rate limit에 걸리면 회원가입 화면에서 남은 대기 시간이 바로 안내됩니다.

## 현재 데이터 스택

| 소스 | 역할 | 상태 |
|---|---|---|
| `Yahoo Finance` | 가격 이력, 지수, 기본 펀더멘털 | 기본 사용 |
| `PyKRX` | 한국 수급/보조 입력 | best effort |
| `ECOS` | 한국은행 거시 데이터 | API 키 필요 |
| `KOSIS` | 통계청 계열 통계 보강 | 선택 |
| `OpenDART` | 공시 / 재무 / 주요 이벤트 | 선택 |
| `Naver Search API` | 국내 뉴스 메타데이터 | 선택 |
| `Google News RSS` | 뉴스 헤드라인 | 기본 사용 |
| `FMP` | 가격, 일부 펀더멘털, 일정, 애널리스트, 보도자료 보조 | 선택 |
| `KDI / 한국은행 공식 리서치` | 리서치 아카이브 | 기본 사용 |
| `OpenAI / GPT-4o` | 뉴스·공시 구조화, 서술형 설명 보조 | 선택 |

## 분석 엔진 상세

현재 canonical backbone은 `backend/app/analysis/distributional_return_engine.py` 입니다.

핵심 원칙은 아래 세 가지입니다.

1. 숫자 예측은 `LLM`이 아니라 `확률모형`이 한다.
2. 가격·변동성·상대강도 같은 `숫자 시계열`이 주신호다.
3. 점예측이 아니라 `미래 로그수익률의 조건부 분포`를 직접 예측한다.

### 1. 예측 타깃

기본 타깃은 가격 수준이 아니라 `h` 거래일 뒤 로그수익률입니다.

```text
y_i,t^(h) = log(P_i,t+h / P_i,t)
h in {1, 5, 20}
```

포트폴리오와 랭킹용 보조 타깃은 벤치마크 대비 초과수익률입니다.

```text
y_i,t^ex,(h) = y_i,t^(h) - y_m(i),t^(h)
```

### 2. 가격 / 거래량 / 상대강도 입력

가격 블록은 `OHLCV + VWAP`에서 파생한 수치 특징을 사용합니다.

대표 특징:

```text
r_i,t = log(C_i,t / C_i,t-1)
M_i,t(L) = sum_{k=1..L} r_i,t-k+1
RV_i,t(L) = annualized realized volatility
GK_i,t(L) = Garman-Klass range volatility
VZ_i,t(L) = log-volume z-score
RS_i,t(L) = cumulative relative strength vs benchmark
VWAPGap_i,t = (Close - VWAP) / VWAP
```

즉, 이 엔진은 단순 이동평균 신호보다

- 다중 기간 모멘텀
- 변동성
- 거래량 이상치
- 상대강도
- 종가-VWAP 괴리

를 함께 읽습니다.

### 3. 다중 기간 가격 인코더

금융 시계열은 단기 이벤트와 중기 추세가 동시에 중요하므로, 하나의 lookback만 쓰지 않고 여러 기간을 병렬 처리합니다.

현재 개념은 아래와 같습니다.

```text
h_i,t^(L) = f_L(X_i,t-L+1:t^price)
L in {20, 60, 120, 252}

alpha_i,t^(L) = softmax_L(q^T tanh(W_L h_i,t^(L) + U m_t))
h_i,t^p = sum_L alpha_i,t^(L) h_i,t^(L)
```

의미:

- `20일`: 최근 이벤트와 수급 변화
- `60일`: 중단기 추세
- `120일`: 중기 구조
- `252일`: 연간 추세와 장기 체력

거시 상태 `m_t`를 보고 어떤 기간 표현을 더 믿을지 동적으로 조정합니다.

### 4. 공개시차 안전 거시 압축

거시는 `ECOS + KOSIS + 일부 FMP macro proxy`를 사용합니다.

중요한 점은 `release-safe` 입니다. 예측 시점에 아직 발표되지 않은 값을 쓰면 미래누수이므로, 각 지표는 예측 시점 이전에 공개된 마지막 값만 사용합니다.

```text
x̄_j,t = x_j,τ_j(t)
τ_j(t) = max { s : release_time_j,s <= t }
```

그 뒤 지표별 적절한 변환을 적용합니다.

```text
level형: 100 * (log x̄_j,t - log x̄_j,t-1)
rate/spread형: x̄_j,t - x̄_j,t-1
z_j,t = (u_j,t - μ_j) / (σ_j + ε)
```

KR 거시는 개별 지표를 사람이 손으로 가중합하지 않고 `요인 압축(PCA/factor compression)`을 거칩니다.

```text
m_t = W_macro z_t
```

실무적으로는 `K=4` 정도의 요인으로 충분히 해석 가능하도록 설계합니다.

### 5. 펀더멘털 / 실적 / 공시 블록

펀더멘털과 이벤트는 `FMP + OpenDART`로 보강합니다.

대표 벡터 예시:

```text
f_i,t = [
  earnings_yield,
  book_yield,
  ev_ebitda_yield,
  ROE,
  ROA,
  gross_margin,
  operating_margin,
  revenue_growth,
  EPS_growth,
  debt_to_equity,
  current_ratio,
  estimate_revision,
  EPS_surprise,
  DART_event_flags
]
```

핵심은 `뉴스보다 지속기간이 긴 신호`를 별도 블록으로 다룬다는 점입니다.

### 6. 뉴스 / 공시 이벤트 구조화

`GPT-4o`는 숫자 예측기가 아니라 구조화 추출기로만 사용합니다.

입력:

- Naver 뉴스 제목 / 설명
- FMP press release / news
- OpenDART 주요 공시

출력:

```text
z_n = [
  sentiment,
  surprise,
  uncertainty,
  relevance,
  event_type_one_hot,
  horizon_one_hot
]
```

집계는 시차 감소 가중치로 수행합니다.

```text
e_i,t = sum_n ω_n z_n / (sum_n ω_n + ε)
ω_n = relevance_n * source_weight(n) * exp(-Δt_n / τ_type(n))
```

소스 신뢰도는 일반적으로 아래 순서를 권장합니다.

```text
OpenDART 공시 > 회사 press release > 일반 뉴스 메타데이터
```

### 7. 숫자 주도 게이트 결합

가격 블록이 중심이고, 펀더멘털 / 거시 / 이벤트는 게이트를 통과한 보정치로만 작동합니다.

```text
g_f = a_f * σ(W_f^g [h^p ; f ; m ; e] + b_f^g)
g_m = a_m * σ(W_m^g [h^p ; f ; m ; e] + b_m^g)
g_e = a_e * σ(W_e^g [h^p ; f ; m ; e] + b_e^g)

h_i,t = h_i,t^p + g_f ⊙ φ_f(f_i,t) + g_m ⊙ φ_m(m_t) + g_e ⊙ φ_e(e_i,t)
```

이 설계의 의도는 분명합니다.

- 주신호는 가격
- 거시/공시/뉴스는 `가격 표현을 뒤집는 주체`가 아니라 `보정자`

### 8. Regime gate

시장 상태는 종목 개별 특징만으로 충분하지 않기 때문에, breadth·dispersion·금리 프록시를 함께 씁니다.

```text
Breadth_t = average( Close_i,t > MA20_i,t )
Dispersion_t = cross-sectional variance of recent returns
AD_t = (#up - #down) / N_t
u_t = [m_t, Breadth_t, Dispersion_t, AD_t, ΔTreasury_t, MRP_t]

π_t = softmax(W_r u_t + b_r)
```

현재 체제는 보통 3개로 나눕니다.

- `risk_on`
- `neutral`
- `risk_off`

### 9. 최종 출력: regime-aware Student-t mixture

최종 수익률 분포는 아래 개념식으로 표현됩니다.

```text
p(y_i,t^(h) | F_t)
= sum_{r=1..3} π_t,r
  sum_{k=1..K} ω_i,t,r,k^(h) * StudentT(y ; μ_i,t,r,k^(h), σ_i,t,r,k^(h), ν_i,t,r,k^(h))
```

여기서:

- `π_t,r`: 장세(regime) 확률
- `ω_i,t,r,k`: mixture weight
- `μ`: location
- `σ`: scale
- `ν`: degrees of freedom

이 구조를 고른 이유:

- 금융 수익률은 `fat tail`을 가짐
- 이벤트 구간은 분포가 쉽게 한쪽으로 찌그러짐
- 가우시안 1개로는 비대칭과 tail을 잘 처리하지 못함

### 10. 가격 / 방향 / 지수 예측으로 파생

#### 가격

가격은 수익률 분포 분위수를 가격으로 다시 변환합니다.

```text
q_τ,i,t^(h) = F^{-1}(τ)
P̂_i,t+h^(τ) = P_i,t * exp(q_τ,i,t^(h))
```

현재는 보통 `q10 / q25 / q50 / q75 / q90` 형태로 보여줍니다.

#### 방향

방향은 별도의 휴리스틱 시그모이드가 아니라 같은 분포에서 바로 계산합니다.

```text
P_up   = 1 - F(δ)
P_flat = F(δ) - F(-δ)
P_down = F(-δ)
```

여기서 `δ`는 거래비용과 노이즈를 감안한 작은 중립 구간입니다.

#### 지수 / 증시

지수도 같은 엔진을 씁니다. 차이는 개별 종목보다 breadth와 거시 비중을 더 높게 읽는다는 점입니다.

즉 과거의 `지수 Monte Carlo + LLM 보정` 구조보다, 지금 구조가

- calibration
- tail 처리
- regime 적응성

측면에서 더 타당합니다.

## 포트폴리오 최적화 상세

현재 canonical optimizer는 `backend/app/services/portfolio_optimizer.py` 입니다.

이제 포트폴리오 비중은 단순 선형 점수 나눗셈이 아니라, 분포 엔진에서 나온 기대수익률과 공분산을 함께 사용합니다.

### 목적 함수

첫 버전의 핵심 목적 함수는 아래 개념과 같습니다.

```text
w*_t = argmax_{w >= 0, 1^T w <= 1} (
  w^T μ̂_t
  - η w^T Σ̂_t w
  - τ ||w - w_{t-1}||_1
)
```

의미:

- `μ̂_t`: 20거래일 기대초과수익률 벡터
- `Σ̂_t`: EWMA + shrinkage 공분산
- `η`: 리스크 회피 강도
- `τ`: 회전율 패널티

즉, 수익을 높이되

- 변동성/공분산 리스크
- 기존 포지션과의 괴리
- 과도한 리밸런싱

를 동시에 제어합니다.

### 공분산

공분산은 현재 아래 철학을 사용합니다.

```text
Σ̂_t = λ Σ̂_t^EWMA + (1 - λ) Σ̂_t^shrinkage
```

이는

- 최근 변동성 체제 반영
- 표본 잡음 완화

를 동시에 노린 구성입니다.

### 현재 추천 계층

아래 추천 계열은 모두 같은 optimizer 철학을 공유합니다.

- 조건 추천
- 최적 추천
- 일일 이상적 포트폴리오
- 포트폴리오 모델 패널

즉, 이제 포트폴리오 전체가 `같은 20거래일 분포 스냅샷` 위에서 읽히도록 맞춰져 있습니다.

## 왜 이 구조가 이전 방식보다 나은가

이전 구조에서 약했던 부분은 대체로 아래였습니다.

- 지수 쪽은 Monte Carlo + LLM 설명이 섞여 calibration이 흔들릴 수 있었음
- 종목 쪽은 휴리스틱 가중치에 의존하는 부분이 많았음
- 포트폴리오는 선형 점수 기반 비중 산정 비중이 컸음

현재 구조의 장점:

- `점예측`보다 `분포 예측`이어서 tail과 불확실성 표현이 자연스러움
- `가격이 주신호`이고 뉴스/공시는 보조 신호라 과적합 가능성이 낮음
- 장세 변화에 따라 기간 가중과 regime gate가 적응함
- 종목 예측과 포트폴리오 비중이 같은 엔진 철학 위에서 연결됨

## 현재 주요 라우트

### 인증 / 계정

- `GET /api/account/me`
- `POST /api/account/signup/validate`
- `PATCH /api/account/me`
- `GET /api/account/username-availability`

### 시장 / 분석

- `GET /api/countries`
- `GET /api/country/{code}/report`
- `GET /api/country/{code}/heatmap`
- `GET /api/country/{code}/forecast`
- `GET /api/country/{code}/sector-performance`
- `GET /api/market/indicators`
- `GET /api/market/movers/{code}`
- `GET /api/market/opportunities/{code}`
- `GET /api/stock/{ticker}/detail`
- `GET /api/stock/{ticker}/chart`
- `GET /api/stock/{ticker}/technical-summary`
- `GET /api/stock/{ticker}/pivot-points`
- `GET /api/stock/{ticker}/forecast-delta`
- `GET /api/search`
- `GET /api/ticker/resolve`

### 포트폴리오 / 관심종목

- `GET /api/watchlist`
- `POST /api/watchlist/{ticker}`
- `DELETE /api/watchlist/{ticker}`
- `GET /api/portfolio`
- `PUT /api/portfolio/profile`
- `POST /api/portfolio/holdings`
- `PUT /api/portfolio/holdings/{id}`
- `DELETE /api/portfolio/holdings/{id}`
- `GET /api/portfolio/ideal`
- `GET /api/portfolio/event-radar`
- `GET /api/portfolio/recommendations/conditional`
- `GET /api/portfolio/recommendations/optimal`

### 브리핑 / 캘린더 / 아카이브

- `GET /api/briefing/daily`
- `GET /api/market/sessions`
- `GET /api/calendar/{code}`
- `GET /api/archive`
- `GET /api/archive/accuracy/stats`
- `GET /api/archive/research`
- `GET /api/archive/research/status`
- `POST /api/archive/research/refresh`

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

프론트 `frontend/.env.example` 예시:

```env
NEXT_PUBLIC_API_URL=
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
BACKEND_PROXY_URL=http://localhost:8000
```

메모:

- `SUPABASE_SERVER_KEY`는 백엔드 전용입니다.
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`는 프론트에서만 사용합니다.
- `DB_PATH`는 Render free 기준으로는 `/tmp/stock_predict.db` 같은 임시 경로를 사용합니다.
- `KOSIS_*_STATS_ID`는 별도 API가 아니라 같은 KOSIS 통계자료 API에 전달하는 통계표 ID입니다.

## 무료 배포 권장 구성

- 프론트: `Vercel Hobby`
- 백엔드: `Render Free`
- 인증/사용자 데이터: `Supabase Free`
- DNS/SSL: `Cloudflare Free`

운영 메모:

- Render free는 유휴 시 spin-down 될 수 있습니다.
- Supabase free도 저활동 상태면 pause될 수 있습니다.
- 사용자 핵심 데이터는 Supabase에 있으므로 Render 재기동 시에도 계정 데이터는 유지됩니다.
- 공개 집계형 패널은 timeout과 fallback을 기본 전제로 설계합니다.

## 배포 순서

1. Supabase 프로젝트 준비
   - `Site URL`, `Redirect URLs` 설정
   - `watchlist`, `portfolio_holdings`, `portfolio_profile` 생성
2. Render 백엔드 배포
   - `rootDir=backend`
   - `plan=free`
   - `SUPABASE_URL`, `SUPABASE_SERVER_KEY`, `FRONTEND_URL` 설정
3. Render 기본 주소에서 `/api/health` 확인
4. Vercel 프론트 배포
   - Root Directory: `frontend`
   - `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
5. Cloudflare DNS 연결
6. 도메인 검증 후 재배포

## 로컬 실행

저장소 루트 기준:

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

프론트 제외:

```powershell
& .\venv\Scripts\python.exe .\verify.py --skip-frontend
```

실호출 스모크:

```powershell
& .\venv\Scripts\python.exe .\verify.py --live-api-smoke
```

## 주요 파일

- 에이전트 규칙: `AGENTS.md`
- 디자인 기준: `DESIGN_BIBLE.md`
- 백엔드 버전: `backend/app/version.py`
- 프론트 버전: `frontend/package.json`
- 변경 이력: `CHANGELOG.md`
- 공통 분포 엔진: `backend/app/analysis/distributional_return_engine.py`
- 포트폴리오 optimizer: `backend/app/services/portfolio_optimizer.py`

## 에러 코드

| 코드 | 의미 |
|---|---|
| `SP-1001` | OpenAI API 키 미설정 |
| `SP-1003` | 추가 공공데이터 API 키 미설정 |
| `SP-1004` | ECOS API 키 미설정 |
| `SP-1005` | FMP API 키 미설정 |
| `SP-1006` | Supabase 서버 키 미설정 |
| `SP-2001`~`SP-2008` | 외부 데이터 소스 실패 |
| `SP-3001`~`SP-3007` | 분석 파이프라인 실패 |
| `SP-4001`~`SP-4005` | LLM / OpenAI 실패 |
| `SP-5001`~`SP-5009` | DB / 아카이브 / 캐시 / 시스템 실패 |
| `SP-5010`~`SP-5018` | 티커 해석, 브리핑, 세션, 포트폴리오 추천, timeout 실패 |
| `SP-5019` | 계정 프로필 / 아이디 확인 실패 |
| `SP-6001`~`SP-6013` | 요청 형식 / 파라미터 검증 실패 |
| `SP-6014` | 로그인 필요 |
| `SP-6015` | 계정 프로필 입력 형식 오류 |
| `SP-6016` | 공개 계정 API rate limit 초과 |
| `SP-9999` | 예기치 못한 서버 오류 |

운영 메모:

- 공개 대시보드에서 특정 패널이 오래 멈추면 `SP-5018` timeout 응답과 fallback 문구를 먼저 확인합니다.
- 인증 관련 문제가 나면 `/api/account/me`와 `/api/account/username-availability` 계약부터 확인하는 것이 가장 빠릅니다.

## 버전 정책

- 사용자 동작이 바뀌면 `README.md`, `CHANGELOG.md`, 관련 테스트를 함께 갱신합니다.
- API 응답이 바뀌면 프론트 타입과 호출부를 함께 수정합니다.
- 릴리즈 가치가 있는 기능 추가는 백엔드/프론트 버전을 함께 올립니다.
