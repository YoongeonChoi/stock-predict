# Changelog

All notable changes to this project are tracked here.

## v2.60.21 - 2026-04-11

- 공개 `stock detail`의 cached full/quick lookup 경로를 import-light로 다시 정리했습니다. 이제 라우터가 `stock_analyzer` 전체를 import하기 전에 cache key를 직접 읽어 cached/shell 응답을 먼저 만들 수 있으므로, cold 첫 요청에서 `pandas`, `ta`, 분포 엔진 적재 비용 때문에 20초 가까이 밀리던 구간을 더 줄일 수 있습니다.
- `app.analysis.stock_cache_keys`를 분리해 stock detail cache key 버전을 분석기와 라우터가 같은 기준으로 공유하게 했습니다. key 문자열 중복을 없애면서, 빠른 cached lookup 경로가 추후 버전 변경 때도 어긋나지 않도록 고정했습니다.
- `test_stock_router`에 경량 cached lookup 회귀를 추가해, quick/full cached 조회가 `cache.get` 직접 경로를 유지하는지 고정했습니다.

## v2.60.20 - 2026-04-11

- `/api/health`는 memory-safe 모드의 pre-request memory trim 대상에서 제외했습니다. Render wake/readiness 확인은 가능한 한 가벼워야 하므로, health 요청이 `gc.collect()`/`malloc_trim()` 비용을 같이 지불하지 않도록 분리했습니다.
- 공개 `country report`의 stale archived path를 짧게 정리했습니다. archived 리포트를 이미 찾은 경우 fallback 빌더에서 archived/opportunity lookup을 다시 반복하지 않고, stale 안내와 `partial/fallback_reason`만 붙여 바로 반환합니다.
- 공개 `stock detail` memory-guard shell은 더 이상 `yfinance_client.get_stock_info()`를 호출하지 않습니다. 고압박 500MB 구간에서는 외부 가격 조회를 생략하고 티커·기본 메타데이터 중심 최소 응답을 먼저 반환해, shell 경로가 다시 heavy import/external IO를 유발하지 않게 고정했습니다.
- Vercel server fetch는 Render `hibernate-*` 503을 한 번만 짧게 재시도합니다. wake 순간의 일시적 503은 한 번 흡수하고, 그래도 실패하면 기존 페이지 fallback 흐름으로 내려가 사용자 화면이 멈추지 않도록 했습니다.
- `test_main_memory_hygiene`, `test_public_dashboard_timeouts`, `test_stock_router`를 갱신해 health trim 예외, country stale 중복 lookup 제거, stock memory-guard shell의 heavy builder 우회를 회귀로 고정했습니다.

## v2.60.19 - 2026-04-11

- backend startup import footprint를 더 줄였습니다. `app.main`과 공개/상세 핵심 라우터는 이제 `market_service`, `archive_service`, `prediction_capture_service`, `yfinance_client`, `sector_analyzer`, `stock_scorer` 같은 무거운 모듈을 import 시점이 아니라 실제 사용 시점에 로드합니다. Render cold start에서 `/api/health`와 첫 공개 요청이 불필요한 `pandas/yfinance/ta` 적재를 먼저 하지 않도록 바꿔, 500MB 메모리 한도와 cold latency를 함께 낮추는 방향으로 정리했습니다.
- `app.utils` 패키지는 더 이상 import만으로 `market_calendar`와 `pandas_market_calendars`를 끌어오지 않습니다. `next_trading_day`는 lazy wrapper로 노출해, route trace나 async util만 쓰는 경로가 달력 계산 모듈까지 함께 적재하지 않도록 정리했습니다.
- `backend/tests/test_import_footprint.py`를 추가하고, `test_main_startup`, `test_country_router`, `test_stock_router`, `test_public_dashboard_timeouts`, `test_market_route_stability`, `test_watchlist_router`, `test_portfolio_recommendations`, `test_api_error_contracts`를 다시 돌려 import proxy 전환이 실제 기능 회귀 없이 startup footprint만 줄인다는 점을 고정했습니다.

## v2.60.18 - 2026-04-11

- Render `500MB` memory-safe 모드에서 공개 `country report`, `market opportunities`, `stock detail`이 캐시 미스 시에도 요청 안에서 무거운 full/quick 계산을 계속 시도하던 경로를 더 강하게 줄였습니다. 메모리 압박이 높은 운영 구간에서는 `country report`는 memory-guard fallback을, `market opportunities`는 placeholder partial을, `stock detail`은 프론트 계약을 유지하는 최소 shell 상세를 바로 반환하도록 바꿔 first-hit 10~20초대 지연과 peak RSS를 함께 줄이는 방향으로 맞췄습니다.
- `backend/app/routers/country.py`, `backend/app/routers/stock.py`의 무거운 분석 import를 lazy import로 옮겼습니다. Render cold start와 `/api/health` 초기 응답이 불필요한 분석 모듈 적재 때문에 더 느려지고 메모리를 더 점유하던 구간을 완화하는 목적입니다.
- `backend/tests/test_country_router.py`, `backend/tests/test_stock_router.py`에 high-pressure memory guard fallback과 placeholder/shell 응답 회귀를 추가해, 압박 구간에서 heavy analysis path를 타지 않는 동작을 자동 검증으로 고정했습니다.

## v2.60.17 - 2026-04-11

- Render `500MB` memory-safe 모드에서 공개 route가 실제 메모리 압박을 잘못 읽어 non-critical side effect를 계속 이어가던 버그를 수정했습니다. memory pressure snapshot이 실제 budget bytes를 기준으로 계산되도록 바로잡아, 고압 상태에서 archive/prediction capture 같은 후처리가 더 보수적으로 건너뛰어지도록 맞췄습니다.
- 공개 `country report`는 hard-timeout 후 취소 정리까지 기다리느라 예산보다 오래 붙잡히던 경로를 `task + shield + 즉시 fallback` 구조로 바꿨습니다. fallback 내부의 `countries/archive/opportunity` 조회도 짧게 timebox해서, 운영에서 보이던 `partial인데도 10초 이상 늦는` 구간을 더 줄였습니다.
- 공개 `stock detail`도 full 분석 timeout을 hard-timeout으로 바꾸고, quick 응답 뒤에 붙던 distributional capture scheduling을 짧게 제한했습니다. 이로써 일부 티커의 first-hit 504와 quick response 뒤 추가 지연 가능성을 더 줄였습니다.
- `backend/tests/test_memory_hygiene.py`, `backend/tests/test_country_router.py`, `backend/tests/test_stock_router.py`를 확장해 memory pressure 판정, cancellation-cleanup 비대기, high-pressure ultra-fast fallback, quick-path capture timebox를 회귀로 고정했습니다.

## v2.60.16 - 2026-04-11

- 공개 `country report`와 `stock detail`은 cached/archive lookup 자체에도 짧은 timeout을 적용합니다. SQLite/cache 조회가 지연되면 오래 붙잡히지 않고 즉시 miss로 간주해 fallback/quick path로 내려가도록 바꿔, 운영에서 보인 `report는 partial인데도 10초 이상 늦는` 구간을 더 줄였습니다.
- `backend/tests/test_country_router.py`, `backend/tests/test_stock_router.py`에 slow cached lookup을 timeout으로 건너뛰고 정상 응답을 유지하는 회귀를 추가했습니다.

## v2.60.15 - 2026-04-11

- 공개 `country report`와 `stock detail`이 응답 직전에 prediction capture / archive save를 동기식으로 기다리던 경로를 정리했습니다. 이제 full report는 응답을 먼저 반환하고 저장성 후처리는 분리해, 운영에서 보이던 `SP-9999 / No response returned` 500과 첫 응답 지연 가능성을 줄였습니다.
- stock quick path와 cached full path에서는 inline prediction capture를 제거했습니다. 이미 보관된 보고서가 다시 같은 prediction row를 중복으로 쓰면서 응답 시간을 늘리고, 일부 티커에서 실패가 응답까지 전파되던 구간을 줄였습니다.
- Render `500MB` memory-safe 모드에서는 공개 후처리성 작업도 현재 pressure가 높으면 건너뛰도록 가드했습니다. 메모리 경고 상태에서 non-critical archive/capture가 다시 워크셋을 키워 peak RSS를 밀어 올리는 경로를 더 보수적으로 막습니다.
- `backend/tests/test_country_router.py`, `backend/tests/test_stock_router.py`에 partial country response와 stock cached/quick response가 inline prediction capture 없이도 정상 응답을 유지하는 회귀를 추가했습니다.

## v2.60.14 - 2026-04-11

- Render `500MB` memory-safe 모드에서 `/api/countries`가 캐시 미스 + cold start 구간에 너무 오래 붙잡히던 문제를 줄였습니다. 이제 공개 `countries`는 캐시가 비어 있어도 즉시 fallback을 돌려주고, 실제 지수 quote 재계산은 백그라운드 refresh로 분리합니다. 인덱스 quote에도 개별 timeout을 넣어 느린 외부 호출 한두 개가 전체 응답을 붙잡지 않게 했습니다.
- 공개 `screener`는 representative snapshot warming 경로가 늦어질 때도 길게 대기하지 않도록 safe-mode shell-first partial 응답을 추가했습니다. 캐시가 비어 있고 representative path가 제시간에 끝나지 않으면 먼저 shell partial을 보내고, 짧은 seed cache와 safe-mode background warmup으로 다음 요청이 빨라지도록 맞췄습니다.
- `backend/tests/test_public_dashboard_timeouts.py`를 확장해 countries safe-mode fallback/background refresh와 screener representative timeout shell 응답을 회귀로 고정했습니다.

## v2.60.13 - 2026-04-11

- Render `500MB` memory-safe 모드에서 trim이 실제로 너무 드문 간격으로만 실행돼, 운영 실측상 pressure가 `critical`인데도 `/api/health`, `/api/country/KR/report`, 일부 종목 상세가 다시 오래 붙잡히는 문제가 있었습니다. 이번 패치에서는 공개 API GET 요청 진입 전에 pre-request trim을 먼저 시도하고, `stock detail`, `daily briefing`, `market sessions`까지 공개 heavy route trim 경로를 넓혔습니다.
- memory trim cooldown은 기본 `2초`로 줄이고, pressure가 이미 `critical`이면 cooldown을 우회해 연속 요청에서도 메모리 완화를 다시 시도합니다. `/api/diagnostics`는 최상단 `render_memory_safe_mode` 플래그까지 같이 내려 운영 판독 혼선도 줄였습니다.
- `backend/tests/test_main_memory_hygiene.py`, `backend/tests/test_memory_hygiene.py`, `backend/tests/test_system_service.py`를 확장해 pre-request trim 미들웨어, critical 상태 cooldown bypass, diagnostics 플래그 노출을 회귀로 고정했습니다.

## v2.60.12 - 2026-04-11

- Render `500MB` memory-safe 모드에서 공개 heavy route(`countries`, `country report`, `heatmap`, `market opportunities`, `screener`) 응답 뒤에 메모리 압박 비율이 `70%` 이상이면 `gc.collect() + malloc_trim(0)` 기반 trim을 짧은 cooldown으로 시도하도록 추가했습니다. 큰 pandas/HTML/JSON 작업 뒤에 RSS가 OS로 잘 반환되지 않아 압박이 누적되던 구간을 운영 환경에서 직접 낮추는 목적입니다.
- `/api/diagnostics`의 `memory_diagnostics`에는 이제 `memory_trim` 메타데이터가 포함됩니다. 최근 trim 시도 횟수, 마지막 trim 사유, trim 전후 메모리 MB, trim 후 압박 비율을 같이 확인해 운영에서 실제로 메모리 완화가 일어났는지 바로 추적할 수 있습니다.
- `backend/tests/test_memory_hygiene.py`를 추가했고, 기존 timeout/public fallback 회귀와 함께 safe mode background suppression + memory trim 경로를 다시 검증했습니다.

## v2.60.11 - 2026-04-11

- Render `500MB` memory-safe 모드에서 공개 `country report`, `market opportunities`, `screener`가 partial/fallback 응답 뒤에 무거운 background refresh를 즉시 이어 붙이지 않도록 정리했습니다. 작은 인스턴스에서 공개 요청이 다시 공개 background 계산을 증폭시키며 재시작으로 이어지던 경로를 줄이는 쪽에 초점을 맞췄습니다.
- `country report` 공개 fallback은 이제 실제 동작과 맞는 안내 문구와 에러 코드를 사용합니다. background refresh를 이어가지 않는 경로에서는 “다음 재조회에서 정밀 리포트를 다시 시도한다”는 문구를 사용하고, public non-background 오류가 export용 `SP-5004`로 잘못 섞이던 copy-paste 버그도 `SP-3001` 기준으로 바로잡았습니다.
- `backend/tests/test_public_dashboard_timeouts.py`를 확장해 safe mode에서 `country/opportunities/screener` background job이 실제로 생성되지 않는지, 공개 fallback 문구가 거짓 약속을 하지 않는지, public country error path가 export용 코드로 오염되지 않는지를 회귀로 고정했습니다.

## v2.60.10 - 2026-04-11

- 메모리 hot cache에 `entry_count + total bytes + per-entry bytes` 상한을 함께 걸고, oversized payload는 SQLite에만 저장하고 in-memory cache에는 올리지 않도록 정리했습니다. Render memory-safe 모드에서는 캐시 상한을 더 보수적으로 적용해 `500MB` 서버에서 큰 partial/report payload가 deep copy와 함께 누적되는 경로를 줄였습니다.
- `/api/diagnostics`는 `memory_diagnostics`를 함께 반환해 RSS/cgroup 사용량, cache entry 수, 추정 캐시 바이트, oversized write skip 횟수, memory pressure 상태를 바로 볼 수 있게 했습니다. accuracy/research archive probe도 병렬화해 진단 엔드포인트 자체의 응답 시간을 더 짧게 유지합니다.
- 공개 지연 경로는 `market/opportunities` quick timeout, `stock detail` quick/full grace, 홈·레이더·스크리너·종목/관심종목 SSR timebox를 더 짧게 조정했습니다. fallback 구조는 유지하면서 first HTML과 quick partial 응답이 cold path를 오래 기다리지 않도록 다시 맞췄습니다.
- `backend/tests/test_cache_and_universe.py`, `backend/tests/test_system_service.py`를 확장해 oversized memory cache skip과 diagnostics 병렬 probe를 회귀로 고정했고, `verify.py --skip-frontend`, `verify.py --skip-frontend --live-api-smoke`까지 다시 통과했습니다.

## v2.60.9 - 2026-04-10

- `verify.py --deployed-site-smoke`가 하위 headless browser 프로세스에서 오래 멈추지 않도록 `browser_smoke.py`에 per-command timeout과 전체 deadline을 추가하고, `verify.py`도 같은 시간 예산을 넘겨 주도록 정리했습니다. 이제 배포 브라우저 스모크는 hang 대신 구조화된 실패로 빠르게 종료됩니다.
- `backend/tests/test_browser_smoke_runtime.py`를 추가해 browser subprocess timeout, virtual time 기준 timeout 보정, 전체 deadline 초과 시 즉시 종료를 회귀로 고정했습니다.
- `country report` timeout 회귀 테스트는 최근 `last_success`/archived cache 상태에 흔들리지 않도록 분리해, 검증 순서에 따라 `partial` 필드 기대가 깨지던 flaky 경로를 정리했습니다.
- SQLite schema bootstrap은 import 시점과 startup `initialize()`에서 두 번 반복하지 않도록 1회 보장으로 바꿨습니다. `backend/tests/test_database_cache_resilience.py`에 constructor + initialize 중복 bootstrap 방지 회귀를 추가했고, cold start 초기화 비용을 더 줄였습니다.

## v2.60.8 - 2026-04-10

- UI 품질 루프를 한 번 더 돌려 `action-chip`이 실행 CTA로 남아 있던 구간을 추가 정리했습니다. `AuthGateCard`, `PortfolioConditionalRecommendationPanel`, `OpportunityRadarBoard`, `RadarNextDayFocusCard`의 로그인/회원가입, 조건 추천 실행, 연구실 이동, 종목 상세 이동은 모두 `primary / secondary` button hierarchy로 다시 흡수했습니다.
- `/settings`의 계정 패널은 로그인 전 CTA를 공용 버튼으로 맞추고, 보안/이메일/탈퇴 보조 패널이 `lg`부터 더 이른 시점에 2열로 읽히도록 조정해 데스크톱 세로 길이와 액션 혼선을 줄였습니다.
- `/watchlist`는 관심종목 추가, 심화 추적, 상세 보기, 제거 버튼을 공용 실행 버튼 계층으로 다시 정리했고, `/country/[code]/sector/[id]`는 모바일에서 상위 종목 summary card를 먼저 보여준 뒤 `md` 이상에서 표를 확장하도록 보강했습니다.

## v2.60.7 - 2026-04-10

- 전 화면 UI 리디자인 품질 루프를 한 번 더 돌려 `globals.css`, `layout.tsx`, `Navigation`, `SearchBar`, `AuthStatus`의 공용 비율과 간격을 다시 조정했습니다. 데스크톱 좌측 레일은 더 슬림하게 줄이고, 상단 검색/계정 스트립과 `PageHeader`는 더 낮은 높이로 맞춰 첫 viewport에서 제목과 첫 판단 카드가 함께 보이도록 정리했습니다.
- `/`, `/radar`, `/calendar`, `/screener`, `/compare`, `/archive`, `/stock/[ticker]`의 카드 스팬과 버튼 언어를 다시 다듬어, 실행 버튼은 `primary / secondary / text`, 필터/세그먼트만 chip으로 남기도록 정리했습니다. 특히 `/calendar`는 단일 국가일 때 어색한 헤더 액션을 숨기고, 상단 빈 공간을 agenda preview와 이번 달 리듬 요약으로 다시 채웠습니다.
- `/watchlist`, `/settings`, `/country/[code]/sector/[id]`는 모바일/태블릿 흐름을 추가로 보강했습니다. 관심종목 추가/삭제/상세/심화 추적은 button 계층으로 다시 흡수했고, 설정 패널은 로그인 전 CTA와 보안/이메일 패널 배치를 정리했으며, 섹터 상세는 모바일에서 상위 종목 summary card를 먼저 보여주고 `md` 이상에서 표를 확장하도록 바꿨습니다.
- `DESIGN_BIBLE.md`와 `README.md`를 현재 공용 규칙에 맞게 갱신해, slim rail, action chip 제한, 상태 카드 액션 스택, summary-first 모바일 규칙이 실제 구현과 같은 의미를 말하도록 동기화했습니다.

