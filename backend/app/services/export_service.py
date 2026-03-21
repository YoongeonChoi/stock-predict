"""PDF and CSV export service."""

import csv
import io
import json
from fpdf import FPDF


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


def export_pdf(data: dict, title: str = "Stock Analysis Report") -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 10)

    if "market_summary" in data:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Market Summary", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        summary = data["market_summary"][:2000]
        for line in summary.split("\n"):
            pdf.multi_cell(0, 5, line)
        pdf.ln(3)

    if "score" in data:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Scores", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        score = data["score"]
        if "total" in score:
            pdf.cell(0, 6, f"Total Score: {score['total']} / 100", new_x="LMARGIN", new_y="NEXT")
        for key, val in score.items():
            if isinstance(val, dict) and "score" in val:
                pdf.cell(0, 5, f"  {val.get('name', key)}: {val['score']} / {val.get('max_score', '')}",
                         new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    if "top_stocks" in data:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Top Stocks", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for s in data["top_stocks"][:10]:
            line = f"#{s.get('rank', '')} {s.get('ticker', '')} - {s.get('name', '')} | Score: {s.get('score', '')} | ${s.get('current_price', '')}"
            pdf.cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    if "buy_sell_guide" in data:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Buy/Sell Guide", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        bsg = data["buy_sell_guide"]
        pdf.cell(0, 5, f"Buy Zone: {bsg.get('buy_zone_low')} - {bsg.get('buy_zone_high')}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, f"Fair Value: {bsg.get('fair_value')}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, f"Sell Zone: {bsg.get('sell_zone_low')} - {bsg.get('sell_zone_high')}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, f"Confidence: {bsg.get('confidence_grade')} | R:R = {bsg.get('risk_reward_ratio')}",
                 new_x="LMARGIN", new_y="NEXT")

    return pdf.output()
