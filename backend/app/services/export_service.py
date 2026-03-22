"""PDF and CSV export service with Unicode (Korean/Japanese) support."""

import csv
import io
import os
import platform

from fpdf import FPDF


SECTION_TITLES = {
    "market_summary": "시장 요약",
    "score": "점수",
    "institutional_analysis": "기관 관점",
    "top_stocks": "상위 종목",
    "analysis_summary": "AI 분석",
    "buy_sell_guide": "매매 가이드",
    "key_news": "핵심 뉴스",
}


def _find_unicode_font() -> str | None:
    """Find a system TTF font that supports CJK characters."""
    candidates = []
    if platform.system() == "Windows":
        fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        candidates = [
            os.path.join(fonts_dir, "malgun.ttf"),
            os.path.join(fonts_dir, "malgungbd.ttf"),
            os.path.join(fonts_dir, "NotoSansCJK-Regular.ttc"),
            os.path.join(fonts_dir, "msgothic.ttc"),
            os.path.join(fonts_dir, "YuGothR.ttc"),
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _sanitize_for_latin(text: str) -> str:
    """Remove non-Latin characters if no Unicode font is available."""
    return "".join(c if ord(c) < 256 else "?" for c in text)


def export_csv(data: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    if "top_stocks" in data:
        writer.writerow(["순위", "티커", "종목명", "점수", "가격", "등락률(%)"])
        for stock in data["top_stocks"]:
            writer.writerow([
                stock.get("rank"), stock.get("ticker"), stock.get("name"),
                stock.get("score"), stock.get("current_price"), stock.get("change_pct"),
            ])
    elif "ticker" in data:
        writer.writerow(["항목", "값"])
        for key in ["ticker", "name", "sector", "current_price", "pe_ratio", "pb_ratio", "ev_ebitda", "market_cap"]:
            writer.writerow([key, data.get(key, "")])
        if "score" in data:
            writer.writerow([])
            writer.writerow(["점수 구간", "점수", "최대"])
            score = data["score"]
            for category in ["fundamental", "valuation", "growth_momentum", "analyst", "risk"]:
                bucket = score.get(category, {})
                writer.writerow([category, bucket.get("total", ""), bucket.get("max_score", "")])
    else:
        writer.writerow(["키", "값"])
        for key, value in data.items():
            if isinstance(value, (str, int, float)):
                writer.writerow([key, value])

    return output.getvalue()


class UnicodePDF(FPDF):
    """FPDF subclass with Unicode font support."""

    def __init__(self):
        super().__init__()
        self._unicode_ready = False
        font_path = _find_unicode_font()
        if font_path:
            try:
                self.add_font("Unicode", "", font_path, uni=True)
                self.add_font("Unicode", "B", font_path, uni=True)
                self._unicode_ready = True
            except Exception:
                pass

    def set_unicode_font(self, style: str = "", size: int = 10):
        if self._unicode_ready:
            self.set_font("Unicode", style, size)
        else:
            self.set_font("Helvetica", style, size)

    def safe_cell(self, w, h, txt, **kwargs):
        if not self._unicode_ready:
            txt = _sanitize_for_latin(txt)
        self.cell(w, h, txt, **kwargs)

    def safe_multi_cell(self, w, h, txt, **kwargs):
        if not self._unicode_ready:
            txt = _sanitize_for_latin(txt)
        self.multi_cell(w, h, txt, **kwargs)


def export_pdf(data: dict, title: str = "주식 분석 리포트") -> bytes:
    pdf = UnicodePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_unicode_font("B", 16)
    pdf.safe_cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    if "market_summary" in data:
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, SECTION_TITLES["market_summary"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        summary = str(data["market_summary"])[:2000]
        for line in summary.split("\n"):
            pdf.safe_multi_cell(0, 5, line)
        pdf.ln(3)

    if "score" in data:
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, SECTION_TITLES["score"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        score = data["score"]
        if "total" in score:
            pdf.safe_cell(0, 6, f"총점: {score['total']} / 100", new_x="LMARGIN", new_y="NEXT")
        for key, value in score.items():
            if isinstance(value, dict) and "score" in value:
                pdf.safe_cell(
                    0,
                    5,
                    f"  {value.get('name', key)}: {value['score']} / {value.get('max_score', '')}",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
        pdf.ln(3)

    if "institutional_analysis" in data:
        institutional = data["institutional_analysis"]
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, SECTION_TITLES["institutional_analysis"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        if institutional.get("consensus_summary"):
            pdf.safe_multi_cell(0, 5, str(institutional["consensus_summary"]))
        for group_key in ("policy_institutions", "sell_side"):
            for institution in institutional.get(group_key, []):
                name = institution.get("name", "")
                stance = institution.get("stance", "")
                pdf.safe_cell(0, 5, f"  {name} ({stance})", new_x="LMARGIN", new_y="NEXT")
                for point in institution.get("key_points", [])[:3]:
                    pdf.safe_cell(0, 4, f"    - {point}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    if "top_stocks" in data:
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, SECTION_TITLES["top_stocks"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        for stock in data["top_stocks"][:10]:
            line = f"#{stock.get('rank', '')} {stock.get('ticker', '')} - {stock.get('name', '')} | 점수: {stock.get('score', '')} | 가격: {stock.get('current_price', '')}"
            pdf.safe_cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")
            if stock.get("reason"):
                pdf.set_unicode_font("", 8)
                pdf.safe_cell(0, 4, f"   {stock['reason']}", new_x="LMARGIN", new_y="NEXT")
                pdf.set_unicode_font("", 9)
        pdf.ln(3)

    if "analysis_summary" in data and data["analysis_summary"]:
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, SECTION_TITLES["analysis_summary"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        for line in str(data["analysis_summary"])[:3000].split("\n"):
            pdf.safe_multi_cell(0, 5, line)
        pdf.ln(3)

    if "buy_sell_guide" in data:
        guide = data["buy_sell_guide"]
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, SECTION_TITLES["buy_sell_guide"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        pdf.safe_cell(0, 5, f"매수 구간: {guide.get('buy_zone_low')} - {guide.get('buy_zone_high')}", new_x="LMARGIN", new_y="NEXT")
        pdf.safe_cell(0, 5, f"적정 가치: {guide.get('fair_value')}", new_x="LMARGIN", new_y="NEXT")
        pdf.safe_cell(0, 5, f"매도 구간: {guide.get('sell_zone_low')} - {guide.get('sell_zone_high')}", new_x="LMARGIN", new_y="NEXT")
        pdf.safe_cell(
            0,
            5,
            f"신뢰 등급: {guide.get('confidence_grade')} | 손익비: {guide.get('risk_reward_ratio')}",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    if "key_news" in data and data["key_news"]:
        pdf.ln(3)
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, SECTION_TITLES["key_news"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 8)
        for news in data["key_news"][:8]:
            pdf.safe_cell(0, 4, f"- [{news.get('source', '')}] {news.get('title', '')}", new_x="LMARGIN", new_y="NEXT")

    return pdf.output()