## v2.60.6 - 2026-04-10

- `kr_market_quote_client`의 representative quote 캐시에 짧은 `wait_timeout`과 `last_success` fallback을 추가했습니다. 이제 공개 `/api/screener?country=KR&limit=20`의 cold partial 경로가 느린 대표 시세 fetch를 끝까지 기다리지 않고, 최근 정상 시세가 있으면 바로 그 값을 재사용하며 없을 때도 빈 placeholder로 빨리 복귀한 뒤 background refresh를 이어 갑니다.
- `backend/tests/test_kr_market_quote_client.py`, `backend/tests/test_public_dashboard_timeouts.py`를 확장해 대표 시세 refresh timeout 시 stale cache 즉시 응답, 첫 timeout의 empty placeholder 복귀, screener bulk partial fallback 경로를 회귀로 고정했습니다.

## v2.60.5 - 2026-04-10

- 공개 `/api/country/{code}/report`는 최근 정상 `last_success` 캐시가 있으면 그 응답을 먼저 내리고, 캐시가 없더라도 최근 아카이브가 있으면 stale public fallback을 즉시 내려주도록 바꿨습니다. 최신 정밀 계산은 background refresh로 계속 이어 가기 때문에 운영에서 첫 응답이 `20초+`로 늘어지는 구간을 더 줄였습니다.
- `country_analyzer`는 정상 리포트를 만들면 `country_report:last_success:{code}` 캐시도 함께 갱신해, 공개 국가 리포트가 timeout에 매번 새로 걸리지 않고 가장 최근의 정상 결과를 다시 사용할 수 있게 했습니다.
- `backend/tests/test_country_router.py`를 확장해 `last_success` 즉시 응답과 archived stale public fallback 우선 경로를 회귀로 고정했습니다.

## v2.60.4 - 2026-04-10

- 공개 `/api/country/{code}/report`는 정밀 계산 timeout을 export timeout과 분리했습니다. 공개 경로는 더 이른 시점에 partial fallback으로 내려가 Render 워밍업이나 느린 외부 소스 구간에서도 배포 스모크의 `15초` 기준을 더 잘 맞추고, PDF/CSV export는 기존 여유 시간을 유지합니다.
- `country report` fallback은 최근 정상 아카이브에 이미 `top_stocks`가 있으면 quick 후보 조회를 다시 돌지 않도록 순서를 정리했습니다. 그래서 timeout fallback 단계에서 quick 후보 경로를 한 번 더 기다리며 응답이 불필요하게 길어지던 구간을 줄였습니다.
- `backend/tests/test_country_router.py`, `backend/tests/test_public_dashboard_timeouts.py`를 확장해 공개/내보내기 timeout budget 분리와 archived report 우선 fallback 경로를 회귀로 고정했습니다.

## v2.60.3 - 2026-04-10

- `market/opportunities`의 `next_day_focus`와 기회 아이템 빌더를 다시 정리해, `NaN`/`inf`가 섞인 예측값·분위수·trade plan 값이 들어와도 JSON 직렬화가 깨지지 않고 안전한 기본값으로 내려가도록 보강했습니다.
- `backend/tests/test_market_service.py`에 `allow_nan=False` 직렬화 회귀와 비정상 예측값 sanitize 테스트를 추가해, 실제로 실패했던 레이더 응답 경로를 다시 고정했습니다.
- 분포 인코더, 시장 국면, 과거 패턴 예측, 공포·탐욕 점수, `yfinance` 수익률 추출의 로그 수익률 계산을 `0`/음수 가격 안전 경로로 정리해 `verify.py --skip-frontend --live-api-smoke` 기준 `RuntimeWarning`이 남지 않도록 보강했습니다.
- `backend/tests/test_log_safety.py`를 추가해 비정상 가격이 섞여도 `price_encoder`, `market_regime`, `historical_pattern_forecast`, `fear_greed`, `get_historical_returns`가 `RuntimeWarning` 없이 유한값만 내도록 회귀를 고정했습니다.

## v2.60.2 - 2026-04-10

- `/api/briefing/daily`의 내부 레이더 로딩을 soft-timeout 방식으로 다시 묶었습니다. 이제 느린 quick 레이더 작업이 취소를 늦게 받거나 늦게 끝나도 브리핑 전체가 그 cleanup를 기다리며 오래 붙잡히지 않고, partial 요약 응답이 더 빨리 내려갑니다.
- 브리핑 회귀 테스트를 확장해, 늦게 끝나는 레이더 작업이 있어도 서비스가 빠르게 partial로 복귀하는 동작을 고정했습니다.
- `verify.py`에 workspace lock과 `--allow-parallel` 우회 옵션을 추가해, 같은 저장소에서 regression sweep를 겹쳐 실행할 때 unittest/cache probe가 서로 간섭하던 flaky 경로를 기본값에서 막았습니다.
- `backend/tests/test_verify_runtime.py`를 확장해 active lock 차단과 stale lock 정리까지 회귀로 고정했습니다.

## v2.60.1 - 2026-04-09

- 모바일 상단 chrome과 `PageHeader`, `SearchBar`, `AuthStatus` 간격을 다시 조정해 `네비게이션 -> 검색 -> 계정 -> 본문` 흐름이 첫 화면에서 과하게 쌓이지 않도록 정리했습니다.
- `/auth`, `/settings`, `/portfolio`, `/watchlist`, `/stock/[ticker]`의 모바일 레이아웃을 보강했습니다. segmented 전환, 입력/액션 래핑, 긴 이메일 줄바꿈, 모바일 카드 액션 정렬, 고정 폭 보조 패널 제거를 함께 맞췄습니다.
- `/stock/[ticker]`는 차트 컨트롤 래핑을 정리하고, 최근 재무 스냅샷에 모바일 카드 요약을 추가해 좁은 화면에서는 summary-first, `md` 이상에서는 표 상세를 유지하도록 바꿨습니다.
- `DESIGN_BIBLE.md`와 `README.md`를 갱신해 모바일 first viewport, dense action wrapping, dense table의 모바일 대체 규칙이 현재 구현과 같은 의미를 말하도록 동기화했습니다.
- `PublicAuditStrip`와 `MetricValueCard`에 모바일 wrap 안전장치를 추가하고, `/settings`의 API 경로 표기와 `/stock/[ticker]`의 가이드·복합 점수 헤더를 더 느슨하게 재배치해 긴 메타와 값이 좁은 화면에서 잘리지 않도록 보강했습니다.
- `/calendar`, `/watchlist/[ticker]`, `OpportunityRadarBoard`는 모바일 action row를 공용 래핑 규칙에 맞추고, 긴 운영 설명을 pill에서 본문 메모로 내려 디자인 기준의 `긴 문장을 pill 안에 넣지 않는다` 원칙과 같은 흐름으로 다시 정리했습니다.
- `NextDayForecastCard`, `TradePlanCard`, `HistoricalPatternCard`, `SetupBacktestCard`는 상단 summary row와 5칸 metric strip을 모바일 우선 1열/2열 흐름으로 다시 배치해 종목 상세 내부 카드도 같은 반응형 리듬을 따르도록 맞췄습니다.
- `dev_runtime.py`, `start.py`, `verify.py`의 실행기 해석 규칙을 통일했습니다. 이제 Python은 `repo-local venv -> 현재 Python -> Windows py -3`, 프론트 실행기는 `frontend/node_modules/.bin -> PATH npm/npx` 순서로 찾고, `verify.py --deployed-site-smoke`가 로컬 dev server를 불필요하게 띄우던 동작도 제거했습니다.
- `verify.py`에 `--full-sweep`, backend requirements import probe, responsive viewport matrix 연결을 추가하고, `--skip-frontend`는 `start.py --check --skip-frontend`와 같은 의미로 동작하도록 맞췄습니다. 그래서 frontend toolchain이 없는 backend-only 점검과 missing dependency 실패가 더 짧고 분명하게 보입니다.
- backend data 경로에서 이미 사용하던 `requests`를 `backend/requirements.txt`에 반영하고, 관련 런처/verify 회귀 테스트를 추가해 새 환경에서 requirements 누락 때문에 검증 루프가 불완전하게 깨지지 않도록 보강했습니다.

## v2.60.0 - 2026-04-08

- 전역 UI 디자인 시스템을 `glass/card-heavy` 톤에서 `brutal editorial + less is more` 기준으로 다시 정리했습니다. 라이트 모드를 canonical theme로 두고 `IBM Plex Sans KR`와 `IBM Plex Mono`를 기준 글꼴로 맞췄습니다.
- `globals.css`, `layout.tsx`, `Navigation`, `SearchBar`, `AuthStatus`, `WorkspaceStateCard`를 다시 설계해 상단 chrome, 상태 카드, 입력 필드, slab/metric/data frame 규칙을 하나의 시각 언어로 통일했습니다.
- `/compare`, `/country/[code]`, `/country/[code]/sector/[id]`, `/settings`, `/auth`, `/lab`와 홈/레이더/종목/포트폴리오 핵심 패널을 새 primitive 기준으로 정리해 pill 남발, 다중 보더, 긴 문장의 캡슐 배치를 줄였습니다.
- `DESIGN_BIBLE.md`를 전면 갱신해 `한 블록 = 한 visible frame`, `chip은 짧은 상태만`, `긴 한국어 문장은 box보다 rhythm 우선` 규칙을 canonical spec으로 명시했습니다.

## v2.59.0 - 2026-04-07

- `/api/research/predictions`에 `pipeline_health`, `coverage_breakdown`, `pipeline_alerts`를 additive로 추가하고, `/lab` 첫 화면을 `표본 수집 퍼널 -> horizon 커버리지 -> 지금 막히는 지점` 순서로 다시 정리했습니다.
- `prediction_capture_service`를 도입해 `stock` quick detail, `country` partial report, `market/opportunities` quick/cached 응답에서도 canonical sample을 누적하도록 복구했습니다.
- 최근 archive만 작은 배치로 복구하는 bounded backfill을 연구실 집계 경로에 연결해, 누락된 prediction log를 한 번에 몰지 않고 되살리도록 조정했습니다.

## v2.58.1 - 2026-04-07

- iPhone Safari 기준으로 `Navigation`, `SearchBar`, `AuthStatus`, `PageHeader`를 다시 묶어 모바일 상단 shell을 더 낮고 읽기 쉽게 정리했습니다.
- `WorkspaceStateCard`와 `ErrorBanner` 시각 규칙을 맞추고, `/`, `/radar`, `/stock/[ticker]`, `/portfolio`, `/watchlist`, `/lab`에서 `blocking / partial / empty / loading` 상태 표현을 같은 언어로 통일했습니다.
- `/calendar` 모바일 월간 보드를 `월 제목 -> 이동 컨트롤 -> 범례 -> 월간 보드 -> 선택 날짜 agenda` 순서로 재정리하고, 날짜 셀은 `날짜 번호 + 이벤트 점/건수 + 선택 강조` 중심으로 단순화했습니다.

## v2.58.0 - 2026-04-06

- `다음 거래일 포커스` 추천에 단타용 `차트 점수`를 추가했습니다. 추세 정렬, MACD 모멘텀, RSI 위치, 거래량 확인, 볼린저 밴드/돌파 품질, ATR 기반 과열 여부를 묶어 1일 추천 점수에 크게 반영합니다.
- 포커스 카드에 차트 총점, 진입 스타일, 핵심 차트 신호를 함께 보여주도록 바꿨습니다. 이제 사용자는 왜 이 종목이 뽑혔는지와 추격보다 눌림이 나은지까지 같은 카드에서 바로 확인할 수 있습니다.
- 차트 점수 전용 백엔드 테스트와 포커스 통합 테스트를 추가해, `질서 있는 돌파`가 `과열 추격`보다 높은 평가를 받는 회귀를 고정했습니다.

## v2.57.0 - 2026-04-06

- `다음 거래일 포커스`의 후보군을 넓히고, 최근 급등 종목은 추격 매수를 줄이도록 감점하는 선별 로직을 추가했습니다. 이제 상단 추천은 보드 상위 몇 종목 재사용보다 `넓은 레이더 후보군 재평가`에 가깝게 동작합니다.

- `/radar`에 `다음 거래일 포커스`를 추가했습니다. 이제 레이더 응답은 상위 후보 중 1일 예상 수익률, 상승 확률, 손익비, 시장 국면을 함께 본 단기 추천 1종목과 진입가/손절가/목표가를 additive로 포함합니다.
- 기회 레이더 상단 흐름을 `단기 포커스 -> 첫 판단 스레드 -> 시장 국면 -> 20거래일 후보 보드` 순서로 다시 정리했습니다. 사용자가 먼저 바로 볼 1종목을 읽고, 그다음 전체 레이더 근거를 내려가며 확인할 수 있게 맞췄습니다.
- `시장 국면` 카드 내부 배치도 다시 정리해 summary, 플레이북, 판단 강도, 세부 신호가 넓은 화면에서 멀리 떨어져 보이며 생기던 빈 공간을 줄였습니다.
- 레이더 후보 보드의 확률/수익률 라벨은 `20거래일` 기준임을 명시하도록 정리했습니다. 그래서 상단 `다음 거래일 포커스`와 아래 레이더 후보 보드의 시간축이 섞여 보이던 혼선을 줄였습니다.

## v2.56.0 - 2026-04-05

- KR `Opportunity Radar`의 기본 유니버스를 `코스피 상위 190개 + 코스닥 상위 10개` 대표 200종목으로 고정했습니다. 그래서 레이더의 1차 스캔 숫자, 후보 보드, 설명 문구가 실제 운영 동작과 같은 의미를 말하도록 맞췄습니다.
- KR quick path는 이제 대표 200종목 quote screen을 먼저 만들고, 그 안에서 상위 후보만 정밀 분석합니다. `KRX listing cache`나 전종목 quote 확보가 늦어질 때도 대표 유니버스 기준 후보를 더 빠르게 보여주도록 cache key와 seed 재사용 조건을 함께 정리했습니다.
- `/radar` 페이지 헤더와 레이더 보드 문구도 `대표 유니버스`, `코스피 190개 + 코스닥 10개` 기준으로 바꿨습니다. README와 화면에서 여전히 전종목 스캔처럼 읽히던 혼선을 줄였습니다.

## v2.55.2 - 2026-04-05

- `/api/research/predictions`와 예측 연구실 기본 조회가 `refresh=false`여도 만기 도달한 pending 예측 로그를 짧은 background refresh로 먼저 재평가하도록 바꿨습니다. 이 경로는 cache miss 기준에서만 제한적으로 돌고, 만기 표본이 있으면 연구실 통계를 더 빨리 실측값으로 승격합니다.
- 연구실 인사이트와 액션 큐에 `저장된 로그는 있지만 아직 실측 평가가 끝난 표본이 없는 상태`를 별도 안내하도록 보강했습니다. 이제 `stored_predictions`, `pending_predictions`, `total_predictions=0` 조합이 단순 bootstrapping 메시지로 묻히지 않습니다.
- `archive_service.refresh_prediction_accuracy()`는 평가 요약을 반환하고, 실제로 새 표본을 평가한 경우에만 empirical calibration refresh를 이어 실행합니다. 덕분에 연구실 기본 조회와 운영 startup에서 불필요한 무거운 재보정을 줄였습니다.
- Render 메모리 세이프 startup에서도 `prediction_accuracy_refresh`만은 제한된 timeout과 작은 limit로 실행되도록 조정했습니다. `learned_fusion`, `research archive sync`, `market opportunity prewarm` 같은 더 무거운 작업은 계속 건너뜁니다.
- Render 배포 설정에서 연구실 DB 경로를 `/tmp` 대신 앱 경로로 옮기고, startup prediction accuracy refresh를 다시 활성화했습니다. free 플랜의 장기 영속성 한계는 남아 있지만, sleep 이후나 짧은 재시작 뒤에도 표본이 비어 보이는 시간을 줄였습니다.

## v2.55.1 - 2026-04-04

- 모바일 고정 상단 바 오프셋을 본문 열 기준으로 다시 맞춰, 첫 진입 시 검색 헤더와 페이지 첫 카드가 상단 UI 아래로 겹쳐 보이던 문제를 수정했습니다.
- 모바일 메뉴 드로어를 독립 스크롤 컨테이너로 바꾸고 body scroll lock을 추가해, 긴 메뉴에서도 하단 항목까지 안정적으로 탐색할 수 있게 했습니다.
- `info-chip`, `ui-chip`, 버튼, 경고/빈 상태 패널에 모바일 줄바꿈과 overflow 보호 규칙을 공통으로 적용해, 긴 문구가 컬러 박스나 액션 영역 밖으로 튀어나오지 않게 했습니다.

## v2.55.0 - 2026-04-04

- `/lab` 예측 연구실에 `지금 볼 것` 액션 큐를 추가해, horizon별 표본 부족, calibration gap, graph coverage 저하, 고신뢰 미스 같은 신호를 우선순위로 정리해 보여줍니다.
- 최근 실측 로그를 묶어 `반복되는 실패 패턴`을 새로 노출하고, 어떤 종류의 미스가 반복되는지와 평균 오차/신뢰도를 한 번에 읽을 수 있게 했습니다.
- `리뷰 큐`를 추가해 최근 예측 중 먼저 복기할 항목을 정렬하고, stock scope 항목은 `/stock/[ticker]` 상세 화면으로 바로 이어지게 했습니다.
- prediction lab 응답에 `action_queue`, `failure_patterns`, `review_queue`, `prediction_type`, `prediction_label`을 additive로 확장하고, 관련 회귀 테스트와 프론트 타입을 함께 맞췄습니다.

