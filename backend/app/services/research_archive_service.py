"""Curated external research archive sourced from official institutions."""

from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from time import struct_time
from typing import Any
from urllib.parse import urljoin

import feedparser
import httpx

from app.database import db

log = logging.getLogger("stock_predict.research_archive")

SYNC_STATUS_CACHE_KEY = "research_archive:sync_status"
SUPPORTED_REGIONS = {"US", "KR", "JP", "GLOBAL"}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

HTML_TAG_RE = re.compile(r"<[^>]+>")
PDF_HREF_RE = re.compile(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', re.I)
KDI_DOWNLOAD_RE = re.compile(r'["\'](/file/download\?[^"\']+)["\']', re.I)
KDI_ITEM_RE = re.compile(
    r'<div class="item">\s*<a href="([^"]+)"[^>]*>.*?<b[^>]*>(.*?)</b>.*?<strong>(.*?)</strong>.*?<p>(.*?)</p>.*?<span>(\d{4}\.\d{2}\.\d{2})</span>',
    re.I | re.S,
)


@dataclass(frozen=True)
class ResearchSource:
    id: str
    name: str
    region_code: str
    organization_type: str
    language: str
    category: str
    home_url: str
    feed_url: str | None = None
    page_url: str | None = None
    entry_limit: int = 6
    title_keywords: tuple[str, ...] = ()
    verify_ssl: bool = True


SOURCES: tuple[ResearchSource, ...] = (
    ResearchSource(
        id="fed_feds",
        name="Federal Reserve FEDS",
        region_code="US",
        organization_type="중앙은행 연구",
        language="en",
        category="미국 경제·금융 연구",
        home_url="https://www.federalreserve.gov/econres/feds/",
        feed_url="https://www.federalreserve.gov/feeds/feds.xml",
    ),
    ResearchSource(
        id="kdi_publications",
        name="KDI 한국개발연구원",
        region_code="KR",
        organization_type="국책연구원",
        language="ko",
        category="한국 경제 전망·정책 연구",
        home_url="https://www.kdi.re.kr/research/reportList",
        page_url="https://www.kdi.re.kr/research/reportList",
        entry_limit=8,
        verify_ssl=False,
    ),
    ResearchSource(
        id="bok_monetary_policy",
        name="한국은행 통화정책",
        region_code="KR",
        organization_type="중앙은행",
        language="ko",
        category="통화정책·금융통화위원회",
        home_url="https://www.bok.or.kr/portal/bbs/P0000559/list.do?menuNo=200690",
        feed_url="https://www.bok.or.kr/portal/bbs/P0000559/news.rss?menuNo=200690",
    ),
    ResearchSource(
        id="bok_research_ko",
        name="한국은행 경제연구(국문)",
        region_code="KR",
        organization_type="중앙은행 연구",
        language="ko",
        category="경제연구",
        home_url="https://www.bok.or.kr/imer/bbs/P0002455/list.do?menuNo=500788",
        feed_url="https://www.bok.or.kr/imer/bbs/P0002455/news.rss?menuNo=500788",
    ),
    ResearchSource(
        id="boj_whats_new",
        name="Bank of Japan",
        region_code="JP",
        organization_type="중앙은행",
        language="en",
        category="일본 통화정책·연구",
        home_url="https://www.boj.or.jp/en/",
        feed_url="https://www.boj.or.jp/en/rss/whatsnew.xml",
        title_keywords=(
            "statement on monetary policy",
            "research",
            "report",
            "review",
            "outlook",
            "policy",
            "prices",
            "exports",
            "imports",
            "inflation",
            "financial system",
            "bond market survey",
        ),
    ),
    ResearchSource(
        id="bis_research_hub",
        name="BIS Research Hub",
        region_code="GLOBAL",
        organization_type="국제기구·중앙은행 네트워크",
        language="en",
        category="글로벌 중앙은행 연구",
        home_url="https://www.bis.org/doclist/reshub_papers.rss",
        feed_url="https://www.bis.org/doclist/reshub_papers.rss",
        entry_limit=10,
    ),
)


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    cleaned = HTML_TAG_RE.sub(" ", value)
    return " ".join(html.unescape(cleaned).split())


def _to_absolute(url: str | None, base_url: str) -> str:
    if not url:
        return base_url
    absolute = urljoin(base_url, url)
    if absolute.startswith("http://"):
        absolute = "https://" + absolute[len("http://"):]
    return absolute


def _normalize_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, struct_time):
        return datetime(*value[:6], tzinfo=timezone.utc).date().isoformat()
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return datetime.now(timezone.utc).date().isoformat()
        normalized = normalized.replace(".", "-").replace("/", "-")
        for fmt in (
            "%Y-%m-%d",
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%B %d, %Y",
            "%b %d, %Y",
        ):
            try:
                return datetime.strptime(normalized, fmt).date().isoformat()
            except ValueError:
                continue
        if re.match(r"^\d{4}-\d{2}-\d{2}$", normalized):
            return normalized
    return datetime.now(timezone.utc).date().isoformat()


