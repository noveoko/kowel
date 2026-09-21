"""Polona search-service client (current API; not pypolona /api/entities/)."""

from __future__ import annotations

import io
import re
import zipfile
from typing import Any, Iterator

import requests

SEARCH_BASE = "https://polona.pl/api/search-service"
PREVIEW_URL = "https://polona.pl/preview/{object_id}"
GAZETA_SLEDCA_IDENTIFICATION_ID = "db8425b7-2fdc-428d-94d9-35eef49a985a"
GAZETA_SLEDCA_TITLE = "Gazeta Śledcza"
PAGE_SIZE = 24
TIMEOUT = 60
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "kowel-archives/0.1 (Gazeta Sledcza harvest)",
}


class PolonaError(RuntimeError):
    pass


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _raise_for_status(resp: requests.Response) -> None:
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise PolonaError(f"{resp.status_code} {resp.request.method} {resp.url}") from e


def field_values(hit: dict[str, Any], *groups_and_name: str) -> list[str]:
    """Read ResultField.values from basic/expanded/hidden fields."""
    *groups, name = groups_and_name
    if not groups:
        groups = ("basicFields", "expandedFields", "hiddenFields")
    for group in groups:
        block = (hit.get(group) or {}).get(name) or {}
        values = block.get("values") or []
        if values:
            return [str(v) for v in values]
    return []


def first_value(hit: dict[str, Any], name: str) -> str:
    vals = field_values(hit, name)
    return vals[0] if vals else ""


def preview_url(object_id: str) -> str:
    return PREVIEW_URL.format(object_id=object_id)


def identification_page(
    session: requests.Session,
    identification_id: str,
    page: int,
    page_size: int = PAGE_SIZE,
    sort: str = "OLDEST",
) -> dict[str, Any]:
    url = f"{SEARCH_BASE}/search/identification"
    params = {
        "identificationID": identification_id,
        "page": page,
        "pageSize": page_size,
        "sort": sort,
    }
    body = {"keywordFilters": {"copyright": ["false"]}}
    resp = session.post(url, params=params, json=body, timeout=TIMEOUT)
    _raise_for_status(resp)
    return resp.json()


def iter_identification(
    session: requests.Session,
    identification_id: str = GAZETA_SLEDCA_IDENTIFICATION_ID,
    page_size: int = PAGE_SIZE,
) -> Iterator[dict[str, Any]]:
    page = 0
    total = None
    seen = 0
    while True:
        data = identification_page(session, identification_id, page, page_size)
        if total is None:
            total = int(data.get("totalElements") or 0)
        hits = data.get("hits") or []
        if not hits:
            break
        for hit in hits:
            yield hit
            seen += 1
            if total and seen >= total:
                return
        page += 1
        if data.get("last"):
            break


def fulltext_page(
    session: requests.Session,
    query: str,
    page: int,
    page_size: int = PAGE_SIZE,
    title: str | None = GAZETA_SLEDCA_TITLE,
    sort: str = "OLDEST",
) -> dict[str, Any]:
    url = f"{SEARCH_BASE}/fulltext/polona/fulltext/{page}/{page_size}"
    params = {"sort": sort, "query": query}
    body: dict[str, Any] = {
        "filters": {"keywordFilters": {"copyright": ["false"]}},
        "searchOperator": "AND",
    }
    if title:
        body["fieldQueries"] = {
            "title": [{"query": title, "isExact": False}],
        }
    resp = session.post(url, params=params, json=body, timeout=TIMEOUT)
    _raise_for_status(resp)
    return resp.json()


def iter_fulltext(
    session: requests.Session,
    query: str,
    title: str | None = GAZETA_SLEDCA_TITLE,
    page_size: int = PAGE_SIZE,
) -> Iterator[dict[str, Any]]:
    page = 0
    total = None
    seen = 0
    while True:
        data = fulltext_page(session, query, page, page_size, title=title)
        if total is None:
            total = int(data.get("totalElements") or 0)
        hits = data.get("hits") or []
        if not hits:
            break
        for hit in hits:
            yield hit
            seen += 1
            if total and seen >= total:
                return
        page += 1
        if data.get("last"):
            break


def object_hit(session: requests.Session, object_id: str) -> dict[str, Any]:
    resp = session.get(f"{SEARCH_BASE}/search/{object_id}", timeout=TIMEOUT)
    _raise_for_status(resp)
    return resp.json()


def download_ocr_zip(session: requests.Session, object_id: str) -> bytes:
    url = f"{SEARCH_BASE}/fulltext/polona/fulltext/content/{object_id}"
    resp = session.get(url, timeout=TIMEOUT, headers={"Accept": "*/*"})
    _raise_for_status(resp)
    return resp.content


def ocr_text_from_zip(blob: bytes) -> str:
    """Prefer per-page files; the zip also contains a duplicate whole-issue .txt."""
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = [n for n in zf.namelist() if n and not n.endswith("/")]
        page_names = [
            n for n in names
            if re.search(r"(?:^|/)pages?/page\d+\.txt$", n.replace("\\", "/"), re.I)
        ]
        if page_names:
            def page_key(n: str) -> int:
                m = re.search(r"page(\d+)", n.replace("\\", "/"), re.I)
                return int(m.group(1)) if m else 0
            page_names.sort(key=page_key)
            chosen = page_names
        else:
            chosen = sorted(names)
        pages = [zf.read(n).decode("utf-8", errors="replace") for n in chosen]
    return "\n\n".join(pages)


def session() -> requests.Session:
    return _session()