## v2.54.2 - 2026-04-04

- `/api/country/KR/report`가 라이브 계산을 끝내지 못하는 구간에도 최신 아카이브 리포트를 stale-but-usable fallback으로 되살려, 대시보드의 핵심 뉴스, 상위 종목, 오늘 포커스가 한 번에 비는 현상을 줄였습니다.
- `/api/country/KR/heatmap`은 대표 종목 quote 또는 마지막 정상 스냅샷을 우선 재사용하도록 보강해, partial fallback이 all-gray 또는 `+0.00%` 기준 화면처럼 보이는 문제를 줄였습니다.
- `/api/market/movers/KR`는 representative quote fallback과 last-success cache를 추가해, 무료 티어 워밍업이나 짧은 타임아웃 뒤에도 상승/하락 상위 패널이 완전히 비지 않도록 조정했습니다.
- 홈 대시보드 movers 패널은 빈 gainers/losers 배열만 도착한 partial 응답을 정상 패널로 렌더하지 않고, 지연 상태 카드로 정리해 오해를 줄였습니다.

## v2.54.1 - 2026-04-04

- `/watchlist`가 legacy 예측 이력 list payload를 받을 때 preview 집계가 `.get()` 호출로 죽으며 목록 전체가 실패하던 문제를 수정했습니다. 이력 payload는 이제 dict/list 두 형태를 모두 흡수하고, 관련 회귀 테스트도 추가했습니다.
- 대시보드 지수/보조지표 fallback은 더 이상 `0`, `₩0`, `$0` 같은 숫자를 실제 값처럼 보여주지 않습니다. usable 값이 없는 경우에는 지연 안내를 먼저 보여주고, 확보된 수치만 카드로 렌더합니다.
- 히트맵 partial fallback은 zero-change snapshot을 전부 초록색 보드로 칠하지 않고 중립 톤으로 렌더하도록 바꿨습니다. 그래서 실시간 등락률 분포 지연이 상승장처럼 오해되는 문제를 줄였습니다.
- `기회 레이더`의 운영성 fallback 문구를 상단 안내 한 줄로 모으고, usable 후보 카드에서는 generic fallback copy를 제거했습니다. 실제 경고와 실행 포인트가 운영 메시지에 묻히지 않도록 정리했습니다.
- `/portfolio`는 모델 포트폴리오 서브계산이 실패해도 계정 자산 요약과 보유 종목 workspace를 그대로 유지하고, `model_portfolio`만 degraded fallback으로 내려가도록 fail-open 경로를 추가했습니다.

## v2.54.0 - 2026-04-04

- 관심종목 row를 확장해 `tracking_enabled`, `tracking_started_at`, `tracking_updated_at`를 같은 lifecycle 안에서 관리하도록 정리하고, 별도 tracking table 없이 심화 추적 on/off를 저장하도록 바꿨습니다.
- `/watchlist`에 `전체 / 추적 중` 필터, tracked-first 정렬, `심화 추적 시작/중지`, `상세 보기` 흐름을 추가했습니다. 추적 중인 종목은 최근 예측 라벨과 신뢰도 preview를 바로 보여줍니다.
- 새 상세 화면 `/watchlist/[ticker]`를 추가했습니다. 이 화면은 공개 stock shell을 먼저 렌더하고, 로그인 후에는 관심종목 membership을 확인한 뒤 최근 예측 변화, 적중 기록, 현재 판단 근거를 이어서 불러옵니다.
- 보호 API `POST /api/watchlist/{ticker}/tracking`, `DELETE /api/watchlist/{ticker}/tracking`, `GET /api/watchlist/{ticker}/tracking-detail`를 추가했습니다. 관심종목에 없는 종목으로 심화 추적을 요청하면 새 에러 코드 `SP-6017`을 반환합니다.
- `/stock/[ticker]`에서 관심종목 여부를 확인해 심화 추적 시작/보기로 연결되는 진입 패널을 추가했고, 기존 공개 stock detail 분석과 watchlist 상세 흐름이 자연스럽게 이어지도록 정리했습니다.

## v2.53.2 - 2026-04-04

- 전 화면 반응형 정리를 위해 `frontend/src/app/globals.css`에 semantic `clamp()` typography / spacing / control 토큰을 추가하고, 버튼·입력·패널·테이블 래퍼를 `ui-button-*`, `ui-input`, `ui-panel*`, `ui-table-shell` 공용 primitive로 다시 묶었습니다.
- `layout`, `Navigation`, `SearchBar`, `AuthStatus`를 같은 밀도 체계로 다시 정리해 모바일 드로어, 상단 검색, 계정 배지가 작은 화면에서도 겹치지 않도록 조정했습니다.
- `/auth`, `/settings`, `/portfolio`, `/screener`의 line-panel, form, CTA 버튼을 공용 반응형 스타일로 옮기고, `portfolio`와 `screener`는 모바일 카드형 요약 + 데스크톱 테이블 혼합 정책으로 재구성했습니다.
- `scripts/browser_smoke.py`에 다중 viewport 옵션을 추가해 `390x844`, `768x1024`, `1440x900` 같은 반응형 검증을 route smoke에 함께 태울 수 있게 했습니다.
- `market_service`는 현재 유니버스 source/size와 맞는 경우에만 cached quick seed를 재사용하도록 좁혀, 큰 quick cache가 작은 mocked universe를 덮어써 `market_service` 회귀 테스트가 깨지던 문제를 함께 수정했습니다.

## v2.53.1 - 2026-04-04

- `/api/country/KR/report`가 실데이터에서 `NaN` 또는 `Infinity`를 포함할 때 `SP-9999` 500으로 떨어지던 운영 오류를 수정했습니다. 국가 리포트 응답은 이제 비정상 float를 `null`로 정리한 뒤 JSON으로 반환합니다.
- settings 계정 패널의 프로필 저장 흐름을 `useAccountProfileSection` 훅으로 분리해 프로필 draft, 아이디 중복 확인, 저장 오류 처리를 페이지 렌더 로직과 분리했습니다.
- `frontend/src/lib/api.ts`를 계속 얇게 유지하도록 `market`, `portfolio` 도메인 클라이언트를 추가로 분리했고, browser smoke의 calendar 계약도 현재 운영 UI 문구와 맞췄습니다.

## v2.53.0 - 2026-04-02

- 전체 워크스페이스 안정성 리팩터링의 첫 단계를 반영했습니다. 백엔드는 `route_trace`와 `route_stability_service`를 추가해 `request_phase`, `cache_state`, `served_state`, `fallback_reason`, cold-start 의심 여부를 공통 규칙으로 기록하고, `/api/diagnostics`에 route 안정성 요약과 first usable / hydration / session recovery 지표를 additive로 노출합니다.
- `market_service`, `portfolio_service`, `distributional_return_engine`는 기존 import 계약을 깨지 않으면서 thin facade 구조로 정리하기 시작했습니다. `backend/app/services/market/*`, `backend/app/services/portfolio/*`, `backend/app/analysis/distributional/*` 패키지로 순수 helper와 validation/summary/encoder 로직을 분리해 quick/full/fallback 책임이 큰 파일 한 곳에 뭉치지 않게 바꿨습니다.
- 프론트는 `frontend/src/lib/api/` 아래에 request/auth/error 코어를 분리하고, `/`, `/radar`, `/stock/[ticker]`, `/portfolio`, `/watchlist`, `/settings`에서 SSR 성공, hydration refetch 성공/timeout, panel degrade, session recovery failure를 공통 방식으로 기록합니다. 그래서 “HTML은 200인데 hydration 뒤 blank/error-only로 무너지는” 회귀를 settings diagnostics와 browser smoke에서 더 빨리 볼 수 있습니다.
- route 안정성 기준에 맞춰 홈과 레이더도 독립 패널 단위로 계측하고, stock detail quick/full, portfolio/watchlist panel isolation, diagnostics UI까지 같은 언어로 묶었습니다. 이 패스는 UI 재디자인이 아니라 shell/quick/full과 세션/패널 실패를 서로 독립적으로 다루는 구조 정리에 집중합니다.

## v2.52.11 - 2026-04-02

- KR 레이더의 `quick quote-only` 점수식이 상단 급등 종목에서 너무 빨리 `90.0` 상한에 닿아 카드가 같은 점수로 평탄해지던 문제를 조정했습니다. 이제 quick 후보는 `변동률 + 상대 순위`를 함께 반영하되 상한을 낮춰, 1차 스캔 상태에서도 상위 후보 간 점수 차이가 유지됩니다.
- `get_cached_market_opportunities()`는 이제 `detailed_scanned_count > 0`인 실제 정밀 snapshot만 `cached full`로 승격합니다. 그래서 quote-only 결과가 full cache처럼 보이며 `/radar`에서 정밀 계산이 끝난 것처럼 읽히는 혼선을 줄였습니다.
- background full refresh는 최근 usable quick 후보를 seed로 재사용해 상위 종목 정밀 스캔을 다시 시도합니다. 응답은 계속 quick로 먼저 살리되, 뒤에서는 이미 확보된 후보를 바로 분석하게 바꿔 full snapshot이 올라올 가능성을 높였습니다.
- 레이더/포트폴리오/관심종목 UI에서도 `전수 1차 스캔` 후보는 `레이더 점수` 대신 `1차 스캔 점수`로 표시하도록 정리했습니다. 그래서 quick quote-only 후보를 정밀 레이더 점수처럼 오해하기 어렵게 맞췄습니다.

## v2.52.10 - 2026-03-30

- 개별 종목 상세 quick fallback의 후속 처리 방식을 Render 저메모리 운영 환경에 맞게 다시 정리했습니다. 이제 `/api/stock/{ticker}/detail`이 quick partial을 반환한 뒤 무거운 full 분석을 무조건 background task로 떼어놓지 않고, memory-safe 모드에서는 브라우저의 후속 `prefer_full=true` 요청 안에서만 bounded full refresh를 시도합니다.
- 그래서 stock detail 한 번 조회한 뒤 detached full-analysis task가 남아 backend health까지 같이 흔들리던 복합 장애를 줄였습니다. quick snapshot은 계속 first click을 살리고, richer detail 업그레이드는 사용자가 실제 보고 있는 페이지의 follow-up request 안에서만 수행됩니다.
- full detail이 완성됐을 때 archive save도 memory-safe 모드에서는 같은 요청 안에서 마치도록 바꿔, post-response background 작업이 Render 인스턴스에 남지 않게 했습니다.
- 운영 스모크는 `stock-detail` 호출 뒤 `/api/health`를 한 번 더 확인하도록 넓혀, 개별 종목 페이지가 200을 준 직후 backend가 다시 502로 쓰러지는 회귀를 더 빨리 잡을 수 있게 했습니다.

## v2.52.9 - 2026-03-30

- 개별 종목 상세의 first click 흐름을 다시 정리했습니다. `/api/stock/{ticker}/detail`은 이제 `cached full -> cached quick -> fresh quick -> background full refresh` 순서로 응답해, uncached 종목이라도 빠른 partial snapshot을 먼저 내려 화면이 통째로 빈 에러 카드로 무너지지 않게 맞췄습니다.
- quick stock snapshot은 `fallback_reason=stock_quick_detail`로 명시하고, full detail과 archive save는 응답 뒤 background task로 분리했습니다. 그래서 detail route가 archive DB 저장까지 기다리며 더 느려지던 복합 병목을 줄였습니다.
- 개별 종목 페이지 `/stock/[ticker]`는 client-only first paint 대신 server-first initial snapshot을 사용하도록 바꿨습니다. 첫 HTML에 partial stock snapshot이 있으면 그대로 보여주고, hydration 뒤에는 partial일 때만 background refetch를 걸어 full detail로 교체합니다.
- 운영 스모크 범위에 `GET /api/stock/003670/detail`과 `/stock/003670.KS`를 추가해, stock detail API와 페이지가 다시 `504` 또는 빈 화면으로 회귀하는 문제를 더 빨리 잡을 수 있게 했습니다.

## v2.52.8 - 2026-03-30

- 개별 종목 상세 `/api/stock/{ticker}/detail`의 복합 장애를 정리했습니다. 이벤트 컨텍스트가 ISO timezone 날짜와 naive 날짜를 섞어 읽을 때 `can't subtract offset-naive and offset-aware datetimes`로 `SP-3003` 500을 내던 경로를 UTC 정규화로 고쳤습니다.
- 종목 상세 캐시는 더 이상 2년 price history를 먼저 모두 읽은 뒤에야 cache hit를 확인하지 않습니다. 최신 usable detail snapshot을 먼저 확인하고, quote refresh가 늦거나 실패해도 저장된 snapshot을 그대로 재사용하도록 바꿔 first paint를 더 안정적으로 유지합니다.
- stock detail route는 timeout이나 조합 오류가 나도 최근 저장 snapshot이 있으면 `200 + partial + fallback_reason=stock_cached_detail`로 먼저 반환합니다. 프론트 detail 화면도 이 메타를 audit strip으로 표시해, 개별 종목 페이지가 한 번의 detail 실패로 통째로 빈 에러 화면이 되지 않도록 맞췄습니다.

## v2.52.7 - 2026-03-30

- dense workspace 화면의 공통 레이아웃 축을 정리했습니다. 대시보드, 레이더, 포트폴리오, 캘린더, 아카이브, 관심종목이 더 이상 페이지마다 다른 `main / aside` 비율을 쓰지 않고, 같은 폭과 시작선 기준으로 읽히도록 맞췄습니다.
- `기회 레이더`의 compact board는 상단 요약과 숫자 스트립을 한 줄에서 억지로 나누지 않고, 배지 -> 요약 수치 -> 후보 목록 순서로 다시 정리했습니다. 그래서 대시보드의 `강한 셋업`과 레이더 내부 compact view에서 세로로 찌그러진 숫자 칩이나 들쑥날쑥한 정렬이 줄었습니다.
- `포트폴리오`, `아카이브`, `예측 연구실`은 실패/표본 부족 상태를 빈 공백이나 거대한 빈 차트로 두지 않고, 지금 무엇이 준비됐고 다음에 무엇이 채워질지 설명하는 상태 카드로 바꿨습니다. 특히 `prediction lab`은 검증 표본이 적을 때 큰 빈 그래프 대신 bootstrapping 상태를 먼저 보여줍니다.
- `관심종목` 화면도 나머지 워크스페이스와 같은 헤더/입력/목록 구조로 다시 정리해, 별도 툴처럼 보이던 밀도와 정렬 차이를 줄였습니다.
- 사이드바의 테마 토글은 서버와 클라이언트가 같은 아이콘/레이블 기준으로 먼저 렌더되게 맞춰, 로컬과 개발 환경에서 보이던 hydration mismatch와 초기 레이아웃 흔들림을 줄였습니다.

## v2.52.6 - 2026-03-29

- `calendar`와 `prediction lab`의 남아 있던 복합 병목을 추가로 정리했습니다. `calendar`는 경제 일정과 실적 일정을 순차로 기다리지 않고 병렬 source fetch로 가져오며, 한 source가 늦어도 이미 확인된 실제 일정과 월간 핵심 일정을 먼저 반환합니다. 그래서 외부 FMP 한쪽이 지연돼도 전체 월간 보드가 recurring placeholder처럼 오래 고정되는 경로를 줄였습니다.
- FMP 경제/실적 캘린더 source cache key를 `v2`로 올리고 source HTTP timeout을 줄였습니다. 예전 빈 source 결과가 오래 재사용되던 상태를 끊고, 이번 릴리즈부터는 새 병렬 fetch 결과가 바로 새 cache로 채워지도록 맞췄습니다.
- `prediction lab`은 더 이상 요청 시마다 `prediction_evaluated_samples`를 다시 훑어 learned fusion / graph runtime 상태를 집계하지 않습니다. profile refresh에서 만든 runtime summary를 재사용해 first screen을 더 가볍게 만들고, 일부 세부 breakdown 쿼리가 늦어도 `recent_records`, `fusion_status_summary`, `graph_context_summary`를 먼저 보여주는 partial payload를 유지합니다.
- 운영 배포 smoke 범위도 넓혔습니다. 이제 `calendar`, `prediction-lab`, 그리고 `/radar`, `/screener`, `/calendar`, `/archive`, `/lab`, `/portfolio`, `/watchlist` HTML까지 함께 확인해, 공개 화면 전반의 회귀를 더 빨리 잡습니다.

## v2.52.5 - 2026-03-29

- 공개 집계 화면이 여전히 느려지던 공통 원인을 추가로 정리했습니다. `SQLite cache/summary read`가 최대 30초까지 락 대기를 하면서 `wait_timeout`과 partial fallback 설계보다 먼저 전체 응답을 붙잡는 경로가 있었고, 실제 운영에서도 `/api/countries`, `/api/briefing/daily`, `/api/market/opportunities/KR`, `/api/calendar/KR`, `/api/archive/accuracy/stats`가 20~60초까지 늘어지는 현상이 재현됐습니다.
- `backend/app/data/cache.py`에는 프로세스 메모리 캐시를 추가해, 한 번 생성한 공개 스냅샷을 같은 인스턴스 안에서는 SQLite 상태와 무관하게 바로 재사용하도록 바꿨습니다. 그래서 홈, 레이더, 캘린더, 연구실, 포트폴리오/관심종목 미리보기처럼 같은 공개 스냅샷을 여러 화면이 함께 쓰는 흐름에서 first paint가 더 안정적으로 유지됩니다.
- `backend/app/database.py`는 cache read/write와 공개 요약 read 경로를 `fast-fail` 프로필로 분리했습니다. cache, 리서치 상태, 예측 정확도/연구실 통계가 DB 락을 오래 기다리지 않고 짧게 비워진 값이나 partial fallback으로 내려가도록 바꿔, 공개 fallback 계약이 실제 운영에서도 의미 있게 작동하도록 맞췄습니다.
- 회귀 테스트를 추가해 메모리 캐시가 DB roundtrip 없이 최근 값을 재사용하는지, 공개 read-only DB 메서드가 락 상황에서 빈 요약으로 안전하게 내려오는지를 고정했습니다.

