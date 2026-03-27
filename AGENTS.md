# Agent Guide

이 문서는 이 저장소에서 작업하는 AI 에이전트를 위한 기본 규칙입니다. 범위는 저장소 전체입니다.

## 목표

- 기능 추가 속도보다 신뢰성과 일관성을 우선합니다.
- 사용자에게 보이는 변경은 코드, 문서, 버전, 에러 코드까지 함께 반영합니다.
- 프론트와 백엔드 계약이 어긋나지 않도록 항상 함께 확인합니다.

## 현재 서비스 기준선

문서와 구현은 `예전에 구상한 제품`이 아니라 `지금 운영 중인 사이트`를 기준으로 맞춥니다.

- 프론트 배포: `Vercel`
- 백엔드 배포: `Render`
- 인증/사용자 데이터: `Supabase`
- DNS/도메인: `Cloudflare`

현재 서비스는 한국 시장 중심으로 운영되지만, 문서와 사용자 문구에서 이 제약을 매 문단의 headline처럼 반복하지 않습니다.
먼저 `무엇을 할 수 있는지`를 설명하고, 시장 범위는 필요한 문맥에서만 분명하게 적습니다.

## 현재 제품 지도

### 프론트 주요 화면

- `/`
  - 대시보드
  - 브리핑, 시장 스냅샷, 히트맵, 모멘텀, 레이더 요약
- `/auth`
  - 이메일 회원가입 / 로그인 / 비밀번호 재설정
- `/radar`
  - Opportunity Radar
- `/screener`
  - 조건 기반 종목 필터링
- `/compare`
  - 종목 비교
- `/portfolio`
  - 자산 프로필, 보유 종목, 추천, 이벤트 레이더
- `/watchlist`
  - 관심종목 관리
- `/calendar`
  - 일정 캘린더
- `/archive`
  - 리서치/예측 아카이브
- `/lab`
  - 예측 연구실
- `/settings`
  - 계정 관리, 시스템/진단/운영 설정
- 상세 라우트
  - `/country/[code]`
  - `/country/[code]/sector/[id]`
  - `/stock/[ticker]`
  - `/archive/export/[id]`

### 백엔드 API 지도

- 상태/시스템
  - `/api/health`
  - `/api/diagnostics`
- 계정 / 인증
  - `/api/account/me`
  - `/api/account/signup/validate`
  - `/api/account/username-availability`
- 시장/국가
  - `/api/countries`
  - `/api/country/{code}/report`
  - `/api/country/{code}/heatmap`
  - `/api/country/{code}/forecast`
  - `/api/country/{code}/sector-performance`
  - `/api/country/{code}/sectors`
  - `/api/market/indicators`
  - `/api/market/movers/{code}`
  - `/api/market/opportunities/{code}`
- 섹터/종목/검색
  - `/api/country/{code}/sector/{sector_id}/report`
  - `/api/stock/{ticker}/detail`
  - `/api/stock/{ticker}/chart`
  - `/api/stock/{ticker}/technical-summary`
  - `/api/stock/{ticker}/pivot-points`
  - `/api/stock/{ticker}/forecast-delta`
  - `/api/search`
  - `/api/ticker/resolve`
- 포트폴리오/관심종목
  - `/api/watchlist`
  - `/api/watchlist/{ticker}`
  - `/api/portfolio`
  - `/api/portfolio/profile`
  - `/api/portfolio/holdings`
  - `/api/portfolio/ideal`
  - `/api/portfolio/event-radar`
  - `/api/portfolio/recommendations/conditional`
  - `/api/portfolio/recommendations/optimal`
- 브리핑/리서치/캘린더/아카이브
  - `/api/briefing/daily`
  - `/api/market/sessions`
  - `/api/calendar/{code}`
  - `/api/archive`
  - `/api/archive/accuracy/stats`
  - `/api/archive/research`
  - `/api/archive/research/status`
  - `/api/archive/research/refresh`
  - `/api/archive/{report_id}`
  - `/api/predictions`
  - `/api/compare`
  - `/api/screener`
  - `/api/export/{fmt}/{report_id}`

규칙:

- 새 기능을 설계할 때는 먼저 이 지도 안에서 `기존 화면 확장`인지 `새 화면/새 라우트`인지 판단합니다.
- 이미 있는 라우트/페이지와 목적이 겹치면 새 파일을 만들기 전에 기존 흐름에 흡수할 방법을 먼저 찾습니다.
- 문서에는 존재하지 않는 메뉴, 라우트, 모드를 미리 적지 않습니다.

