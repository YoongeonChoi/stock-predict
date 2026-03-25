"""OpenDART helpers for recent Korean company filings."""

from __future__ import annotations

import asyncio
import io
import zipfile
from datetime import datetime, timedelta
from xml.etree import ElementTree

import httpx

from app.config import get_settings
from app.errors import SP_2001

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
LIST_URL = "https://opendart.fss.or.kr/api/list.json"

_CORP_CODE_INDEX: dict[str, dict] | None = None
_CORP_CODE_LOCK = asyncio.Lock()


async def get_recent_filings(ticker: str, limit: int = 8, lookback_days: int = 90) -> list[dict]:
    settings = get_settings()
    if not settings.opendart_api_key:
        return []

    corp = await resolve_corp_code(ticker)
    if not corp:
        return []

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=max(lookback_days, 30))
    params = {
        "crtfc_key": settings.opendart_api_key,
        "corp_code": corp["corp_code"],
        "bgn_de": start_date.strftime("%Y%m%d"),
        "end_de": end_date.strftime("%Y%m%d"),
        "last_reprt_at": "Y",
        "sort": "date",
        "sort_mth": "desc",
        "page_no": 1,
        "page_count": max(1, min(limit, 100)),
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(LIST_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        SP_2001("OpenDART", str(exc)[:150]).log("warning")
        return []

    filings: list[dict] = []
    for item in payload.get("list", [])[:limit]:
        receipt_no = str(item.get("rcept_no") or "")
        filings.append(
            {
                "corp_name": item.get("corp_name") or corp.get("corp_name") or ticker,
                "report_name": item.get("report_nm") or "",
                "receipt_date": _normalize_receipt_date(item.get("rcept_dt")),
                "receipt_no": receipt_no,
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}" if receipt_no else "",
                "market": item.get("corp_cls") or "",
                "remark": item.get("rm") or "",
            }
        )
    return filings


async def resolve_corp_code(ticker: str) -> dict | None:
    index = await _load_corp_code_index()
    return index.get(_normalize_stock_code(ticker))


async def _load_corp_code_index() -> dict[str, dict]:
    global _CORP_CODE_INDEX
    if _CORP_CODE_INDEX is not None:
        return _CORP_CODE_INDEX

    settings = get_settings()
    if not settings.opendart_api_key:
        return {}

    async with _CORP_CODE_LOCK:
        if _CORP_CODE_INDEX is not None:
            return _CORP_CODE_INDEX

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    CORP_CODE_URL,
                    params={"crtfc_key": settings.opendart_api_key},
                )
                response.raise_for_status()
                binary = response.content
        except Exception as exc:
            SP_2001("OpenDART", str(exc)[:150]).log("warning")
            _CORP_CODE_INDEX = {}
            return _CORP_CODE_INDEX

        index: dict[str, dict] = {}
        try:
            with zipfile.ZipFile(io.BytesIO(binary)) as zipped:
                xml_name = zipped.namelist()[0]
                xml_bytes = zipped.read(xml_name)
            root = ElementTree.fromstring(xml_bytes)
            for item in root.findall("list"):
                stock_code = (item.findtext("stock_code") or "").strip()
                corp_code = (item.findtext("corp_code") or "").strip()
                if not stock_code or not corp_code:
                    continue
                index[stock_code] = {
                    "corp_code": corp_code,
                    "corp_name": (item.findtext("corp_name") or "").strip(),
                    "modify_date": (item.findtext("modify_date") or "").strip(),
                }
        except Exception as exc:
            SP_2001("OpenDART", str(exc)[:150]).log("warning")
            index = {}

        _CORP_CODE_INDEX = index
        return _CORP_CODE_INDEX


def _normalize_stock_code(ticker: str) -> str:
    normalized = str(ticker or "").upper()
    if "." in normalized:
        normalized = normalized.split(".", 1)[0]
    return normalized.zfill(6) if normalized.isdigit() else normalized


def _normalize_receipt_date(value: str | None) -> str:
    raw = str(value or "")
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw
