"""Resumable downloads that can span several workflow runs.

Each dataset query is saved to data/raw/<dataset>/ as it downloads:

  meta.json            what's on disk, and how far an unfinished download got
  <YYYY-MM>.jsonl.gz   rows from a finished download for that month
  partial.jsonl.gz     rows from a download still in progress

Rules:
  * One fresh download per calendar month. Once a month's download finishes,
    later runs that month reuse it without touching the API.
  * Rows are paged by offset in row-id order; a row count taken at the start
    stops the download if it ever fetches more rows than the source has.
  * If a run's time budget (PIPELINE_TIME_BUDGET_MIN) runs out mid-download, the
    rows so far are kept and the next run continues from that row.
  * Until the new month's download finishes, the build uses the previous
    finished download, so the site keeps working with last month's data.
  * If the query or the columns change, everything for that dataset is discarded.

The GitHub workflow keeps data/raw between runs with actions/cache.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import os
import shutil
import time

ROOT = os.environ.get("PIPELINE_RAW_DIR", "data/raw")
_budget = os.environ.get("PIPELINE_TIME_BUDGET_MIN")
DEADLINE = time.time() + float(_budget) * 60 if _budget else None


class NotReady(Exception):
    """A dataset's download is unfinished and there is no earlier copy to use."""


def this_month() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")


def out_of_time() -> bool:
    return DEADLINE is not None and time.time() >= DEADLINE


class RawCache:
    def __init__(self, key: str, where: str | None, fields: list[str], root: str = ROOT):
        self.dir = os.path.join(root, key)
        self.key = key
        # "v2": offset paging. Changing this discards downloads made the old way.
        self.sig = hashlib.sha1(json.dumps(["v2", where or "", sorted(fields)]).encode()).hexdigest()[:16]
        self.meta_path = os.path.join(self.dir, "meta.json")
        self.partial_path = os.path.join(self.dir, "partial.jsonl.gz")
        self.meta = self._load()

    def _load(self) -> dict:
        blank = {"sig": self.sig, "complete": None, "partial": None, "rows": 0, "bytes": 0, "expected": None}
        if not os.path.exists(self.meta_path):
            return blank
        with open(self.meta_path) as f:
            m = json.load(f)
        if m.get("sig") != self.sig:
            shutil.rmtree(self.dir, ignore_errors=True)  # query changed: start over
            return blank
        return m

    def _save(self):
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.meta_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.meta, f)
        os.replace(tmp, self.meta_path)

    def complete_path(self) -> str | None:
        g = self.meta.get("complete")
        p = os.path.join(self.dir, f"{g}.jsonl.gz") if g else None
        return p if p and os.path.exists(p) else None

    def sync(self, pages_from, count=None) -> bool:
        """Bring this month's download up to date. Returns True when finished.

        pages_from(offset) yields pages of rows starting at that row offset.
        count() returns how many rows the query matches; it guards against the
        dataset changing mid-download and against runaway paging.
        """
        month = this_month()
        if self.meta.get("complete") == month and self.complete_path():
            return True
        if out_of_time():
            return False
        expected = count() if count else None
        fresh = self.meta.get("partial") != month
        if not fresh and expected is not None and self.meta.get("expected") not in (None, expected):
            print(f"  {self.key}: source changed ({self.meta['expected']:,} -> {expected:,} rows); restarting",
                  flush=True)
            fresh = True
        if fresh:
            if os.path.exists(self.partial_path):
                os.remove(self.partial_path)
            self.meta.update(partial=month, rows=0, bytes=0, expected=expected)
            self._save()
        elif self.meta.get("rows"):
            print(f"  {self.key}: resuming after {self.meta['rows']:,} rows", flush=True)
        if expected is not None:
            print(f"  {self.key}: {expected:,} rows to download", flush=True)
        os.makedirs(self.dir, exist_ok=True)
        # Drop anything written after the last recorded page (e.g. a run killed mid-write).
        if os.path.exists(self.partial_path) and os.path.getsize(self.partial_path) > self.meta.get("bytes", 0):
            with open(self.partial_path, "r+b") as f:
                f.truncate(self.meta.get("bytes", 0))
        for page in pages_from(self.meta["rows"]):
            if page:
                # Each page is its own gzip member, so the file is valid after every page.
                blob = gzip.compress("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in page).encode())
                with open(self.partial_path, "ab") as f:
                    f.write(blob)
                self.meta["rows"] += len(page)
                self.meta["bytes"] = self.meta.get("bytes", 0) + len(blob)
                self._save()
                if expected is not None and self.meta["rows"] > expected * 1.02 + 1000:
                    raise RuntimeError(f"{self.key}: downloaded {self.meta['rows']:,} rows but the source has "
                                       f"{expected:,}; paging is repeating rows. Stopping.")
            if out_of_time():
                print(f"  {self.key}: time budget used; saved {self.meta['rows']:,} rows to resume next run",
                      flush=True)
                return False
        if not os.path.exists(self.partial_path):
            open(self.partial_path, "wb").close()  # an empty result is still a finished download
        # finished: promote partial to this month's complete copy
        old = self.complete_path()
        final = os.path.join(self.dir, f"{month}.jsonl.gz")
        os.replace(self.partial_path, final)
        if old and old != final and os.path.exists(old):
            os.remove(old)
        self.meta.update(complete=month, partial=None, complete_rows=self.meta["rows"], rows=0, bytes=0)
        self._save()
        return True

    def read(self):
        p = self.complete_path()
        if not p:
            raise NotReady(self.key)
        if os.path.getsize(p) == 0:
            return
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)