## 예측 엔진 기준선

현재 예측 엔진의 canonical backbone은 `backend/app/analysis/distributional_return_engine.py` 입니다.

- 숫자 예측은 확률모형이 담당합니다.
- `OpenAI / GPT-4o`는 숫자 예측기가 아니라 구조화 이벤트 추출기와 서술형 요약기입니다.
- 뉴스, 보도자료, 공시는 보조 신호이고 가격·변동성·상대강도 같은 수치 시계열이 주신호입니다.
- 출력은 점예측보다 조건부 수익률 분포를 우선하며, 가격은 분위수, 방향은 `up / flat / down` 확률로 파생합니다.
- 새 예측 로직을 넣을 때는 Monte Carlo + LLM 숫자 보정 방식이나 상수 가중 휴리스틱을 다시 들여오지 않습니다.
- 예측 엔진을 수정하면 wrapper, 시스템 진단, README, CHANGELOG, 버전, 회귀 테스트를 함께 맞춥니다.

## 포트폴리오 최적화 기준선

현재 포트폴리오 비중의 canonical optimizer는 `backend/app/services/portfolio_optimizer.py` 입니다.

- 포트폴리오 추천, 조건 추천, 최적 추천, 일일 이상적 포트폴리오는 같은 optimizer를 공유합니다.
- 비중 계산은 `20거래일 기대수익률 + 기대초과수익률 + EWMA+shrinkage 공분산 + 회전율 패널티` 기준을 유지합니다.
- 새 포트폴리오 로직을 추가할 때는 선형 점수 합으로 비중을 나누는 ad-hoc 방식을 다시 들여오지 않습니다.
- 포트폴리오 응답을 바꾸면 최소한 아래를 함께 확인합니다.
  - `backend/app/services/portfolio_service.py`
  - `backend/app/services/portfolio_recommendation_service.py`
  - `backend/app/services/ideal_portfolio_service.py`
  - `frontend/src/lib/api.ts`
  - 포트폴리오 관련 패널 컴포넌트
  - README / CHANGELOG / 회귀 테스트

## 필수 규칙

1. 사용자에게 보이는 동작이 바뀌면 `README.md`를 업데이트합니다.
2. 새로운 실패 경로나 예외 응답을 추가하면 `backend/app/errors.py`에 에러 코드를 등록하고, `README.md`의 에러 코드 표도 함께 갱신합니다.
3. 릴리즈 가치가 있는 기능 추가나 예측 엔진 개선을 반영하면 다음 파일의 버전을 함께 점검합니다.
   - `backend/app/version.py`
   - `frontend/package.json`
   - `frontend/package-lock.json`
   - `CHANGELOG.md`
4. 백엔드 API 응답이나 스키마가 바뀌면 프론트 타입과 호출부를 함께 수정합니다.
   - `frontend/src/lib/api.ts`
   - 관련 페이지/컴포넌트
5. 예측 엔진을 수정하면 모델 버전과 설명도 함께 맞춥니다.
   - `backend/app/analysis/next_day_forecast.py`
   - `backend/app/models/forecast.py`
   - `backend/app/services/system_service.py`
   - `README.md`
   - `CHANGELOG.md`
   - 관련 회귀 테스트
6. 사용자 설명, 상세 패널, 운영 안내 문구는 한국어 우선으로 작성합니다.
   - 고유명사, 티커, API 이름처럼 영어가 더 명확한 부분은 유지해도 됩니다.
7. 다운로드, 내보내기, 파일 생성 흐름을 바꾸면 브라우저 fallback까지 같이 확인합니다.
   - 필요 시 CORS 헤더와 파일명 처리도 점검합니다.
8. 비즈니스 로직이나 API를 바꾸면 최소 1개 이상의 검증 코드를 추가하거나 기존 테스트를 갱신합니다.
9. 사용자가 만든 기존 변경 사항은 절대 되돌리지 않습니다. 예상치 못한 수정이 보이면 먼저 멈추고 확인합니다.
10. 프론트엔드나 UI/UX를 수정할 때는 반드시 `DESIGN_BIBLE.md`를 먼저 읽고, 그 안의 메뉴 구조, page thread, button hierarchy, table, spacing 규칙을 따릅니다.
11. 새로운 UI primitive나 시각 규칙을 추가했다면 `DESIGN_BIBLE.md` 또는 관련 공용 파일에 기준을 함께 반영합니다.
12. 공개 대시보드나 집계형 API를 추가/수정할 때는 반드시 timeout과 부분 fallback을 함께 설계합니다.
   - 느린 외부 소스 하나 때문에 전체 화면이 `불러오는 중` 상태로 고정되지 않게 합니다.
   - timeout을 추가하면 관련 에러 코드와 사용자 안내 문구도 함께 맞춥니다.
