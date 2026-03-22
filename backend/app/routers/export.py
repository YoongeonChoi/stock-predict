from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse
from app.services import archive_service, export_service
from app.errors import SP_6005, SP_6006, SP_5004

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/export/{fmt}/{report_id}")
async def export_report(fmt: str, report_id: int):
    if fmt not in ("pdf", "csv"):
        err = SP_6006()
        err.log()
        return JSONResponse(status_code=400, content=err.to_dict())

    report = await archive_service.get_report(report_id)
    if not report:
        err = SP_6005(report_id)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    data = report.get("report_json", report)

    try:
        if fmt == "csv":
            content = export_service.export_csv(data)
            return Response(
                content=content,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=report_{report_id}.csv"},
            )

        pdf_bytes = export_service.export_pdf(data, title=f"리포트 #{report_id}")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report_{report_id}.pdf"},
        )
    except Exception as e:
        err = SP_5004(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())

