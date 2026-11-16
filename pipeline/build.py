"""Build site/data/city.json and site/data/state.json."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from collections import defaultdict

from . import bills as B
from .entities import EntityResolver
from .normalize import candidate_from_committee, entity_key, person_key
from .officials import OfficialIndex
from .socrata import soql_quote
from .sources import Dataset, load_manual_csv

CITY_OFFICES = {"1": "Mayor", "2": "Public Advocate", "3": "Comptroller", "4": "Borough President",
                "5": "City Council", "6": "Undeclared"}


def _year(v) -> int | None:
    if v in (None, ""):
        return None
    m = re.search(r"(19|20)\d{2}", str(v))
    return int(m.group(0)) if m else None


def _amt(v) -> float:
    try:
        return float(str(v).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return 0.0


class Out:
    """Accumulates records; ids are resolved at the end once entities are merged."""

    def __init__(self, jurisdiction: str, settings: dict):
        self.j = jurisdiction
        self.settings = settings
        self.ents = EntityResolver(settings["entity_match"]["auto_merge"], settings["entity_match"]["review"])
        self.offs = OfficialIndex()
        self.bills: dict[str, dict] = {}
        self.contribs = defaultdict(lambda: [0.0, 0, ""])   # (donor_key, off_key, year) -> [amt, n, src]
        self.ie_contribs = defaultdict(lambda: [0.0, 0, ""])
        self.ie_spend = defaultdict(lambda: [0.0, "", ""])   # (ie_key, off_key, year) -> [amt, stance, src]
        self.lobby: list[list] = []
        self.fundraising: list[list] = []
        self.db_keys: set[str] = set()
        self.sources: dict[str, dict] = {}
        self.warnings: list[str] = []
        self.counts = defaultdict(int)

    def add_bill(self, b: B.Bill):
        rec = self.bills.setdefault(b.id, {"label": b.label, "session": b.session, "versions": set(), "parts": set()})
        if b.version:
            rec["versions"].add(b.label + b.version)
        if b.part:
            rec["parts"].add(b.part)

    def register_source(self, code: str, ds: Dataset | None, title: str, page_url: str, api: str = ""):
        self.sources[code] = {"title": title, "page": page_url, "api": api or (ds.api if ds else "")}

    def finalize(self) -> dict:
        self.ents.resolve()
        from .normalize import slug
        E = lambda k: slug(self.ents.canonical(k, is_key=True)) if k else ""
        O = self.offs.id_for

        entities = self.ents.export()
        for k in self.db_keys:
            eid = E(k)
            if eid in entities:
                entities[eid]["db"] = 1

        def collapse(d, mapper):
            agg = defaultdict(lambda: [0.0, 0, ""])
            for (a, b, y), (amt, n, src) in d.items():
                key = (mapper[0](a), mapper[1](b), y)
                agg[key][0] += amt
                agg[key][1] += n
                agg[key][2] = agg[key][2] or src
            return [[a, b, y, round(v[0], 2), v[1], v[2]] for (a, b, y), v in agg.items() if a and b]

        contribs = collapse(self.contribs, (E, O))
        ie_contribs = collapse(self.ie_contribs, (E, E))
        ie_spend = []
        agg = defaultdict(lambda: [0.0, "", ""])
        for (a, b, y), (amt, st, src) in self.ie_spend.items():
            key = (E(a), O(b), y)
            agg[key][0] += amt
            agg[key][1] = agg[key][1] or st
            agg[key][2] = agg[key][2] or src
        ie_spend = [[a, b, y, round(v[0], 2), v[1], v[2]] for (a, b, y), v in agg.items() if a and b]

        lobby = []
        for rec in self.lobby:
            client, lob, year, period, bill_ids, off_keys, others, comp, positions, src = rec[:10]
            row = [E(client), E(lob), year, period, sorted(bill_ids),
                   sorted({O(k) for k in off_keys if k}), sorted(others)[:15],
                   round(comp, 2) if comp else 0, positions, src]
            if len(rec) > 10:
                # State filings pair each bill with the parties lobbied on it.
                row.append({b: sorted({O(k) for k in ks if k}) for b, ks in rec[10].items()})
            lobby.append(row)
        fundraising = [[E(l), O(o), y, round(a, 2), kind, src] for l, o, y, a, kind, src in self.fundraising if l and o]

        bills = {bid: {"label": b["label"], "session": b["session"], "versions": sorted(b["versions"]),
                       "parts": sorted(b["parts"])} for bid, b in self.bills.items()}

        # Keep only officials that appear in at least one record.
        used = {r[1] for r in contribs} | {r[1] for r in ie_spend} | {r[1] for r in fundraising}
        for r in lobby:
            used.update(r[5])
        officials = {k: v for k, v in self.offs.export().items() if k in used}

        used_e = {r[0] for r in contribs} | {r[0] for r in ie_contribs} | {r[1] for r in ie_contribs} \
            | {r[0] for r in ie_spend} | {r[0] for r in lobby} | {r[1] for r in lobby} | {r[0] for r in fundraising}
        entities = {k: v for k, v in entities.items() if k in used_e}

        years = sorted({r[2] for r in contribs + ie_contribs + ie_spend + lobby + fundraising if r[2]})
        os.makedirs("data/review", exist_ok=True)
        self.ents.write_review(f"data/review/{self.j}_entity_review.csv")
        return {
            "meta": {
                "jurisdiction": self.j,
                "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
                "start_year": self.settings["start_year"],
                "years": [years[0], years[-1]] if years else [],
                "threshold": self.settings["donor_threshold"],
                "refresh_label": self.settings["refresh_label"],
                "sources": self.sources,
                "warnings": self.warnings,
                "counts": dict(self.counts),
            },
            "officials": officials,
            "entities": entities,
            "bills": bills,
            "contribs": contribs,
            "ie_contribs": ie_contribs,
            "ie_spend": ie_spend,
            "lobby": lobby,
            "fundraising": fundraising,
        }


# --------------------------------------------------------------------------- city

def build_city(conf: dict, settings: dict, fixtures: str | None = None) -> dict:
    out = Out("city", settings)
    start = settings["start_year"]
    sessions = conf["council_sessions"]

    # Doing Business list (flags donors)
    db = Dataset("city_doing_business", conf["doing_business"], fixtures, settings["page_size"])
    out.register_source("db", db, conf["doing_business"]["title"], conf["doing_business"]["page_url"])
    if db.available:
        for r in db.rows():
            for k in ("entity", "name"):
                if r.get(k):
                    out.db_keys.add(entity_key(r[k]))
    else:
        out.warnings.append("Doing Business list unavailable; no donors flagged.")

    # Campaign contributions from organizations to candidates
    ds = Dataset("city_contributions", conf["contributions"], fixtures, settings["page_size"])
    out.register_source("cc", ds, conf["contributions"]["title"], conf["contributions"]["page_url"])
    ind = set(conf["contributions"]["individual_codes"])
    where = None
    if ds.f("donor_type") and ds.f("date"):
        codes = ",".join(soql_quote(c) for c in ind)
        where = f"{ds.f('date')} >= '{start}-01-01T00:00:00' AND NOT ({ds.f('donor_type')} IN ({codes}))"
    for r in ds.rows(where):
        y = _year(r.get("date")) or _year(r.get("election"))
        if not y or y < start or (r.get("donor_type") or "").upper() in ind:
            continue
        name = r.get("recip_name") or ""
        if r.get("cand_first") and "," not in name:
            name = f"{name}, {r['cand_first']}"
        office = CITY_OFFICES.get(str(r.get("office", "")).strip(), "")
        ok = out.offs.add(name, office)
        dk = out.ents.add(r.get("donor_name", ""), "donor")
        if not ok or not dk:
            continue
        cell = out.contribs[(dk, ok, y)]
        cell[0] += _amt(r.get("amount"))
        cell[1] += 1
        if not cell[2]:
            cell[2] = "cc|" + ds.src(r, ["recip_id", "donor_name"])
        out.counts["contribution_rows"] += 1

    # Independent expenditures (manual CFB exports)
    iec = load_manual_csv(conf["ie_contributions"]["manual_csv"]) if not fixtures else \
        load_manual_csv(os.path.join(fixtures, "city_ie_contributions.csv"))
    ies = load_manual_csv(conf["ie_expenditures"]["manual_csv"]) if not fixtures else \
        load_manual_csv(os.path.join(fixtures, "city_ie_expenditures.csv"))
    out.register_source("iec", None, conf["ie_contributions"]["title"], conf["ie_contributions"]["page_url"],
                        conf["ie_contributions"]["page_url"])
    if iec is None or ies is None:
        out.warnings.append("City independent-expenditure files not found in data/manual/; super PAC donors "
                            "are missing from the City tab. See README.")
    else:
        for r in iec:
            y = _year(r.get("date"))
            if not y or y < start:
                continue
            sk = out.ents.add(r.get("spender", ""), "ie_committee")
            dk = out.ents.add(r.get("contributor", ""), "ie_donor")
            if sk and dk:
                c = out.ie_contribs[(dk, sk, y)]
                c[0] += _amt(r.get("amount"))
                c[1] += 1
                c[2] = c[2] or "url|" + r.get("source_url", "")
        for r in ies:
            y = _year(r.get("date"))
            if not y or y < start:
                continue
            sk = out.ents.add(r.get("spender", ""), "ie_committee")
            ok = out.offs.add(r.get("candidate", ""))
            if sk and ok:
                c = out.ie_spend[(sk, ok, y)]
                c[0] += _amt(r.get("amount"))
                st = (r.get("support_oppose") or "").lower()
                c[1] = c[1] or ("oppose" if st.startswith("o") else "support" if st.startswith("s") else "")
                c[2] = c[2] or "url|" + r.get("source_url", "")

    # Lobbying
    lb = Dataset("city_lobbying", conf["lobbying"], fixtures, settings["page_size"])
    out.register_source("cl", lb, conf["lobbying"]["title"], conf["lobbying"]["page_url"])
    where = f"{lb.f('year')} >= {start}" if lb.f("year") else None
    for r in lb.rows(where):
        y = _year(r.get("year"))
        if not y or y < start or not (r.get("activities") or r.get("targets")):
            continue
        ck = out.ents.add(r.get("client_name", ""), "client")
        lk = out.ents.add(r.get("lobbyist_name", ""), "lobbyist")
        bl, positions = [], {}
        for seg in re.split(r";", r.get("activities") or ""):
            seg_bills = B.parse_city(seg, y, sessions)
            p = B.detect_position(seg)
            for b in seg_bills:
                if b.id not in {x.id for x in bl}:
                    bl.append(b)
                if p:
                    positions[b.id] = p
        for b in bl:
            out.add_bill(b)
        offs, others = set(), set()
        for t in re.split(r";", r.get("targets") or ""):
            t = t.strip()
            if not t:
                continue
            k, _ = out.offs.match_text(t)
            if k:
                offs.add(k)
            else:
                others.add(re.sub(r"\s+", " ", t)[:120])
        out.lobby.append([ck, lk, y, r.get("period", ""), {b.id for b in bl}, offs, others,
                          _amt(r.get("compensation")), positions,
                          "cl|" + lb.src(r)])
        out.counts["lobbying_rows"] += 1

    # Lobbyist fundraising / consulting for candidates
    fr = Dataset("city_fundraising", conf["fundraising"], fixtures, settings["page_size"])
    out.register_source("cf", fr, conf["fundraising"]["title"], conf["fundraising"]["page_url"])
    if fr.available and not fr.fields.missing_required:
        for r in fr.rows():
            y = _year(r.get("year"))
            if not y or y < start:
                continue
            lk = out.ents.add(r.get("lobbyist_name", ""), "lobbyist")
            ok = out.offs.add(r.get("candidate", ""))
            if lk and ok:
                out.fundraising.append([lk, ok, y, _amt(r.get("amount")), r.get("kind", ""), "cf|" + fr.src(r)])
    _missing(out, [ds, lb, fr, db])
    return out.finalize()


# --------------------------------------------------------------------------- state

STATE_TITLE = re.compile(r"(?i)\b(SENATOR|ASSEMBLY ?MEMBER|ASSEMBLYMAN|ASSEMBLYWOMAN|GOVERNOR|LIEUTENANT GOVERNOR|ATTORNEY GENERAL|COMPTROLLER)\b")
TITLE_OFFICE = {"SENATOR": "State Senate", "ASSEMBLY MEMBER": "State Assembly", "ASSEMBLYMEMBER": "State Assembly",
                "ASSEMBLYMAN": "State Assembly", "ASSEMBLYWOMAN": "State Assembly", "GOVERNOR": "Governor",
                "LIEUTENANT GOVERNOR": "Lieutenant Governor", "ATTORNEY GENERAL": "Attorney General",
                "COMPTROLLER": "Comptroller"}


def build_state(conf: dict, settings: dict, fixtures: str | None = None) -> dict:
    out = Out("state", settings)
    start = settings["start_year"]

    # 1) Lobbying first: party names give a clean list of legislators.
    lb = Dataset("state_lobbying", conf["lobbying"], fixtures, settings["page_size"])
    out.register_source("sl", lb, conf["lobbying"]["title"], conf["lobbying"]["page_url"])
    where = f"{lb.f('year')} >= {start}" if lb.f("year") else None
    forms: dict[str, dict] = {}
    for r in lb.rows(where):
        y = _year(r.get("year"))
        if not y or y < start:
            continue
        if (r.get("level") or "").strip().lower() == "municipal":
            continue  # municipal-only lobbying belongs to local tabs
        fid = str(r.get("form_id") or "")
        f = forms.setdefault(fid, {"row": r, "y": y, "bills": {}, "pos": {}, "parties": set(), "comp": 0.0,
                                   "pairs": defaultdict(set)})
        f["comp"] = max(f["comp"], _amt(r.get("compensation")))
        ft = (r.get("focus_type") or "").upper()
        row_bills = []
        if not ft or "BILL" in ft:
            row_bills = B.parse_state(r.get("focus", ""), y)
            for b in row_bills:
                f["bills"][b.id] = b
                p = B.detect_position(r.get("focus", ""))
                if p:
                    f["pos"][b.id] = p
        party = " ".join(x for x in [r.get("party", ""), r.get("person", "")] if x).strip()
        if party and (r.get("monitoring_only") or "").lower() not in ("yes", "y", "true"):
            f["parties"].add((party, r.get("gov_body", "")))
            m = STATE_TITLE.search(party)
            if m:
                office = TITLE_OFFICE.get(re.sub(r"\s+", " ", m.group(1).upper()), "")
                name = STATE_TITLE.sub(" ", re.sub(r"(?i)\bSTAFF MEMBER\b", " ", party))
                out.offs.add(name, office)
            for b in row_bills:
                f["pairs"][b.id].add(party)

    # Amendments supersede originals for the same lobbyist/client/period.
    latest: dict[tuple, dict] = {}
    for fid, f in forms.items():
        r = f["row"]
        key = (entity_key(r.get("lobbyist_name", "")), entity_key(r.get("client_name", "")), f["y"], r.get("period", ""))
        prev = latest.get(key)
        is_amend = (r.get("filing_type") or "").lower().startswith("amend")
        if prev is None or (is_amend and not prev["amend"]) or (is_amend == prev["amend"] and str(fid) > str(prev["fid"])):
            latest[key] = {"f": f, "amend": is_amend, "fid": fid}
    for v in latest.values():
        f = v["f"]
        r = f["row"]
        ck = out.ents.add(r.get("client_name") or r.get("contract_client", ""), "client")
        lk = out.ents.add(r.get("lobbyist_name", ""), "lobbyist")
        for b in f["bills"].values():
            out.add_bill(b)
        offs, others = set(), set()
        for party, body in f["parties"]:
            k, _ = out.offs.match_text(party)
            if k:
                offs.add(k)
            else:
                others.add((f"{body}: {party}" if body else party)[:120])
        pairs = {bid: {out.offs.match_text(p)[0] for p in parties} for bid, parties in f["pairs"].items()}
        out.lobby.append([ck, lk, f["y"], r.get("period", ""), set(f["bills"]), offs, others, f["comp"],
                          f["pos"], "sl|" + lb.src(r), pairs])
        out.counts["lobbying_filings"] += 1

    # 2) Contributions from organizations to candidates, and anyone to IE committees.
    ds = Dataset("state_contributions", conf["contributions"], fixtures, settings["page_size"])
    cc = conf["contributions"]
    out.register_source("sc", ds, cc["title"], cc["page_url"])
    ind = {t.lower() for t in cc["individual_types"]}
    ie_markers = [m.lower() for m in cc["ie_committee_markers"]]
    offices = [o.lower() for o in cc["offices"]]
    where = None
    if ds.f("year"):
        where = f"{ds.f('year')} >= {start}"
    ie_filers: dict[str, str] = {}
    for r in ds.rows(where):
        y = _year(r.get("date")) or _year(r.get("year"))
        if not y or y < start:
            continue
        ctype = (r.get("committee_type") or "").lower()
        fname = r.get("filer_name", "")
        is_ie = any(m in ctype for m in ie_markers) or "INDEPENDENT EXPENDITURE" in fname.upper()
        dtype = (r.get("donor_type") or "").strip().lower()
        donor = r.get("donor_name") or " ".join(x for x in [r.get("donor_first", ""), r.get("donor_last", "")] if x)
        if is_ie:
            sk = out.ents.add(fname, "ie_committee")
            dk = out.ents.add(donor, "ie_donor")
            ie_filers[str(r.get("filer_id"))] = sk
            if sk and dk:
                c = out.ie_contribs[(dk, sk, y)]
                c[0] += _amt(r.get("amount"))
                c[1] += 1
                c[2] = c[2] or "sc|" + ds.src(r, ["filer_id", "donor_name"])
            continue
        if dtype in ind or not donor:
            continue
        office = (r.get("office") or "").lower()
        if ds.f("office") and office and not any(o in office for o in offices):
            continue
        cand = r.get("cand_name") or candidate_from_committee(fname)
        ok, _ = out.offs.match_text(cand)
        if not ok:
            if not ds.f("office") or not office:
                continue  # can't tell this is a state official's committee
            ok = out.offs.add(cand, r.get("office", ""))
        dk = out.ents.add(donor, "donor")
        if ok and dk:
            c = out.contribs[(dk, ok, y)]
            c[0] += _amt(r.get("amount"))
            c[1] += 1
            c[2] = c[2] or "sc|" + ds.src(r, ["filer_id", "donor_name"])
            out.counts["contribution_rows"] += 1

    # 3) What IE committees spent, and on whom.
    ie = Dataset("state_ie_expenditures", conf["ie_expenditures"], fixtures, settings["page_size"])
    out.register_source("se", ie, conf["ie_expenditures"]["title"], conf["ie_expenditures"]["page_url"])
    if not ie.f("target"):
        out.warnings.append("No candidate column found in state IE expenditure data; super PAC donors can't be "
                            "linked to the officials those committees supported or opposed.")
    elif ie_filers:
        ids = list(ie_filers)
        for i in range(0, len(ids), 150):
            chunk = ",".join(soql_quote(x) for x in ids[i:i + 150])
            w = f"{ie.f('filer_id')} IN ({chunk}) AND {ie.f('year')} >= {start}"
            for r in ie.rows(w):
                if str(r.get("filer_id")) not in ie_filers or not r.get("target"):
                    continue
                y = _year(r.get("year"))
                ok, _ = out.offs.match_text(r["target"])
                ok = ok or out.offs.add(r["target"])
                if ok and y:
                    c = out.ie_spend[(ie_filers[str(r["filer_id"])], ok, y)]
                    c[0] += _amt(r.get("amount"))
                    st = (r.get("stance") or "").lower()
                    c[1] = c[1] or ("oppose" if st.startswith("o") else "support" if st.startswith("s") else "")
                    c[2] = c[2] or "se|" + ie.src(r)
    _missing(out, [lb, ds, ie])
    return out.finalize()


def _missing(out: Out, datasets: list[Dataset]):
    for d in datasets:
        if not d.available:
            out.warnings.append(f"{d.key}: dataset unavailable.")
        elif d.fields.missing_required:
            out.warnings.append(f"{d.key}: required fields not found: {', '.join(d.fields.missing_required)}")


def write(data: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