13. 소개 문구, 헤더 설명, README 첫 문단은 `제약`보다 `효용`을 먼저 설명합니다.
   - 시장 범위, free 플랜 제약, 외부 API 한계는 숨기지 않되, headline처럼 반복하지 않습니다.
14. AI 과장 카피를 금지합니다.
   - `혁신적`, `놀라운`, `AI가 다 해준다`, `차세대` 같은 문구보다 실제 기능, 근거, 입력/출력 계약을 우선 적습니다.
15. 사용자 시선 흐름을 우선합니다.
   - 카드, 섹션, 버튼은 “예뻐 보이는 대칭”보다 “읽기 쉬운 정렬”을 우선하며, 한 화면에서 동시에 여러 강조점이 경쟁하지 않게 합니다.
16. 가입 / 계정 프로필 흐름을 수정할 때는 프론트와 백엔드 검증 규칙을 반드시 같은 의미로 유지합니다.
   - `frontend/src/lib/account.ts`
   - `frontend/src/app/auth/page.tsx`
   - `frontend/src/components/AuthProvider.tsx`
   - `backend/app/services/account_service.py`
   - `backend/app/routers/account.py`
   - `backend/app/auth.py`
17. 회원가입 필드를 바꾸면 README와 테스트도 같이 갱신합니다.
   - 필수 입력, 비밀번호 규칙, 아이디 중복 확인, 프로필 노출 방식이 문서와 실제 UI에서 다르게 보이면 안 됩니다.

## 문구 원칙

- 한국어 우선이지만 과한 설명체보다 운영형 문장을 씁니다.
- 기능명은 가능한 한 현재 내비게이션과 같은 용어를 유지합니다.
  - 예: `기회 레이더`, `포트폴리오`, `관심종목`, `예측 연구실`
- 사용자가 바로 이해할 수 있는 명사/동사 조합을 씁니다.
  - 좋은 예: `보유 종목 추가`, `조건 추천 보기`, `관심종목에서 제거`
  - 피할 예: `실행`, `확인`, `AI 분석 시작`
- “한국 시장만 지원” 같은 제약은 아래 경우에만 전면에 드러냅니다.
  - 잘못된 입력을 막아야 할 때
  - API/데이터 범위를 설명해야 할 때
  - 지원 범위 차이로 오해가 생길 수 있을 때

## 계정 / 인증 기준선

- 현재 가입 UI는 `/auth`에서 이메일 기반 회원가입/로그인을 처리하고, 복구 링크 진입 시 같은 화면에서 비밀번호 재설정을 마칩니다.
- 필수 가입 입력은 `아이디, 이메일, 이름, 전화번호, 생년월일, 비밀번호, 비밀번호 재확인` 입니다.
- 아이디는 `영문 소문자 시작 + 영문 소문자/숫자/밑줄 + 4~20자` 규칙을 유지합니다.
- 비밀번호는 `10자 이상 + 대문자 + 소문자 + 숫자 + 특수문자 + 재확인 일치` 규칙을 유지합니다.
- 회원가입 직전에는 `POST /api/account/signup/validate`로 서버 사전 검증을 통과한 뒤 Supabase 가입을 진행합니다.
- 로그인 후 `/settings`에서 아이디, 이름, 전화번호, 생년월일 수정, 이메일 변경 요청, 인증 메일 재전송, 새 비밀번호 즉시 변경, 비밀번호 재설정 메일 발송, 현재 세션 확인, 이 기기 로그아웃, 모든 기기 로그아웃, 회원 탈퇴를 처리합니다.
- 계정 프로필은 현재 `Supabase Auth user_metadata` 기반으로 읽고, `/api/account/me`에서 마스킹된 전화번호와 이메일 인증 상태, `pending_email`을 함께 반환합니다.
- 프로필 수정은 `PATCH /api/account/me`를 사용하며, 서버가 아이디 중복과 입력 형식을 다시 검증합니다.
- 회원 탈퇴는 `DELETE /api/account/me`를 사용하며, 현재 아이디 또는 이메일 재입력을 확인한 뒤 `Supabase Auth` 계정과 연관 포트폴리오/관심종목 데이터를 함께 정리합니다.
- 아이디 중복 확인은 `GET /api/account/username-availability`를 사용하며, 로그인 전에도 호출 가능해야 합니다.
- 로그인 전 공개 계정 API는 UX를 해치지 않는 짧은 rate limit을 유지합니다.

