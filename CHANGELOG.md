# Changelog

All notable changes to this project are tracked here.

## v2.10.2 - 2026-03-24

- 대시보드의 `지금 가장 강한 셋업` 패널을 compact 전용 레이아웃으로 다시 정리해, 우측 좁은 컬럼 안에서도 카드가 눌리거나 내용이 깨지지 않도록 안정화했습니다.
- compact 레이더에서 카드 수를 줄이고, 태그/시나리오/thesis 밀도를 조정해 대시보드에서는 핵심만 빠르게 읽히고 상세한 내용은 종목 상세나 전체 레이더로 넘기도록 역할을 분리했습니다.
- 상단 헤더, 데스크톱 사이드바, 모바일 메뉴, 검색 결과 드롭다운, 공통 카드의 blur 계층을 줄이고 배경 패턴도 더 가볍게 바꿔 스크롤 시 페인트 비용을 낮췄습니다.
- 대시보드 상단 2열 섹션에 `min-w-0` 제약을 추가해 우측 컬럼이 긴 레이더 콘텐츠 때문에 가로로 밀리거나 overflow 되는 문제를 함께 잡았습니다.

## v2.10.1 - 2026-03-24

- Tailwind 색상 토큰을 `rgb(var(--token-rgb) / alpha)` 구조로 재정의해 `bg-surface/60`, `bg-bg/78`, `border-border/70` 같은 투명도 클래스가 실제 CSS로 생성되도록 수정했습니다.
- 그 결과 상단 헤더, 데스크톱 사이드바, 모바일 메뉴, 카드, 표 배경이 비정상적으로 비거나 깨져 보이던 워크스페이스 셸 렌더링 문제를 한 번에 안정화했습니다.
- 전역 스크롤바 스타일을 추가해 스크롤이 생기는 모든 영역에서 흰 트랙 배경을 제거하고, 투명 트랙 + 얇은 thumb 기준으로 일관되게 맞췄습니다.
- 프론트 빌드 아티팩트 기준으로 누락되던 배경/테두리 opacity 클래스가 실제 생성되는 것을 다시 확인했고, 전체 검증 스크립트로 백엔드와 프론트 검증을 함께 통과했습니다.

## v2.10.0 - 2026-03-24

- 데스크톱/모바일 네비게이션을 시장 탐색, 운영, 리서치 그룹으로 재구성하고 각 메뉴에 설명을 붙여 현재 위치와 용도를 더 쉽게 파악할 수 있게 정리했습니다.
- 공통 레이아웃에 상단 워크스페이스 바와 통일된 페이지 헤더 스타일을 도입해 검색, 빠른 이동, 핵심 액션이 한 톤으로 읽히도록 개선했습니다.
- 홈 대시보드를 `추천 포트폴리오 → 강한 셋업 → 시장 스냅샷 → 빠른 이동 → 히트맵/모멘텀` 순서로 재배치해 가독성과 시선 흐름을 크게 정리했습니다.
- 포트폴리오, 레이더, 예측 연구실 페이지 헤더와 입력/필터 영역을 같은 리듬으로 정리해 화면마다 제각각이던 밀도와 정렬감을 맞췄습니다.
- 검색바를 한국어 중심 UX로 다듬고 검색 결과 카드, Enter 진입, 빈 결과 안내를 추가해 빠른 탐색 흐름을 더 명확하게 만들었습니다.

## v2.9.1 - 2026-03-24

- FMP Stock Screener가 401/403/429를 반환할 때 거래소별 probe 후 즉시 fallback 유니버스로 전환하고, 일정 시간 재시도를 멈추도록 정리해 Opportunity Radar 로그 폭주를 크게 줄였습니다.
- Opportunity Radar 응답에 `universe_source`, `universe_note`를 추가하고 프론트 카드에도 fallback 상태를 노출해 실시간 유니버스 제한 여부를 바로 알 수 있도록 개선했습니다.
- FMP peers/calendar/dcf 같은 보조 엔드포인트도 권한 제한을 한 번 감지하면 조용히 fallback 하도록 만들어 종목 상세 진입 시 반복 403 에러 로그를 줄였습니다.
- PDF 내보내기에서 `bytearray` 응답으로 실패하던 버그를 수정해 국가 리포트 PDF와 아카이브 PDF export가 안정적으로 동작하도록 고쳤습니다.
- 한국 수급 보조 입력의 `pykrx` 내부 logging 충돌을 우회하고, 확인된 무효 KR 티커를 기본 유니버스에서 추가로 제거해 스크리너/히트맵/레이더 잡음을 낮췄습니다.
- FastAPI TestClient 기반으로 32개 핵심 API 스모크를 돌려 health, 국가/섹터/종목, radar, portfolio, archive, diagnostics, export 전 구간이 200/정상 계약으로 응답하는 것을 확인했습니다.

