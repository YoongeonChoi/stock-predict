import unittest
from unittest.mock import AsyncMock, patch

from app.data import kr_market_quote_client


SAMPLE_HTML = """
<html>
  <body>
    <table class="type_2">
      <tr>
        <th>N</th><th>종목명</th><th>현재가</th><th>전일비</th><th>등락률</th>
        <th>액면가</th><th>시가총액</th><th>상장주식수</th><th>외국인비율</th><th>거래량</th><th>PER</th><th>ROE</th><th>토론</th>
      </tr>
      <tr>
        <td>1</td><td><a class="tltle" href="/item/main.naver?code=005930">삼성전자</a></td><td>179,700</td><td>하락 400</td><td>-0.22%</td>
        <td>100</td><td>10,637,589</td><td>5,919,638</td><td>48.90</td><td>29,113,466</td><td>27.38</td><td>10.85</td><td></td>
      </tr>
      <tr>
        <td>2</td><td><a class="tltle" href="/item/main.naver?code=000660">SK하이닉스</a></td><td>922,000</td><td>하락 11,000</td><td>-1.18%</td>
        <td>5,000</td><td>6,571,116</td><td>712,702</td><td>53.21</td><td>4,520,842</td><td>15.64</td><td>44.15</td><td></td>
      </tr>
    </table>
    <td class="pgRR"><a href="/sise/sise_market_sum.naver?sosok=0&page=49">맨뒤</a></td>
  </body>
</html>
"""


class KrMarketQuoteClientTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_market_page_quotes_extracts_tickers(self):
        last_page, quotes = kr_market_quote_client._parse_market_page_quotes(SAMPLE_HTML, suffix=".KS")

        self.assertEqual(last_page, 49)
        self.assertEqual(set(quotes.keys()), {"005930.KS", "000660.KS"})
        self.assertEqual(quotes["005930.KS"]["name"], "삼성전자")
        self.assertEqual(quotes["005930.KS"]["current_price"], 179700.0)
        self.assertEqual(quotes["005930.KS"]["change_pct"], -0.22)
        self.assertGreater(quotes["005930.KS"]["market_cap"], 0.0)

    async def test_get_kr_bulk_quotes_merges_market_pages_and_fallback(self):
        market_quotes = {
            "005930.KS": {
                "ticker": "005930.KS",
                "name": "삼성전자",
                "current_price": 179700.0,
                "prev_close": 180100.0,
                "change_pct": -0.22,
                "market_cap": 1063758900000000.0,
                "session_date": "2026-03-27",
            }
        }
        fallback_quotes = {
            "123456.KQ": {
                "ticker": "123456.KQ",
                "current_price": 1050.0,
                "prev_close": 1000.0,
                "change_pct": 5.0,
                "session_date": "2026-03-27",
            }
        }

        with (
            patch(
                "app.data.kr_market_quote_client._fetch_full_kr_market_quotes",
                new=AsyncMock(return_value=market_quotes),
            ),
            patch(
                "app.data.kr_market_quote_client.yfinance_client.get_batch_stock_quotes",
                new=AsyncMock(return_value=fallback_quotes),
            ),
        ):
            quotes = await kr_market_quote_client.get_kr_bulk_quotes(["005930.KS", "123456.KQ"])

        self.assertEqual(set(quotes.keys()), {"005930.KS", "123456.KQ"})
        self.assertEqual(quotes["123456.KQ"]["current_price"], 1050.0)
        self.assertEqual(quotes["123456.KQ"]["name"], "123456")

    async def test_get_kr_bulk_quotes_uses_fast_small_batch_path_without_full_market_fetch(self):
        fallback_quotes = {
            "005930.KS": {
                "ticker": "005930.KS",
                "current_price": 179700.0,
                "prev_close": 180100.0,
                "change_pct": -0.22,
                "session_date": "2026-03-27",
            },
            "000660.KS": {
                "ticker": "000660.KS",
                "current_price": 922000.0,
                "prev_close": 933000.0,
                "change_pct": -1.18,
                "session_date": "2026-03-27",
            },
        }

        with (
            patch(
                "app.data.kr_market_quote_client.yfinance_client.get_batch_stock_quotes",
                new=AsyncMock(return_value=fallback_quotes),
            ) as batch_quotes,
            patch(
                "app.data.kr_market_quote_client._fetch_full_kr_market_quotes",
                new=AsyncMock(side_effect=AssertionError("full market fetch should not run")),
            ) as full_fetch,
            patch(
                "app.data.kr_market_quote_client.yfinance_client._kr_ticker_name",
                side_effect=lambda ticker: {"005930.KS": "삼성전자", "000660.KS": "SK하이닉스"}.get(ticker),
            ),
        ):
            quotes = await kr_market_quote_client.get_kr_bulk_quotes(["005930.KS", "000660.KS"])

        self.assertEqual(set(quotes.keys()), {"005930.KS", "000660.KS"})
        self.assertEqual(quotes["005930.KS"]["name"], "삼성전자")
        self.assertEqual(quotes["000660.KS"]["name"], "SK하이닉스")
        batch_quotes.assert_awaited_once()
        full_fetch.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
