# Stock Predict

투자 판단과 포트폴리오 운영을 위한 AI 분석 워크스페이스입니다.

현재 릴리즈: `v2.52.8`

이 프로젝트는 단순한 종목 조회 앱이 아니라 `시장 탐색 -> 종목 해석 -> 포트폴리오 운영 -> 예측 검증` 흐름을 한 제품 안에서 연결하는 것을 목표로 합니다. 프론트는 `Vercel`, 백엔드는 `Render`, 인증과 사용자 데이터는 `Supabase`, 도메인과 DNS는 `Cloudflare`를 기준으로 운영합니다.

현재 서비스는 한국 시장 중심으로 운영되지만, 제품 설명의 중심은 `제약`보다 `지금 실제로 할 수 있는 일`에 둡니다. 로그인 후 계정별 포트폴리오와 관심종목을 분리 관리할 수 있고, 가격·변동성·거시·공시·뉴스 구조화 신호를 결합한 분포형 예측을 기반으로 종목과 비중 추천을 받을 수 있습니다.

`v2.52.7`부터 dense workspace 화면은 공통 `main / aside` 정렬 축을 공유하고, 표본 부족이나 부분 지연 상태에서는 거대한 빈 카드 대신 작업 맥락이 보이는 상태 카드로 먼저 보여주도록 정리했습니다. 그래서 대시보드, 레이더, 포트폴리오, 캘린더, 아카이브, 예측 연구실의 첫 인상이 더 일관되게 유지됩니다. 내비게이션의 테마 토글도 초기 hydration 기준을 맞춰, 로컬과 개발 환경에서 아이콘이나 정렬이 흔들리지 않게 정리했습니다.

## AI / Reviewer Quick Start

이 저장소를 `GitHub 링크만` 받고 읽는 사람이나 AI는 아래 순서로 보면 가장 빠릅니다.

1. `README.md`
2. `AGENTS.md`
3. `DESIGN_BIBLE.md`
4. `AI_CONTEXT.md`
5. `ARCHITECTURE.md`
6. `API_CONTRACT.md`
7. `backend/app/main.py`
8. `frontend/src/lib/api.ts`
9. `verify.py`

추가로 실행 전제를 바로 확인할 수 있도록 예시 환경 변수를 함께 둡니다.

- 백엔드 예시: `backend/.env.example`
- 프론트 예시: `frontend/.env.example`

이 구성이 있으면 AI는 링크만으로도 `구조 평가`, `API 계약 검토`, `회귀 위험 판단`, `문서-구현 일치성 확인`을 꽤 정확하게 할 수 있습니다. 다만 `실제 배포 환경 변수`, `외부 API quota`, `실운영 체감 속도`, `브라우저 렌더링 품질`까지 완전히 확인하려면 preview 또는 배포 URL이 있으면 더 좋습니다.

## 핵심 가치

- `판단 지원형 워크스페이스`
  - 대시보드, 레이더, 포트폴리오, 리서치가 서로 이어집니다.
- `확률 기반 예측`
  - 점 하나를 찍는 대신 미래 로그수익률의 조건부 분포를 예측합니다.
- `학습형 fusion + graph context`
  - prior backbone은 유지한 채, 실측 prediction log가 충분한 horizon만 learned fusion과 경량 graph context로 보강합니다.
- `보정된 확신도`
  - 표시 confidence는 단순 heuristic 점수가 아니라, 실제 적중률과 맞도록 보정된 확률을 사용합니다.
  - 표본이 충분해지면 horizon별 calibrator가 `empirical sigmoid`에서 `isotonic + reliability bin` 단계로 승격됩니다.
- `계정별 데이터 분리`
  - 워치리스트, 보유 종목, 자산 기준은 로그인 사용자별로 저장됩니다.
- `무료 스택 우선`
  - 학생 예산에서도 시작 가능한 `Vercel Hobby + Render Free + Supabase Free + Cloudflare Free` 조합을 기본 운영 가정으로 둡니다.

## 버전 관리 정책

이 프로젝트는 `MAJOR.MINOR.PATCH` 버전 규칙을 사용합니다.

- `PATCH`
  - 버그 수정
  - timeout / fallback / 운영 안정화
  - 문서, 테스트, 진단 보강
  - 기존 흐름을 바꾸지 않는 UI 정리
- `MINOR`
  - 새 사용자 기능
  - 새 페이지 / 새 API / 새 응답 필드
  - 예측 엔진, 포트폴리오 엔진의 의미 있는 개선
  - 계정, 가입, 내보내기 같은 핵심 흐름 확장
- `MAJOR`
  - 기존 계약을 깨는 API 변경
  - 라우트 / 메뉴 / 데이터 구조의 비호환 변경
  - 운영 전환 안내나 별도 마이그레이션이 필요한 변경

릴리즈를 올릴 때는 아래 파일을 항상 같이 맞춥니다.