## v2.9.0 - 2026-03-23

- 한국·미국·일본 Opportunity Radar를 묶어 다음 거래일 기준의 `일일 이상적 포트폴리오`를 생성하고, 목표 비중·현금 버퍼·국가/섹터 상단 캡까지 함께 제안하는 기능을 추가했습니다.
- 일일 추천 포트폴리오 스냅샷을 DB에 저장하고, 다음 날 실제 종가 기준으로 성과를 다시 붙여 예측 대비 실제 결과를 날짜별로 추적할 수 있도록 확장했습니다.
- 홈 대시보드에 `내일의 이상적 포트폴리오` 패널을 추가해 추천 비중, 시장 국면, 운영 플레이북, 과거 추천안 성과를 한 번에 볼 수 있도록 구성했습니다.
- 하위 경로에서 사이드 내비게이션 활성 상태가 풀리던 UI 버그를 수정해 country/stock/archive 세부 페이지에서도 현재 섹션이 일관되게 강조되도록 정리했습니다.
- 일일 추천 포트폴리오 생성/평가 회귀 테스트를 추가하고, 기존 포트폴리오 회귀 테스트와 함께 검증 범위를 넓혔습니다.

## v2.8.0 - 2026-03-23

- 포트폴리오 응답에 모델 포트폴리오 추천 엔진을 추가해 추천 주식 비중, 현금 버퍼, 단일 종목/국가/섹터 상단 캡, 권장 포지션 수를 함께 계산하도록 확장했습니다.
- 현재 보유 종목의 예측 시나리오·실행 바이어스·리스크 점수와 Opportunity Radar, 워치리스트 후보를 합쳐 목표 비중과 리밸런싱 큐를 자동 생성하도록 연결했습니다.
- 포트폴리오 화면에 모델 포트폴리오 패널을 추가해 권장 비중 테이블, 리밸런싱 큐, 후보 파이프라인, 추천 국가/섹터 비중을 한 번에 볼 수 있도록 개선했습니다.
- 포트폴리오 회귀 테스트를 확장해 새 모델 포트폴리오 계약과 워치리스트/레이더 연동 흐름을 함께 검증하도록 강화했습니다.

## v2.7.0 - 2026-03-23

- 다음 거래일 예측 엔진을 `signal-v2.4`로 확장해 상방/기준/하방 3개 시나리오와 실행 바이어스, 리스크 플래그를 함께 반환하도록 개선했습니다.
- 국가/종목 상세의 다음 거래일 예측 카드에 시나리오별 가격·확률, 실행 해석, 리스크 플래그를 추가해 한 번에 해석할 수 있도록 정리했습니다.
- 포트폴리오 인텔리전스 테이블에 실행 바이어스, 상방/기준/하방 시나리오 가격, 리스크 플래그를 연결해 보유 종목별 대응 우선순위를 더 직접적으로 보여주도록 확장했습니다.
- 포트폴리오 리스크 패널에 방어 노출, 약세 시나리오 노출, 실행 믹스, 액션 큐를 추가해 어떤 포지션을 먼저 손볼지 바로 보이도록 개선했습니다.
- Opportunity Radar 점수에 실행 바이어스 보정과 리스크 플래그 패널티를 반영하고, 카드에도 시나리오 가격/확률과 핵심 리스크 플래그를 노출하도록 확장했습니다.
- 짧은 가격 이력 fallback에서도 동일한 예측 구조를 유지하도록 정리해 프론트가 빈 필드 없이 일관된 계약을 받도록 보강했습니다.
- `NextDayForecast` 리스트 필드에 안전한 `default_factory`를 적용해 예측 객체 기본값 공유 가능성을 제거했습니다.
- next-day forecast 회귀 테스트를 확장해 새 시나리오 구조와 fallback 계약을 검증하도록 강화했습니다.

## v2.5.1 - 2026-03-23

