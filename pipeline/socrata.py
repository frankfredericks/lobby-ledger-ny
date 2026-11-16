"""Minimal Socrata (SODA 2.1) client with schema-tolerant field resolution."""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

import requests

APP_TOKEN = os.environ.get("SOCRATA_APP_TOKEN", "")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


@dataclass
class FieldMap:
    """Logical field name -> actual API field name (or None)."""
    resolved: dict[str, str | None] = field(default_factory=dict)
    missing_required: list[str] = field(default_factory=list)
    available: list[tuple[str, str]] = field(default_factory=list)  # (fieldName, display name)

    def get(self, logical: str) -> str | None:
        return self.resolved.get(logical)


def resolve_fields(spec: dict, columns: list[dict]) -> FieldMap:
    """Match each logical field to a real column.

    Order: exact API field name, then normalized display name, then keyword
    contained in the display name.
    """
    by_field = {c["fieldName"].lower(): c["fieldName"] for c in columns}
    by_name = {_norm(c.get("name", "")): c["fieldName"] for c in columns}
    fm = FieldMap(available=[(c["fieldName"], c.get("name", "")) for c in columns])
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

    def _get(self, url: str, params: dict | None = None, tries: int = 5):
        for i in range(tries):
            r = self.s.get(url, params=params, timeout=180)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** i * 3)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()

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
             limit: int | None = None):
        offset = 0
        while True:
            n = page_size if limit is None else min(page_size, limit - offset)
            if n <= 0:
                return
            params = {"$select": ",".join(select), "$limit": n, "$offset": offset, "$order": ":id"}
            if where:
                params["$where"] = where
            page = self._get(self.resource_url, params)
            yield from page
            if len(page) < n:
                return
            offset += n

    def record_url(self, key_values: dict[str, str]) -> str:
        """Link to the exact source record(s) as JSON from the official API."""
        q = {k: v for k, v in key_values.items() if v not in (None, "")}
        return f"{self.resource_url}?{urlencode(q)}" if q else f"https://{self.domain}/d/{self.id}"


def soql_quote(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"