- `backend/app/version.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `README.md`의 현재 릴리즈 표기
- `CHANGELOG.md` 최상단 항목

또한 `/settings`의 시스템 준비 상태 카드에서 프론트 버전과 백엔드 버전이 다르게 보이면, 코드는 머지되었더라도 실제 배포 전파는 아직 끝나지 않은 상태로 봅니다.

## 현재 사용자 기능

- 대시보드
- 대시보드 공개 첫 화면
  - `/`는 선택 시장 현황, 핵심 수치, 오늘의 포커스, 마지막 갱신 시각을 서버에서 먼저 채운 뒤 세부 패널을 이어받습니다.
- Opportunity Radar
  - 현재 KR 레이더는 KRX 상장사 전종목을 1차 스캔하고, 실제 시세 확보 수를 분리해 보여준 뒤 상위 종목만 정밀 분석
  - 첫 decision block에는 시장 국면, 전체 스캔 수, 실제 시세 확보 수, 표시 후보 수, 마지막 갱신 시각을 먼저 보여주고, 후보 카드에는 보정 confidence와 probability edge, analog support를 함께 노출합니다.
  - 홈과 `/radar`의 KR first screen은 같은 opportunities snapshot 기준으로 맞추고, usable하지 않은 placeholder partial은 초기 결과로 그대로 고정하지 않습니다.
- 국가 리포트 / PDF / CSV 내보내기
  - 서버 워밍업이나 외부 데이터 지연이 길어질 때는 raw timeout 대신 1차 시장 스냅샷 기반 부분 보고서를 먼저 반환
  - 공개 숫자 근거는 `macro_claims` 구조체로 분리해 보여주고, `market_summary`는 숫자·퍼센트·목표가 없는 정성 서술만 유지합니다.
- 스크리너
  - `/screener`는 최초 진입 시 latest close 기준 seeded 결과를 먼저 보여주고, 사용자 실행 결과와 실제 결과 없음 상태를 구분합니다.
- 종목 검색 / 비교
- 이메일 회원가입 / 로그인
- 계정 프로필 수정 / 이메일 변경 / 이메일 인증 재전송 / 비밀번호 변경 / 비밀번호 재설정 / 세션 종료 / 회원 탈퇴
- 사용자별 관심종목
- 사용자별 포트폴리오 / 자산 프로필
- 포트폴리오 조건 추천 / 최적 추천
  - 신규 확대 후보와 함께 줄이거나 보류할 defensive 후보도 같은 추천 인터페이스 안에서 확인할 수 있습니다.
- 일일 이상적 포트폴리오
- 월간 캘린더
  - `/calendar`는 다음 3개 일정과 official / estimated 상태를 first screen에 먼저 보여주고, 월간 보드는 그 아래에서 이어집니다.
  - 경제 일정과 실적 일정은 병렬 source fetch로 가져오고, 한 source가 늦어도 확인된 실제 일정과 월간 핵심 일정부터 먼저 보여줍니다.
  - 외부 캘린더 공급이 제한되면 `partial + fallback_reason=calendar_external_source_unavailable` 상태로 월간 핵심 일정 중심 보드를 유지합니다.
- 리서치 아카이브
  - 한국, 미국, 유로존, 일본 공식 기관 리포트를 지역별로 다시 볼 수 있습니다.
- 아카이브 공개 첫 화면
  - `/archive`는 최신 기관 리포트 2개를 기관, 발행일, 한 줄 요약, 원문/PDF 액션과 함께 서버에서 먼저 보여줍니다.
  - 공개 리포트 카드는 HTML 원문이 아니라 정리된 `summary_plain`만 렌더해 first screen에 raw 마크업이 섞이지 않게 유지합니다.
- 대시보드 / 레이더 / 캘린더 / 포트폴리오 / 설정의 로딩·지연 상태
  - 큰 빈 카드 대신 무엇을 불러오는 중인지 설명하는 상태 카드와 재시도 경로를 먼저 보여 줍니다.
- 공개 페이지 SSR + 감사 표시
  - `/`, `/radar`, `/calendar`, `/archive`, `/screener`는 first screen 핵심 값과 `generated_at / partial / fallback_reason` 기반 audit strip을 서버 우선으로 렌더합니다.
  - `opportunity radar` 응답은 내부 진단용 `snapshot_id`, `fallback_tier`를 함께 포함해 홈과 레이더의 snapshot 일치 여부를 추적합니다.
- 로그아웃 미리보기
  - `/portfolio`, `/watchlist`는 빈 인증 벽 대신 public data 기반 demo cards와 로그인 CTA를 first screen에 배치합니다.
  - 익명 first paint에서는 auth loading보다 preview가 먼저 렌더되고, user-specific API 호출은 세션이 확인된 뒤에만 시작합니다.
- 다음 거래일 예측
- 무료 KR 확률 엔진
- 과거 유사 국면 예측
- 예측 연구실
  - `1D / 5D / 20D` 실측 성과
  - empirical calibrator 샘플 수, Brier score, reliability gap 확인
  - horizon별 learned fusion 상태, graph coverage, prior 대비 Brier delta, 평균 blend weight 확인
  - learned fusion runtime summary를 profile refresh 결과에서 재사용해, 연구실 first screen이 무거운 샘플 재집계 때문에 오래 비지 않도록 유지합니다.
  - `/lab` first screen은 공개 검증 스냅샷과 최근 실패 사례를 서버에서 먼저 채워 추천과 검증 흐름이 같은 제품 안에서 이어지게 합니다.

공개 API의 운영 원칙도 현재 구조에 맞춰 정리되어 있습니다.

- 공개 읽기 페이지는 first screen을 `빈 카드 + skeleton-only + raw 브라우저 에러`로 두지 않고, 서버에서 최소 결과 또는 `200 + partial` 상태를 먼저 렌더합니다.
- 공개 서버 페이지(`/`, `/radar`, `/calendar`, `/archive`, `/screener`, `/lab`, `/portfolio`, `/watchlist`)는 `export const revalidate = 0`으로 request-time SSR을 강제하고, 각 공개 fetch는 개별 `next.revalidate` 캐시를 유지합니다. 그래서 Vercel build의 `Collecting page data` 단계가 Render live API에 직접 매달리지 않게 유지합니다.
- 공개 카드 헤더는 가능한 한 `generated_at`, `partial`, `fallback_reason`을 같은 audit strip 규칙으로 노출해 freshness와 fallback 상태를 즉시 읽을 수 있게 유지합니다.
- 공개 숫자 문장은 `macro_claims` 같은 구조화 근거 필드에서만 렌더하고, 자유 서술 요약은 정성 문장으로만 유지합니다. 숫자가 섞인 자유 서술은 백엔드 validation 단계에서 공개 서술로 승격하지 않습니다.
- 프론트의 공개 읽기 fetch는 `revalidate` 기반 서버 fetch를 우선 사용하고, 브라우저 인증 호출과 저장성 호출만 계속 `no-store`로 유지합니다.
- 프론트의 공개 서버 fetch는 route별 timeout과 page-level timebox를 함께 사용합니다. 기본 fetch 예산은 `8초`, `opportunity radar`는 `18초`, `screener seed`는 `12초`, `prediction lab / research archive`는 `10초`를 유지하고, 각 server page는 더 짧은 화면 예산 안에서 `timeboxServerPromise`로 first paint를 보호합니다. 그래서 느린 backend 응답이 있어도 `/`, `/calendar`, `/archive`, `/lab`, `/portfolio`, `/watchlist`가 서버에서 너무 오래 붙잡히지 않고 부분 렌더로 먼저 내려갑니다.
- 백엔드 공용 캐시의 `get_or_fetch`도 이제 첫 호출자부터 `wait_timeout`을 적용합니다. 덕분에 cold cache 첫 요청이 곧바로 긴 live fetch에 매달리지 않고, `calendar`, `daily briefing`, `prediction accuracy`, `prediction lab` 같은 경로가 첫 요청부터 `fallback + background cache warmup` 구조를 유지합니다.
- 운영 smoke는 `calendar`, `prediction lab`, `/radar`, `/screener`, `/calendar`, `/archive`, `/lab`, `/portfolio`, `/watchlist`까지 함께 확인해 공개 화면 전반의 first screen 회귀를 더 빨리 잡습니다.
- 공용 cache 레이어는 SQLite cache table 앞에 프로세스 메모리 캐시를 함께 두고, cache read/write는 짧은 SQLite timeout으로 fast-fail 처리합니다. 그래서 같은 공개 스냅샷을 여러 화면이 연달아 읽을 때 SQLite 락 때문에 20~30초씩 대기하기보다, 최근 snapshot을 먼저 재사용하고 느린 DB 접근은 fallback으로 넘기도록 유지합니다.
- `country report`, `heatmap`, `screener`, `opportunity radar` 같은 집계형 경로는 느린 외부 소스 하나 때문에 전체 화면이 멈추지 않도록 timeout과 부분 fallback을 함께 둡니다.
- KR `screener` 기본 조회는 운영 배포에서 느린 동적 유니버스 조회보다 검증된 기본 종목군과 bulk quote 경로를 먼저 사용해, 공개 경로 timeout이 길게 이어지지 않도록 유지합니다.
- KR `screener`의 소규모 공개 요청은 yfinance batch coverage가 조금 부족하더라도 전체 Naver 시총 페이지 scrape로 바로 내려가지 않고, 확보된 bulk quote만으로 먼저 응답합니다.
- KR `screener` 기본 조회는 후보 종목 수도 `limit` 기준으로 바로 줄여, `limit=1` 같은 작은 요청이 내부적으로 30개 이상 종목 batch를 불필요하게 들고 가지 않게 유지합니다.
- KR `screener` 기본 공개 경로는 cold cache에서 먼저 `Naver 시총 대표 페이지` snapshot partial을 돌려주고, 뒤에서 전체 cache를 채우는 2단계 구조를 사용합니다. Render 배포 직후 첫 호출도 read timeout 대신 `200 + partial`로 살아남게 유지하는 쪽에 초점을 둡니다.
- KR 기회 레이더의 빠른 경로는 `KRX 상장사 목록 캐시 -> 운영용 기본 종목군 fallback` 순서로 내려가므로, cold start 직후에도 `총 8개 스캔`처럼 과도하게 작은 숫자로 고정되지 않게 관리합니다.
- KR 기회 레이더의 quick fallback은 전체 유니버스를 포기하는 것이 아니라, 초기 응답에서는 `대표 1차 스캔`만 먼저 계산하고 전체 스캔은 후속 재조회에서 다시 시도하도록 설계합니다.
- KR 기회 레이더의 quick 경로는 이제 `KOSPI/KOSDAQ 대표 시총 페이지 -> sampled universe quote screen -> lightweight snapshot` 순서로 usable 후보를 먼저 확보합니다. 그래서 Render free cold start에서도 representative quick 후보가 먼저 살아나고, sampled `yfinance` quote screen은 그 다음 fallback으로만 사용합니다.
- KR 기회 레이더 공개 API는 이제 `cached full -> cached quick -> fresh quick -> background full warmup` 순서로 응답합니다. 그래서 같은 요청 안에서 `full`과 `quick`가 서로 느리게 물고 늘어지던 경로를 줄이고, 다음 재조회에서는 warmup된 full cache를 더 빨리 재사용할 수 있게 유지합니다.
- 기관 리서치 아카이브는 이제 `KDI / 한국은행 / Federal Reserve / ECB / BOJ` 공식 소스를 같은 화면에서 지역별로 보여주고, 현재 운영 기준 활성 소스만 상태 카드와 목록에 함께 반영합니다.
- 프론트의 공통 오류 배너는 더 이상 raw `Failed to fetch`를 그대로 보여주지 않고, 백엔드 워밍업·네트워크 지연을 한국어 안내와 재시도 흐름으로 정리합니다.
- `설정 및 시스템`은 `시장 세션 / 시스템 진단 / 기관 리서치 상태`를 독립적으로 불러오므로, 한 패널이 늦어도 전체 페이지가 같이 빈 상태로 멈추지 않게 유지합니다.
- KR 소량 시세 조회는 더 이상 항상 시장 전체 시가총액 페이지를 끝까지 긁지 않고, 먼저 가벼운 batch quote 경로를 사용합니다. 그래서 `섹터 퍼포먼스`, 요약 카드 같은 첫 진입이 Render free 환경에서도 덜 무겁게 시작됩니다.
- 종목 상세 분석은 요약 생성과 이벤트 구조화를 병렬로 처리하고, 느린 AI 보조 단계는 timeout fallback으로 전환해 정량 시계열 분석 결과가 먼저 보이도록 유지합니다.
- 종목 상세 상단의 공개 판단 요약은 `public_summary` 구조를 사용합니다. 여기에는 `근거`, `반대 근거`, `지금 바로 사지 않는 이유`, `무효화 조건`, `데이터 품질`, `신뢰 메모`를 먼저 보여주고, `fair value`, `매수 구간`, `매도 구간`, `애널리스트 목표가` 같은 sell-side 문구는 아래 상세 가이드 영역에만 남깁니다.
- 종목 상세의 `SP-4004` timeout fallback은 부분 응답을 허용하되, 공개 판단 요약과 트레이드 플랜이 영어 내부 문구를 그대로 노출하지 않도록 한국어 운영 문장으로 정리합니다.
- 종목 상세 `/api/stock/{ticker}/detail`은 이벤트 날짜를 UTC 기준으로 정규화해 계산하며, 상세 분석이 timeout 또는 조합 오류로 실패해도 최근 저장 스냅샷이 있으면 `200 + partial + fallback_reason=stock_cached_detail`로 먼저 내려 화면이 통째로 비지 않게 유지합니다.
- startup 보강 작업은 정해진 시간 안에 끝나지 않아도 헬스 상태를 즉시 `degraded`로 내리지 않고, 본 서비스 응답을 먼저 살린 뒤 다음 워밍업/재요청에서 다시 보강되도록 유지합니다.
- 예측 정확도 집계와 관련된 SQLite 경로는 동일한 `WAL + busy_timeout` 설정을 공유해, startup refresh나 집계 화면이 `database is locked`로 불안정해지는 구간을 줄였습니다.
- 운영 스모크 검증은 현재 제품 기준선에 맞춰 KR 대표 종목(`005930.KS`, `000660.KS`) 중심으로 확인합니다.

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
  - 필요 시 보안 확인 코드(reauth nonce) 요청 후 즉시 비밀번호 변경
  - 비밀번호 재설정 메일 발송
  - 저장 전 입력 상태 경고 / 섹션별 입력 초기화
  - 회원 탈퇴

보호된 페이지에서 세션이 오래되어 `401 / SP-6014`가 발생하면 프론트는 `AuthProvider`에서 현재 Supabase 세션을 한 번 더 재검증합니다. 복구 가능한 세션이면 토큰을 다시 맞추고, 복구되지 않으면 인증 상태를 정리한 뒤 각 페이지를 로그인 유도 상태로 자연스럽게 내립니다.

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
- 인증 메일 재전송과 비밀번호 재설정 메일은 `/auth`, `/settings` 모두에서 같은 60초 cooldown을 적용해 같은 메일 액션이 짧은 시간에 반복되지 않도록 안내합니다.
- 이메일 변경 요청도 새 주소로 인증 메일을 보내는 흐름이므로 같은 60초 cooldown 기준을 적용합니다.
- `/settings`에서 비밀번호를 즉시 바꿀 때 세션이 오래된 상태라면 Supabase가 추가 확인을 요구할 수 있어, 같은 패널 안에서 보안 확인 코드를 요청하고 입력한 뒤 바로 저장할 수 있습니다.
- `/settings` 계정 관리 패널은 저장하지 않은 입력이 남아 있으면 상단 경고 배너와 브라우저 이탈 보호를 함께 표시하고, 프로필/이메일/비밀번호/탈퇴 확인 입력을 섹션별로 바로 초기화할 수 있습니다.

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
  - `/settings`에서 아이디를 바꿀 때도 같은 재시도 안내와 버튼 잠금 UX가 적용됩니다.
  - `429` 응답에는 `Retry-After` 헤더가 함께 내려와 클라이언트가 남은 대기 시간을 표준적으로 읽을 수 있습니다.
- 인증 메일 재전송 / 비밀번호 재설정 메일
  - `/auth`, `/settings` 모두 같은 한국어 helper text와 남은 초 표시를 사용합니다.
  - 같은 메일 액션은 60초 동안 다시 실행되지 않으며, 버튼이 잠시 잠깁니다.
  - 서버 rate limit과 별개로, 메일 액션 자체는 프론트가 즉시 cooldown을 보여 불필요한 반복 클릭을 줄입니다.
- `/settings` 즉시 비밀번호 변경
  - 기본적으로는 로그인 세션에서 바로 새 비밀번호를 저장합니다.
  - 세션이 오래된 경우에는 같은 패널 안에서 `보안 확인 코드 보내기`를 실행하고, 메일로 받은 reauth nonce를 입력한 뒤 저장합니다.
  - 이 nonce 요청도 60초 cooldown을 적용해 반복 클릭을 줄입니다.
- 이메일 변경 요청
  - 새 이메일 주소로 인증 메일을 발송하는 요청도 같은 60초 cooldown을 적용합니다.
  - 변경 대기 중인 이메일이 이미 있으면 같은 주소로 다시 요청하지 않도록 막고, 다른 주소로 바꿀 때도 짧은 재시도 제한을 함께 안내합니다.
- `/settings` 편집 보호
  - 프로필, 이메일 변경, 비밀번호 변경, 회원 탈퇴 입력 중 하나라도 작성되면 상단에 저장 전 경고가 표시됩니다.
  - 이 상태에서 새로고침이나 탭 종료를 시도하면 브라우저 기본 이탈 경고가 나타납니다.
  - 각 섹션에는 별도의 `입력 초기화` 버튼이 있어 저장하지 않은 내용만 빠르게 비울 수 있습니다.

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
| `KDI / 한국은행 / Federal Reserve / ECB / BOJ 공식 리서치` | 리서치 아카이브 | 기본 사용 |
| `OpenAI / GPT-4o` | 뉴스·공시 구조화, 서술형 설명 보조 | 선택 |

## 분석 엔진 상세

현재 canonical backbone은 `backend/app/analysis/distributional_return_engine.py` 입니다. 현재 운영 모델 버전은 `dist-studentt-v3.3-lfgraph`이며, prior backbone 위에 learned fusion과 경량 graph context를 조건부로 얹는 구조를 사용합니다.

핵심 원칙은 아래 세 가지입니다.

1. 숫자 예측은 `LLM`이 아니라 `확률모형`이 한다.
2. 가격·변동성·상대강도 같은 `숫자 시계열`이 주신호다.
3. 점예측이 아니라 `미래 로그수익률의 조건부 분포`를 직접 예측한다.

### 0. prior backbone + learned fusion + graph context

현재 엔진은 기존 분포 엔진을 버리지 않고, horizon별로 `prior backbone -> learned fusion -> graph context blend` 순서로 보강합니다.

- `prior backbone`
  - 가격·변동성·거시·펀더멘털·이벤트 신호를 결합한 기존 분포형 예측
- `learned fusion`
  - `prediction_records`에 저장된 실측 로그에서 horizon `1 / 5 / 20`별 pure `numpy` L2 logistic profile을 다시 맞춰 prior score를 보정
  - 표본 부족 기준은 `MIN_FUSION_SAMPLES = 36`, `MIN_DIRECTION_CLASS_COUNT = 8`
- `graph context`
  - full GNN 대신 `FMP peers -> same sector/industry -> rolling return correlation` 순서로 경량 peer context를 만든 뒤, coverage가 있을 때만 blend에 반영

현재 blend 정책은 아래를 따릅니다.

- profile 없음 또는 표본 부족: `prior_only`
- profile 있음, graph 없음: `learned_blended`
- profile 있음, graph 있음: `learned_blended_graph`
- blend weight
  - `clip((sample_count - 24) / 120, 0.0, 0.65) * data_quality_support * max(0.35, graph_coverage)`

중요한 점은 learned fusion이 기존 분포 예측을 대체하지 않는다는 것입니다. 기존 `q10 / q25 / q50 / q75 / q90`, `p_up / p_flat / p_down`, confidence calibration loop는 그대로 유지하고, horizon별 mean/tilt/score 입력만 더 정교하게 보강합니다.

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

### 3-1. 표시 confidence와 calibration

현재 화면에 노출되는 confidence는 “100점에 가까워 보이게 만드는 점수”가 아니라, 실제 적중률과 맞도록 보정된 확률입니다. 먼저 분포 엔진, analog 백테스트, 시장 regime, 방향 확률 차이, 모델 간 합의, 데이터 품질, 이벤트 불확실성, 예측 변동성을 합쳐 raw support를 만든 뒤, horizon별 calibrator로 다시 눌러 UI confidence를 계산합니다.

```text
raw_confidence_h
  = 100 * (
      0.35 d_h
    + 0.18 a_h
    + 0.08 r_h
    + 0.12 e_h
    + 0.10 g_h
    + 0.07 q_h
    + 0.05 (1 - u_h)
    + 0.05 (1 - v_h)
  )

