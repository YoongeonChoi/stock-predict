"""Stock universe provider.

Tries FMP Stock Screener API first for dynamic, always-current data.
Falls back to hardcoded lists (S&P 500, KOSPI 200, Nikkei 225 level).
Dynamic data is cached for 24h so it doesn't burn API calls.
"""

import asyncio
import logging
from dataclasses import dataclass

from app.config import get_settings
from app.utils.async_tools import gather_limited

log = logging.getLogger("stock_predict.universe")

GICS_SECTORS = [
    "Energy", "Materials", "Industrials", "Consumer Discretionary",
    "Consumer Staples", "Health Care", "Financials",
    "Information Technology", "Communication Services", "Utilities", "Real Estate",
]

EXCHANGE_MAP = {
    "US": ["NYSE", "NASDAQ"],
    "KR": ["KSE"],
    "JP": ["TSE"],
}

SUFFIX_MAP = {"KR": ".KS", "JP": ".T"}
INVALID_TICKERS = {
    "091990.KS",
    "098560.KS",
    "042670.KS",
    "006390.KS",
    "119860.KS",
    "002270.KS",
    "049770.KS",
}


@dataclass(slots=True)
class UniverseSelection:
    sectors: dict[str, list[str]]
    source: str
    note: str = ""


def _sanitize_tickers(tickers: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw or "").strip().upper()
        if not ticker or ticker in INVALID_TICKERS or ticker in seen:
            continue
        seen.add(ticker)
        cleaned.append(ticker)
    return cleaned


async def fetch_dynamic_universe(country_code: str) -> dict[str, list[str]] | None:
    """Try fetching top stocks per sector from FMP Stock Screener API."""
    try:
        from app.data import fmp_client, cache
        cached = await cache.get(f"dynamic_universe:{country_code}")
        if cached:
            return cached

        exchanges = EXCHANGE_MAP.get(country_code, [])
        if not exchanges:
            return None

        market_cap_min = 500_000_000 if country_code == "US" else 100_000_000
        probe_results = await gather_limited(
            exchanges,
            lambda exchange: fmp_client.probe_stock_screener(
                exchange=exchange,
                market_cap_min=market_cap_min,
            ),
            limit=max(1, min(3, len(exchanges))),
        )
        available_exchanges = [
            exchange
            for exchange, allowed in zip(exchanges, probe_results)
            if not isinstance(allowed, Exception) and allowed
        ]
        if not available_exchanges:
            return None

        result: dict[str, list[str]] = {}
        suffix = SUFFIX_MAP.get(country_code, "")

        async def _fetch_sector(sector: str):
            tickers: list[str] = []
            tasks = [
                fmp_client.screen_stocks(
                    exchange=exchange, sector=sector,
                    market_cap_min=market_cap_min,
                    limit=60,
                )
                for exchange in available_exchanges
            ]
            for fetched in await asyncio.gather(*tasks, return_exceptions=True):
                if isinstance(fetched, Exception):
                    continue
                for t in fetched:
                    if suffix and not t.endswith(suffix):
                        t = t + suffix
                    if t not in tickers:
                        tickers.append(t)
            tickers = _sanitize_tickers(tickers)
            if tickers:
                return sector, tickers[:50]
            return sector, []

        for item in await gather_limited(GICS_SECTORS, _fetch_sector, limit=4):
            if isinstance(item, Exception):
                continue
            sector, tickers = item
            if tickers:
                result[sector] = tickers

        if len(result) >= 5:
            await cache.set(f"dynamic_universe:{country_code}", result, 86400)
            log.info(f"Dynamic universe for {country_code}: {sum(len(v) for v in result.values())} tickers across {len(result)} sectors")
            return result
    except Exception as e:
        log.warning(f"Dynamic universe fetch failed for {country_code}: {e}")
    return None


async def get_universe(country_code: str) -> dict[str, list[str]]:
    """Get stock universe: dynamic first, hardcoded fallback."""
    return (await resolve_universe(country_code)).sectors


def _fallback_universe(country_code: str) -> dict[str, list[str]]:
    return {
        sector: _sanitize_tickers(tickers)
        for sector, tickers in UNIVERSE.get(country_code, {}).items()
    }