## v2.52.4 - 2026-03-29

- 공용 캐시 레이어의 `get_or_fetch`가 더 이상 `두 번째 요청부터만` `wait_timeout`을 적용하지 않습니다. 이제 첫 호출자도 같은 시간 예산 안에서 fallback으로 빠지고 background task가 cache를 채우도록 바꿔, cold cache에서 `/api/calendar/KR`, `/api/briefing/daily`, `/api/archive/accuracy/stats`, `/api/research/predictions`가 첫 요청 한 번에 오래 붙잡히던 경로를 줄였습니다.
- 회귀 테스트를 추가해 첫 호출자가 timeout fallback을 먼저 받고, 뒤에서 완료된 background fetch가 실제 cache를 채우는 계약을 고정했습니다.

## v2.52.3 - 2026-03-29

- 공개 화면 전수 점검 기준으로 남아 있던 연결 어긋남을 정리했습니다. `/portfolio`, `/watchlist`의 로그아웃 미리보기는 다시 공개 `Opportunity Radar` snapshot을 기준으로 렌더하고, 더 이상 느린 `screener seed`를 first paint 데이터 원천으로 쓰지 않습니다. 그래서 익명 first paint가 preview보다 늦게 뜨거나, preview 카드가 seed-only 필드에 기대다 빈 상태로 흔들리던 경로를 줄였습니다.
- `/lab`은 partial/fallback 메타데이터를 audit strip에 그대로 연결하고, `/api/research/predictions` 공개 기본값도 `refresh=false`로 낮췄습니다. 그래서 실측 검증 화면과 raw API 호출이 모두 무거운 refresh를 불필요하게 바로 시작하지 않고, 준비된 스냅샷을 먼저 보여준 뒤 필요한 경우에만 보강 refresh를 타게 맞췄습니다.
- 공개 server page는 각 route의 fetch timeout 외에 page-level timebox도 함께 사용하도록 정리했습니다. `/calendar`, `/portfolio`, `/watchlist`, `/lab`을 포함한 공개/로그아웃 first screen이 backend 응답을 오래 기다리다 한 번에 늦게 열리는 문제를 줄이고, first paint를 더 짧은 예산 안에서 안정적으로 살리도록 맞췄습니다.
- 로컬 실측 기준으로 핵심 공개 API `/api/briefing/daily`, `/api/country/KR/report`, `/api/market/indicators`, `/api/market/opportunities/KR`, `/api/screener`, `/api/archive/accuracy/stats`, `/api/research/predictions`는 모두 `200` 응답을 유지했고, page HTML `/`, `/radar`, `/screener`, `/calendar`, `/archive`, `/lab`, `/portfolio`, `/watchlist`에서도 raw `Failed to fetch`와 `불러오지 못했습니다` 문구가 first paint에 남지 않는 것을 다시 확인했습니다.

## v2.52.2 - 2026-03-29

- 공개 집계 API 안정화를 위해 `/api/countries`는 더 이상 국가별 지수 quote를 순차 호출하지 않습니다. 이제 병렬 quote + `6초` timeout + `5분` 캐시를 사용하고, 느릴 때도 zeroed index fallback으로 먼저 살아남아 홈 SSR이 국가 selector 때문에 같이 멈추지 않게 맞췄습니다.
- `/api/market/movers/{code}`는 KR에서 representative quote 경로를 먼저 사용하고, `6초` timeout과 partial fallback을 함께 둡니다. 홈의 상승/하락 상위 패널이 전체 유니버스 snapshot 경로에 끌려가다 backend를 다시 흔들던 부담을 줄였습니다.
- 공개 background refresh는 이제 중복 실행을 재사용합니다. `country report`, `opportunity radar`, `screener cache warmup`은 같은 key의 background task가 이미 돌고 있으면 새 task를 또 만들지 않아, 홈·레이더·포트폴리오를 같이 열었을 때 Render free 인스턴스에 무거운 refresh가 겹쳐 쌓이는 경로를 줄였습니다.
- Render production startup profile도 문서와 배포 설정을 같은 의미로 맞췄습니다. `STARTUP_LEARNED_FUSION_REFRESH=false`, `STARTUP_MARKET_OPPORTUNITY_PREWARM=false`를 render.yaml에 명시하고, code는 Render memory-safe mode에서 startup heavy job을 건너뛰는 기준을 유지합니다. 그래서 cold start는 on-demand 공개 응답을 먼저 살리고, learned fusion refresh와 radar warmup은 요청 시점 캐시/refresh 경로로 넘기도록 정리했습니다.
- 회귀 테스트를 추가해 `countries timeout fallback`, `KR market movers representative path`, `opportunity refresh dedupe`, `Render memory-safe startup skip` 계약을 고정했습니다.

## v2.52.1 - 2026-03-29

- KR `Opportunity Radar` 공개 API는 더 이상 같은 요청 안에서 `full`과 `quick` 계산을 동시에 붙잡고 기다리지 않습니다. 이제 `/api/market/opportunities/{code}`는 `cached full -> cached quick -> fresh quick -> background full warmup` 순서로 응답해, cold start 직후에도 `/radar`가 20초 이상 비어 있다가 실패 카드로 떨어지는 경우를 줄였습니다.
- KR quick 후보는 `대표 시총 페이지` 기반 representative quote를 우선 사용하도록 바꿨습니다. 기존에는 sampled universe `yfinance` quote screen이 먼저여서 Render free 환경에서 quick 자체가 10초 이상 걸리거나 usable 후보를 못 만들 수 있었는데, 이제 representative quick가 먼저 살아나고 sampled quote screen은 그 다음 fallback으로만 내려갑니다.
- 공개 SSR과 클라이언트 재호출 timeout도 레이더 경로에 맞춰 다시 잡았습니다. `/radar` server fetch는 `18초`, 브라우저 재호출은 `28초`까지 허용하고, 실제 후보가 아직 준비되지 않은 경우에도 `background full warmup`이 다음 재조회용 cache를 채우도록 정리했습니다.
- 회귀 테스트를 추가해 `cached quick 우선 응답`, `quick timeout placeholder`, `KR representative quick 우선 경로`, `full cache reusable snapshot` 계약을 함께 고정했습니다.

## v2.52.0 - 2026-03-29

- 예측 엔진 backbone은 그대로 유지한 채 `learned fusion + lightweight graph context`를 추가했습니다. `distributional_return_engine`는 기존 prior 분포 예측을 계속 생성하고, horizon `1 / 5 / 20`별로 실측 prediction log가 충분할 때만 pure `numpy` L2 logistic profile을 사용해 prior score를 보강합니다.
- `prediction_records`의 `calibration_json`은 새 SQL 컬럼 없이 확장됐습니다. 이제 기존 calibration snapshot 위에 `fusion_features`, `graph_context`, `fusion_metadata`를 함께 적재해, 과거 레코드와 새 레코드가 섞여 있어도 연구실 집계와 시스템 진단이 backward-compatible하게 동작합니다.
- 경량 graph context는 full GNN 대신 `FMP peers -> same sector/industry -> rolling return correlation` 순서로 피어 문맥을 구성하고, coverage가 있을 때만 bounded scalar로 blend에 반영합니다. graph가 비어도 전체 forecast는 자동으로 `prior_only`로 안전 종료합니다.
- `/api/research/predictions`는 이제 horizon별 `fusion_method`, `fusion_profile_sample_count`, `fusion_blend_weight`, `graph_context_used`, `graph_context_score`, `graph_coverage`, `fusion_profile_fitted_at` 메타데이터를 포함하고, top-level `fusion_profiles`, `graph_context_summary`, `fusion_status_summary`도 함께 반환합니다.
- `/lab`과 `/settings` 진단 패널은 새 엔진 메타데이터를 바로 읽습니다. Prediction Lab은 horizon별 현재 method, sample count, graph coverage, prior 대비 Brier delta, 평균 blend weight를 보여 주고, 시스템 진단은 active model version, 마지막 profile refresh 시각, horizon별 learned fusion 상태를 함께 노출합니다.
- startup task에 `learned_fusion_profile_refresh`를 추가했습니다. 권장 env는 `STARTUP_LEARNED_FUSION_REFRESH=true`, `STARTUP_LEARNED_FUSION_REFRESH_TIMEOUT=25`이고, timeout이나 예외가 나도 서비스 시작은 계속되며 엔진은 자동으로 `prior_only`로 동작합니다.

## v2.51.5 - 2026-03-29

- Render production이 예전 `STARTUP_*` 환경값을 계속 들고 있어도 backend가 메모리 세이프 startup profile을 우선 적용하도록 바꿨습니다. 이제 Render 런타임으로 감지되면 `prediction_accuracy_refresh`, `research_archive_sync`는 startup에서 강제로 건너뛰고, `market_opportunity_prewarm`만 `45초` 예산과 concurrency `1`로 실행합니다.
- startup 진단 detail도 이유를 더 분명하게 남깁니다. 메모리 세이프 모드에서 건너뛴 작업은 단순 `skipped by configuration`이 아니라 `Render 메모리 세이프 startup 프로필` 때문에 보류되었다는 안내를 남겨, health/diagnostics에서 실제 원인을 바로 읽을 수 있게 했습니다.
- `/api/market/opportunities/{code}`는 full/quick task를 만든 직후 이벤트 루프에 한 번 올려 timeout 직후 취소 경로가 더 안정적으로 작동하도록 맞췄습니다. 아주 짧은 timeout 테스트에서도 background cancel signal이 일관되게 잡히도록 회귀 테스트를 보강했습니다.

## v2.51.4 - 2026-03-29

- Render free backend startup profile을 메모리 절약형으로 다시 고정했습니다. 운영 `render.yaml`에서는 `prediction_accuracy_refresh`, `research_archive_sync`를 startup에서 기본 비활성화하고, `market_opportunity_prewarm`만 `45초` 예산 안에서 우선 실행하도록 바꿨습니다.
- backend startup orchestrator는 이제 설정된 concurrency에 따라 task를 `running / queued` 상태로 순차 실행할 수 있습니다. cold start 시 여러 background job이 동시에 올라가 메모리 피크와 SQLite lock을 만들던 경로를 줄였고, `startup_tasks` 진단에도 현재 어떤 작업이 대기 중인지 그대로 남기도록 맞췄습니다.
- 운영 진단에서 보이던 `research_archive_sync`의 `database is locked` 경쟁을 줄이기 위해 startup 동시성 제어와 Render env를 함께 정리했습니다. 공개 `/archive`와 `/lab`은 계속 on-demand 경로로 데이터를 갱신하므로, cold start first paint 안정성을 우선해도 기능 계약은 유지합니다.

## v2.51.3 - 2026-03-29

- 종목 상세 `SP-4004` timeout fallback이 공개 판단 요약과 트레이드 플랜에 영어 내부 문구를 섞어 보여주던 문제를 고쳤습니다. 이제 `public_summary`는 영어 bullet을 공개 카드에 올리지 않고, fallback 근거와 무효화 조건도 한국어 우선 문장으로만 정리합니다.
- `trade_plan`의 `setup_label`, `thesis`, `invalidation`을 한국어 운영 문장으로 바꿨습니다. 그래서 LLM 보조 요약이 제한 시간 안에 오지 않아도 종목 상세의 `판단 요약`, `트레이드 플랜`, `무효화 조건`이 같은 톤과 언어로 유지됩니다.
- 회귀 테스트를 추가해 영어 fallback 문장이 `public_summary.evidence_for`로 새지 않는지, 리스크 축소 시나리오의 `trade_plan`이 한국어 label과 무효화 문구를 유지하는지 고정했습니다.

## v2.51.2 - 2026-03-29

- KR `Opportunity Radar`의 quick 경로가 `yfinance` quick 배치에서 usable 후보를 만들지 못하면, 이제 `KOSPI/KOSDAQ 대표 시총 페이지` 기반 quote-only 후보로 즉시 전환합니다. 그래서 `첫 판단 스레드 준비 중` placeholder가 이틀씩 고정되는 대신 대표 후보 보드가 더 빨리 살아나도록 맞췄습니다.
- `/api/market/opportunities/{code}` timeout fallback은 이제 partial 응답을 반환한 뒤 무거운 레이더 task를 계속 백그라운드에 쌓아 두지 않습니다. quick 또는 cached quick로 먼저 응답한 경우 남은 full task를 정리하고, placeholder로 내려간 경우에도 다음 재조회에서 fresh quick 스냅샷을 새로 시도하도록 바꿨습니다.
- `/radar` placeholder 문구와 audit 라벨은 더 이상 `계속 스캔 중`처럼 오해되지 않게 정리했습니다. 이번 요청에서 `사용 가능한 후보를 만들지 못함`을 먼저 설명하고, 같은 화면을 켜 둔다고 완료되는 구조가 아니라 `다시 불러오기`가 새 quick 시도를 시작한다는 점을 명시합니다.
- 회귀 테스트를 추가해 quick 경로가 비었을 때 representative quotes fallback으로 candidate를 다시 살리는 흐름을 고정했고, README도 current release와 운영 설명을 같은 의미로 업데이트했습니다.

## v2.51.1 - 2026-03-29

- 공개 서버 페이지 `/`, `/radar`, `/calendar`, `/archive`, `/screener`, `/lab`, `/portfolio`, `/watchlist`는 이제 `export const revalidate = 0`으로 request-time SSR을 강제합니다. 각 페이지의 개별 공개 fetch는 기존 `next.revalidate` 캐시를 유지하므로, Vercel build의 `Collecting page data` 단계가 Render live API 응답에 매달리다 실패하는 경로를 막았습니다.
- `public-server-api`는 route별 timeout을 추가했습니다. 기본 공개 fetch는 `8초`, `market opportunities / screener seed`는 `12초`, `prediction lab / research archive`는 `10초` 예산 안에서만 대기하고, timeout이면 구조화 에러로 떨어져 page-level `.catch()`와 `Promise.allSettled()`가 부분 결과를 먼저 살릴 수 있게 했습니다.

## v2.51.0 - 2026-03-29

- `country report`는 공개 숫자와 공개 서술을 분리했습니다. 이제 `market_summary`는 숫자·퍼센트·날짜 없는 정성 요약만 유지하고, 공개 홈과 국가 상세의 숫자 근거는 `macro_claims` 구조체에서만 렌더합니다.
- `country report` 생성 단계는 숫자가 섞인 자유 서술을 그대로 공개하지 않습니다. LLM 요약에 숫자가 섞이거나 비어 있으면, 백엔드 validation이 이를 폐기하고 점수·기관 정렬 상태 기반의 정성 요약으로 자동 강등합니다.
- 공개용 prompt 계층을 분리하기 위해 stock detailed analysis prompt와 public stock summary prompt를 나눴고, 종목 상세 응답에 `public_summary` 블록을 실제로 연결했습니다. 상단 판단 요약은 이제 `근거 / 반대 근거 / 지금 바로 사지 않는 이유 / 무효화 조건 / 데이터 품질 / 신뢰 메모`를 먼저 보여주고, 목표가·buy/sell zone 중심 문구는 상세 가이드 레이어에만 남깁니다.
- `stock_analyzer`는 공개 요약용 LLM 응답이 늦거나 비어도 빈 카드 대신 정량 기반 fallback을 생성합니다. 트레이드 플랜, 보정 confidence, 리스크 플래그, 시장 국면, 진입 구간 정보를 조합해 공개 요약을 구성하고, sell-side 가격 문구나 숫자가 섞인 텍스트는 상단 공개 판단 요약에서 폐기합니다.
- 홈과 `/radar`가 같은 KR 공개 opportunities snapshot을 기준으로 first screen을 맞출 수 있도록 `snapshot_id`, `fallback_tier` 메타데이터를 추가했습니다. 홈은 이제 `/radar`와 같은 limit 기준 snapshot을 먼저 받고, 레이더는 `partial=true`라도 `quote_available_count=0` 또는 후보 `0개`인 placeholder snapshot을 usable 결과로 고정하지 않습니다.
- `/radar`는 usable snapshot이 없는 placeholder partial을 별도 준비 상태로 다루고, 마지막 usable snapshot이 있으면 그 보드를 먼저 유지한 채 최신 audit 상태만 갱신합니다. 그래서 “대표 스냅샷만 잡힌 상태”와 “실제로 쓸 수 있는 후보가 있는 상태”를 같은 것으로 보지 않게 됐습니다.
- `market opportunities`의 cached quick 재사용은 이제 정확히 같은 limit 캐시만 보지 않고, 최근에 확보된 다른 quick limit 결과도 usable하면 잘라서 먼저 재사용합니다. 그래서 `/radar` 재시도 시 같은 usable 후보를 더 안정적으로 먼저 보여주고, placeholder로 바로 떨어지는 경우를 한 번 더 줄였습니다.
- `/radar` placeholder first screen은 raw `0 / 0 / 0` 숫자 보드 대신 `첫 판단 스레드 준비 중` 상태 카드와 준비 중인 유니버스, 다음 갱신 단계를 먼저 안내하도록 정리했습니다.
- `/portfolio`, `/watchlist`는 로그아웃 first paint에서 auth loading보다 public preview를 먼저 렌더합니다. 익명 상태에서는 demo cards와 로그인 CTA가 바로 나오고, user-specific API 호출은 세션이 확인된 뒤에만 시작합니다.
- `/archive` 공개 리포트 목록은 이제 HTML이 제거된 `summary_plain`만 렌더합니다. 최신 기관 리포트 카드와 전체 목록에서 raw `<p>`, `<br>`, `&nbsp;` 같은 마크업이 그대로 노출되지 않도록 sanitizer와 프론트 렌더를 함께 맞췄습니다.
- `/lab` 첫 화면은 공개 검증 스냅샷을 서버에서 먼저 채웁니다. 1D / 5D / 20D 방향 적중률, Brier score, reliability gap, 표본 수, generated_at을 바로 보여주고, 최근 실패 사례도 같은 페이지에서 공개해 검증 흐름이 좋은 결과만 보여주지 않도록 정리했습니다.
- 포트폴리오와 레이더에는 `/lab`로 이어지는 검증 링크를 추가해 추천 결과와 검증 기록이 분리된 섬처럼 보이지 않게 했습니다.
- 회귀 테스트를 추가해 research archive `summary_plain` 생성과 opportunities snapshot 메타(`snapshot_id`, `fallback_tier`) 계약을 고정했고, README / API_CONTRACT / DESIGN_BIBLE / AGENTS 문서도 새 공개 신뢰도 기준에 맞춰 동기화했습니다.

