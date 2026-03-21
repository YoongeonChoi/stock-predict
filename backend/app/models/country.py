from pydantic import BaseModel
from datetime import datetime
from app.models.score import CountryScore


class IndexInfo(BaseModel):
    ticker: str
    name: str
    current_price: float = 0
    change_pct: float = 0
    prev_close: float = 0


class InstitutionView(BaseModel):
    name: str
    stance: str
    key_points: list[str]
    source_date: str = ""


class InstitutionalAnalysis(BaseModel):
    policy_institutions: list[InstitutionView]
    sell_side: list[InstitutionView]
    policy_sellside_aligned: bool
    consensus_count: int
    consensus_summary: str


class NewsItem(BaseModel):
    title: str
    source: str
    url: str
    published: str
    sentiment: str = "neutral"


COUNTRY_REGISTRY: dict[str, "CountryInfo"] = {}


class CountryInfo(BaseModel):
    code: str
    name: str
    name_local: str
    currency: str
    indices: list[IndexInfo]
    research_institutions: list[str]
    sectors_gics: list[str] = [
        "Energy", "Materials", "Industrials", "Consumer Discretionary",
        "Consumer Staples", "Health Care", "Financials",
        "Information Technology", "Communication Services", "Utilities",
        "Real Estate",
    ]


class CountryReport(BaseModel):
    country: CountryInfo
    score: CountryScore
    market_summary: str
    key_news: list[NewsItem]
    institutional_analysis: InstitutionalAnalysis
    top_stocks: list["StockSummaryRef"]
    generated_at: datetime


class StockSummaryRef(BaseModel):
    rank: int
    ticker: str
    name: str
    score: float
    current_price: float
    change_pct: float
    reason: str


def _init_registry():
    COUNTRY_REGISTRY["US"] = CountryInfo(
        code="US",
        name="United States",
        name_local="미국",
        currency="USD",
        indices=[
            IndexInfo(ticker="^GSPC", name="S&P 500"),
            IndexInfo(ticker="^DJI", name="Dow Jones"),
            IndexInfo(ticker="^IXIC", name="NASDAQ"),
        ],
        research_institutions=[
            "Federal Reserve",
            "Goldman Sachs Research",
            "J.P. Morgan Global Research",
            "Morgan Stanley Research",
            "BofA Global Research",
        ],
    )
    COUNTRY_REGISTRY["KR"] = CountryInfo(
        code="KR",
        name="South Korea",
        name_local="한국",
        currency="KRW",
        indices=[
            IndexInfo(ticker="^KS11", name="KOSPI"),
            IndexInfo(ticker="^KQ11", name="KOSDAQ"),
        ],
        research_institutions=[
            "한국은행(BOK)",
            "삼성증권 리서치",
            "NH투자증권 리서치본부",
            "미래에셋증권 리서치센터",
            "자본시장연구원(KCMI)",
            "KDI",
        ],
    )
    COUNTRY_REGISTRY["JP"] = CountryInfo(
        code="JP",
        name="Japan",
        name_local="일본",
        currency="JPY",
        indices=[
            IndexInfo(ticker="^N225", name="Nikkei 225"),
            IndexInfo(ticker="1306.T", name="TOPIX ETF"),
        ],
        research_institutions=[
            "Bank of Japan",
            "野村證券 / Nomura Reports",
            "Daiwa Institute of Research",
            "Mizuho Research & Technologies",
            "ニッセイ基礎研究所 / NLI Research Institute",
            "Japan Research Institute",
        ],
    )


_init_registry()
