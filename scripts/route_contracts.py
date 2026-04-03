from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FAILED_TO_FETCH = "Failed to fetch"
BROWSER_TIMEOUT_MESSAGE = "32초 안에 응답이 오지 않았습니다."

DEFAULT_FORBIDDEN_TEXTS = (
    FAILED_TO_FETCH,
    BROWSER_TIMEOUT_MESSAGE,
)


DASHBOARD_TITLE = "대시보드"
RADAR_TITLE = "기회 레이더"
SCREENER_TITLE = "스크리너"
COMPARE_TITLE = "종목 비교"
CALENDAR_TITLE = "시장 일정 캘린더"
ARCHIVE_TITLE = "리포트 아카이브"
LAB_TITLE = "예측 연구실"
STOCK_SUMMARY_TITLE = "판단 요약"
PORTFOLIO_TITLE = "포트폴리오"
WATCHLIST_TITLE = "관심종목"
SETTINGS_TITLE = "설정 및 시스템"
AUTH_TITLE = "로그인 및 회원가입"
LOGIN_TITLE = "로그인"
SIGNUP_TITLE = "회원가입"


@dataclass(frozen=True)
class BrowserSmokeExpectation:
    required_texts: tuple[str, ...] = ()
    any_of_texts: tuple[str, ...] = ()
    forbidden_texts: tuple[str, ...] = DEFAULT_FORBIDDEN_TEXTS
    include_in_browser_smoke: bool = False
    include_in_deployed_frontend_smoke: bool = False


@dataclass(frozen=True)
class RouteContract:
    key: str
    route: str
    auth_required: bool
    operation_kind: str
    required_visible_state: tuple[str, ...]
    optional_upgrade_state: tuple[str, ...] = ()
    required_api_calls: tuple[str, ...] = ()
    external_dependencies: tuple[str, ...] = ()
    timeout_budgets: dict[str, int] = field(default_factory=dict)
    fallback_policy: str = ""
    retry_policy: str = ""
    smoke: BrowserSmokeExpectation = field(default_factory=BrowserSmokeExpectation)
    reversible_write_policy: str = "not-applicable"


@dataclass(frozen=True)
class ApiSmokeCheck:
    name: str
    method: str
    path: str
    expected_status: int = 200
    expected_error_code: str | None = None
    json_body: dict[str, Any] | None = None
    timeout: int = 45
    operation_kind: str = "public-read"


@dataclass(frozen=True)
class ReversibleAuthWriteCheck:
    name: str
    route: str
    operation_kind: str
    reversible_write_policy: str