## v2.50.1 - 2026-03-29

- `/api/market/opportunities/{code}`는 정밀 응답과 quick fallback이 모두 늦어질 때 더 이상 바로 `504 / SP-5018`로 끝나지 않고, 가능한 경우 `cached quick`를 다시 사용하거나 placeholder `200 + partial` 응답을 먼저 반환합니다. 그래서 전용 `/radar` first screen이 통째로 비는 구간을 줄였습니다.
- quick fallback이 성공한 경우에도 이제 `partial: true`와 `fallback_reason=opportunity_quick_response`를 명시합니다. `PublicAuditStrip`은 `이전 quick 결과 기준`, `워밍업 placeholder 기준` 같은 새 fallback reason도 한국어로 읽히게 맞췄습니다.
- README와 API 계약 문서에 Render Free / Supabase Free의 공식 idle·pause 정책 링크, 현재 KR 레이더 timeout 예산, 2026-03-29 실측 warm/cold 응답 시간을 따로 정리했습니다. 그래서 “free tier라 느리다”와 “실제 어떤 경로가 몇 초 안에 timeout 되는지”를 분리해서 확인할 수 있습니다.
- 회귀 테스트를 추가해 `market opportunities`가 quick timeout 뒤 cached quick를 재사용하는 경우와, cached quick도 없을 때 placeholder partial로 내려오는 경우를 함께 고정했습니다.

## v2.50.0 - 2026-03-28

- 공개 핵심 페이지 `/`, `/radar`, `/calendar`, `/archive`, `/screener`를 server-first 첫 화면으로 다시 정리했습니다. 이제 first screen은 최소한의 실제 수치, decision thread, 마지막 갱신/partial 상태를 서버 HTML에 먼저 담아 보내고, 클라이언트는 이어서 세부 패널만 보강합니다.
- 공통 `PublicAuditStrip`과 공개 서버 fetch 레이어를 추가했습니다. `generated_at`, `partial`, `fallback_reason`을 같은 audit strip 규칙으로 드러내고, raw `Failed to fetch`나 큰 빈 카드보다 `사용 가능한 최소 결과`를 먼저 보여주는 방향으로 맞췄습니다.
- 대시보드는 `선택 시장 현황 -> 핵심 수치 -> 오늘의 포커스 -> 히트맵/상승·하락 상위 -> 강한 셋업/뉴스` 흐름으로 다시 고정했습니다. 기회 레이더는 시장 국면, 전체 스캔 수, 실제 시세 확보 수, 표시 후보 수, 마지막 갱신 시각을 first decision block에서 바로 보여주고 후보 카드에 보정 confidence, probability edge, analog support를 함께 노출합니다.
- 캘린더는 다음 3개 일정과 `official / estimated` 상태를 먼저 보여주고, 아카이브는 최신 기관 리포트 2개를 기관, 발행일, 요약, 원문/PDF 액션과 함께 first screen에 고정했습니다. 스크리너는 검색 전 0개 상태 대신 latest close seeded 결과를 먼저 보여주고, seeded / searched / 실제 결과 없음 상태를 분리했습니다.
- `/portfolio`, `/watchlist`는 로그아웃 상태에서 빈 auth wall 대신 public data 기반 demo cards + 로그인 CTA를 first screen에 배치했습니다. 데모는 가짜 수익률이나 허구의 자산이 아니라 실제 공개 레이더/시장 데이터 기반 설명형 미리보기만 사용합니다.
- selection score는 downside penalty를 `0.20`, forecast volatility penalty를 `0.12`로 강화하고, `press_long`, `lean_long`, `accumulate`, `breakout_watch` 가점을 절반 이하로 줄였습니다. 반대로 `stay_selective`, `reduce_risk`, `capital_preservation`은 중립~약한 양수 중요도로 끌어올려 방어 판단이 랭킹에서 사라지지 않게 조정했습니다.
- trade planner는 long 진입 조건을 더 좁히고, `risk_off + premium_to_fair`, `up_probability <= 45`, `direction == down`, `약한 trend + 낮은 risk/reward` 같은 경우를 `reduce_risk`로 더 적극적으로 분기합니다.
- 포트폴리오 조건 추천, 최적 추천, 일일 이상적 포트폴리오는 defensive bias 후보를 더 이상 초기에 버리지 않습니다. 기존 보유 defensive 후보는 감축/보류 판단과 함께 유지하고, 신규 확대가 아닌 경우 `target_weight_pct = 0`으로 남겨 같은 인터페이스 안에서 늘릴 종목과 줄이거나 보류할 종목을 함께 읽을 수 있게 했습니다.
- 회귀 테스트를 추가해 selection penalty 강화, risk-off `reduce_risk` routing, defensive 후보 유지, ideal portfolio zero-weight 계약을 고정했고, 프론트 빌드까지 새 SSR/public audit 흐름 기준으로 다시 통과시켰습니다.

## v2.49.4 - 2026-03-28

- `대시보드`, `기회 레이더`, `시장 일정 캘린더`, `리포트 아카이브`, `포트폴리오`, `설정 및 시스템`의 로딩 상태를 설명형 상태 카드로 다시 정리했습니다. 그래서 큰 빈 카드만 남아 실제보다 느리거나 고장난 것처럼 보이던 구간을 줄였습니다.
- 공통 오류 배너는 이제 raw `Failed to fetch`를 그대로 노출하지 않고, 백엔드 워밍업·네트워크 지연을 한국어 안내와 재시도 동작으로 보여줍니다.
- `설정 및 시스템`은 `Promise.allSettled` 기반 부분 로딩으로 바꿨고, `계정 관리` 패널은 상단 프로필 편집 + 하단 2열 보안/인증 카드 흐름으로 재배치했습니다. 한 패널이 늦어도 다른 패널과 계정 편집 화면은 바로 사용할 수 있도록 맞췄습니다.
- `시장 일정 캘린더`는 월 이동 시 이전 보드를 유지한 채 새 월 데이터를 다시 불러오도록 조정했고, `calendar / diagnostics / market sessions / research status` 프론트 호출에 timeout 옵션을 붙여 오래 매달리는 흐름을 줄였습니다.

## v2.49.3 - 2026-03-28

- 공개 `KR screener`의 cold cache partial 경로를 `yfinance` 10종목 묶음에서 `Naver 시총 대표 페이지 snapshot` 기반으로 다시 바꿨습니다. 운영에서는 첫 묶음도 50초 이상 늘어지는 경우가 있어, 대표 시총 페이지 1차 응답을 먼저 보여주는 쪽이 실제 배포 안정성에 더 맞았습니다.
- 이 변경으로 큰 기본 요청(`/api/screener?country=KR&limit=20`)의 cold start partial이 로컬 기준 약 3.5초 수준으로 내려왔고, background cache warming은 그대로 유지돼 다음 요청부터는 full quick 결과를 이어서 받을 수 있습니다.
- 회귀 테스트는 representative snapshot 경로와 `kr_market_quote_client.get_kr_representative_quotes()` 제한 동작까지 함께 확인하도록 보강했습니다.

## v2.49.2 - 2026-03-28

- 공개 `KR screener`의 cold cache 기본 요청은 이제 대표 10개 snapshot partial을 먼저 반환하고, 전체 quick 결과는 뒤에서 cache warming으로 이어집니다. 그 결과 배포 직후 첫 `/api/screener?country=KR&limit=20` 요청이 proxy read timeout으로 끊기기보다 `200 + partial`로 먼저 살아남도록 맞췄습니다.
- 이 warming 경로는 이미 cache가 채워진 뒤에는 건너뛰고, 작은 요청(`limit <= 10`)은 기존처럼 바로 full quick path를 사용합니다. 그래서 `limit=1` 같은 소규모 조회 계약은 유지하면서, 큰 공개 요청만 cold start 방어를 추가했습니다.
- 회귀 테스트는 `KR screener`의 cold cache large-limit 요청이 실제로 partial warming 응답을 반환하고 background cache warmup을 시작하는지까지 함께 확인하도록 보강했습니다.

## v2.49.1 - 2026-03-28

- KR `Opportunity Radar`의 마지막 복구 경로를 한 번 더 보강했습니다. 전종목 경로와 기본 fallback 종목군 모두에서 시세 확보 수가 `0`이면, 이제 앞쪽 종목만 자르는 대신 섹터를 섞은 대표 120개 샘플로 즉시 줄여 1차 후보를 다시 시도합니다.
- KR 레이더의 축약 스캔도 같은 분산 샘플 순서를 사용하도록 맞췄습니다. 그래서 특정 섹터 앞부분 종목이 비어 있을 때 후보가 통째로 사라지던 현상을 줄였습니다.
- 회귀 테스트는 `분산 샘플링 helper`, `sampled fallback quote recovery` 계약까지 추가로 고정했습니다.

## v2.49.0 - 2026-03-28

- 대시보드와 기회 레이더의 빈 카드·지연 상태를 더 명확한 부분 업데이트 안내와 준비 중 메시지로 정리했습니다. 그래서 일부 공개 패널이 늦어져도 화면이 고장난 것처럼 보이기보다, 어떤 데이터가 늦는지 바로 읽을 수 있습니다.
- KR `Opportunity Radar`는 이제 `KRX 상장사 전종목 1차 시세 확보 수 = 0`이 나오면 운영용 기본 종목군으로 즉시 재시도합니다. 운영 배포에서 `실제 시세 확보 0 / 표시 후보 0`이 길게 고정되던 흐름을 줄이고, 후보와 실행 메모를 먼저 보여주도록 맞췄습니다.
- 기관 리서치 아카이브를 `KR / US / EU / JP`까지 확장했습니다. `KDI`, `한국은행`, `Federal Reserve`, `ECB`, `BOJ` 공식 리포트를 지역 탭으로 나눠 다시 볼 수 있고, 상태 카드와 실제 목록이 현재 활성 소스 기준으로 같은 숫자를 보이도록 정리했습니다.
- 회귀 테스트는 `KR 레이더 quote fallback`, `리서치 status normalization`, `inactive source filter` 계약까지 함께 고정했습니다.

## v2.48.4 - 2026-03-28

- 공개 `KR screener` 기본 quick path는 이제 SQLite shared cache를 우회하고 바로 계산합니다. Render free 환경에서 캐시 DB 경합이나 느린 I/O 때문에 공개 응답이 같이 막히는 위험을 줄이기 위한 조정입니다.
- 이 quick path는 `skip_full_market_fallback=True`와 `max(limit, 10)` 후보 제한을 그대로 유지하므로, 전체 시장 scrape 없이 작은 bulk quote 묶음만으로 먼저 응답합니다.
- 회귀 테스트는 공개 `KR screener` 기본 경로가 shared cache를 타지 않는다는 계약까지 함께 확인하도록 확장했습니다.

## v2.48.3 - 2026-03-28

- 공개 `KR screener` 기본 경로는 이제 bulk quote 후보 수를 `max(limit, 10)`으로 먼저 줄입니다. 그래서 `limit=1` 같은 작은 요청도 내부적으로 36개 후보 batch를 잡지 않고, 요청 규모에 맞는 작은 묶음으로 응답을 준비합니다.
- 이 변경은 `skip_full_market_fallback=True`와 함께 적용돼, Render 운영 환경에서 기본 `screener` 요청이 과도한 batch workload로 timeout 나는 가능성을 한 번 더 줄였습니다.
- 회귀 테스트는 `limit=1` 요청이 실제로 첫 10개 후보까지만 bulk quote를 호출하는지 확인하도록 추가했습니다.

## v2.48.2 - 2026-03-28

- 공개 `KR screener`의 기본/timeout fallback 경로는 이제 소규모 종목 묶음에서 `skip_full_market_fallback=True`를 명시해, yfinance batch coverage가 약간 부족하더라도 전체 Naver 시총 페이지 scrape로 즉시 내려가지 않게 맞췄습니다.
- 그 결과 운영 배포에서 `/api/screener?country=KR&limit=20`가 작은 요청인데도 full-market fetch 때문에 길게 멈추는 가능성을 더 줄였습니다.
- 회귀 테스트는 공개 `KR screener`가 bulk quote 호출 시 full-market fallback 차단 플래그를 함께 전달하는지 확인하도록 보강했습니다.

## v2.48.1 - 2026-03-28

- 공개 `KR screener`는 이제 느린 동적 유니버스 조회를 기본 진입점으로 삼지 않고, 검증된 기본 종목군과 bulk quote 경로를 먼저 사용합니다. 그 결과 운영 배포에서 `/api/screener?country=KR&limit=20`가 오래 멈추거나 read timeout으로 끊기던 흐름을 줄였습니다.
- `screener` timeout 범위도 `_build_response` 내부 fetcher만이 아니라 `cache.get_or_fetch` 전체를 감싸도록 넓혔습니다. 캐시 조회/저장이나 유니버스 해석이 느려져도 `snapshot fallback`이 더 빨리 내려오도록 맞췄습니다.
- FastAPI `TestClient` 기반 회귀 테스트는 startup background task 패치를 공통 헬퍼로 통합했습니다. 테스트 종료 시 `aiosqlite` 워커 스레드가 닫힌 이벤트 루프에 응답을 밀어넣으며 noisy exception을 남기던 구간을 정리했습니다.

## v2.48.0 - 2026-03-28

- horizon별 empirical confidence calibrator를 `bootstrap prior -> empirical sigmoid -> isotonic 승격` 구조로 확장했습니다. 표본 수와 클래스 균형이 충분할 때만 isotonic을 적용해 과적합을 피하면서 reliability gap을 더 줄이도록 했습니다.
- empirical calibration profile에는 이제 `reliability_bins`와 `max_reliability_gap`이 함께 저장됩니다. 예측 연구실과 시스템 상태 카드에서 각 horizon의 보정 방식, 샘플 수, Brier score와 함께 confidence 구간 최대 오차를 바로 확인할 수 있습니다.
- 회귀 테스트를 추가해 `isotonic 승격`, `reliability bin summary`, `isotonic profile 적용 우선순위` 계약을 고정했습니다.

## v2.47.0 - 2026-03-28

- 표시 confidence는 이제 `raw support -> bootstrap prior -> empirical sigmoid calibrator` 순서로 계산합니다. `next_day`, `distributional_5d`, `distributional_20d` 예측 결과가 실제 target date 이후 평가되면, 그 실측 로그를 다시 먹여 horizon별 calibrator를 점진적으로 재학습합니다.
- `prediction_records`에는 calibration snapshot이 함께 저장되고, 예측 정확도 refresh가 끝날 때마다 empirical profile을 다시 맞춥니다. 그 결과 시간이 지날수록 confidence가 “높아 보이는 점수”가 아니라 “실제 적중률에 가까운 점수” 쪽으로 수렴합니다.
- 예측 연구실은 이제 `1D / 5D / 20D` horizon별 실측 성과와 empirical calibrator 상태를 함께 보여줍니다. 샘플 수, positive rate, Brier score, prior 대비 개선 정도를 현재 UI에서 바로 확인할 수 있습니다.
- 시스템 준비 상태 카드에도 empirical calibrator 요약을 추가해, 운영 중인 API가 bootstrap prior 단계인지 실측 기반 재보정 단계인지 더 쉽게 확인할 수 있게 했습니다.
- 회귀 테스트를 추가해 `calibration snapshot 저장`, `empirical profile fitting`, `예측 연구실 응답`, `forecast model calibration metadata` 계약을 고정했습니다.

## v2.46.0 - 2026-03-28

- 표시 confidence를 단순 heuristic 합이 아니라, 분포 support·analog support·regime·probability edge·agreement·data quality·uncertainty·volatility를 합친 raw support 뒤 horizon별 bootstrap sigmoid calibrator로 보정하는 구조로 올렸습니다.
- bootstrap calibrator 단계에서는 표시 confidence를 `88점`에서 포화시켜, walk-forward 적중률 로그가 충분히 쌓이기 전 과도한 high-confidence 표시를 억제했습니다.
- historical analog confidence는 단순 `max weight` 대신 weighted win rate, effective sample size, profit factor, dispersion을 함께 반영합니다. 그 결과 한 사례 쏠림이 큰 analog set이 과신으로 이어지는 문제를 줄였습니다.
- 기회 레이더와 포트폴리오 후보 정렬은 더 이상 `directional_score`와 기대수익·confidence를 중복 합산하지 않고, `기대초과수익률 + 보정 confidence + probability edge + tail ratio + regime alignment` 중심의 selection score를 사용합니다.
- 신규 편입 후보와 일일 이상적 포트폴리오에는 `confidence floor`를 실제로 강제해, confidence가 낮은 후보가 단순 기대수익만으로 상단에 올라오는 흐름을 줄였습니다.
- 응답 스키마, 시스템 설명, 프론트 타입, 회귀 테스트, README를 새 confidence/selection 계약에 맞게 동기화했습니다.

## v2.45.4 - 2026-03-28