display_confidence_h = 100 * G_h(raw_confidence_h)
```

여기서

- `d_h`: 분포 엔진 raw confidence support
- `a_h`: analog win rate, effective sample size, profit factor, dispersion 기반 support
- `r_h`: 시장 regime의 명확도
- `e_h`: `up/down` 확률 차이
- `g_h`: 분포/analog/regime 방향 합의 정도
- `q_h`: 데이터 품질과 가용성
- `u_h`: 이벤트 불확실성
- `v_h`: 예측 변동성 대비 기준 변동성

를 뜻합니다.

현재는 `bootstrap prior -> empirical sigmoid -> isotonic 승격` 구조를 사용합니다. 처음에는 horizon별 bootstrap prior가 confidence를 보수적으로 잡고, 이후 `prediction_records`에 쌓이는 실측 결과를 바탕으로 `next_day / 5D / 20D`별 empirical sigmoid가 다시 맞춰집니다. 표본 수와 클래스 균형이 충분히 쌓이면, 그 위에 horizon별 isotonic 보정을 한 번 더 얹어 reliability gap을 더 줄입니다. 즉, 시간이 지날수록 단순 heuristic이 아니라 실제 적중 로그가 confidence를 재학습합니다. learned fusion이 함께 활성화되더라도 confidence loop의 canonical 기준선은 그대로 유지됩니다.

운영 루프는 다음과 같습니다.

```text
예측 저장
  -> prediction_records에 calibration snapshot 함께 적재
  -> calibration_json 안에 fusion_features / graph_context / fusion_metadata 중첩 저장
  -> target_date 이후 actual_close 평가
  -> horizon별 empirical sigmoid 재학습
  -> horizon별 learned fusion profile refresh
  -> 표본이 충분하면 isotonic + reliability bin 재계산
  -> 다음 예측의 표시 confidence에 다시 반영
