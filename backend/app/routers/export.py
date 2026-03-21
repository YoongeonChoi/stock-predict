from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.services import archive_service, export_service

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/export/{fmt}/{report_id}")
async def export_report(fmt: str, report_id: int):
    if fmt not in ("pdf", "csv"):
        raise HTTPException(400, "Format must be 'pdf' or 'csv'")

    report = await archive_service.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")

    data = report.get("report_json", report)

    if fmt == "csv":
        content = export_service.export_csv(data)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=report_{report_id}.csv"},
        )

    pdf_bytes = export_service.export_pdf(data, title=f"Report #{report_id}")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report_{report_id}.pdf"},
    )