- `AGENTS.md`와 `README.md`에 버전 관리 기준을 추가했습니다. 이제 `PATCH / MINOR / MAJOR`를 언제 올리는지와 어떤 파일을 반드시 같이 동기화해야 하는지 문서 기준으로 바로 확인할 수 있습니다.
- `/settings`의 시스템 준비 상태 카드에 `백엔드 시작 시각`을 추가하고, 버전 일치 여부와 실제 운영 상태를 함께 읽을 수 있게 문구를 보강했습니다. 그래서 프론트·백엔드 버전이 같아도 backend startup 주의가 남아 있는 경우를 더 자연스럽게 이해할 수 있습니다.

## v2.45.3 - 2026-03-27

- KR `Opportunity Radar`의 batch quote screen에서 첫 종목만 담고 조기 반환하던 회귀를 수정했습니다. 이제 quick/full 경로 모두 실제 확보한 시세 종목 수만큼 정상 정렬합니다.
- KR quick fallback은 더 이상 소량 `yfinance` 커버리지 부족 시 시장 전체 시가총액 scrape까지 이어지지 않고, 빠른 부분 시세만으로 먼저 응답합니다. 그래서 `다시 시도`를 눌러도 quick fallback 자체가 같이 timeout 나는 경우를 더 줄였습니다.
- 예측 정확도 refresh와 관련된 SQLite prediction 조회/집계 경로도 `WAL + busy_timeout` 설정을 공유하도록 맞춰, startup/background 작업이 `database is locked`로 흔들리던 구간을 완화했습니다.

## v2.45.2 - 2026-03-27

- startup background timeout은 이제 긴 `CancelledError` stacktrace와 즉시 `degraded` 상태로 번지지 않고, 서비스 응답을 먼저 살린 채 보강 작업만 다음 워밍업/재요청으로 넘깁니다. 특히 `market opportunity prewarm`은 무거운 full radar 대신 quick prewarm을 사용합니다.
- KR `Opportunity Radar`의 quick fallback은 전체 유니버스 수와 실제 quick 1차 스캔 수를 분리해 반환하고, 초기 응답에서는 대표 1차 스캔만 먼저 계산합니다. 그래서 quick 경로가 다시 전종목 bulk quote를 기다리다 `504 / SP-5018`로 같이 무너지는 문제를 줄였습니다.
- SQLite 캐시 연결에 `WAL + busy_timeout`을 적용하고, `database is locked`가 cache 경로에서 발생하면 읽기는 cache miss, 쓰기는 no-op으로 떨어지게 바꿨습니다. 그 결과 `market snapshot fetch failed ... database is locked`가 공개 화면 전체 `SP-3001`로 번지던 구간을 완화했습니다.

## v2.45.1 - 2026-03-27

- KR 소량 시세 조회는 이제 먼저 `yfinance batch quote` 경로를 시도하고, 커버리지가 충분할 때는 시장 전체 시가총액 페이지 fetch를 생략합니다. 그래서 `sector performance` 같은 첫 진입 카드가 서버가 막 깨어난 직후에도 덜 무겁게 시작됩니다.
- 종목 상세 분석은 요약 생성과 이벤트 구조화를 병렬로 처리하고, 느린 AI 보조 단계는 timeout fallback으로 넘겨 정량 시계열 결과가 먼저 보이도록 응답 구조를 정리했습니다.
- 회귀 테스트를 추가해 `KR small quote fast path`와 `stock analyzer timeout fallback` 계약을 고정했습니다.

## v2.45.0 - 2026-03-27

- `country report` 공개 경로는 Render free warmup이나 외부 소스 지연이 길어질 때 더 이상 raw `504 / SP-5018`만 반환하지 않고, 대표 지수와 빠른 후보를 담은 `partial` 보고서를 먼저 돌려줍니다. 같은 fallback은 `PDF / CSV export`에도 적용돼 cold start 직후 `500`으로 바로 끊기던 흐름을 줄였습니다.
- `KR sector performance`는 개별 종목 스냅샷을 순차로 모으는 대신 `kr_market_quote_client` bulk quote를 먼저 사용하도록 정리해 첫 진입 latency를 줄였습니다.
- `Opportunity Radar`의 quick path는 KRX 상장사 캐시가 아직 준비되지 않았을 때도 즉시 `운영용 기본 종목군`으로 내려가도록 바꿨습니다. 그래서 quick fallback이 다시 느린 유니버스 해석으로 빠지며 `8개/0개`처럼 왜곡된 숫자를 오래 보여주던 구간을 줄였습니다.
- 라이브 API 스모크 스크립트도 현재 운영 기준선에 맞춰 `AAPL/MSFT` 대신 `005930.KS`, `000660.KS`를 사용하도록 다시 맞췄습니다.

## v2.44.0 - 2026-03-27

- `Opportunity Radar`는 Render free warmup이나 외부 데이터 지연으로 정밀 분포 계산이 늦어질 때, 더 이상 바로 `504 / SP-5018`로 끊지 않고 `1차 시세 스캔 후보`를 먼저 반환합니다. 백그라운드 계산은 계속 진행되며 같은 조건의 다음 재조회에서는 정밀 후보가 캐시로 바로 보일 수 있습니다.
- `KR Screener` 기본 조회는 개별 종목 `yfinance` 스냅샷을 순차로 긁지 않고 `kr_market_quote_client`의 bulk quote 경로를 먼저 사용하도록 바꿨습니다. 그래서 첫 진입에서 오래 멈추거나 timeout 뒤 fallback까지 느리던 문제가 줄어들고, timeout이 나더라도 `kr_bulk_snapshot_only` 부분 응답이 더 빠르게 살아남습니다.
- 공개 fallback/timeout 회귀 테스트를 추가해, `레이더 timeout -> quick fallback`, `KR 스크리너 기본 조회 -> bulk quotes`, `무거운 스크리너 -> partial fallback` 계약을 고정했습니다.

## v2.43.0 - 2026-03-27

- `Opportunity Radar`의 KR 응답은 이제 `전체 유니버스`와 `실제 시세 확보 수`를 분리해 내려, 전종목 1차 스캔을 시도했는데 일부 종목만 데이터 원본에서 빠진 경우에도 왜 숫자가 작아졌는지 더 정확히 설명합니다.
- KR 1차 quote screen은 `Naver Finance market summary` 기반 bulk quote를 기본 경로로 사용하고, 일부 잔여 종목만 제한적으로 fallback 처리해 `총 8개 스캔`처럼 보이던 오래된 상태를 실질적으로 해소했습니다.
- 레이더 캐시 버전을 다시 올려 이전의 소수 종목 응답이 남지 않게 했고, 프론트 보드도 `전체 유니버스 / 1차 스캔 / 실제 시세 확보 / 표시 후보` 기준으로 문구와 숫자를 맞췄습니다.

## v2.42.0 - 2026-03-27

- `Opportunity Radar`의 KR 유니버스를 더 이상 `201개 fallback 종목군`에 묶어두지 않고, KRX KIND 상장사 목록 기준 전종목을 1차 quote screen으로 스캔하도록 확장했습니다.
- KR 전종목 1차 스캔은 `krx_listing` 소스로 별도 표기하고, 상세 분포 계산은 상위 후보에만 적용하도록 유지해 Render free 환경에서도 `후보 0개`나 오래된 `총 8개 스캔` 상태가 반복되지 않게 정리했습니다.
- KR 레이더 응답 캐시 버전을 올려, 배포 직후에도 이전 8종목/기본 유니버스 응답이 남지 않고 새 전종목 스캔 결과가 바로 반영되도록 했습니다.
- 운영 설정, 문서, 테스트를 새 KR 레이더 기준으로 맞췄고, startup prewarm timeout도 전종목 1차 스캔 기준으로 늘렸습니다.

## v2.41.0 - 2026-03-27

- `market opportunities` 라우터는 timeout 시 계산을 바로 취소하지 않고 백그라운드에서 계속 마무리하도록 바꿔, 첫 요청이 느려도 캐시가 채워지지 않아 재시도마다 같은 `504 / SP-5018`이 반복되던 문제를 줄였습니다.
- FastAPI startup background task에 `KR opportunity radar prewarm`을 추가해, 서버가 깨어난 직후에도 KR 레이더 캐시를 먼저 채우도록 보강했습니다.
- KR batch quote chunk 크기를 `80` 고정값에서 대형 배치에 더 유리한 동적 크기로 바꿔, 201개 fallback 유니버스 1차 스캔의 응답 안정성을 조금 더 끌어올렸습니다.
- 프론트 레이더 보드 문구도 `정밀 분석 0개`일 때는 오류처럼 보이지 않도록 `정밀 분석 전 상위 후보를 먼저 표시`하는 현재 동작 기준으로 다시 정리했습니다.

## v2.40.3 - 2026-03-27

- `market opportunities`의 무거운 시장 컨텍스트 계산을 최종 응답 캐시 안으로 옮겨, 같은 KR 레이더 요청이 들어올 때마다 `지수 이력 -> 거시 스냅샷 -> 유니버스 해석 -> 1차 스캔`을 다시 수행하던 병목을 줄였습니다.
- KR 대량 fallback 유니버스 batch quote는 더 이상 개별 `stock_quote` 캐시를 수백 건씩 추가 기록하지 않도록 조정해, Render free 환경에서 레이더 첫 응답 뒤 SQLite 캐시 쓰기 때문에 다시 느려지던 문제를 완화했습니다.
- 회귀 테스트를 추가해 캐시된 레이더 응답은 무거운 전처리를 다시 타지 않고, 큰 batch quote는 개별 캐시 priming을 건너뛰는 계약을 고정했습니다.

## v2.40.2 - 2026-03-27

- `market opportunities`는 큰 KR fallback 유니버스에서 응답 안정성을 우선해 `1차 전수 스캔 상위 후보`를 먼저 반환하도록 바꿨습니다. Render free cold-start 구간에서 정밀 분석 때문에 전체 응답이 `SP-5018`로 끊기던 문제를 줄이기 위한 조정입니다.
- batch quote 결과를 개별 `stock_quote` 캐시에도 함께 채워, 레이더 이후 상세 종목 조회가 같은 세션에서 다시 느려지지 않도록 보강했습니다.
- 공개 opportunity timeout도 `24초`로 소폭 완화해, 현재 운영 구조에서 `201개 기본 종목군 1차 스캔 + 후보 반환`이 실제로 끝날 수 있는 여유를 추가했습니다.

## v2.40.1 - 2026-03-27

- `market opportunities`의 KR 1차 스캔은 개별 종목 quote를 순차 호출하던 경로 대신 batch quote fetch를 우선 사용하도록 바꿔, Render free 환경에서도 `후보 0개`나 `504`로 무너질 확률을 크게 낮췄습니다.
- 레이더 후보 카드와 응답 note에 `현재 KR 레이더 유니버스`와 `운영용 기본 종목군 N개` 문구를 넣어, 실제 fallback 범위가 전 종목 전체인지 운영용 기본 유니버스인지 더 정확히 보이도록 정리했습니다.
- 운영 문서도 `8종목 하드캡`은 더 이상 현재 기준선이 아니고, 현재는 `전체 유니버스 / 1차 스캔 / 정밀 분석 / 표시 후보` 카운트를 함께 본다는 흐름으로 다시 맞췄습니다.

## v2.40.0 - 2026-03-27

- `market opportunities`는 더 이상 하드캡 8종목만 훑지 않고, KR 유니버스 전체를 1차 quote screen으로 먼저 스캔한 뒤 상위 종목만 정밀 분포 분석하도록 구조를 바꿨습니다.
- 정밀 분석이 일부 실패하거나 늦어도 전수 1차 스캔 결과를 후보 카드로 먼저 내려, `총 8개 스캔`, `후보 0개`처럼 오해를 주는 상태가 오래 남지 않도록 정리했습니다.
- 프론트 레이더 보드도 `전체 유니버스 / 1차 스캔 / 정밀 분석` 기준으로 문구와 카운트를 다시 맞췄습니다.

## v2.39.3 - 2026-03-27

- `heatmap` fallback 경로에서 취소된 비동기 작업 객체를 스냅샷처럼 읽다가 `SP-9999`로 터질 수 있던 버그를 수정했습니다. 이제 timeout 직후 `CancelledError`가 섞여도 사전 타입 검사로 안전하게 건너뜁니다.

## v2.39.2 - 2026-03-27

- `market opportunities`는 cold-start 직후에도 router timeout에 덜 걸리도록 스캔 예산을 더 줄였습니다. 무거운 스캔 timeout과 경량 fallback 예산을 함께 낮추고, 최대 후보 수도 다시 줄여 첫 요청에서 `SP-5018`이 반복되는 빈도를 낮췄습니다.
- 경량 fallback이 과도하게 많은 후보를 다시 스캔하지 않도록 상한을 테스트로 고정했습니다.

## v2.39.1 - 2026-03-27

- 공개 `heatmap` 경로는 Render free 환경에서 외부 시세가 느릴 때도 `200` 기반의 부분 응답으로 먼저 살아남도록 바꿨습니다. 섹터 구조와 대표 종목군은 먼저 보여주고, 상세 시세 스냅샷이 늦을 때만 `partial` 플래그와 fallback 이유를 함께 반환합니다.
- 공개 `screener`는 기본 탐색 모드를 `snapshot-only` 빠른 경로로 다시 나눠, 고급 필터가 없을 때는 무거운 종목 상세 조회를 생략하고 화면이 먼저 뜨도록 정리했습니다. timeout이 나더라도 대표 결과와 섹터 요약을 담은 부분 응답을 우선 돌려줍니다.
- `market opportunities`는 전체 스캔이 느릴 때 compact 후보군만으로 경량 추천을 먼저 만들도록 보강해, 첫 진입에서 `다시 시도`만 반복되는 빈도를 낮췄습니다.
- 운영 문서와 에이전트 가이드도 공개 경로는 `대표 표본 + 캐시 + 부분 응답 fallback`을 기본 원칙으로 삼도록 다시 동기화했습니다.

## v2.39.0 - 2026-03-27

- 공개 대시보드의 `heatmap`과 `screener` 경로를 Render free 환경 기준으로 다시 다듬어, 대표 종목 표본만 먼저 계산하고 서버측 timeout을 구조화된 `504 / SP-5018`로 반환하도록 정리했습니다.
- 홈 대시보드는 서버 timeout보다 짧게 끊기지 않도록 workspace 대기 시간을 늘렸고, 스크리너 페이지는 실패 시 조용히 비는 대신 인라인 오류 문구와 재시도 버튼을 보여주도록 보강했습니다.
- `scripts/deployed_site_smoke.py`는 운영 검증 범위에 `KR heatmap`, `opportunities`, `screener`를 추가해, 사용자 체감이 큰 느린 공개 API 회귀를 배포 단계에서 바로 잡을 수 있게 했습니다.

## v2.38.0 - 2026-03-27

- `/settings`의 즉시 비밀번호 변경 카드에 `보안 확인 코드 보내기`와 `reauth nonce` 입력 흐름을 추가해, Supabase가 오래된 세션에 추가 확인을 요구할 때도 같은 패널 안에서 비밀번호를 바로 바꿀 수 있도록 정리했습니다.
- 즉시 비밀번호 저장 버튼은 비밀번호 규칙뿐 아니라 필요한 경우 reauth nonce 입력까지 확인한 뒤 활성화되도록 맞췄습니다.
- README와 AGENTS 문서를 현재 운영 중인 계정 관리 흐름 기준으로 다시 동기화하고, 현재 릴리즈 표기와 계정 보안 설명을 함께 바로잡았습니다.

## v2.37.0 - 2026-03-27

- `/settings`의 시스템 진단 카드에 현재 프론트 배포 버전, 백엔드 API 버전, 두 버전의 일치 여부를 함께 표시하도록 보강했습니다.
- README와 AGENTS 문서도 설정 화면에서 배포 반영 상태를 직접 확인할 수 있는 현재 운영 흐름 기준으로 다시 동기화했습니다.
- `scripts/deployed_site_smoke.py`에 짧은 재시도 로직을 추가해, Render free 워밍업이나 배포 전환 구간의 일시적인 `502/503/504`·timeout 때문에 전체 검증이 불필요하게 깨지는 빈도를 낮췄습니다.

## v2.36.0 - 2026-03-27

- `scripts/wait_for_deployed_version.py`를 추가해, 로컬 `APP_VERSION` 기준으로 운영 `api.yoongeon.xyz/api/health`가 같은 버전과 `status=ok`를 반환할 때까지 주기적으로 확인할 수 있도록 했습니다.
- README와 AGENTS 문서에 운영 배포 반영 대기 명령을 추가해, `main` 머지 후 실제 서비스 반영 시점을 같은 기준으로 확인할 수 있게 정리했습니다.

## v2.35.0 - 2026-03-27

- `scripts/deployed_site_smoke.py`를 추가해 현재 운영 중인 `Vercel`/`Render` URL을 직접 호출하는 배포 스모크 체크를 만들었습니다.
- `verify.py --deployed-site-smoke`로 프론트 HTML 응답, 핵심 공개 API, 인증 필요 API의 `401 / SP-6014` 계약을 한 번에 점검할 수 있도록 런처를 확장했습니다.
- README와 AGENTS 문서를 운영 스모크 명령까지 포함하도록 다시 동기화했습니다.

## v2.34.0 - 2026-03-27

- 보호된 API가 `401 / SP-6014`를 반환할 때 프론트가 공통 인증 이벤트를 발생시키고, `AuthProvider`가 현재 Supabase 세션을 한 번 더 재검증하도록 정리했습니다.
- 복구 가능한 세션이면 토큰을 다시 맞추고, 복구되지 않는 세션이면 인증 상태를 정리해 보호 페이지가 멈춘 데이터 화면 대신 로그인 유도 상태로 자연스럽게 내려가도록 보강했습니다.
- README와 AGENTS 문서를 현재 세션 복구 흐름 기준에 맞춰 다시 동기화했습니다.

## v2.33.0 - 2026-03-27