```

표본이 충분해지기 전에는 과신을 막기 위해 bootstrap prior 비중과 confidence 상한을 유지합니다. 반대로 실측 로그가 늘어나면 bootstrap prior에서 점차 벗어나 empirical sigmoid가 더 큰 영향을 갖고, 이후에는 isotonic과 reliability bin이 “어느 confidence 구간에서 실제 적중률이 얼마나 어긋나는지”까지 다시 눌러줍니다. 중요한 점은 “점수를 높게 보이게” 하는 것이 아니라, 예를 들어 `70점이면 실제로 약 70% 수준으로 맞는 점수`가 되게 만드는 것입니다.

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

### selection score와 confidence floor

레이더 후보와 포트폴리오 신규 편입 정렬도 단순 중복합산에서 정리했습니다. 이제 selection score는 `기대초과수익률 + 보정 confidence + 확률 격차 + tail ratio + regime 정렬 + analog 확인 + 데이터 품질 - downside - 예측 변동성`을 중심으로 계산합니다.

```text
selection
= 100 * clip(
    0.30 expected_excess_return
  + 0.25 calibrated_confidence
  + 0.15 probability_edge
  + 0.10 tail_ratio
  + 0.08 regime_alignment
  + 0.07 analog_support
  + 0.05 data_quality
  - 0.20 downside
  - 0.12 forecast_volatility
)
```

이전처럼 `directional_score` 안에 이미 들어 있는 기대수익, confidence, edge를 다시 바깥 점수에서 중복 합산하지 않고, action과 execution bias는 tie-breaker 수준의 작은 보정으로만 남겼습니다. 또한 `press_long`, `lean_long`, `accumulate`, `breakout_watch` 가점은 절반 이하로 줄이고, `stay_selective`, `reduce_risk`, `capital_preservation`은 suppress 대상이 아니라 중립~약한 양수의 결정 중요도로 다시 올려 방어 판단이 상단 후보에서 사라지지 않게 맞췄습니다.

포트폴리오 추천과 이상적 포트폴리오도 같은 방향을 따릅니다. defensive bias 후보를 초기 필터에서 바로 버리지 않고, 기존 보유 종목이면 감축/보류 판단을 유지하며, 신규 비중은 `target_weight_pct = 0`으로 고정해 확장을 막습니다. 그래서 현재 인터페이스 안에서 “늘릴 종목”과 “줄이거나 보류할 종목”을 함께 읽을 수 있습니다.

또한 신규 레이더 후보와 일일 이상적 포트폴리오 편입 후보에는 `confidence floor`를 둡니다. 현재 기본값은 `62점`이며, 이 기준을 넘지 못하면 기대수익이 높아도 신규 편입 후보에서 제외합니다. 이 방식은 기대수익만 높고 신뢰도가 낮은 후보가 상단으로 튀는 현상을 줄이고, 사용자가 보는 confidence와 실제 성과를 더 가깝게 맞추는 데 목적이 있습니다.

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
- 표시 confidence를 실측 적중 로그로 계속 다시 맞춰, 시간이 갈수록 confidence와 실제 적중률의 간격을 줄임

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
  - `public_summary`는 공개 판단 요약 전용 블록입니다.
  - 필드: `summary`, `evidence_for`, `evidence_against`, `why_not_buy_now`, `thesis_breakers`, `data_quality`, `confidence_note`
  - 공개 요약은 가격대/목표가 중심 문구보다 근거와 실패 조건을 먼저 보여줍니다.
  - `generated_at`, `partial`, `fallback_reason`
    - freshness / fallback audit 메타
  - `fallback_reason=stock_cached_detail`
    - 상세 계산이 timeout 또는 조합 오류로 끝나지 않을 때 최근 저장 스냅샷을 먼저 보여줍니다.
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
- 로그아웃 상태 `/portfolio`, `/watchlist`의 first paint는 공개 스크리너가 아니라 공개 레이더 snapshot을 미리보기 데이터로 사용합니다. 그래서 익명 preview가 seed table 결측치에 흔들리지 않고, 같은 시장 snapshot 위에서 포트폴리오/관심종목 CTA를 먼저 보여줍니다.
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
- `GET /api/research/predictions`
  - `/lab`의 canonical 검증 API입니다.
  - `fusion_profiles`, `graph_context_summary`, `fusion_status_summary`를 함께 반환합니다.
  - 공개 경로 기본값은 `refresh=false`로 두고, 상세 보강이 필요할 때만 명시적으로 refresh를 올립니다.

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
STARTUP_PREDICTION_ACCURACY_REFRESH=false
STARTUP_PREDICTION_ACCURACY_REFRESH_TIMEOUT=20
STARTUP_RESEARCH_ARCHIVE_SYNC=false
STARTUP_RESEARCH_ARCHIVE_SYNC_TIMEOUT=35
STARTUP_LEARNED_FUSION_REFRESH=false
STARTUP_LEARNED_FUSION_REFRESH_TIMEOUT=25
STARTUP_MARKET_OPPORTUNITY_PREWARM=false
STARTUP_MARKET_OPPORTUNITY_PREWARM_TIMEOUT=45
STARTUP_BACKGROUND_TASK_CONCURRENCY=1
STARTUP_ALLOW_HEAVY_RENDER_JOBS=false
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
- 공개 대시보드와 스크리너는 Render free 환경에서 대표 표본 + 캐시 + 부분 응답 fallback을 우선합니다.
- `market opportunities`는 현재 KR 레이더 유니버스를 1차 quote screen으로 먼저 스캔하고, 상위 종목만 정밀 분포 분석하는 2단계 구조를 사용합니다.
- KR 기본 스크리너는 개별 종목별 시세 호출보다 `kr_market_quote_client` bulk quote 경로를 먼저 사용하고, cold cache면 `Naver 시총 대표 페이지` snapshot partial을 먼저 보여준 뒤 full cache를 채우는 방향으로 설계합니다.
- FMP KR 스크리너가 막히더라도 레이더는 가능한 한 `krx_listing` 또는 운영 fallback 유니버스로 내려가 1차 후보를 먼저 보여주며, 현재 기본 fallback 종목군은 `201개`입니다.
- 큰 KR fallback 유니버스에서는 응답 안정성을 우선해 `1차 전수 스캔 결과`를 먼저 반환하고, 정밀 분석은 상위 후보나 후속 상세 화면에서 이어집니다.
- Render free에서 서버가 막 깨어난 직후에는 KR 레이더 warmup이 먼저 돌고, 정밀 계산이 길어지면 `504` 대신 빠른 1차 후보 응답을 먼저 돌려주도록 구성합니다. 다만 partial 뒤에 장기 스캔이 계속 유지된다고 가정하지 않고, 다음 재조회에서 quick 스냅샷과 정밀 계산을 다시 시작하는 방식으로 안정성을 맞춥니다.
- `/api/market/opportunities/{code}`는 먼저 `cached full`, 그다음 `cached quick`, 그다음 `fresh quick`를 우선 확인하고, 정밀 full 계산은 필요할 때만 background warmup으로 분리합니다. 그래서 `/radar` first screen이 full 계산 때문에 같이 늦어지던 구간을 줄였습니다.
- cached quick 재사용은 이제 요청 limit와 정확히 같은 캐시 키만 보지 않고, 최근에 확보된 다른 quick limit 결과도 usable하면 잘라서 다시 사용합니다. 그래서 `/radar?limit=12`가 막혀도 직전 `limit=8` quick 결과를 먼저 보여 줄 수 있습니다.
- 레이더 응답 캐시는 이제 `시장 컨텍스트 계산 + 유니버스 해석 + 1차 quote screen`까지 함께 감싸므로, 같은 조건의 재조회가 들어올 때 매번 무거운 전처리를 다시 수행하지 않습니다.
- KR처럼 큰 fallback 유니버스를 batch quote로 읽을 때는 개별 `stock_quote` 캐시를 수백 건씩 추가 기록하지 않고 batch 응답만 우선 사용해, Render free의 캐시 쓰기 병목을 줄입니다.
- 사용자 핵심 데이터는 Supabase에 있으므로 Render 재기동 시에도 계정 데이터는 유지됩니다.
- 공개 집계형 패널은 timeout과 fallback을 기본 전제로 설계하며, 가능한 경우 `504` 대신 `200 + partial` 응답으로 먼저 살아남는 것을 우선합니다.
- Render 운영 로그에서 `Ran out of memory (used over 512MB)`가 잡힌 뒤부터는 cold start startup profile을 메모리 절약형으로 고정했습니다. 현재 production은 `prediction_accuracy_refresh=false`, `learned_fusion_refresh=false`, `research_archive_sync=false`, `market_opportunity_prewarm=false`, `STARTUP_BACKGROUND_TASK_CONCURRENCY=1` 기준으로 동작하고, 공개 경로가 먼저 살아난 뒤 on-demand refresh와 캐시로 후속 보강을 이어갑니다.
- Render 서비스에 예전 `STARTUP_*` 값이 남아 있어도 backend code는 자동으로 메모리 세이프 startup profile을 우선 적용합니다. 즉 Render 런타임으로 감지되면 `prediction_accuracy_refresh`, `learned_fusion_profile_refresh`, `research_archive_sync`, `market_opportunity_prewarm`는 startup에서 건너뛰고, concurrency는 `1`로 유지됩니다. 정말 무거운 startup job까지 함께 돌려야 할 때만 `STARTUP_ALLOW_HEAVY_RENDER_JOBS=true`로 명시적으로 풀어야 합니다.
- `/api/countries`와 `/api/market/movers/KR`는 이제 홈 SSR 안정화를 위해 가벼운 대표 경로를 우선 사용합니다. `countries`는 병렬 quote + timeout fallback으로, `market movers`는 KR representative quote + timeout fallback으로 먼저 응답해 공용 홈 패널이 같은 cold start 구간에서 backend를 다시 무겁게 만들지 않도록 맞췄습니다.
- 공개 background refresh는 이제 key 단위로 dedupe됩니다. 같은 시점에 홈, 레이더, 포트폴리오, 스크리너가 비슷한 cache warmup을 다시 걸어도 `country report`, `opportunity radar`, `screener cache warmup`은 기존 background task를 재사용해 Render free 인스턴스에 중복 job이 쌓이지 않게 유지합니다.
- `prediction_accuracy_refresh`와 `research_archive_sync`는 startup에서 빠졌지만 기능이 없어진 것은 아닙니다. 예측 검증은 `/api/research/predictions` 계열에서, 기관 리포트 동기화는 `/api/archive/research`와 `/api/archive/research/refresh`에서 on-demand로 계속 갱신됩니다. 즉 cold start 메모리 피크를 줄이고, 실제로 해당 화면을 열었을 때만 무거운 보강 작업을 시작합니다.

### 운영 latency / warm-up 메모

아래는 “이론상 가능성”이 아니라, 현재 배포 구조와 실제 관찰값을 함께 적은 메모입니다.

공식 provider 기준:

- Render Free web service는 `15분` 동안 inbound traffic이 없으면 spin down 되고, 다음 요청 시 다시 깨어나는 데 `약 1분`이 걸릴 수 있습니다. 공식 문서: [Render Free instances](https://render.com/docs/free), [Render FAQ](https://render.com/docs/faq)
- Supabase는 프로젝트가 inactivity 때문에 pause될 수 있고, pause된 project는 `540 project paused`를 반환합니다. 공식 문서: [Supabase HTTP status codes](https://supabase.com/docs/guides/troubleshooting/http-status-codes)
- 현재 Render free 인스턴스 로그 기준 메모리 한도는 `512MB`였고, 2026-03-29 17:46 KST 장애는 cold start background job이 겹치며 이 한도를 넘은 사례로 기록했습니다. 그래서 운영 startup profile을 `한 번에 한 작업` 기준으로 다시 맞췄습니다.

이 프로젝트에서 실제로 중요한 시간 예산:

- `/api/market/opportunities/{code}`
  - route-level 정밀 응답 대기: `12초`
  - route-level quick fallback 대기: `최대 4초`
  - service-level 1차 스캔 timeout: `4초`
  - service-level 후보 정밀 계산 timeout: `4초`
  - quick quote screen 내부 빠른 quote timeout: `1.2초`
- Render production startup
  - `database_initialize`: 즉시
  - `market_opportunity_prewarm`: startup 비활성화, on-demand
  - `learned_fusion_profile_refresh`: startup 비활성화, on-demand
  - `prediction_accuracy_refresh`: startup 비활성화, on-demand
  - `research_archive_sync`: startup 비활성화, on-demand
  - `startup background concurrency`: `1`
- `/radar` 클라이언트 재호출 timeout: `28초`
- startup opportunity prewarm timeout: `45초` budget only when explicitly enabled

사진 두 장이 다르게 보인 이유:

- 첫 사진은 `/radar`가 아니라 대시보드의 `강한 셋업 + 주요 뉴스 + 상위 종목` 구간입니다.
- 대시보드는 여러 공개 API를 `Promise.allSettled`로 불러와 일부 패널만 살아남아도 화면을 유지합니다.
- 둘째 사진의 `/radar`는 전용 레이더 first screen이라, 같은 시점에 `market opportunities` warm-up gap을 만나면 그 페이지만 빈 경고 카드처럼 보일 수 있었습니다.
- 즉 원인은 “무료 서버라 느림” 한 줄로 끝나지 않고, `Render Free warm-up + KR 레이더 첫 quick build 비용 + 대시보드와 /radar의 실패 흡수 방식 차이`가 함께 겹친 것입니다.
- 현재 패치 기준으로는 quick fallback이 늦어도 `cached quick` 또는 placeholder `partial`을 먼저 내려 `/radar`가 통째로 비는 상황을 줄였습니다.
- placeholder partial이 unavoidable한 경우에도 `/radar` first screen은 더 이상 `실제 시세 확보 0 / 표시 후보 0` 같은 숫자 보드를 그대로 크게 보여주지 않고, 어떤 단계에서 준비 중인지와 다음 갱신 동작을 먼저 안내합니다.

2026-03-29 관찰값 예시:

- 측정 환경: 한국(서울) 데스크톱 네트워크에서 운영 도메인 직접 호출
- `GET https://yoongeon.xyz/radar`
  - `469.2ms`
  - `107.3ms`
  - `99.4ms`