규칙:

- 가입 UX를 바꿀 때는 서버 검증 메시지, 프론트 helper text, README 설명이 같은 규칙을 말해야 합니다.
- 계정 정보는 과장된 마케팅 카피 대신 `보안`, `계정별 데이터 분리`, `세션 유지` 같은 실제 효용으로 설명합니다.
- 전화번호, 생년월일, 이름은 dense form에서도 모바일 한 열 배치가 깨지지 않도록 먼저 확인합니다.
- 공개 계정 엔드포인트를 수정할 때는 `rate limit`, `에러 코드`, `재시도 안내 문구`를 함께 맞춥니다.

## 작업 순서

1. 변경 범위를 파악하고 기존 계약을 읽습니다.
2. UI 작업이면 `DESIGN_BIBLE.md`를 먼저 확인합니다.
3. 기능 코드를 수정합니다.
4. 아래 동기화 항목을 빠짐없이 반영합니다.
5. 테스트와 빌드를 실행합니다.
6. 최종 보고에서 변경 파일, 검증 결과, 남은 리스크를 설명합니다.

## 동기화 체크리스트

- [ ] 사용자 동작 변경이 `README.md`에 반영되었는가
- [ ] 새 에러 코드가 `backend/app/errors.py`와 `README.md`에 반영되었는가
- [ ] 릴리즈 버전이 백엔드/프론트/체인지로그에 동기화되었는가
- [ ] 백엔드 응답 변경이 프론트 타입과 UI에 반영되었는가
- [ ] 한국어 사용자 문구가 자연스럽게 정리되었는가
- [ ] UI 변경이 `DESIGN_BIBLE.md`와 일관된가
- [ ] 테스트 또는 회귀 검증이 추가되었는가
- [ ] 아래 검증 명령을 실행했는가

## 기본 검증 명령

가장 먼저 아래 원클릭 검증을 권장합니다.

```powershell
& .\venv\Scripts\python.exe .\verify.py
```

프론트 수정이 없거나 백엔드만 빠르게 볼 때는 아래처럼 실행합니다.

```powershell
& .\venv\Scripts\python.exe .\verify.py --skip-frontend
```

주요 기능을 실제 라우트 기준으로 한 번 더 전수 점검하려면 아래 옵션을 사용합니다.

```powershell
& .\venv\Scripts\python.exe .\verify.py --live-api-smoke
```

PowerShell 실행 정책이나 `cmd` 자동 실행 훅이 있는 Windows 환경에서는 `start.py`, `verify.py`를 가상환경 Python으로 직접 실행하는 경로를 기본 진입점으로 사용합니다.
프론트 의존성 설치는 저장소 루트에서 `npm install`을 기본 진입점으로 사용해도 되며, 이 경우 `frontend` 설치까지 자동 위임되고 PowerShell provider path 환경에서도 같은 흐름이 유지되도록 관리합니다.

### Backend

```powershell
cd backend
& ..\venv\Scripts\python.exe -m compileall app
& ..\venv\Scripts\python.exe -m unittest discover -s tests -v
```

### Frontend

```powershell
cd frontend
npm run build
npx tsc --noEmit
```

## Git 주의사항

- 기본 작업 브랜치는 `dev`입니다. 기능 개발, 문서 수정, 검증은 `dev`에서 진행하고, 배포 기준 브랜치는 `main`으로 유지합니다.
- 파괴적인 git 명령은 사용하지 않습니다.
- 사용자가 요청하지 않은 리셋, 강제 체크아웃, 히스토리 재작성은 금지합니다.
- 커밋 메시지는 기능 범위가 드러나게 작성합니다.
- 브랜치 머지는 fast-forward로 처리하지 않고 항상 명시적 merge commit을 남깁니다.
- 머지 시 기본 원칙은 `git merge --no-ff <branch>` 이며, 가능하면 `Merge branch '<branch>'` 형태의 메시지를 사용합니다.
- 특별한 지시가 없으면 작업 흐름은 `main에서 dev 생성 -> dev에서 작업 -> 검증 -> origin/dev 푸시 -> main에 --no-ff merge -> origin/main 푸시 -> dev 삭제 -> 최신 main 기준으로 dev 재생성` 순서를 따릅니다.
- `dev` 삭제는 반드시 `main` 반영과 원격 푸시가 끝난 뒤에만 진행합니다.