- `backend/scripts/live_api_smoke.py`를 현재 인증 계약에 맞게 갱신해, 로그인 없이 호출하는 `watchlist`·`portfolio` 저장 API는 `401 / SP-6014`를 정상 결과로 검증하도록 정리했습니다.
- 국가 리포트 공개 timeout을 18초로 완화해, 워밍업 직후에도 `/api/country/KR/report`가 불필요하게 `SP-5018`로 끊기는 빈도를 낮췄습니다.
- README와 AGENTS의 검증 명령 설명을 현재 라이브 스모크 기준에 맞춰 다시 동기화했습니다.

## v2.32.0 - 2026-03-27

- `/settings` 계정 관리 패널에 저장 전 경고 배너와 브라우저 이탈 보호를 추가해, 프로필·이메일·비밀번호·회원 탈퇴 입력 중 작업하던 내용이 실수로 사라지지 않도록 정리했습니다.
- 프로필, 이메일 변경, 비밀번호 변경, 회원 탈퇴 영역마다 `입력 초기화` 버튼을 넣어 저장하지 않은 draft를 섹션별로 바로 비울 수 있게 했습니다.
- README와 AGENTS 문서를 현재 운영 기준의 계정 설정 편집 보호 UX까지 포함하도록 다시 동기화했습니다.

## v2.31.0 - 2026-03-27

- `/settings`의 새 이메일 변경 요청에도 60초 cooldown을 추가해, 인증 메일 재전송·비밀번호 재설정 메일과 같은 기준으로 메일 액션 흐름을 통일했습니다.
- 계정 관리 문서와 에이전트 기준선도 이메일 변경 요청의 cooldown 규칙까지 포함하도록 갱신했습니다.

## v2.30.0 - 2026-03-27

- `/auth`와 `/settings`의 인증 메일 재전송, 비밀번호 재설정 메일 액션에 60초 로컬 cooldown을 추가해 같은 메일 액션을 연속으로 반복하지 않도록 정리했습니다.
- 계정 화면의 초 단위 카운트다운 로직을 `frontend/src/hooks/useCooldownTimer.ts`로 공통화해, 공개 rate limit과 메일 액션 cooldown이 같은 방식으로 보이도록 맞췄습니다.
- README를 현재 운영 기준의 계정 보안 흐름과 메일 액션 cooldown 규칙까지 포함하도록 갱신했습니다.

## v2.29.0 - 2026-03-27

- 공개 계정 rate limit(`SP-6016`) 응답에 `Retry-After` 헤더를 추가해, 프론트가 문구 파싱에만 기대지 않고 표준 헤더로 남은 대기 시간을 읽을 수 있도록 정리했습니다.
- `/auth`, `/settings` 계정 흐름은 먼저 `Retry-After`를 읽고, 헤더가 없을 때만 기존 상세 문구를 보조 fallback으로 사용하도록 맞췄습니다.
- 공개 가입 API contract 테스트와 문서를 최신 계약에 맞춰 갱신했습니다.

## v2.28.0 - 2026-03-27

- `/settings` 계정 관리 패널에서도 공개 아이디 중복 확인 API의 rate limit(`SP-6016`)을 읽어 남은 대기 시간을 바로 표시하고, 버튼을 잠시 잠가 같은 요청을 반복하지 않도록 정리했습니다.
- 회원가입 화면과 설정 화면이 같은 재시도 안내 문구를 사용하도록 맞춰 공개 계정 엔드포인트의 UX가 흐름마다 다르게 보이지 않게 했습니다.
- README와 버전을 현재 운영 UX 기준으로 다시 동기화했습니다.

## v2.27.0 - 2026-03-27

- `/auth`에서 공개 계정 rate limit(`SP-6016`)이 걸릴 때 남은 대기 시간을 바로 보여주고, 중복 확인 버튼과 회원가입 제출 버튼을 잠시 잠가 같은 요청을 반복하지 않도록 정리했습니다.
- 공개 계정 엔드포인트가 제한될 때 토스트와 인라인 helper text가 같은 의미의 재시도 안내를 보여주도록 맞췄습니다.
- README와 버전을 현재 운영 UX 기준으로 다시 동기화했습니다.

## v2.26.0 - 2026-03-27

- `GET /api/account/username-availability`와 `POST /api/account/signup/validate`에 IP 기준의 짧은 sliding-window rate limit을 추가해 공개 가입 API 남용을 완화했습니다.
- 공개 계정 엔드포인트가 제한에 걸릴 때 `429`와 새 에러 코드 `SP-6016`을 일관되게 반환하도록 정리하고, 재시도 안내 문구를 함께 맞췄습니다.
- account router / API error contract 테스트를 갱신해 공개 가입 API의 구조화 에러 응답이 다시 깨지지 않도록 고정했습니다.

## v2.25.0 - 2026-03-27

- `/settings`에 `이메일 변경` 카드를 추가해 새 이메일 입력, 재확인, 검증 상태 확인, 변경 요청까지 같은 화면에서 처리할 수 있도록 정리했습니다.
- 계정 프로필 응답에 `pending_email`, `email_change_sent_at`를 추가해 현재 이메일 변경 대기 상태와 메일 발송 시각을 프론트에서 바로 안내할 수 있게 확장했습니다.
- 기존 인증 메일 재전송 카드도 일반 가입 인증과 변경 대기 이메일 인증을 구분해 다시 보낼 수 있도록 보강했습니다.

## v2.24.0 - 2026-03-27

- `/settings`에 `세션 보안` 카드를 추가해 마지막 로그인 시각과 현재 세션 만료 시각을 바로 확인할 수 있게 했습니다.
- 이 기기만 종료하는 일반 로그아웃과, 현재 계정으로 열려 있는 다른 세션까지 함께 종료하는 `모든 기기에서 로그아웃`을 분리해 보안 작업의 의미를 더 명확하게 정리했습니다.
- README와 AGENTS 문서를 현재 운영 기준의 세션 보안 흐름까지 포함하도록 갱신했습니다.

## v2.23.0 - 2026-03-27

- `/settings`에서 로그인 상태로 바로 새 비밀번호를 저장할 수 있는 인라인 변경 카드를 추가하고, 회원가입과 같은 강도 체크리스트를 그대로 재사용하도록 정리했습니다.
- 비밀번호 재설정 메일 카드의 역할을 `세션이 없거나 메일 링크 방식이 필요할 때의 대체 경로`로 다시 분리해, 즉시 변경과 메일 복구 흐름의 목적이 겹치지 않게 정돈했습니다.
- README와 AGENTS 문서를 현재 운영 기준의 비밀번호 변경 흐름까지 포함하도록 갱신했습니다.

## v2.22.0 - 2026-03-27

- `/settings` 계정 관리 패널에 `회원 탈퇴` 위험 작업 영역을 추가해, 현재 아이디 또는 이메일을 다시 입력해야만 탈퇴가 진행되도록 보강했습니다.
- 백엔드에 `DELETE /api/account/me`를 추가하고 Supabase Admin 삭제를 연결해, 계정 삭제 시 Auth 계정과 연결된 관심종목·포트폴리오 데이터가 함께 정리되도록 맞췄습니다.
- README와 AGENTS 문서를 현재 운영 기준의 탈퇴 흐름까지 포함하도록 갱신하고, account service/router 회귀 테스트를 추가했습니다.

## v2.21.0 - 2026-03-27

- 회원가입 직전에 `POST /api/account/signup/validate`를 호출하도록 추가해, 아이디/이메일/이름/전화번호/생년월일/비밀번호 규칙을 서버에서도 같은 의미로 다시 검증하도록 보강했습니다.
- 백엔드 account service에 이메일 정규화와 비밀번호 규칙 판정을 추가해, 프론트 우회 시에도 약한 비밀번호나 잘못된 계정 입력이 바로 통과하지 않도록 정리했습니다.
- `/auth` 회원가입 흐름이 서버가 반환한 정규화 값을 그대로 사용해 Supabase 가입을 진행하도록 바꿔, 클라이언트와 서버의 계정 입력 계약이 한 단계 더 일치하게 되었습니다.
- 계정 API 지도와 운영 문서를 새 공개 사전 검증 라우트 기준으로 갱신하고, 회원가입 사전 검증 서비스/라우터 회귀 테스트를 추가했습니다.

## v2.20.0 - 2026-03-27

- `/settings`에 `계정 관리` 패널을 추가해 로그인 후 아이디, 이름, 전화번호, 생년월일을 한 곳에서 수정하고, 이메일 인증 상태를 확인할 수 있게 정리했습니다.
- 백엔드에 `PATCH /api/account/me`를 추가해 프로필 수정 시에도 아이디 중복, 이름/전화번호/생년월일 형식을 서버에서 다시 검증하도록 보강했습니다.
- `/auth`를 로그인, 회원가입, 비밀번호 재설정 복구 모드까지 다루는 단일 흐름으로 재구성하고, 인증 메일 재전송과 비밀번호 재설정 메일 요청을 같은 화면에서 처리할 수 있게 만들었습니다.
- 계정 프로필 응답에 이메일 인증 상태와 인증 시각을 포함해, 프론트가 보안 상태를 명확하게 안내할 수 있도록 API 계약을 확장했습니다.
- 계정 서비스/라우터/인증 의존성 테스트를 추가 및 갱신하고, README와 AGENTS 문서를 현재 운영 기준의 계정 관리 흐름에 맞게 함께 갱신했습니다.

## v2.19.0 - 2026-03-27

- 이메일 회원가입 화면을 재구성해 아이디 중복 확인, 비밀번호 강도 체크리스트, 비밀번호 재확인, 이름·전화번호·생년월일 필수 입력을 한 흐름으로 정리했습니다.
- 계정 관련 로직을 `frontend/src/lib/account.ts`, `frontend/src/components/auth/*`, `backend/app/services/account_service.py`, `backend/app/routers/account.py` 중심으로 분리해 인증/프로필 검증 규칙과 화면 구성을 관리하기 쉽게 정리했습니다.
- `/api/account/username-availability`를 로그인 전 공개 확인 API로 바로 쓸 수 있게 수정하고, `/api/account/me`를 통해 현재 계정 프로필을 일관되게 읽도록 연결했습니다.
- 모바일 기준으로 상단 셸, 대시보드, 포트폴리오, 인증 화면의 레이아웃 브레이크포인트를 다시 조정하고, 과한 보라색 계열 강조를 줄여 더 차분한 단일 포인트 색 중심의 UI로 정돈했습니다.
- README를 예측 공식, 포트폴리오 최적화 공식, 무료 배포 구조, 회원가입 보안 규칙까지 포함하는 상세 문서로 전면 재작성하고, AGENTS/DESIGN_BIBLE도 현재 운영 구조에 맞춰 갱신했습니다.

## v2.18.0 - 2026-03-27

- 포트폴리오 추천, 조건 추천, 최적 추천, 일일 이상적 포트폴리오를 모두 `20거래일 기대수익률 + 기대초과수익률 + EWMA+shrinkage 공분산 + 회전율 패널티` 기준의 공통 optimizer로 통합했습니다.
- 새 공통 optimizer `backend/app/services/portfolio_optimizer.py`를 추가하고, 종목·레이더·보유 포지션이 모두 같은 20거래일 분포 스냅샷을 사용하도록 비중 산정과 요약 수치를 정리했습니다.
- 포트폴리오 관련 프론트 패널을 20거래일 기대수익률, 기대초과수익률, 상방·하방 확률, 예상 변동성, 회전율 중심으로 다시 맞춰 읽기 흐름을 통일했습니다.
- 이상적 포트폴리오와 포트폴리오 추천 회귀 테스트를 현재 계약에 맞춰 갱신하고, optimizer 자체의 가중치 상단 캡·국가/섹터 제약·20거래일 요약 출력 검증을 추가했습니다.

## v2.17.0 - 2026-03-26

- 공통 예측 백본을 다중 기간 가격 인코더, 공개시차 안전 거시 압축, 숫자 주도 게이트 결합, regime-aware Student-t mixture 분포 헤드 기준으로 정리하고, 종목/지수/무료 KR 확률 엔진이 같은 분포 모델을 기준으로 움직이도록 구조를 맞췄습니다.
- Opportunity Radar에서 분포 시그널 프로필 계산 순서가 잘못되어 즉시 예외가 날 수 있던 런타임 버그를 수정하고, KR 시장 레이더에서 1차 지수 예측에도 거시 입력을 함께 넣도록 보강했습니다.
- GPT-4o는 숫자 예측기가 아니라 구조화 이벤트 추출기로만 사용하도록 JSON schema 기반 추출 경로를 추가하고, 시스템 진단/README/에이전트 가이드의 구식 Monte Carlo·휴리스틱 설명을 현재 구현 기준으로 전면 갱신했습니다.
- 예측 엔진 회귀 테스트를 추가해 구조화 이벤트 추출의 fallback 경로와 Opportunity Radar의 분포 기반 응답 생성이 다시 깨지지 않도록 고정했습니다.

## v2.16.1 - 2026-03-26

- 로그인 후 홈 대시보드가 한 집계 API 지연 때문에 계속 `불러오는 중`에 머무르던 문제를 수정하고, 브리핑/히트맵/모멘텀/레이더/국가 리포트를 섹션별 timeout과 개별 fallback UI로 분리했습니다.
- 공개 대시보드에 사용하는 집계형 API에 timeout 보호를 추가하고, 지연 시 `504`와 새 에러 코드 `SP-5018`을 반환하도록 정리했습니다.
- 브리핑과 Opportunity Radar 계산량을 Render free 환경 기준으로 다시 낮추고, 일부 보강 데이터가 느릴 때는 요약 중심 응답으로 안전하게 축소되도록 보강했습니다.
- 프론트 에러 가이드를 실제 백엔드 에러 코드 정의에 맞춰 다시 정리하고, 로그인 필요 코드 판정(`SP-6014`)도 올바르게 수정했습니다.

## v2.16.0 - 2026-03-26

- Supabase 이메일 로그인과 세션 연동을 프론트에 추가해, 로그인 상태를 헤더에서 바로 확인하고 인증이 필요한 워치리스트/포트폴리오 화면은 계정 연결 흐름으로 자연스럽게 안내하도록 정리했습니다.
- 워치리스트, 포트폴리오 보유 종목, 포트폴리오 프로필 저장소를 사용자별 Supabase 테이블로 전환해, 같은 배포 URL을 여러 사용자가 써도 각자 데이터가 섞이지 않도록 구조를 바꿨습니다.
- 백엔드에 Supabase 토큰 검증 의존성과 사용자별 CRUD 경로를 추가하고, 로그인 필요 에러 `SP-6014`와 서버용 Supabase 키 미설정 에러 `SP-1006`을 새로 등록했습니다.
- 무료 배포 기준을 `Vercel Hobby + Render Free + Supabase Free + Cloudflare` 조합으로 다시 정리하고, Render free 제약에 맞춰 `render.yaml`, `.env.example`, README를 함께 갱신했습니다.

## v2.15.3 - 2026-03-26

- Vercel 프론트 + Render 백엔드 상시 배포 구성을 바로 가져갈 수 있도록 `render.yaml`, `frontend/.env.example`, 확장된 `backend/.env.example`를 추가했습니다.
- 백엔드 CORS 설정을 다중 프론트 도메인과 regex 기반 프리뷰 도메인까지 받을 수 있게 확장해, 커스텀 도메인과 `*.vercel.app` 프리뷰를 함께 운영하기 쉬워졌습니다.
- 부팅 시 예측 정확도/리서치 아카이브 동기화를 백그라운드 작업으로 돌리도록 바꿔, 저비용 호스팅 환경에서도 `/api/health`가 더 빨리 살아나도록 안정화했습니다.
- README를 상시 배포 기준으로 갱신하고, 환경 변수와 Render/Vercel/Cloudflare 연결 순서를 문서에 반영했습니다.
- KOSIS 설정명을 `*_USER_STATS_ID`에서 `*_STATS_ID`로 정리해, 별도 API가 아니라 같은 KOSIS 통계자료 API에 넘기는 통계표 ID라는 점이 코드와 문서에 드러나도록 맞췄습니다.
- `start.py`를 다시 실행하면 기존 개발 서버를 자동 종료 후 재시작하도록 바꿔, 로컬 개발 중 매번 `--stop`을 먼저 치지 않아도 되게 했습니다.

## v2.15.0 - 2026-03-25

- 기존 `signal-v2.4` 휴리스틱 예측을 그대로 유지한 채, 가격·거래량·상대강도·거시를 중심으로 `q10/q25/q50/q75/q90`, `상승/중립/하락 확률`, `장세 확률`을 반환하는 무료 한국장 확률 엔진 `kr-free-prob-v0.1`을 종목 상세에 병렬 추가했습니다.
- 무료 KR 확률 엔진 보강용으로 `OpenDART`, `Naver Search API`, `KOSIS` 클라이언트를 추가하고, 설정되어 있을 때만 공시/국내 뉴스/정부 통계를 약한 보조 신호로 반영하도록 연결했습니다.
- 종목 상세 화면에 새 `무료 KR 확률 엔진` 카드를 추가해 1·5·20거래일 중심 가격, 확률 밴드, 핵심 근거, 사용한 데이터 소스를 기존 다음 거래일 예측과 분리해서 읽을 수 있게 정리했습니다.
- 시스템 진단에 새 데이터 소스 상태와 확률 엔진 메타데이터를 반영하고, README와 `.env.example`도 무료 KR 확률 엔진 기준으로 함께 갱신했습니다.

## v2.14.0 - 2026-03-25