async def _fetch_text(url: str, *, verify_ssl: bool = True) -> str:
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        verify=verify_ssl,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def _discover_pdf_url(page_url: str, *, verify_ssl: bool = True) -> str | None:
    if page_url.lower().endswith(".pdf"):
        return page_url
    try:
        text = await _fetch_text(page_url, verify_ssl=verify_ssl)
    except Exception:
        return None

    match = KDI_DOWNLOAD_RE.search(text)
    if match:
        return _to_absolute(match.group(1), page_url)

    match = PDF_HREF_RE.search(text)
    if match:
        return _to_absolute(match.group(1), page_url)

    return None


def _build_report(
    source: ResearchSource,
    *,
    title: str,
    summary: str,
    published_at: str,
    report_url: str,
    pdf_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source.id,
        "source_name": source.name,
        "region_code": source.region_code,
        "organization_type": source.organization_type,
        "language": source.language,
        "category": source.category,
        "title": title.strip(),
        "summary": summary.strip(),
        "published_at": published_at,
        "report_url": report_url,
        "pdf_url": pdf_url,
        "metadata": {
            "source_home_url": source.home_url,
            **(metadata or {}),
        },
    }


async def _fetch_feed_source(source: ResearchSource) -> list[dict[str, Any]]:
    if not source.feed_url:
        return []

    feed = await asyncio.to_thread(feedparser.parse, source.feed_url)
    reports: list[dict[str, Any]] = []

    for entry in feed.entries:
        title = _strip_html(entry.get("title", ""))
        if not title:
            continue
        lowered = title.lower()
        if source.title_keywords and not any(keyword in lowered for keyword in source.title_keywords):
            continue

        report_url = _to_absolute(entry.get("link"), source.home_url)
        summary = _strip_html(entry.get("summary") or entry.get("description") or "")
        published_at = _normalize_date(
            entry.get("published_parsed")
            or entry.get("updated_parsed")
            or entry.get("published")
            or entry.get("updated")
            or entry.get("cb_publicationdate")
        )

        pdf_url = None
        for link in entry.get("links", []):
            href = _to_absolute(link.get("href"), source.home_url)
            if href.lower().endswith(".pdf"):
                pdf_url = href
                break

        if not pdf_url and source.id in {"fed_feds", "bok_monetary_policy", "bok_research_ko"}:
            pdf_url = await _discover_pdf_url(report_url, verify_ssl=source.verify_ssl)

        reports.append(
            _build_report(
                source,
                title=title,
                summary=summary,
                published_at=published_at,
                report_url=report_url,
                pdf_url=pdf_url,
                metadata={
                    "source_feed": source.feed_url,
                    "tags": [tag.get("term") for tag in entry.get("tags", []) if tag.get("term")],
                },
            )
        )

        if len(reports) >= source.entry_limit:
            break

    return reports


