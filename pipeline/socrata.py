"""Minimal Socrata (SODA 2.1) client with schema-tolerant field resolution."""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

import requests

APP_TOKEN = os.environ.get("SOCRATA_APP_TOKEN", "")


# Network failures worth retrying: timeouts, refused or reset connections, and
# responses cut off mid-transfer (ChunkedEncodingError / ContentDecodingError).
TRANSIENT = (requests.Timeout, requests.ConnectionError,
             requests.exceptions.ChunkedEncodingError, requests.exceptions.ContentDecodingError)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


@dataclass
class FieldMap:
    """Logical field name -> actual API field name (or None)."""
    resolved: dict[str, str | None] = field(default_factory=dict)
    missing_required: list[str] = field(default_factory=list)
    available: list[tuple[str, str]] = field(default_factory=list)  # (fieldName, display name)
    types: dict[str, str] = field(default_factory=dict)              # fieldName -> Socrata data type

    def get(self, logical: str) -> str | None:
        return self.resolved.get(logical)

    def year_at_least(self, logical: str, year: int) -> str | None:
        """SoQL filter 'field >= year' written to match the column's data type."""
        f = self.get(logical)
        if not f:
            return None
        t = self.types.get(f, "").lower()
        if t in ("number", "double", "money"):
            return f"{f} >= {int(year)}"
        if "date" in t or "timestamp" in t:
            return f"{f} >= '{int(year)}-01-01T00:00:00'"
        return f"{f} >= '{int(year)}'"  # text years compare correctly as 4-digit strings


def resolve_fields(spec: dict, columns: list[dict]) -> FieldMap:
    """Match each logical field to a real column.

    Order: exact API field name, then normalized display name, then keyword
    contained in the display name.
    """
    by_field = {c["fieldName"].lower(): c["fieldName"] for c in columns}
    by_name = {_norm(c.get("name", "")): c["fieldName"] for c in columns}
    fm = FieldMap(available=[(c["fieldName"], c.get("name", "")) for c in columns],
                  types={c["fieldName"]: c.get("dataTypeName", "") for c in columns})
    taken: set[str] = set()
    for logical, conf in spec.items():
        hit = None
        for cand in conf.get("candidates", []):
            if cand.lower() in by_field and by_field[cand.lower()] not in taken:
                hit = by_field[cand.lower()]
                break
            if _norm(cand) in by_name and by_name[_norm(cand)] not in taken:
                hit = by_name[_norm(cand)]
                break
        if hit is None:
            for kw in conf.get("keywords", []):
                for name, fname in by_name.items():
                    if _norm(kw) in name and fname not in taken:
                        hit = fname
                        break
                if hit:
                    break
        fm.resolved[logical] = hit
        if hit:
            taken.add(hit)
        elif conf.get("required"):
            fm.missing_required.append(logical)
    return fm


class Socrata:
    def __init__(self, domain: str, dataset_id: str, session: requests.Session | None = None):
        self.domain = domain
        self.id = dataset_id
        self.s = session or requests.Session()
        if APP_TOKEN:
            self.s.headers["X-App-Token"] = APP_TOKEN

    @property
    def resource_url(self) -> str:
        return f"https://{self.domain}/resource/{self.id}.json"

    def _get(self, url: str, params: dict | None = None, tries: int = 6):
        """GET with retries. The open data portals are slow under load, so timeouts
        and dropped connections are retried with growing waits before giving up."""
        last = None
        for i in range(tries):
            try:
                r = self.s.get(url, params=params, timeout=300)
            except TRANSIENT as e:
                last = e
                print(f"  retrying after {type(e).__name__} (attempt {i + 1} of {tries})", flush=True)
                time.sleep(min(120, 10 * 2 ** i))
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                last = requests.HTTPError(f"HTTP {r.status_code} from {url}")
                time.sleep(min(120, 10 * 2 ** i))
                continue
            if r.status_code >= 400:
                raise requests.HTTPError(f"HTTP {r.status_code} from {r.url}: {r.text[:300]}")
            try:
                return r.json()
            except ValueError as e:  # truncated body that still arrived "successfully"
                last = e
                time.sleep(min(120, 10 * 2 ** i))
        raise last

    def columns(self) -> list[dict]:
        meta = self._get(f"https://{self.domain}/api/views/{self.id}.json")
        return [c for c in meta.get("columns", []) if not c["fieldName"].startswith(":")]

    def metadata(self) -> dict:
        return self._get(f"https://{self.domain}/api/views/{self.id}.json")

    def count(self, where: str | None = None) -> int:
        params = {"$select": "count(*) as n"}
        if where:
            params["$where"] = where
        rows = self._get(self.resource_url, params)
        return int(rows[0]["n"]) if rows else 0

    def rows(self, select: list[str], where: str | None = None, page_size: int = 50000,
             limit: int | None = None, ordered: bool = True):
        """Yield rows. Pages are fetched by row id ("give me rows after the last id
        I saw") rather than by offset, which stays fast deep into big datasets.
        ordered=False skips sorting, for quick samples."""
        label = f"{self.domain}/{self.id}"
        got, last, t0 = 0, None, time.time()
        while True:
            n = page_size if limit is None else min(page_size, limit - got)
            if n <= 0:
                return
            w = where
            if ordered and last is not None:
                w = f"({where}) AND :id > {soql_quote(last)}" if where else f":id > {soql_quote(last)}"
            params = {"$select": ",".join([":id"] + select), "$limit": n}
            if ordered:
                params["$order"] = ":id"
            if w:
                params["$where"] = w
            try:
                page = self._get(self.resource_url, params)
            except (*TRANSIENT, ValueError) as e:
                # Repeated failures on one batch: ask for smaller batches and carry on
                # from the same place, rather than abandoning the whole download.
                if page_size <= 1000:
                    raise
                page_size = max(1000, page_size // 2)
                print(f"  {label}: {type(e).__name__}; retrying with batches of {page_size:,}", flush=True)
                continue
            for r in page:
                last = r.get(":id", last)
                yield r
            got += len(page)
            if got and (got // page_size) % 10 == 0:
                print(f"  {label}: {got:,} rows in {time.time() - t0:,.0f}s", flush=True)
            if len(page) < n or not ordered:
                if got:
                    print(f"  {label}: done, {got:,} rows in {time.time() - t0:,.0f}s", flush=True)
                return

    def record_url(self, key_values: dict[str, str]) -> str:
        """Link to the exact source record(s) as JSON from the official API."""
        q = {k: v for k, v in key_values.items() if v not in (None, "")}
        return f"{self.resource_url}?{urlencode(q)}" if q else f"https://{self.domain}/d/{self.id}"


def soql_quote(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"