- 앱 전체를 한국장 전용으로 재정렬해 국가 레지스트리, 캘린더, 워치리스트, 포트폴리오, 브리핑, 리서치 아카이브가 이제 `KR`만 기준으로 동작하도록 정리했습니다.
- 프론트의 국가 선택 흔적을 걷어내고 대시보드, 레이더, 워치리스트, 스크리너, 포트폴리오, 아카이브, 설정 화면을 모두 한국 시장 중심 문구와 계약으로 맞췄습니다.
- 미국/일본 전용 보조 소스였던 `FRED`, `BOJ` 클라이언트를 제거하고, 무료 한국 스택 기준 문구와 오류 안내를 `ECOS + Yahoo Finance + PyKRX + Google News RSS` 중심으로 다시 정리했습니다.
- README를 한국 무료 버전 기준으로 전면 갱신해 현재 무료 스택, 추가로 붙일 무료 KR API(`OpenDART`, `KOSIS`, `Naver News Search API`), 그리고 무료 KR 확장 로드맵을 문서화했습니다.
- KR-only 전환에 맞춰 티커 해석, 캘린더, 유니버스, 포트폴리오, 예측 관련 회귀 테스트를 한국 기준으로 다시 고정했습니다.

## v2.13.0 - 2026-03-25

- 포트폴리오를 대시보드형 구성에서 자산 운영형 화면으로 다시 정리해, 총자산 요약과 자산 구성 막대, 총자산 설정, 보유 종목 관리가 상단에 먼저 오고 추천은 마지막에 보도록 정보 우선순위를 재배치했습니다.
- 포트폴리오에 총자산·예수금·월 추가 자금 프로필을 저장하는 API와 요약 계산을 추가해, 보유 주식과 현금을 함께 읽는 자산 관리 기준을 화면과 추천 엔진에 연결했습니다.
- 스크리너를 국가·섹터·P/E·배당 수준의 기본 검색에서 확장해 가격, 시총, P/B, 베타, 등락률, 52주 고점 대비, 성장률, ROE, 부채비율, 거래량, 수익성까지 함께 거르는 실전형 조건 검색으로 재설계했습니다.
- 대시보드는 선택한 국가의 시장 상태, 히트맵, 상승·하락 상위, 뉴스, 레이더에 집중하도록 단순화하고, 시장 세션 상태와 시스템 진단은 설정 화면으로 이동시켜 군더더기를 줄였습니다.
- 네비게이션 브랜드 영역과 상단 셸을 정리해 불필요한 문구와 버튼을 제거했고, 전역 액센트 색을 `#7C6AE6`으로 통일해 디자인 가이드와 실제 UI를 함께 맞췄습니다.
- `DESIGN_BIBLE.md`에 dense 페이지 배치 원칙, 포트폴리오/대시보드 decision thread 우선순위, accent 색상 규칙을 추가하고 README와 에러 코드 표에 `SP-5017`, `SP-6013`을 반영했습니다.

## v2.12.1 - 2026-03-24

- 포트폴리오 화면의 `조건 추천` 필터 영역을 고정 폭 그리드에서 반응형 그리드로 다시 구성해, 패널이 화면 밖으로 밀리거나 일부 컨트롤이 어색하게 잘리는 문제를 줄였습니다.
- `조건 추천`과 `최적 추천` 카드 래퍼에 `min-w-0`과 더 완만한 컬럼 비율을 적용해 중간~큰 해상도에서 정렬이 흐트러지지 않도록 안정화했습니다.
- `권장 비중 테이블`과 우측 리밸런싱 사이드 패널의 비율을 다시 조정하고 최소 폭을 명확히 잡아, 테이블이 깨지기보다 스크롤 가능한 상태로 유지되도록 보정했습니다.
- README와 버전을 `v2.12.1` 기준으로 동기화했습니다.

## v2.12.0 - 2026-03-24

- 포트폴리오 화면에 `조건 추천`과 `최적 추천`을 추가해, 사용자가 국가·섹터·운영 성향·최소 상승 확률·워치리스트 여부를 직접 지정하는 방식과 현재 포트폴리오 리스크를 기준으로 자동 최적화하는 방식을 나란히 비교할 수 있게 확장했습니다.
- 신규 추천 엔진은 기존 Opportunity Radar, 워치리스트, 현재 보유 비중, 국가/섹터 익스포저를 함께 읽어 신규 자금 투입용 비중안과 핵심 메모, 시장 체제 요약을 한 번에 반환하도록 구성했습니다.
- 추천 캐시 키에 현재 포트폴리오와 워치리스트 상태 시그니처를 반영해, 보유 종목을 추가/삭제한 직후에도 잠시 이전 추천이 남는 문제를 줄였습니다.
- 포트폴리오 API에 `/api/portfolio/recommendations/conditional`, `/api/portfolio/recommendations/optimal` 엔드포인트를 추가하고 관련 에러 코드 `SP-5015`, `SP-5016`을 등록했습니다.
- 포트폴리오 추천 회귀 테스트를 추가해 조건 필터링, 기존 보유 제외, 상태 기반 캐시 키 변화, 신규 라우트 계약이 다시 깨지지 않도록 검증했습니다.

## v2.11.0 - 2026-03-24

- 로그에서 반복적으로 보이던 일본 raw numeric ticker(`8001`)의 Yahoo 오류를 추적해, 검색·워치리스트·포트폴리오 전반에서 한국/일본 숫자 티커와 거래소 접두어 입력을 표준 Yahoo 티커로 자동 해석하는 공통 티커 해석 계층을 추가했습니다.
- 워치리스트와 포트폴리오는 기존에 저장된 raw ticker도 다시 읽을 때 자동으로 표준 티커로 보정하고, 필요한 경우 DB identity를 조용히 갱신해 stale 심볼 때문에 로그가 반복되는 문제를 줄였습니다.
- 홈 대시보드에 `오늘의 마켓 브리핑`과 `시장 세션 상태` 패널을 추가해, 장 개장 여부, 마지막 완결 종가 기준일, 국가별 실행 체제, 오늘 우선 볼 종목과 이벤트를 한 흐름으로 읽을 수 있게 정리했습니다.
- 포트폴리오 화면에 `포트폴리오 이벤트 레이더`를 추가해 보유 종목과 국가 비중을 기준으로 앞으로 3~30일 안에 체크할 실적/거시 이벤트와 직접 영향 비중을 보여주도록 확장했습니다.
- 종목 상세에 `예측 드리프트 모니터`를 추가해 저장된 다음 거래일 예측 이력의 상방 확률 변화, 방향 전환, 최근 적중률을 비교할 수 있게 만들었습니다.
- 새 API `/api/briefing/daily`, `/api/market/sessions`, `/api/ticker/resolve`, `/api/portfolio/event-radar`, `/api/stock/{ticker}/forecast-delta`를 추가하고 관련 에러 코드 `SP-5010`~`SP-5014`를 등록했습니다.
- 회귀 테스트를 확장해 티커 해석, 브리핑/이벤트 라우트, 예측 드리프트 요약이 다시 깨지지 않도록 고정했습니다.

## v2.10.13 - 2026-03-24

- 일봉 기반 예측과 차트 입력이 장중 미완결 봉을 잘못 쓰지 않도록, 시장별 `마지막 완결 거래일` 판정을 추가하고 Yahoo 일봉 이력을 그 기준으로 정규화했습니다.
- `get_stock_info`를 느린 펀더멘털 캐시와 신선한 시세 캐시로 분리해, 전일 `info.currentPrice`가 당일 종가/최신 종가를 덮어쓰던 문제를 수정했습니다.
- 종목/국가/섹터 분석 캐시 키를 최신 완결 일봉 날짜 기준으로 갱신해, 장 마감 후에도 이전 거래일 분석이 오래 남아 있지 않도록 정리했습니다.
- 회귀 테스트를 추가해 `stale info보다 fresh quote 우선`, `미완결 일봉 제외`, `세션 토큰 계산`이 다시 깨지지 않도록 고정했습니다.

## v2.10.12 - 2026-03-24

- 실행 문서를 다시 단순화해, README에는 이제 현재 위치와 무관하게 동작하는 절대경로 기준 명령 1개만 남기고 나머지 변형 경로는 제거했습니다.
- `start.py`의 안내 메시지도 상대경로/상위 폴더/절대경로를 여러 개 나열하지 않고, 어디서든 동작하는 기준 명령 1개와 `--status`, `--stop`, `--check` 옵션 재사용 방식만 보여주도록 정리했습니다.
- 상위 폴더와 프로젝트 루트가 섞여 생기던 혼선을 줄이기 위해, 실행 기준을 다시 절대경로 단일 흐름으로 되돌렸습니다.

## v2.10.11 - 2026-03-24

- 실행/검증 명령은 상대경로 기준으로 반드시 `C:\clone_repo\stock-predict` 안에서만 동작한다는 점을 README에 명확히 적고, 상위 폴더 `C:\clone_repo` 에 있을 때 바로 쓸 수 있는 `.\stock-predict\...` 예시와 절대경로 예시를 추가했습니다.
- `start.py --check`가 이제 프로젝트 루트와 함께 `프로젝트 루트 기준`, `상위 폴더 기준`, `절대경로 기준` 명령 예시를 바로 출력해 현재 위치가 잘못됐을 때 즉시 복구할 수 있도록 보강했습니다.
- 이 환경의 `cmd` AutoRun/Clink 훅 때문에 `.cmd` 실행이 불안정할 수 있다는 점을 문서에 반영하고, 기본 실행 경로를 다시 `python.exe start.py` 방식으로 정리했습니다.
- 상위 폴더에 잘못 생성된 `package-lock.json` 찌꺼기를 정리해 실행 흐름과 파일 목록 혼선을 줄였습니다.

## v2.10.10 - 2026-03-24

- 저장소 루트에 `package.json`과 절대경로 기반 `scripts/frontend_npm.js`를 추가해 `npm install`을 루트에서 실행해도 자동으로 `frontend` 의존성 설치까지 이어지도록 정리했습니다.
- 이제 프론트 의존성 설치 기본 경로를 루트 `npm install`로 안내해, 디렉터리를 잘못 옮긴 뒤 `npm install`을 치다가 `package.json`을 못 찾는 혼선을 줄였습니다.
- `start.py` 성공 메시지에 프롬프트가 바로 돌아오면 정상이라는 안내를 추가해, 서버가 백그라운드에서 계속 돌고 있는 상태를 더 명확하게 알 수 있도록 보강했습니다.
- `verify.py` 완료 메시지를 `[done] 검증 완료`로 바꿔, 출력 문구를 다시 명령처럼 입력하는 실수를 줄이도록 정리했습니다.

## v2.10.9 - 2026-03-24

- `start.py` 기본 동작을 대기형에서 백그라운드 기동형으로 바꿔, 서버를 띄운 뒤 현재 터미널 프롬프트를 바로 돌려주도록 정리했습니다.
- 개발 서버 PID를 `.run` 아래에 저장하고 `--status`, `--stop` 옵션을 추가해 상태 확인과 종료를 같은 런처에서 처리할 수 있게 만들었습니다.
- 실행 중 중복 기동을 감지하면 현재 상태와 중지 명령을 바로 안내하도록 바꿔, 같은 포트에 서버를 여러 번 올리는 실수를 줄였습니다.
- 준비 실패 시 마지막 로그 일부를 바로 보여주도록 유지하면서, 성공 시에는 로그 파일 위치와 다음 명령(`--status`, `--stop`)을 함께 출력하도록 보강했습니다.
- 확장 경로 정규화 회귀 테스트에 런타임 디렉터리 보장 검증을 추가했습니다.

## v2.10.8 - 2026-03-24

- `\\?\C:\...` 형태의 PowerShell 확장 경로가 `cmd`, `npm`, `node`에서 UNC처럼 처리되어 프론트 build/dev가 깨지던 문제를 수정하기 위해, 공용 경로 정규화 모듈 `dev_runtime.py`를 추가했습니다.
- `start.py`는 더 이상 새 콘솔 창 두 개를 띄운 뒤 바로 URL만 출력하지 않고, 현재 터미널을 유지한 채 백엔드/프론트를 백그라운드로 시작하고 실제 health 체크가 성공한 뒤에만 접속 주소를 보여주도록 바꿨습니다.
- 개발 서버 로그는 `.run/backend.log`, `.run/frontend.log`에 기록하도록 정리했고, 준비 실패 시 마지막 로그 일부를 바로 보여주게 해 원인 파악을 쉽게 만들었습니다.
- `verify.py`도 같은 경로 정규화와 Node 실행 경로를 재사용하도록 바꿔, PowerShell provider path와 확장 경로 환경에서도 프론트 build/typecheck가 끊기지 않도록 안정화했습니다.
- 회귀 테스트 `backend/tests/test_dev_runtime.py`를 추가해 Windows 확장 경로와 PowerShell provider prefix 정규화가 다시 깨지지 않도록 검증했습니다.

## v2.10.7 - 2026-03-24

- Windows PowerShell 실행 정책 때문에 `start.ps1` 가 서명 오류로 막히는 환경을 위해, 실행 정책 영향을 받지 않는 `start.cmd`와 공용 Python 런처 `start.py`를 추가했습니다.
- 기존 `start.ps1`는 직접 `Activate.ps1`를 호출하지 않고 `start.py`를 실행하는 얇은 래퍼로 바꿔, 우회 실행 시에도 다시 실행 정책에 걸리지 않도록 정리했습니다.
- 검증 스크립트도 `verify.py`, `verify.cmd`, `start.py --check` 경로를 추가해, 시작 전 가상환경·npm·핵심 패키지 상태를 먼저 확인하도록 강화했습니다.
- README, AGENTS, CONTRIBUTING 문서를 모두 새 실행 진입점 기준으로 맞추고, Windows 사용자는 `start.py` / `verify.py`를 가상환경 Python으로 직접 실행하는 경로를 기본값으로 사용하도록 안내를 정리했습니다.

## v2.10.6 - 2026-03-24

- FastAPI 기본 검증 오류와 잘못된 경로/메서드 오류를 구조화된 앱 에러 응답으로 감싸 `SP-6009`, `SP-6010`, `SP-6011`, `SP-6012` 코드가 일관되게 반환되도록 정리했습니다.
- 스크리너를 `market snapshot -> 상세 정보` 순서로 재구성해 상장폐지/무효 티커를 초기에 걸러내고, Yahoo 호출 수와 로그 노이즈를 줄였습니다.
- 국가 섹터 성과는 더 이상 깨지기 쉬운 하드코딩 ETF 몇 개에 의존하지 않고, 실제 섹터 대표 종목 스냅샷 평균으로 계산하도록 바꿔 한국/미국/일본 모두에서 안정성을 높였습니다.
- 확인된 무효 한국/미국 티커를 기본 유니버스에서 추가로 제외해 스크리너와 레이더가 오래된 심볼을 반복 호출하지 않도록 보강했습니다.
- API 에러 계약, 스크리너 유효성 필터, 섹터 성과 집계 회귀 테스트를 추가했고, 전체 라우트를 실호출하는 `backend/scripts/live_api_smoke.py`와 `.\verify.ps1 -LiveApiSmoke` 옵션을 도입했습니다.

## v2.10.5 - 2026-03-24

- 포트폴리오에 보유 종목을 추가할 때 한국 `005930`, 일본 `7203` 같은 로컬 티커를 자동으로 Yahoo 조회 형식(`.KS`, `.KQ`, `.T`)으로 정규화해 저장하도록 수정했습니다.
- 기존에 로컬 티커만 저장돼 있던 보유 종목도 포트폴리오 화면에서 다시 읽을 때 자동으로 표준 티커로 해석해, 손익·리스크·예측 로딩이 끊기지 않도록 보강했습니다.
- 포트폴리오 입력 카드에 국가별 입력 가이드, 인라인 오류 메시지, 토스트 피드백을 추가해 추가 실패 원인과 성공 결과가 바로 보이도록 정리했습니다.
- 포트폴리오 리스크 카드와 모델 포트폴리오 표의 그리드 분기점을 다시 잡아, 중간 해상도에서 추천 비중 테이블과 상단 입력 블록이 덜 잘리도록 레이아웃을 안정화했습니다.
- 포트폴리오 입력 검증용 에러 코드 `SP-6009`를 추가하고, 티커 정규화 및 저장 계약 회귀 테스트를 함께 확장했습니다.

## v2.10.4 - 2026-03-24

- 반복 스케줄 fallback이 월간 지표를 여러 날 연속 생성하던 문제를 수정해, 미국·한국·일본 CPI 같은 월간 이벤트가 한 달에 한 번만 표시되도록 정규화했습니다.
- 실제 경제 캘린더 데이터가 있는 달에는 같은 제목의 반복 추정 이벤트를 자동으로 숨기도록 바꿔, 외부 일정과 fallback 일정이 동시에 보여 중복처럼 보이던 문제를 줄였습니다.
- 캘린더 페이지를 공통 워크스페이스 헤더와 카드 리듬에 맞춰 다시 정리하고, 월간 요약 카드·선택 날짜 상세·다가오는 핵심 일정 패널의 정렬과 가독성을 개선했습니다.
- 캘린더 회귀 테스트를 추가해 월간 반복 일정 단건화와 실제 일정 우선 병합 규칙을 함께 검증하도록 강화했습니다.

## v2.10.3 - 2026-03-24

- 대시보드 상단을 두 개의 독립된 워크스페이스 카드로 다시 설계해 `내일 바로 볼 추천 포트폴리오`와 `지금 가장 강한 셋업`이 같은 기준선과 패딩으로 정렬되도록 정리했습니다.
- 대시보드용 `일일 이상적 포트폴리오`는 넓은 `추천 비중 테이블`을 제거하고, 화면 폭 안에서 읽히는 핵심 편입 카드·운영 플레이북·최근 기록 추적 중심 레이아웃으로 바꿔 잘림과 밀림을 줄였습니다.
- 모바일에서는 검색 헤더를 더 이상 sticky로 두지 않고, 상단 고정 바는 네비게이션 한 겹만 남기도록 조정해 투명하게 겹쳐 보이던 문제를 완화했습니다.
- 포트폴리오 화면의 `권장 비중 테이블` 스크롤 래퍼와 최소 폭을 다시 잡아 중간 해상도에서도 테이블이 과하게 잘려 보이지 않도록 보정했습니다.
- 검색 입력 영역과 상단 셸 배경을 더 불투명하게 맞춰 스크롤 중 뒤 레이어가 비쳐 보이던 인상을 줄였습니다.

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