- `GET https://api.yoongeon.xyz/api/health`
  - `933.0ms`
  - `2291.7ms`
  - `2023.0ms`
- `GET https://api.yoongeon.xyz/api/market/opportunities/KR?limit=8`
  - cold/warm gap 시 `27377.6ms` 뒤 `504 / SP-5018`
- 같은 endpoint family를 연속 호출한 직후
  - `limit=12`: `15923.5ms`, `200`
  - `limit=20`: `8378.4ms`, `200`

주의:

- 위 ms 값은 운영 샘플이며 SLA가 아닙니다.
- 특히 `market opportunities`는 첫 요청이 warm-up과 cache fill을 떠안으면 뒤 요청보다 훨씬 느릴 수 있습니다.
- Supabase pause는 private/account 경로에 더 직접적인 영향이 있고, 위 두 장의 public radar/대시보드 차이는 주로 Render backend warm-up과 radar aggregation 경로 영향입니다.

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

`--live-api-smoke`는 공개 대시보드 응답뿐 아니라 인증이 필요한 저장성 API가 로그인 없이 `401 / SP-6014`를 올바르게 반환하는지도 함께 확인합니다.

운영 배포 스모크:

```powershell
& .\venv\Scripts\python.exe .\verify.py --deployed-site-smoke
```

