"""Add plain-language titles and official links to bills.

State: NYS Senate Open Legislation API (free key: https://legislation.nysenate.gov/public).
       Set NYSENATE_API_KEY.
City:  NYC Council Legistar Web API (free token: https://council.nyc.gov/legislation/api).
       Set LEGISTAR_TOKEN.

Titles are cached in data/cache/bill_titles_<city|state>.json, which the monthly workflow
commits, so each run only looks up bills it hasn't seen before. Without a key,
bills keep their numbers and the build adds a coverage warning.
"""
from __future__ import annotations

import json
import os
import time

import requests

CACHE = "data/cache/bill_titles_{}.json"
NYS_KEY = os.environ.get("NYSENATE_API_KEY", "")
LEGISTAR_TOKEN = os.environ.get("LEGISTAR_TOKEN", "")
MAX_LOOKUPS = int(os.environ.get("BILL_TITLE_MAX_LOOKUPS", "4000"))  # per run, per jurisdiction


def _load(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=0, sort_keys=True)


def _state_lookup(s: requests.Session, label: str, session: str) -> dict | None:
    year = session.split("-")[0]
    r = s.get(f"https://legislation.nysenate.gov/api/3/bills/{year}/{label}",
              params={"key": NYS_KEY, "view": "info"}, timeout=30)
    if r.status_code == 404:
        return {"title": "", "url": ""}
    r.raise_for_status()
    res = (r.json() or {}).get("result") or {}
    return {"title": (res.get("title") or "").strip(),
            "url": f"https://www.nysenate.gov/legislation/bills/{year}/{label}"}


def _city_lookup(s: requests.Session, label: str, session: str) -> dict | None:
    kind, num = label.split()
    start, end = (session.split("-") + [session])[:2]
    file_prefix = f"{kind} {int(num):04d}-"
    flt = (f"substringof('{file_prefix}', MatterFile) eq true and "
           f"MatterIntroDate ge datetime'{start}-01-01' and MatterIntroDate lt datetime'{int(end) + 1}-01-01'")
    r = s.get("https://webapi.legistar.com/v1/nyc/matters",
              params={"token": LEGISTAR_TOKEN, "$filter": flt, "$top": 5}, timeout=30)
    r.raise_for_status()
    rows = [m for m in r.json() if str(m.get("MatterFile", "")).startswith(file_prefix)]
    if not rows:
        return {"title": "", "url": ""}
    m = rows[0]
    title = (m.get("MatterName") or m.get("MatterTitle") or "").strip()
    url = (f"https://legistar.council.nyc.gov/LegislationDetail.aspx?ID={m['MatterId']}&GUID={m['MatterGuid']}"
           if m.get("MatterId") and m.get("MatterGuid") else "")
    return {"title": title, "url": url}


def enrich(data: dict, jurisdiction: str, fixtures: str | None = None) -> None:
    bills = data["bills"]
    if fixtures:
        known = _load(os.path.join(fixtures, "bill_titles.json"))
        for bid, b in bills.items():
            b.update(known.get(bid, {}))
        return
    cache = _load(CACHE.format(jurisdiction))
    have_key = NYS_KEY if jurisdiction == "state" else LEGISTAR_TOKEN
    lookup = _state_lookup if jurisdiction == "state" else _city_lookup
    s = requests.Session()
    looked = 0
    for bid, b in bills.items():
        ck = f"{jurisdiction}:{bid}"
        if ck not in cache and have_key and looked < MAX_LOOKUPS:
            try:
                cache[ck] = lookup(s, b["label"], b["session"])
            except requests.RequestException:
                pass  # try again next month
            looked += 1
            time.sleep(0.15)  # stay well under the APIs' rate limits
        b.update(cache.get(ck) or {})
    _save(CACHE.format(jurisdiction), cache)
    missing = sum(1 for b in bills.values() if not b.get("title"))
    if not have_key:
        name = "NYSENATE_API_KEY" if jurisdiction == "state" else "LEGISTAR_TOKEN"
        data["meta"]["warnings"].append(f"Bill titles are off: add a free {name} (see README) to show bill names.")
    elif missing:
        data["meta"]["counts"]["bills_without_title"] = missing