async def _fetch_kdi_source(source: ResearchSource) -> list[dict[str, Any]]:
    if not source.page_url:
        return []

    text = await _fetch_text(source.page_url, verify_ssl=source.verify_ssl)
    reports: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    allowed_labels = (
        "KDI 정책연구",
        "KDI 경제전망",
        "KDI FOCUS",
        "KDI 경제동향",
        "Economic Bulletin",
        "정책연구시리즈",
        "연구보고서",
    )

    for href, label, title, summary, published_raw in KDI_ITEM_RE.findall(text):
        clean_label = _strip_html(label)
        if not any(allowed in clean_label for allowed in allowed_labels):
            continue

        report_url = _to_absolute(href, source.home_url)
        if report_url in seen_urls:
            continue
        seen_urls.add(report_url)

        pdf_url = await _discover_pdf_url(report_url, verify_ssl=source.verify_ssl)
        reports.append(
            _build_report(
                source,
                title=_strip_html(title),
                summary=_strip_html(summary),
                published_at=_normalize_date(published_raw),
                report_url=report_url,
                pdf_url=pdf_url,
                metadata={"label": clean_label},
            )
        )
        if len(reports) >= source.entry_limit:
            break

    return reports


async def _fetch_source_reports(source: ResearchSource) -> list[dict[str, Any]]:
    if source.feed_url:
        return await _fetch_feed_source(source)
    return await _fetch_kdi_source(source)


async def sync_public_research_reports(force: bool = False) -> dict[str, Any]:
    today_iso = datetime.now(timezone.utc).date().isoformat()
    cached = await db.cache_get(SYNC_STATUS_CACHE_KEY)
    if not force and cached and cached.get("refreshed_on") == today_iso:
        return cached

    source_results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    processed_total = 0

    for source in SOURCES:
        try:
            reports = await _fetch_source_reports(source)
            for report in reports:
                await db.research_report_upsert(report)
            processed_total += len(reports)
            source_results.append({
                "source_id": source.id,
                "source_name": source.name,
                "region_code": source.region_code,
                "count": len(reports),
            })
        except Exception as exc:
            log.warning("Research archive sync failed for %s: %s", source.id, exc, exc_info=True)
            errors.append({
                "source_id": source.id,
                "source_name": source.name,
                "detail": str(exc)[:240],
            })

    snapshot = await db.research_report_status(today_iso)
    status = {
        "refreshed_on": today_iso,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "processed_total": processed_total,
        "error_count": len(errors),
        "source_results": source_results,
        "errors": errors,
        **snapshot,
    }
    await db.cache_set(SYNC_STATUS_CACHE_KEY, status, ttl_seconds=60 * 60 * 24 * 14)
    return status


async def get_public_research_status(refresh_if_missing: bool = False) -> dict[str, Any]:
    cached = await db.cache_get(SYNC_STATUS_CACHE_KEY)
    if cached:
        return cached

    if refresh_if_missing:
        return await sync_public_research_reports(force=False)

    today_iso = datetime.now(timezone.utc).date().isoformat()
    snapshot = await db.research_report_status(today_iso)
    return {
        "refreshed_on": None,
        "refreshed_at": None,
        "processed_total": 0,
        "error_count": 0,
        "source_results": [],
        "errors": [],
        **snapshot,
    }


async def list_public_research_reports(
    *,
    region_code: str | None = None,
    source_id: str | None = None,
    limit: int = 40,
    auto_refresh: bool = True,
) -> list[dict[str, Any]]:
    if auto_refresh:
        await sync_public_research_reports(force=False)
    rows = await db.research_report_list(region_code=region_code, source_id=source_id, limit=limit)
    today_iso = datetime.now(timezone.utc).date().isoformat()
    for row in rows:
        row["is_new_today"] = str(row.get("published_at", "")).startswith(today_iso)
        row["has_pdf"] = bool(row.get("pdf_url"))
    return rows