def _fallback_note() -> str:
    settings = get_settings()
    if not settings.fmp_api_key:
        return "FMP API 키가 없어 검증된 기본 종목군으로 추천 중입니다."
    return "실시간 FMP 스크리너 연결이 제한돼 검증된 기본 종목군으로 추천 중입니다."


async def resolve_universe(country_code: str) -> UniverseSelection:
    """Return universe data with source metadata."""
    dynamic = await fetch_dynamic_universe(country_code)
    if dynamic:
        return UniverseSelection(
            sectors={sector: _sanitize_tickers(tickers) for sector, tickers in dynamic.items()},
            source="dynamic",
        )
    return UniverseSelection(
        sectors=_fallback_universe(country_code),
        source="fallback",
        note=_fallback_note(),
    )

US = {
    "Energy": [
        "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HAL",
        "DVN", "HES", "FANG", "BKR", "KMI", "WMB", "OKE", "TRGP", "MRO", "APA",
        "CTRA", "EQT", "TPL", "PXD", "AR", "RRC", "DEN", "SM", "MTDR", "CHRD",
        "NOV", "FTI", "HP", "CHK", "CNX", "MGY", "GPOR", "CPE", "PARR", "DINO",
    ],
    "Materials": [
        "LIN", "APD", "SHW", "ECL", "NEM", "FCX", "NUE", "DOW", "DD", "VMC",
        "MLM", "PPG", "IFF", "CE", "CTVA", "ALB", "EMN", "FMC", "BALL", "PKG",
        "IP", "CF", "MOS", "RPM", "AVY", "SEE", "AMCR", "WRK", "SON", "OI",
        "LYB", "HUN", "AXTA", "CC", "CBT", "TROX", "KWR", "NEU", "UFPI", "CRS",
    ],
    "Industrials": [
        "CAT", "GE", "HON", "UNP", "RTX", "DE", "BA", "LMT", "UPS", "MMM",
        "ETN", "ITW", "WM", "RSG", "EMR", "TDG", "NSC", "CSX", "GD", "NOC",
        "PH", "CARR", "OTIS", "TT", "CTAS", "FAST", "PCAR", "FDX", "DAL", "UAL",
        "LUV", "GWW", "ROK", "DOV", "SWK", "AOS", "XYL", "AME", "IEX", "GNRC",
        "VRSK", "WAB", "PAYC", "HEI", "TXT", "LHX", "LDOS", "J", "AXON", "PWR",
    ],
    "Consumer Discretionary": [
        "AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "TJX", "BKNG", "CMG",
        "MAR", "ORLY", "AZO", "ROST", "DHI", "LEN", "YUM", "DG", "DLTR", "EBAY",
        "F", "GM", "APTV", "PHM", "NVR", "GPC", "BBY", "POOL", "HLT", "WYNN",
        "LVS", "DRI", "EXPE", "MGM", "CZR", "RCL", "CCL", "NCLH", "TPR", "GRMN",
        "DECK", "LULU", "ULTA", "WSM", "RH", "KMX", "AN", "TSCO", "W", "ETSY",
    ],
    "Consumer Staples": [
        "PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "CL", "MDLZ", "KHC",
        "GIS", "SJM", "K", "HSY", "MKC", "HRL", "CPB", "CAG", "TSN", "ADM",
        "BG", "STZ", "TAP", "BF-B", "SAM", "MNST", "KDP", "KR", "SYY", "WBA",
        "TGT", "DG", "CLX", "CHD", "EL", "COTY", "NWL", "SPC", "USFD", "LW",
    ],
    "Health Care": [
        "UNH", "JNJ", "LLY", "PFE", "ABT", "TMO", "MRK", "ABBV", "DHR", "AMGN",
        "GILD", "BMY", "ISRG", "MDT", "BSX", "SYK", "REGN", "VRTX", "ZTS", "CI",
        "ELV", "HCA", "MCK", "COR", "CAH", "BDX", "EW", "DXCM", "IDXX", "A",
        "IQV", "HOLX", "ALGN", "BAX", "TECH", "TFX", "RMD", "MTD", "WST", "PODD",
        "MRNA", "BIIB", "ILMN", "RVTY", "HSIC", "DGX", "LH", "CNC", "MOH", "HUM",
    ],
    "Financials": [
        "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "BLK", "AXP",
        "SCHW", "C", "USB", "PNC", "TFC", "AIG", "MMC", "AON", "CB", "MET",
        "PRU", "AFL", "ALL", "TRV", "AJG", "TROW", "ICE", "CME", "NDAQ", "MSCI",
        "BK", "STT", "FITB", "KEY", "RF", "CFG", "HBAN", "ZION", "NTRS", "MTB",
        "COF", "DFS", "SYF", "ALLY", "GL", "FRC", "SIVB", "CINF", "L", "ERIE",
    ],
    "Information Technology": [
        "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "ADBE", "INTC", "CSCO",
        "TXN", "QCOM", "INTU", "AMAT", "IBM", "NOW", "ADI", "KLAC", "LRCX", "MU",
        "SNPS", "CDNS", "MRVL", "NXPI", "FTNT", "PANW", "CRWD", "MCHP", "ON", "SWKS",
        "HPQ", "DELL", "HPE", "WDC", "STX", "KEYS", "ANSS", "EPAM", "IT", "MPWR",
        "ENPH", "SEDG", "FSLR", "GEN", "CTSH", "AKAM", "FFIV", "JNPR", "ZBRA", "GLW",
    ],
    "Communication Services": [
        "META", "GOOGL", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR", "EA",
        "ATVI", "TTWO", "PARA", "WBD", "FOX", "FOXA", "NWS", "NWSA", "MTCH", "ZG",
        "RBLX", "SPOT", "PINS", "SNAP", "TTD", "ROKU", "LYV", "IPG", "OMC", "LUMN",
        "DISH", "IACI", "GOOG", "DKNG", "PENN", "BILL", "U", "YELP", "ZI", "PUBM",
    ],
    "Utilities": [
        "NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "ED", "WEC",
        "ES", "PPL", "FE", "EIX", "DTE", "AEE", "CMS", "AWK", "EVRG", "NI",
        "PEG", "LNT", "ATO", "OGE", "PNW", "NRG", "VST", "CEG", "CNP", "BKH",
        "AVA", "MGEE", "UTL", "SWX", "NWE", "SJW", "WTRG", "OTTR", "SR", "ALE",
    ],
    "Real Estate": [
        "PLD", "AMT", "EQIX", "CCI", "PSA", "SPG", "O", "WELL", "DLR", "AVB",
        "EQR", "ARE", "VTR", "SBAC", "UDR", "ESS", "MAA", "CPT", "REG", "HST",
        "KIM", "FRT", "BXP", "SLG", "VNO", "PEAK", "IRM", "CBRE", "WY", "INVH",
        "CUBE", "EXR", "LSI", "NNN", "STAG", "MPW", "OHI", "DOC", "IIPR", "AIV",
    ],
}