`--deployed-site-smoke`는 현재 운영 중인 `https://www.yoongeon.xyz`, `https://api.yoongeon.xyz`를 직접 호출해 프론트 HTML 응답, 핵심 공개 API, 인증 필요 API의 `401 / SP-6014` 계약을 함께 점검합니다. 이 스모크는 `KR heatmap`, `market opportunities`, `screener` 같은 느린 공개 API도 함께 확인하며, Render free 워밍업이나 배포 전환 구간의 일시적인 `502/503/504`와 timeout에는 짧게 재시도합니다. 최신 기준으로 `heatmap`과 `screener`는 느릴 때도 `partial` 응답으로, `market opportunities`는 느릴 때도 `1차 시세 스캔 후보`, `cached quick`, placeholder partial 중 하나로 먼저 살아남는지 함께 봅니다.

`main` 머지 후 실제 운영 배포가 새 버전으로 반영됐는지 기다릴 때는 아래 명령을 사용합니다.

```powershell
& .\venv\Scripts\python.exe .\scripts\wait_for_deployed_version.py
```

이 스크립트는 기본적으로 로컬 `backend/app/version.py`의 `APP_VERSION`을 읽고, 운영 `api.yoongeon.xyz/api/health`가 같은 `version`과 `status=ok`를 반환할 때까지 주기적으로 확인합니다.