ROUTE_CONTRACTS: tuple[RouteContract, ...] = (
    RouteContract(
        key="home",
        route="/",
        auth_required=False,
        operation_kind="public-read",
        required_visible_state=(DASHBOARD_TITLE,),
        optional_upgrade_state=("브리핑", "시장 히트맵", "강한 셋업"),
        required_api_calls=(
            "/api/countries",
            "/api/market/indicators",
            "/api/briefing/daily",
            "/api/country/KR/report",
            "/api/country/KR/heatmap",
            "/api/market/movers/KR",
            "/api/market/opportunities/KR",
        ),
        external_dependencies=("Render", "Yahoo", "Naver", "OpenAI"),
        timeout_budgets={"shell_ms": 4000, "quick_ms": 12000},
        fallback_policy="home shell 유지, briefing과 시장 요약은 stale/partial 허용",
        retry_policy="hydration에서 패널 단위 재시도",
        smoke=BrowserSmokeExpectation(
            required_texts=(DASHBOARD_TITLE,),
            any_of_texts=("시장 히트맵", "브리핑", "강한 셋업"),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
    ),
    RouteContract(
        key="radar",
        route="/radar",
        auth_required=False,
        operation_kind="public-read",
        required_visible_state=(RADAR_TITLE,),
        optional_upgrade_state=("KR 유니버스", "첫 판단 스레드"),
        required_api_calls=("/api/market/opportunities/KR",),
        external_dependencies=("Render", "Yahoo", "Naver"),
        timeout_budgets={"shell_ms": 4000, "quick_ms": 12000, "full_ms": 24000},
        fallback_policy="stale usable snapshot 우선, placeholder는 마지막 수단",
        retry_policy="사용자 재시도는 fresh quick 재요청",
        smoke=BrowserSmokeExpectation(
            required_texts=(RADAR_TITLE,),
            any_of_texts=("첫 판단 스레드", "KR 유니버스"),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
    ),
    RouteContract(
        key="screener",
        route="/screener",
        auth_required=False,
        operation_kind="public-read",
        required_visible_state=(SCREENER_TITLE,),
        optional_upgrade_state=("조건 기반 종목 필터링",),
        required_api_calls=("/api/screener",),
        external_dependencies=("Render", "Yahoo", "FMP"),
        timeout_budgets={"shell_ms": 4000, "quick_ms": 12000},
        fallback_policy="seed preview 또는 stale summary 우선 후 full 보강",
        retry_policy="필터 변경 또는 route budget 내 재시도",
        smoke=BrowserSmokeExpectation(
            required_texts=(SCREENER_TITLE,),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
    ),
    RouteContract(
        key="compare",
        route="/compare",
        auth_required=False,
        operation_kind="public-read",
        required_visible_state=(COMPARE_TITLE,),
        optional_upgrade_state=("종목 2~4개 나란히 비교",),
        required_api_calls=("/api/compare",),
        external_dependencies=("Render", "Yahoo"),
        timeout_budgets={"shell_ms": 4000, "quick_ms": 12000},
        fallback_policy="비교 shell 유지, 일부 종목 또는 패널만 degrade",
        retry_policy="입력 변경 또는 수동 재시도",
        smoke=BrowserSmokeExpectation(
            required_texts=(COMPARE_TITLE,),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
    ),
    RouteContract(
        key="calendar",
        route="/calendar",
        auth_required=False,
        operation_kind="public-read",
        required_visible_state=(CALENDAR_TITLE,),
        optional_upgrade_state=("월간 일정 요약", "다가오는 일정"),
        required_api_calls=("/api/calendar/KR",),
        external_dependencies=("Render", "FMP", "공식 일정 소스"),
        timeout_budgets={"shell_ms": 4000, "quick_ms": 12000},
        fallback_policy="요약 일정과 stale summary 우선",
        retry_policy="월 이동 또는 수동 재시도",
        smoke=BrowserSmokeExpectation(
            required_texts=(CALENDAR_TITLE,),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
    ),
    RouteContract(
        key="archive",
        route="/archive",
        auth_required=False,
        operation_kind="public-read",
        required_visible_state=(ARCHIVE_TITLE,),
        optional_upgrade_state=("기관 리서치 아카이브",),
        required_api_calls=("/api/archive", "/api/archive/research", "/api/archive/research/status"),
        external_dependencies=("Render", "공식 기관 리서치 소스"),
        timeout_budgets={"shell_ms": 4000, "quick_ms": 12000},
        fallback_policy="빈 데이터와 지연 상태를 분리해서 표시",
        retry_policy="수동 새로고침 또는 source sync 재시도",
        smoke=BrowserSmokeExpectation(
            required_texts=(ARCHIVE_TITLE,),
            any_of_texts=("기관 리서치 아카이브",),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
    ),
    RouteContract(
        key="lab",
        route="/lab",
        auth_required=False,
        operation_kind="public-read",
        required_visible_state=(LAB_TITLE,),
        optional_upgrade_state=("방향 적중률", "Calibration 추적"),
        required_api_calls=("/api/research/predictions", "/api/diagnostics"),
        external_dependencies=("Render", "prediction_records"),
        timeout_budgets={"shell_ms": 4000, "quick_ms": 12000},
        fallback_policy="bootstrapping 상태와 stale summary 우선",
        retry_policy="표본 갱신 이후 수동 재시도",
        smoke=BrowserSmokeExpectation(
            required_texts=(LAB_TITLE,),
            any_of_texts=("방향 적중률", "Calibration 추적"),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
    ),
    RouteContract(
        key="stock",
        route="/stock/003670.KS",
        auth_required=False,
        operation_kind="public-read",
        required_visible_state=(STOCK_SUMMARY_TITLE,),
        optional_upgrade_state=("차트", "기술 요약"),
        required_api_calls=(
            "/api/stock/003670/detail",
            "/api/stock/003670/detail?prefer_full=true",
            "/api/stock/003670/chart",
            "/api/stock/003670/technical-summary",
        ),
        external_dependencies=("Render", "Yahoo", "Naver", "OpenAI"),
        timeout_budgets={"shell_ms": 4000, "quick_ms": 12000, "full_ms": 24000},
        fallback_policy="cached full -> cached quick -> fresh quick -> bounded full",
        retry_policy="partial일 때만 hydration에서 bounded full 재시도",
        smoke=BrowserSmokeExpectation(
            required_texts=(STOCK_SUMMARY_TITLE,),
            any_of_texts=("기술 요약", "차트"),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
    ),
    RouteContract(
        key="portfolio",
        route="/portfolio",
        auth_required=True,
        operation_kind="auth-read",
        required_visible_state=(PORTFOLIO_TITLE,),
        optional_upgrade_state=("보유 종목", "조건 추천", "최적 추천"),
        required_api_calls=(
            "/api/portfolio",
            "/api/portfolio/profile",
            "/api/portfolio/recommendations/conditional",
            "/api/portfolio/recommendations/optimal",
            "/api/portfolio/event-radar",
        ),
        external_dependencies=("Supabase", "Render"),
        timeout_budgets={"shell_ms": 4000, "quick_ms": 12000},
        fallback_policy="preview shell 유지, 패널 단위 degrade",
        retry_policy="패널별 재시도",
        smoke=BrowserSmokeExpectation(
            required_texts=(PORTFOLIO_TITLE,),
            any_of_texts=("보유 종목", "포트폴리오는 로그인 후 관리합니다"),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
    ),
    RouteContract(
        key="watchlist",
        route="/watchlist",
        auth_required=True,
        operation_kind="auth-read",
        required_visible_state=(WATCHLIST_TITLE,),
        optional_upgrade_state=("저장된 관심종목",),
        required_api_calls=("/api/watchlist",),
        external_dependencies=("Supabase", "Render"),
        timeout_budgets={"shell_ms": 3000, "quick_ms": 10000},
        fallback_policy="preview 유지, 목록 패널만 degrade",
        retry_policy="목록 패널 재시도",
        smoke=BrowserSmokeExpectation(
            required_texts=(WATCHLIST_TITLE,),
            any_of_texts=("저장된 관심종목", "관심종목은 로그인 후 사용합니다"),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
        reversible_write_policy="임시 종목 추가 후 즉시 제거",
    ),
    RouteContract(
        key="settings",
        route="/settings",
        auth_required=True,
        operation_kind="auth-read",
        required_visible_state=(SETTINGS_TITLE,),
        optional_upgrade_state=("시스템 진단", "시장 세션"),
        required_api_calls=("/api/account/me", "/api/diagnostics", "/api/market/sessions"),
        external_dependencies=("Supabase", "Render"),
        timeout_budgets={"shell_ms": 3000, "quick_ms": 10000},
        fallback_policy="settings shell 유지, 패널 단위 degrade",
        retry_policy="패널별 재시도",
        smoke=BrowserSmokeExpectation(
            any_of_texts=(SETTINGS_TITLE, LOGIN_TITLE, AUTH_TITLE),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
        reversible_write_policy="profile metadata 변경 후 즉시 원복",
    ),
    RouteContract(
        key="auth",
        route="/auth",
        auth_required=False,
        operation_kind="public-read",
        required_visible_state=(AUTH_TITLE,),
        optional_upgrade_state=(LOGIN_TITLE, SIGNUP_TITLE),
        required_api_calls=("/api/account/signup/validate", "/api/account/username-availability"),
        external_dependencies=("Supabase", "Render"),
        timeout_budgets={"shell_ms": 3000},
        fallback_policy="auth shell 우선",
        retry_policy="사용자 입력과 사전 검증 기준",
        smoke=BrowserSmokeExpectation(
            any_of_texts=(AUTH_TITLE, LOGIN_TITLE, SIGNUP_TITLE),
            include_in_browser_smoke=True,
            include_in_deployed_frontend_smoke=True,
        ),
    ),
)


LIVE_API_SMOKE_CHECKS: tuple[ApiSmokeCheck, ...] = (
    ApiSmokeCheck("health", "GET", "/api/health"),
    ApiSmokeCheck("countries", "GET", "/api/countries"),
    ApiSmokeCheck("country-report", "GET", "/api/country/KR/report", timeout=60),
    ApiSmokeCheck("country-heatmap", "GET", "/api/country/KR/heatmap", timeout=60),
    ApiSmokeCheck("country-report-pdf", "GET", "/api/country/KR/report/pdf"),
    ApiSmokeCheck("country-report-csv", "GET", "/api/country/KR/report/csv"),
    ApiSmokeCheck("country-forecast", "GET", "/api/country/KR/forecast"),
    ApiSmokeCheck("market-indicators", "GET", "/api/market/indicators"),
    ApiSmokeCheck("sector-performance", "GET", "/api/country/KR/sector-performance"),
    ApiSmokeCheck("sectors", "GET", "/api/country/KR/sectors"),
    ApiSmokeCheck("market-movers", "GET", "/api/market/movers/KR"),
    ApiSmokeCheck("market-opportunities", "GET", "/api/market/opportunities/KR?limit=12", timeout=60),
    ApiSmokeCheck("sector-report", "GET", "/api/country/KR/sector/information_technology/report", timeout=60),
    ApiSmokeCheck("stock-detail", "GET", "/api/stock/005930.KS/detail", timeout=60),
    ApiSmokeCheck("stock-chart", "GET", "/api/stock/005930.KS/chart"),
    ApiSmokeCheck("stock-technical-summary", "GET", "/api/stock/005930.KS/technical-summary"),
    ApiSmokeCheck("stock-pivot-points", "GET", "/api/stock/005930.KS/pivot-points"),
    ApiSmokeCheck("search", "GET", "/api/search?q=005930"),
    ApiSmokeCheck(
        "watchlist-auth",
        "GET",
        "/api/watchlist",
        expected_status=401,
        expected_error_code="SP-6014",
        operation_kind="auth-read",
    ),
    ApiSmokeCheck(
        "watchlist-auth-post",
        "POST",
        "/api/watchlist/005930.KS?country_code=KR",
        expected_status=401,
        expected_error_code="SP-6014",
        operation_kind="auth-write",
    ),
    ApiSmokeCheck(
        "watchlist-auth-delete",
        "DELETE",
        "/api/watchlist/005930.KS",
        expected_status=401,
        expected_error_code="SP-6014",
        operation_kind="auth-write",
    ),
    ApiSmokeCheck("compare", "GET", "/api/compare?tickers=005930.KS,000660.KS"),
    ApiSmokeCheck("archive", "GET", "/api/archive"),
    ApiSmokeCheck("archive-accuracy", "GET", "/api/archive/accuracy/stats"),
    ApiSmokeCheck("archive-research", "GET", "/api/archive/research?region_code=KR&limit=20&auto_refresh=false"),
    ApiSmokeCheck("archive-research-status", "GET", "/api/archive/research/status"),
    ApiSmokeCheck("archive-research-refresh", "POST", "/api/archive/research/refresh"),
    ApiSmokeCheck("calendar", "GET", "/api/calendar/KR?year=2026&month=3", timeout=60),
    ApiSmokeCheck("screener", "GET", "/api/screener?country=KR&limit=20", timeout=60),
    ApiSmokeCheck(
        "portfolio-auth",
        "GET",
        "/api/portfolio",
        expected_status=401,
        expected_error_code="SP-6014",
        operation_kind="auth-read",
    ),
    ApiSmokeCheck("portfolio-ideal", "GET", "/api/portfolio/ideal?refresh=false&history_limit=10"),
    ApiSmokeCheck("diagnostics", "GET", "/api/diagnostics"),
    ApiSmokeCheck("diagnostics-legacy", "GET", "/api/system/diagnostics"),
    ApiSmokeCheck("prediction-lab", "GET", "/api/research/predictions?limit_recent=20&refresh=false", timeout=60),
    ApiSmokeCheck(
        "portfolio-holdings-auth",
        "POST",
        "/api/portfolio/holdings",
        expected_status=401,
        expected_error_code="SP-6014",
        json_body={"ticker": "AAPL"},
        operation_kind="auth-write",
    ),
    ApiSmokeCheck("not-found", "GET", "/api/does-not-exist", expected_status=404, expected_error_code="SP-6011"),
)


DEPLOYED_API_SMOKE_CHECKS: tuple[ApiSmokeCheck, ...] = (
    ApiSmokeCheck("health", "GET", "/api/health"),
    ApiSmokeCheck("countries", "GET", "/api/countries"),
    ApiSmokeCheck(
        "watchlist-auth",
        "GET",
        "/api/watchlist",
        expected_status=401,
        expected_error_code="SP-6014",
        operation_kind="auth-read",
    ),
    ApiSmokeCheck("market-indicators", "GET", "/api/market/indicators"),
    ApiSmokeCheck("briefing", "GET", "/api/briefing/daily", timeout=60),
    ApiSmokeCheck("country-report", "GET", "/api/country/KR/report", timeout=60),
    ApiSmokeCheck("diagnostics", "GET", "/api/diagnostics"),
    ApiSmokeCheck("market-heatmap", "GET", "/api/country/KR/heatmap", timeout=60),
    ApiSmokeCheck("market-opportunities", "GET", "/api/market/opportunities/KR?limit=8", timeout=60),
    ApiSmokeCheck("screener", "GET", "/api/screener?country=KR&limit=20", timeout=60),
    ApiSmokeCheck("calendar", "GET", "/api/calendar/KR", timeout=60),
    ApiSmokeCheck("prediction-lab", "GET", "/api/research/predictions?limit_recent=20&refresh=false", timeout=60),
    ApiSmokeCheck("stock-detail", "GET", "/api/stock/003670/detail", timeout=60),
    ApiSmokeCheck("stock-detail-full", "GET", "/api/stock/003670/detail?prefer_full=true", timeout=60),
    ApiSmokeCheck("health-post-stock", "GET", "/api/health"),
)


REVERSIBLE_AUTH_WRITE_CHECKS: tuple[ReversibleAuthWriteCheck, ...] = (
    ReversibleAuthWriteCheck(
        name="watchlist-write",
        route="/watchlist",
        operation_kind="auth-write",
        reversible_write_policy="임시 후보를 추가하고 즉시 제거",
    ),
    ReversibleAuthWriteCheck(
        name="portfolio-holding-write",
        route="/portfolio",
        operation_kind="auth-write",
        reversible_write_policy="임시 보유 종목을 추가 또는 수정한 뒤 즉시 제거",
    ),
    ReversibleAuthWriteCheck(
        name="settings-profile-write",
        route="/settings",
        operation_kind="auth-write",
        reversible_write_policy="profile metadata 변경 후 즉시 원복",
    ),
)


def iter_browser_route_contracts() -> list[RouteContract]:
    return [contract for contract in ROUTE_CONTRACTS if contract.smoke.include_in_browser_smoke]


def iter_browser_route_paths() -> list[str]:
    return [contract.route for contract in iter_browser_route_contracts()]


def iter_deployed_frontend_route_contracts() -> list[RouteContract]:
    return [contract for contract in ROUTE_CONTRACTS if contract.smoke.include_in_deployed_frontend_smoke]


def iter_live_api_smoke_checks() -> list[ApiSmokeCheck]:
    return list(LIVE_API_SMOKE_CHECKS)


def iter_deployed_api_smoke_checks() -> list[ApiSmokeCheck]:
    return list(DEPLOYED_API_SMOKE_CHECKS)


def iter_reversible_auth_write_checks() -> list[ReversibleAuthWriteCheck]:
    return list(REVERSIBLE_AUTH_WRITE_CHECKS)