KR = {
    "Information Technology": [
        "005930.KS", "000660.KS", "035420.KS", "035720.KS", "036570.KS",
        "263750.KS", "034730.KS", "066570.KS", "006400.KS", "009150.KS",
        "402340.KS", "377300.KS", "058470.KS", "042700.KS", "018260.KS",
        "005387.KS", "005935.KS", "000990.KS", "010620.KS", "011070.KS",
        "012450.KS", "064350.KS", "086900.KS", "041510.KS", "302440.KS",
    ],
    "Financials": [
        "105560.KS", "055550.KS", "086790.KS", "316140.KS", "024110.KS",
        "138930.KS", "003550.KS", "005830.KS", "032830.KS", "071050.KS",
        "000810.KS", "029780.KS", "005940.KS", "003410.KS", "001450.KS",
        "002550.KS", "005387.KS", "090350.KS", "030000.KS", "006800.KS",
        "139130.KS", "175330.KS", "024110.KS", "006360.KS", "088350.KS",
    ],
    "Consumer Discretionary": [
        "005380.KS", "000270.KS", "012330.KS", "051910.KS", "004020.KS",
        "003490.KS", "004170.KS", "069960.KS", "161390.KS", "030200.KS",
        "011200.KS", "097950.KS", "004370.KS", "007310.KS", "003240.KS",
        "001040.KS", "023530.KS", "028050.KS", "006260.KS", "005300.KS",
        "014680.KS", "001680.KS", "005740.KS", "003920.KS", "007700.KS",
    ],
    "Industrials": [
        "010130.KS", "028260.KS", "009540.KS", "042660.KS", "011200.KS",
        "010140.KS", "034020.KS", "047050.KS", "000120.KS", "267250.KS",
        "000880.KS", "042670.KS", "009830.KS", "003570.KS", "002380.KS",
        "001740.KS", "000150.KS", "034730.KS", "011790.KS", "006260.KS",
        "047040.KS", "003030.KS", "014820.KS", "004490.KS", "069460.KS",
    ],
    "Materials": [
        "051910.KS", "005490.KS", "010130.KS", "011170.KS", "006800.KS",
        "003670.KS", "004000.KS", "001120.KS", "078930.KS", "005300.KS",
        "006390.KS", "011780.KS", "001520.KS", "000720.KS", "014580.KS",
        "010060.KS", "008930.KS", "004090.KS", "000210.KS", "004980.KS",
        "092780.KS", "008350.KS", "069620.KS", "023150.KS", "019170.KS",
    ],
    "Health Care": [
        "207940.KS", "068270.KS", "128940.KS", "326030.KS", "145020.KS",
        "196170.KQ", "004090.KS", "001630.KS", "195940.KS", "185750.KS",
        "214370.KS", "141080.KS", "006280.KS", "003060.KS", "002390.KS",
        "000100.KS", "119860.KS", "294870.KS", "237690.KS", "263750.KS",
    ],
    "Energy": [
        "096770.KS", "010950.KS", "267250.KS", "078930.KS", "006120.KS",
        "007070.KS", "003620.KS", "011760.KS", "036460.KS", "014680.KS",
        "006650.KS", "005090.KS", "014530.KS", "001510.KS", "004090.KS",
        "078520.KS", "009770.KS", "004170.KS", "003580.KS", "117580.KS",
    ],
    "Consumer Staples": [
        "097950.KS", "271560.KS", "004370.KS", "033780.KS", "280360.KS",
        "005610.KS", "005180.KS", "004990.KS", "014710.KS", "007310.KS",
        "001680.KS", "005740.KS", "003920.KS", "002270.KS", "003230.KS",
        "034120.KS", "016360.KS", "049770.KS", "007070.KS", "004410.KS",
    ],
    "Communication Services": [
        "030200.KS", "036570.KS", "035720.KS", "251270.KS", "041510.KS",
        "035900.KS", "293490.KS", "352820.KS", "259960.KS", "018260.KS",
        "017670.KS", "032640.KS", "078340.KS", "034830.KS", "030520.KS",
        "215600.KS", "053800.KS", "048410.KS", "060250.KS", "054220.KS",
    ],
    "Utilities": [
        "015760.KS", "034590.KS", "017390.KS", "071090.KS", "053210.KS",
        "006360.KS", "001440.KS", "029780.KS", "025820.KS", "003580.KS",
        "093370.KS", "071320.KS", "034590.KS", "130660.KS", "006040.KS",
        "032350.KS", "023350.KS", "025530.KS", "004150.KS", "036580.KS",
    ],
    "Real Estate": [
        "316140.KS", "377300.KS", "395400.KS", "365550.KS", "334890.KS",
        "448730.KS", "357120.KS", "417310.KS", "432320.KS", "330590.KS",
        "010960.KS", "012630.KS", "005010.KS", "003300.KS", "009770.KS",
        "023000.KS", "034300.KS", "006340.KS", "003520.KS", "001430.KS",
    ],
}