`/settings`의 시스템 진단 카드에서는 현재 프론트 빌드 버전과 백엔드 API 버전을 함께 보여 주며, 두 버전이 어긋나면 배포 전파 확인이 필요하다는 안내를 표시합니다.

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

- 공개 대시보드에서 특정 패널이 오래 멈추면 `SP-5018` timeout 응답뿐 아니라 `partial`, `fallback_reason`, 또는 `1차 후보 먼저 반환` 같은 degrade 경로가 먼저 내려오는지 확인합니다.
- `heatmap`과 `screener`는 대표 종목군 기준으로 먼저 계산하므로, 화면이 바로 뜨는 안정성을 우선하고 전체 전수 스캔은 후순위로 둡니다.
- `market opportunities`는 현재 KRX 상장사 전종목을 먼저 1차 스캔하고, 실제 시세를 확보한 종목군 안에서 상위 후보만 정밀 분포 분석합니다. 정밀 분석이 늦거나 일부 종목이 실패해도 전수 1차 스캔 결과를 후보 카드로 먼저 내려 빈 화면이나 `후보 0개` 상태가 오래 고정되지 않게 합니다.
- `총 8개 스캔`은 예전 하드캡/레이트리밋 영향이 남아 있던 오래된 응답 기준 문구였고 현재 구조에서는 더 이상 기준선이 아닙니다. 지금은 응답에 `전체 유니버스 / 1차 스캔 / 실제 시세 확보 / 표시 후보`가 함께 내려갑니다.
- KR Opportunity Radar는 현재 KRX KIND 상장사 목록 기준으로 전종목을 1차 스캔합니다. 다만 데이터 원본 제한이나 거래 상태에 따라 일부 종목은 시세 확보 단계에서 빠질 수 있고, Render free 환경에서는 정밀 분포 계산을 상위 후보에만 적용해 첫 응답을 안정화합니다.
- KR 레이더는 KRX 전종목 경로에서 실제 시세 확보 수가 `0`이면 같은 응답 안에서 운영용 기본 종목군으로 즉시 전환합니다. 그래서 `후보 0개` 상태가 오래 남지 않고, 사용자는 먼저 볼 수 있는 후보와 실행 메모를 바로 받게 됩니다.
- 리서치 아카이브는 한국만 고정하지 않고 현재 `KR / US / EU / JP` 지역 탭과 공식 기관 소스 요약을 함께 제공합니다.
- 인증 관련 문제가 나면 `/api/account/me`와 `/api/account/username-availability` 계약부터 확인하는 것이 가장 빠릅니다.

## 버전 정책

- 사용자 동작이 바뀌면 `README.md`, `CHANGELOG.md`, 관련 테스트를 함께 갱신합니다.
- API 응답이 바뀌면 프론트 타입과 호출부를 함께 수정합니다.
- 릴리즈 가치가 있는 기능 추가는 백엔드/프론트 버전을 함께 올립니다.
