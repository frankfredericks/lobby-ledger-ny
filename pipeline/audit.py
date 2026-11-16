"""Measure whether the datasets can actually be joined.

    python -m pipeline.audit                 # live, samples the most recent rows
    python -m pipeline.audit --fixtures tests/fixtures

Writes data/review/audit_report.md. The numbers that matter most:
  * share of lobbying clients that also appear as campaign donors (entity join rate)
  * share of lobbying targets linked to a named official
  * share of bill references parsed into standard bill IDs
"""
from __future__ import annotations

import argparse
import os
import re
from collections import Counter

import yaml

from . import bills as B
from .normalize import candidate_from_committee, entity_key
from .officials import OfficialIndex
from .sources import Dataset

SAMPLE = 20000


def pct(a, b):
    return f"{(100 * a / b):.0f}%" if b else "n/a"


def take(ds: Dataset, where=None, n=SAMPLE):
    out = []
    for r in ds.rows(where):
        out.append(r)
        if len(out) >= n:
            break
    return out


def schema_section(ds: Dataset) -> list[str]:
    lines = [f"### {ds.conf.get('title', ds.key)} (`{ds.conf.get('id', 'manual')}`)"]
    if not ds.available:
        return lines + ["- Not reachable or not configured.\n"]
    for k, v in ds.fields.resolved.items():
        req = ds.conf["fields"][k].get("required")
        lines.append(f"- `{k}` → {'`' + v + '`' if v else '**not found**'}{' (required)' if req and not v else ''}")
    unused = [f for f, _ in ds.fields.available if f not in ds.fields.resolved.values()]
    if unused:
        lines.append(f"- Columns not used: {', '.join(unused[:40])}")
    return lines + [""]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures")
    args = ap.parse_args(argv)
    S = yaml.safe_load(open("config/sources.yml"))
    st = yaml.safe_load(open("config/settings.yml"))
    start = st["start_year"]
    fx = args.fixtures
    rep = ["# Data audit", "", f"Sample size per dataset: up to {SAMPLE:,} rows from {start} onward.", "",
           "## Schema", ""]

    cc = Dataset("city_contributions", S["city"]["contributions"], fx)
    cl = Dataset("city_lobbying", S["city"]["lobbying"], fx)
    cf = Dataset("city_fundraising", S["city"]["fundraising"], fx)
    cd = Dataset("city_doing_business", S["city"]["doing_business"], fx)
    sc = Dataset("state_contributions", S["state"]["contributions"], fx)
    sl = Dataset("state_lobbying", S["state"]["lobbying"], fx)
    se = Dataset("state_ie_expenditures", S["state"]["ie_expenditures"], fx)
    for d in (cc, cl, cf, cd, sc, sl, se):
        rep += schema_section(d)

    rep += ["## City", ""]
    ind = set(S["city"]["contributions"]["individual_codes"])
    rows = take(cc, f"{cc.f('date')} >= '{start}-01-01T00:00:00'" if cc.f("date") else None) if cc.available else []
    types = Counter((r.get("donor_type") or "").upper() for r in rows)
    org = [r for r in rows if (r.get("donor_type") or "").upper() not in ind]
    rep.append(f"- Contribution donor types in sample: {dict(types.most_common(12))}")
    rep.append(f"- Non-individual share of contributions: {pct(len(org), len(rows))}")
    pair = Counter()
    for r in org:
        try:
            pair[(entity_key(r.get('donor_name', '')), r.get('recip_id'))] += float(r.get("amount") or 0)
        except ValueError:
            pass
    rep.append(f"- Organization→candidate pairs at or above ${st['donor_threshold']:,} in sample: "
               f"{pct(sum(1 for v in pair.values() if v >= st['donor_threshold']), len(pair))} of {len(pair):,}")
    from .normalize import parent_key
    donors = {entity_key(r.get("donor_name", "")) for r in org}
    donors |= {parent_key(k) for k in donors if parent_key(k)}
    offs = OfficialIndex()
    for r in rows:
        offs.add(r.get("recip_name", ""))

    lrows = take(cl, f"{cl.f('year')} >= {start}" if cl.f("year") else None) if cl.available else []
    clients = {entity_key(r.get("client_name", "")) for r in lrows}
    rep.append(f"- Lobbying clients that also appear as organization donors: "
               f"{pct(len(clients & donors), len(clients))} ({len(clients & donors)} of {len(clients)})")
    with_bill = sum(1 for r in lrows if B.parse_city(r.get("activities", ""), int(r.get("year") or start),
                                                     S["city"]["council_sessions"]))
    mentions = sum(1 for r in lrows if re.search(r"(?i)\b(intro|int\.?|res|resolution)\s*(no\.?)?\s*\d", r.get("activities", "")))
    rep.append(f"- Lobbying rows mentioning legislation: {mentions}; rows with a parsed bill ID: {with_bill} "
               f"({pct(with_bill, mentions)} of mentions)")
    tgt = matched = 0
    for r in lrows:
        for t in (r.get("targets") or "").split(";"):
            if "COUNCIL" in t.upper():
                tgt += 1
                matched += bool(offs.match_text(t)[0])
    rep.append(f"- Council-member targets linked to a named official: {pct(matched, tgt)} ({matched} of {tgt})")
    if cd.available:
        dbk = set()
        for r in take(cd, n=200000):
            for k in ("entity", "name"):
                if r.get(k):
                    dbk.add(entity_key(r[k]))
        rep.append(f"- Organization donors found on the Doing Business list: {pct(len(donors & dbk), len(donors))}")

    rep += ["", "## State", ""]
    srows = take(sl, f"{sl.f('year')} >= {start}" if sl.f("year") else None) if sl.available else []
    bill_rows = [r for r in srows if "BILL" in (r.get("focus_type") or "").upper()]
    parsed = sum(1 for r in bill_rows if B.parse_state(r.get("focus", ""), int(r.get("year") or start)))
    posd = Counter(B.detect_position(r.get("focus", "")) for r in bill_rows)
    rep.append(f"- Bill-type lobbying rows parsed into bill IDs: {pct(parsed, len(bill_rows))} ({parsed} of {len(bill_rows)})")
    rep.append(f"- Self-described position on bill rows: {dict(posd)}")
    soffs = OfficialIndex()
    titled = 0
    for r in srows:
        p = r.get("party") or ""
        if re.search(r"(?i)senator|assembly ?member|governor", p):
            titled += 1
            soffs.add(re.sub(r"(?i)senator|assembly ?member|staff member|governor", " ", p))
    rep.append(f"- Party-lobbied rows naming a legislator or governor: {pct(titled, len(srows))}")
    gb = Counter(r.get("gov_body", "") for r in srows)
    rep.append(f"- Top government bodies lobbied: {dict(gb.most_common(8))}")
    sclients = {entity_key(r.get("client_name", "")) for r in srows}
    crow = take(sc, f"{sc.f('year')} >= {start}" if sc.f("year") else None) if sc.available else []
    stypes = Counter(r.get("donor_type", "") for r in crow)
    rep.append(f"- Contribution donor types in sample: {dict(stypes.most_common(10))}")
    from .normalize import parent_key
    sdon = {entity_key(r.get("donor_name", "")) for r in crow}
    sdon |= {parent_key(k) for k in sdon if parent_key(k)}
    rep.append(f"- Lobbying clients that also appear as donors: {pct(len(sclients & sdon), len(sclients))}")
    linked = sum(1 for r in crow if soffs.match_text(r.get("cand_name") or candidate_from_committee(r.get("filer_name", "")))[0])
    rep.append(f"- Contribution rows whose committee links to a lobbied official: {pct(linked, len(crow))}")
    rep.append(f"- Office column present: {'yes' if sc.f('office') else 'no — officials matched by committee name only'}")
    rep.append(f"- IE spending target column present: {'yes' if se.f('target') else 'no — super PAC → official links unavailable'}")

    os.makedirs("data/review", exist_ok=True)
    with open("data/review/audit_report.md", "w") as f:
        f.write("\n".join(rep) + "\n")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