JP = {
    "Information Technology": [
        "6758.T", "6861.T", "6857.T", "4063.T", "6723.T",
        "6702.T", "7735.T", "6645.T", "6146.T", "4307.T",
        "6098.T", "4661.T", "9984.T", "6506.T", "6752.T",
        "7752.T", "6701.T", "6504.T", "6479.T", "6594.T",
        "7741.T", "6963.T", "6762.T", "6981.T", "7974.T",
    ],
    "Consumer Discretionary": [
        "7203.T", "7267.T", "7974.T", "9983.T", "7751.T",
        "7269.T", "7270.T", "2413.T", "3099.T", "7259.T",
        "7201.T", "7211.T", "2432.T", "9843.T", "9449.T",
        "3086.T", "8233.T", "9603.T", "2782.T", "7733.T",
        "4902.T", "3382.T", "7453.T", "8267.T", "9021.T",
    ],
    "Financials": [
        "8306.T", "8316.T", "8411.T", "8766.T", "8035.T",
        "8591.T", "8604.T", "8801.T", "8802.T", "7182.T",
        "8697.T", "8725.T", "8750.T", "8630.T", "7186.T",
        "8628.T", "8354.T", "8331.T", "8355.T", "7167.T",
        "8309.T", "8308.T", "7180.T", "8601.T", "8795.T",
    ],
    "Industrials": [
        "6301.T", "6501.T", "6503.T", "7011.T", "6902.T",
        "6273.T", "6367.T", "7012.T", "9020.T", "9022.T",
        "7013.T", "6471.T", "6302.T", "6305.T", "6326.T",
        "7832.T", "6954.T", "6753.T", "9021.T", "9147.T",
        "4543.T", "6361.T", "6113.T", "6448.T", "6268.T",
    ],
    "Health Care": [
        "4502.T", "4503.T", "4568.T", "4519.T", "4523.T",
        "6869.T", "4901.T", "4543.T", "6479.T", "2897.T",
        "4507.T", "4506.T", "4578.T", "4528.T", "4530.T",
        "4508.T", "4536.T", "4151.T", "4571.T", "4521.T",
    ],
    "Materials": [
        "4063.T", "3407.T", "4005.T", "4188.T", "5020.T",
        "5108.T", "3401.T", "4042.T", "4021.T", "3405.T",
        "5801.T", "5803.T", "5706.T", "5711.T", "5713.T",
        "5714.T", "5802.T", "4183.T", "4004.T", "4208.T",
        "3436.T", "5411.T", "5401.T", "5406.T", "3110.T",
    ],
    "Consumer Staples": [
        "2914.T", "2502.T", "2801.T", "2269.T", "4452.T",
        "2871.T", "2503.T", "4578.T", "2607.T", "2002.T",
        "2282.T", "2212.T", "2229.T", "2809.T", "2875.T",
        "2602.T", "2501.T", "7453.T", "3563.T", "2531.T",
    ],
    "Communication Services": [
        "9432.T", "9433.T", "9434.T", "4689.T", "9602.T",
        "2432.T", "3659.T", "4684.T", "9468.T", "9613.T",
        "4755.T", "9766.T", "3668.T", "2175.T", "4751.T",
        "9697.T", "3635.T", "3765.T", "9414.T", "2379.T",
    ],
    "Energy": [
        "5020.T", "5019.T", "1605.T", "5021.T", "5017.T",
        "9501.T", "9502.T", "9503.T", "1963.T", "5001.T",
        "5012.T", "1662.T", "5008.T", "1515.T", "5009.T",
        "5011.T", "1514.T", "1661.T", "5022.T", "5706.T",
    ],
    "Utilities": [
        "9501.T", "9502.T", "9503.T", "9531.T", "9532.T",
        "9504.T", "9505.T", "9506.T", "9507.T", "9508.T",
        "9509.T", "9511.T", "9513.T", "9514.T", "9515.T",
        "9517.T", "9519.T", "9531.T", "9533.T", "9534.T",
    ],
    "Real Estate": [
        "8801.T", "8802.T", "3289.T", "8830.T", "3291.T",
        "8804.T", "3003.T", "8803.T", "8905.T", "3231.T",
        "8933.T", "3252.T", "8840.T", "3258.T", "8923.T",
        "3289.T", "8934.T", "8818.T", "3231.T", "3482.T",
    ],
}

UNIVERSE = {"US": US, "KR": KR, "JP": JP}
