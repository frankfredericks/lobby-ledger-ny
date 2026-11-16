"""Uniform access to live datasets or local fixtures (for tests and demos)."""
from __future__ import annotations

import csv
import json
import os
from urllib.parse import urlencode

from .socrata import FieldMap, Socrata, resolve_fields


class Dataset:
    """One configured dataset with resolved fields."""

    def __init__(self, key: str, conf: dict, fixtures_dir: str | None = None, page_size: int = 50000):
        self.key = key
        self.conf = conf
        self.fixtures_dir = fixtures_dir
        self.page_size = page_size
        self.api = (f"https://{conf['domain']}/resource/{conf['id']}.json" if conf.get("id") else "")
        self._fixture = None
        self.client = None
        if fixtures_dir:
            path = os.path.join(fixtures_dir, f"{key}.json")
            if os.path.exists(path):
                with open(path) as f:
                    self._fixture = json.load(f)
        elif conf.get("id"):
            self.client = Socrata(conf["domain"], conf["id"])
        self.fields: FieldMap = self._resolve()

    @property
    def available(self) -> bool:
        return self._fixture is not None or self.client is not None

    def _resolve(self) -> FieldMap:
        spec = self.conf.get("fields", {})
        if self._fixture is not None:
            return resolve_fields(spec, self._fixture["columns"])
        if self.client is not None:
            return resolve_fields(spec, self.client.columns())
        return FieldMap(missing_required=[k for k, v in spec.items() if v.get("required")])

    def f(self, logical: str) -> str | None:
        return self.fields.get(logical)

    def year_where(self, logical: str, year: int) -> str | None:
        return self.fields.year_at_least(logical, year)

    def rows(self, where: str | None = None, limit: int | None = None, ordered: bool = True):
        """Yield rows keyed by LOGICAL field names."""
        inv = {v: k for k, v in self.fields.resolved.items() if v}
        if self._fixture is not None:
            src = self._fixture["rows"][:limit] if limit else self._fixture["rows"]
        elif self.client is not None:
            src = self.client.rows(list(inv), where=where, page_size=min(self.page_size, limit or self.page_size),
                                   limit=limit, ordered=ordered)
        else:
            return
        for r in src:
            yield {inv[k]: v for k, v in r.items() if k in inv}

    def src(self, row: dict, keys: list[str] | None = None) -> str:
        """Compact query string identifying source records; expanded in the browser."""
        keys = keys or self.conf.get("record_key", [])
        q = {}
        for k in keys:
            api_field = self.f(k)
            if api_field and row.get(k) not in (None, ""):
                q[api_field] = row[k]
        return urlencode(q)


def load_manual_csv(path: str) -> list[dict] | None:
    if not path or not os.path.exists(path):
        return None
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]