- 한국 헬스케어 유니버스에서 무효 티커 `091990.KS`를 제거하고 `196170.KQ`로 교체했습니다.
- 유니버스 로더에 중복/무효 티커 정리 로직을 추가해 heatmap, movers, radar가 비정상 심볼을 반복 호출하지 않도록 보강했습니다.
- 캐시 계층에 in-flight dedupe를 추가해 동일 키에 대한 동시 요청이 들어와도 fetch를 한 번만 수행하도록 개선했습니다.
- `heatmap`과 `market movers`를 단일 시장 스냅샷 기반으로 재구성해 Yahoo 호출 수를 줄이고 응답 안정성을 높였습니다.
- 한국 거래소 캘린더의 `break_start`, `break_end` 경고를 억제하도록 시장 캘린더 초기화를 정리했습니다.
- 홈 화면 초기 로딩 effect를 개발 모드 중복 실행에서 보호해 불필요한 API 중복 호출과 프록시 `socket hang up` 가능성을 낮췄습니다.
- 루트 `verify.ps1` 검증 스크립트를 추가하고 AI/기여 가이드의 기본 검증 절차를 강화했습니다.

## v2.5.0 - 2026-03-23

- Yahoo Finance 연동을 `info + fast_info + history_metadata + 최근 가격 이력` 기반 fallback 구조로 재정비해 빈 필드와 공급자 흔들림에 더 강하게 만들었습니다.
- 지수 티커는 재무/실적 비지원 자산으로 분기 처리해 불필요한 Yahoo 404 노이즈를 줄였습니다.
- 백엔드 의존성에 `lxml`을 추가하고, 실적 이력은 캘린더 fallback까지 갖추도록 정리했습니다.
- 종목 상세에 `analog-v1.0` 과거 유사 국면 예측 엔진을 추가해 5·20·60거래일 상승 확률, 기대 수익률, 예상 가격 범위, 유사 사례를 노출합니다.
- 현재 셋업과 유사한 과거 사례를 기반으로 승률, 평균 수익률, 평균 최대 낙폭, 프로핏 팩터를 보여주는 셋업 백테스트 카드를 추가했습니다.
- 가격 차트에 다음 거래일 예측선과 함께 과거 유사 국면 기반 미래 경로 밴드를 오버레이하도록 확장했습니다.
- Yahoo fallback과 과거 유사 국면 엔진을 검증하는 회귀 테스트를 추가했습니다.

## v2.4.0 - 2026-03-23

- 대시보드, 비교, 스크리너, 워치리스트, 포트폴리오, 국가/종목 상세 등 주요 화면의 사용자 노출 문구를 한국어 중심으로 재정비했습니다.
- API 상태와 시스템 진단 카드를 홈 화면에서 분리하고 `/settings` 페이지로 이동해 운영 정보와 투자 정보의 역할을 분리했습니다.
- Fed, BIS, 한국은행, KDI, BOJ 공식 리포트를 하루 단위로 동기화하는 기관 리서치 아카이브를 추가했습니다.
- 아카이브에서 PDF 직접 열기와 공식 원문 링크 이동을 함께 지원하고, 직접 다운로드 실패 시 내보내기 허브로 자연스럽게 우회하도록 정리했습니다.
- 한국 시장을 기본 시작점으로 두도록 홈 대시보드, 레이더, 히트맵, 캘린더 기본값을 조정했습니다.
- 버전, README, 테스트, 에러 코드 문서를 `2.4.0` 기준으로 동기화했습니다.

## v2.3.0 - 2026-03-23

- Added a month-scoped market calendar API with color-coded normalized events, recurring fallback generation, and Korean event descriptions
- Rebuilt the calendar UI into a monthly schedule board that refreshes when the month changes and surfaces high-impact events inline
- Reworked archive exports with robust direct download handling, a dedicated export hub page, and CORS `Content-Disposition` exposure
- Upgraded the next-day forecast engine to `signal-v2.3` with candle control, regime overlay, localized news scoring, and stronger confidence shrinkage
- Localized major user-facing detail panels into Korean, including forecast cards, diagnostics, archive flows, navigation, and Prediction Lab summaries
- Added regression coverage for monthly calendar shaping and bullish/bearish forecast separation
- Added repository-wide contribution standards for humans and AI, including required README/error-code/version synchronization rules and a PR checklist

## v2.2.1 - 2026-03-22

- Synchronized backend and frontend version metadata to `2.2.1`
- Added explicit error codes for:
  - `SP-5006` system diagnostics
  - `SP-5007` prediction research
  - `SP-5008` portfolio analytics
  - `SP-9999` unexpected server errors
- Wired research/system/portfolio routers to return structured `AppError` responses
- Updated README release/version guidance and error code reference

## v2.2.0 - 2026-03-22

- Added next-day forecast engine
- Added market regime analysis and opportunity radar
- Added portfolio risk coach and stress testing
- Added prediction lab with calibration and validation analytics
- Added runtime diagnostics and startup task visibility
