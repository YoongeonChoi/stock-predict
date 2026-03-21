"""PDF and CSV export service with Unicode (Korean/Japanese) support."""

import csv
import io
import os
import platform
from fpdf import FPDF


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
        writer.writerow(["Rank", "Ticker", "Name", "Score", "Price", "Change%"])
        for s in data["top_stocks"]:
            writer.writerow([
                s.get("rank"), s.get("ticker"), s.get("name"),
                s.get("score"), s.get("current_price"), s.get("change_pct"),
            ])
    elif "ticker" in data:
        writer.writerow(["Field", "Value"])
        for key in ["ticker", "name", "sector", "current_price", "pe_ratio",
                     "pb_ratio", "ev_ebitda", "market_cap"]:
            writer.writerow([key, data.get(key, "")])
        if "score" in data:
            writer.writerow([])
            writer.writerow(["Score Category", "Score", "Max"])
            score = data["score"]
            for cat in ["fundamental", "valuation", "growth_momentum", "analyst", "risk"]:
                s = score.get(cat, {})
                writer.writerow([cat, s.get("total", ""), s.get("max_score", "")])
    else:
        writer.writerow(["Key", "Value"])
        for k, v in data.items():
            if isinstance(v, (str, int, float)):
                writer.writerow([k, v])

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


def export_pdf(data: dict, title: str = "Stock Analysis Report") -> bytes:
    pdf = UnicodePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_unicode_font("B", 16)
    pdf.safe_cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    if "market_summary" in data:
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, "Market Summary", new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        summary = str(data["market_summary"])[:2000]
        for line in summary.split("\n"):
            pdf.safe_multi_cell(0, 5, line)
        pdf.ln(3)

    if "score" in data:
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, "Scores", new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        score = data["score"]
        if "total" in score:
            pdf.safe_cell(0, 6, f"Total Score: {score['total']} / 100", new_x="LMARGIN", new_y="NEXT")
        for key, val in score.items():
            if isinstance(val, dict) and "score" in val:
                pdf.safe_cell(0, 5, f"  {val.get('name', key)}: {val['score']} / {val.get('max_score', '')}",
                              new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    if "institutional_analysis" in data:
        ia = data["institutional_analysis"]
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, "Institutional Analysis", new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        if ia.get("consensus_summary"):
            pdf.safe_multi_cell(0, 5, str(ia["consensus_summary"]))
        for group_key in ("policy_institutions", "sell_side"):
            for inst in ia.get(group_key, []):
                name = inst.get("name", "")
                stance = inst.get("stance", "")
                pdf.safe_cell(0, 5, f"  {name} ({stance})", new_x="LMARGIN", new_y="NEXT")
                for pt in inst.get("key_points", [])[:3]:
                    pdf.safe_cell(0, 4, f"    - {pt}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    if "top_stocks" in data:
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, "Top Stocks", new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        for s in data["top_stocks"][:10]:
            line = f"#{s.get('rank', '')} {s.get('ticker', '')} - {s.get('name', '')} | Score: {s.get('score', '')} | {s.get('current_price', '')}"
            pdf.safe_cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")
            if s.get("reason"):
                pdf.set_unicode_font("", 8)
                pdf.safe_cell(0, 4, f"   {s['reason']}", new_x="LMARGIN", new_y="NEXT")
                pdf.set_unicode_font("", 9)
        pdf.ln(3)

    if "analysis_summary" in data and data["analysis_summary"]:
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, "AI Analysis", new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        for line in str(data["analysis_summary"])[:3000].split("\n"):
            pdf.safe_multi_cell(0, 5, line)
        pdf.ln(3)

    if "buy_sell_guide" in data:
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, "Buy/Sell Guide", new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 9)
        bsg = data["buy_sell_guide"]
        pdf.safe_cell(0, 5, f"Buy Zone: {bsg.get('buy_zone_low')} - {bsg.get('buy_zone_high')}",
                      new_x="LMARGIN", new_y="NEXT")
        pdf.safe_cell(0, 5, f"Fair Value: {bsg.get('fair_value')}", new_x="LMARGIN", new_y="NEXT")
        pdf.safe_cell(0, 5, f"Sell Zone: {bsg.get('sell_zone_low')} - {bsg.get('sell_zone_high')}",
                      new_x="LMARGIN", new_y="NEXT")
        pdf.safe_cell(0, 5, f"Confidence: {bsg.get('confidence_grade')} | R:R = {bsg.get('risk_reward_ratio')}",
                      new_x="LMARGIN", new_y="NEXT")

    if "key_news" in data and data["key_news"]:
        pdf.ln(3)
        pdf.set_unicode_font("B", 12)
        pdf.safe_cell(0, 8, "Key News", new_x="LMARGIN", new_y="NEXT")
        pdf.set_unicode_font("", 8)
        for n in data["key_news"][:8]:
            pdf.safe_cell(0, 4, f"- [{n.get('source', '')}] {n.get('title', '')}", new_x="LMARGIN", new_y="NEXT")

    return pdf.output()
