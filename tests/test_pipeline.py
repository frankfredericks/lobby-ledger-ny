import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pipeline import bills as B  # noqa: E402
from pipeline.normalize import entity_key, parent_key, person_key  # noqa: E402
from pipeline.officials import OfficialIndex  # noqa: E402

SESS = [[2018, 2021], [2022, 2023], [2024, 2025], [2026, 2029]]


def ids(bs):
    return [b.id for b in bs]


def test_state_same_as_and_versions():
    bs = B.parse_state("S8706B / 9581B -SUPPORT", 2026)
    assert ids(bs) == ["S8706@2025-2026", "A9581@2025-2026"]
    assert bs[1].inferred


def test_state_budget_part():
    bs = B.parse_state("S3006/A3006 PART P – SUPPORT – REQUESTED AMENDMENTS", 2025)
    assert ids(bs) == ["S3006@2025-2026", "A3006@2025-2026"]
    assert bs[0].part == "P"


def test_state_ignores_part_letters_and_years():
    assert ids(B.parse_state("Part A of the budget, NYS Senate 2025 session", 2025)) == []
    assert ids(B.parse_state("Senate Bill 4423", 2024)) == ["S4423@2023-2024"]


def test_city_formats():
    assert ids(B.parse_city("Local Legislation (including introduction) - Intro 30", 2026, SESS)) == ["Int 30@2026-2029"]
    assert ids(B.parse_city("Int 0030-2024", 2026, SESS)) == ["Int 30@2024-2025"]
    assert ids(B.parse_city("Int. No. 412-A", 2025, SESS)) == ["Int 412@2024-2025"]
    assert ids(B.parse_city("Res 12 and Resolution No. 40", 2022, SESS)) == ["Res 12@2022-2023", "Res 40@2022-2023"]


def test_positions():
    assert B.detect_position("S1464A - OPPOSE") == "oppose"
    assert B.detect_position("A3006 - support") == "support"
    assert B.detect_position("S1 support, S2 oppose") == "mixed"
    assert B.detect_position("S929") == ""


def test_entity_keys():
    assert entity_key("Harborview Realty, L.L.C.") == entity_key("HARBORVIEW REALTY LLC")
    assert entity_key("The Uber Technologies, Inc. d/b/a Uber") == "UBER TECHNOLOGIES"
    assert parent_key(entity_key("Empire Gaming Coalition PAC")) == "EMPIRE GAMING COALITION"


def test_people():
    assert person_key("Rivera, Ana M") == person_key("NYC Council Members Ana Rivera") == "RIVERA|ANA"
    assert person_key("ASSEMBLY MEMBER THOMAS O'DWYER") == "ODWYER|THOMAS"
    idx = OfficialIndex()
    idx.add("Rivera, Ana M")
    k, staff = idx.match_text("STAFF MEMBER COUNCIL MEMBER ANA RIVERA - District No. 22")
    assert k == "RIVERA|ANA" and staff
    assert idx.match_text("Department of Transportation (DOT) Ana Lopez")[0] == ""


def test_fixture_build(tmp_path):
    subprocess.check_call([sys.executable, "tests/make_fixtures.py"], cwd=ROOT)
    subprocess.check_call([sys.executable, "-m", "pipeline.run", "--fixtures", "tests/fixtures", "--out", str(tmp_path)], cwd=ROOT)
    city = json.load(open(tmp_path / "city.json"))
    state = json.load(open(tmp_path / "state.json"))
    assert "harborview-realty" in city["entities"] and "harborview-realty-llc" not in city["entities"]
    assert city["entities"]["harborview-realty"].get("db") == 1
    assert "odwyer-thomas" in state["officials"]
    assert "empire-gaming-coalition-pac" in state["entities"]["empire-gaming-coalition"].get("affiliates", [])
    # individuals never appear as direct donors to officials
    assert not any(r[0].startswith("doe-pat") for r in city["contribs"])
    # bill names come through from the title lookup
    assert city["bills"]["Int 412@2024-2025"]["title"].startswith("Licensing")
    # super PAC money is linked through spending targets
    assert any(r[1] == "vega-marisol" for r in state["ie_spend"])


def test_state_bill_official_pairing(tmp_path):
    subprocess.check_call([sys.executable, "tests/make_fixtures.py"], cwd=ROOT)
    subprocess.check_call([sys.executable, "-m", "pipeline.run", "--fixtures", "tests/fixtures", "--out", str(tmp_path), "--only", "state"], cwd=ROOT)
    state = json.load(open(tmp_path / "state.json"))
    rec = next(r for r in state["lobby"] if r[0] == "metro-rideshare-technologies")
    pairs = rec[10]
    # A3006 was lobbied with the Governor only, never with Senator Vega
    assert "vega-marisol" not in pairs["A3006@2023-2024"]
    assert "march-helen" in pairs["A3006@2023-2024"]
    assert "vega-marisol" in pairs["S1464@2023-2024"]


def test_year_filters_match_column_type():
    from pipeline.socrata import resolve_fields
    cols = [{"fieldName": "yr_num", "name": "Y1", "dataTypeName": "number"},
            {"fieldName": "yr_txt", "name": "Y2", "dataTypeName": "text"},
            {"fieldName": "dt", "name": "D", "dataTypeName": "floating_timestamp"}]
    fm = resolve_fields({"a": {"candidates": ["yr_num"]}, "b": {"candidates": ["yr_txt"]}, "c": {"candidates": ["dt"]}}, cols)
    assert fm.year_at_least("a", 2019) == "yr_num >= 2019"
    assert fm.year_at_least("b", 2019) == "yr_txt >= '2019'"
    assert fm.year_at_least("c", 2019) == "dt >= '2019-01-01T00:00:00'"


def test_timeouts_are_retried(monkeypatch):
    import requests
    from pipeline import socrata

    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        url = "x"
        text = ""

        def json(self):
            return [{"ok": 1}]

    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.ReadTimeout("slow")
        return FakeResp()

    monkeypatch.setattr(socrata.time, "sleep", lambda s: None)
    client = socrata.Socrata("example.org", "abcd-1234")
    monkeypatch.setattr(client.s, "get", fake_get)
    assert client._get("https://example.org/x") == [{"ok": 1}]
    assert calls["n"] == 3


def test_paging_by_row_id(monkeypatch):
    from pipeline import socrata

    data = [{":id": f"row-{i:04d}", "v": i} for i in range(25)]
    seen = []

    def fake_get(self, url, params=None, tries=6):
        seen.append(params.get("$where", ""))
        w = params.get("$where", "")
        after = w.split(":id > ")[1].strip("'") if ":id > " in w else ""
        rest = [r for r in data if r[":id"] > after]
        return rest[: params["$limit"]]

    monkeypatch.setattr(socrata.Socrata, "_get", fake_get)
    c = socrata.Socrata("example.org", "abcd-1234")
    out = list(c.rows(["v"], where="v >= 0", page_size=10))
    assert [r["v"] for r in out] == list(range(25))
    assert seen[0] == "v >= 0" and seen[1] == "(v >= 0) AND :id > 'row-0009'"
    assert len(list(c.rows(["v"], page_size=10, limit=5, ordered=False))) == 5


def test_broken_transfers_are_retried(monkeypatch):
    import requests
    from pipeline import socrata

    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        url = "x"
        text = ""

        def json(self):
            return [{"ok": 1}]

    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.exceptions.ChunkedEncodingError("Connection broken: IncompleteRead")
        return FakeResp()

    monkeypatch.setattr(socrata.time, "sleep", lambda s: None)
    c = socrata.Socrata("example.org", "abcd-1234")
    monkeypatch.setattr(c.s, "get", fake_get)
    assert c._get("https://example.org/x") == [{"ok": 1}]


def test_batch_shrinks_when_a_server_keeps_failing(monkeypatch):
    import requests
    from pipeline import socrata

    data = [{":id": f"row-{i:05d}", "v": i} for i in range(5000)]
    limits = []

    def fake_get(self, url, params=None, tries=6):
        limits.append(params["$limit"])
        if params["$limit"] > 2000:
            raise requests.exceptions.ChunkedEncodingError("Connection broken")
        w = params.get("$where", "")
        after = w.split(":id > ")[1].strip("'") if ":id > " in w else ""
        return [r for r in data if r[":id"] > after][: params["$limit"]]

    monkeypatch.setattr(socrata.Socrata, "_get", fake_get)
    c = socrata.Socrata("example.org", "abcd-1234")
    out = list(c.rows(["v"], page_size=8000))
    assert len(out) == 5000 and limits[:3] == [8000, 4000, 2000]


def test_download_resumes_across_runs(tmp_path, monkeypatch):
    import gzip
    from pipeline import rawcache

    data = [{":id": f"row-{i:04d}", "v": str(i)} for i in range(50)]

    def pages_after(after, size=10):
        rest = [r for r in data if after is None or r[":id"] > after]
        for i in range(0, len(rest), size):
            yield rest[i:i + size]

    # Run 1: budget runs out after the first page.
    calls = {"n": 0}

    def tick():
        calls["n"] += 1
        return calls["n"] > 1  # first check passes, second (after page 1) says time is up

    monkeypatch.setattr(rawcache, "out_of_time", tick)
    rc = rawcache.RawCache("ds", "v >= 0", ["v"], root=str(tmp_path))
    assert rc.sync(pages_after) is False
    assert rc.meta["rows"] == 10 and rc.meta["last_id"] == "row-0009"
    try:
        list(rc.read())
        assert False, "should not read an unfinished first download"
    except rawcache.NotReady:
        pass

    # Simulate a run killed mid-write: junk bytes after the last recorded page.
    with open(rc.partial_path, "ab") as f:
        f.write(b"\x1f\x8b garbage")

    # Run 2: plenty of time. Resumes after row 9, cleans up the junk, finishes.
    monkeypatch.setattr(rawcache, "out_of_time", lambda: False)
    rc2 = rawcache.RawCache("ds", "v >= 0", ["v"], root=str(tmp_path))
    assert rc2.sync(pages_after) is True
    assert [r["v"] for r in rc2.read()] == [str(i) for i in range(50)]

    # Run 3, same month: nothing to download.
    def must_not_download(after):
        raise AssertionError("downloaded again")
        yield
    rc3 = rawcache.RawCache("ds", "v >= 0", ["v"], root=str(tmp_path))
    assert rc3.sync(must_not_download) is True

    # Next month, budget runs out immediately: last month's copy is still served.
    monkeypatch.setattr(rawcache, "this_month", lambda: "2099-01")
    monkeypatch.setattr(rawcache, "out_of_time", lambda: True)
    rc4 = rawcache.RawCache("ds", "v >= 0", ["v"], root=str(tmp_path))
    assert rc4.sync(pages_after) is False
    assert len(list(rc4.read())) == 50

    # A changed query discards the old download.
    rc5 = rawcache.RawCache("ds", "v >= 1", ["v"], root=str(tmp_path))
    assert rc5.complete_path() is None


def test_live_dataset_uses_cache_and_reports_not_ready(tmp_path, monkeypatch):
    from pipeline import rawcache, socrata, sources

    cols = [{"fieldName": "nm", "name": "Name", "dataTypeName": "text"}]
    data = [{":id": f"row-{i:03d}", "nm": f"Org {i}"} for i in range(30)]

    def fake_pages(self, select, where=None, page_size=0, limit=None, ordered=True, after=None):
        rest = [r for r in data if after is None or r[":id"] > after]
        for i in range(0, len(rest), 10):
            yield rest[i:i + 10]

    monkeypatch.setattr(socrata.Socrata, "columns", lambda self: cols)
    monkeypatch.setattr(socrata.Socrata, "pages", fake_pages)
    monkeypatch.setattr(rawcache, "ROOT", str(tmp_path))
    monkeypatch.setattr(rawcache.RawCache.__init__, "__defaults__", (str(tmp_path),))
    conf = {"domain": "example.org", "id": "abcd-1234", "fields": {"name": {"candidates": ["nm"]}}}

    monkeypatch.setattr(rawcache, "out_of_time", lambda: True)
    ds = sources.Dataset("x", conf)
    try:
        list(ds.rows("nm IS NOT NULL"))
        assert False, "expected NotReady"
    except rawcache.NotReady:
        pass

    monkeypatch.setattr(rawcache, "out_of_time", lambda: False)
    got = list(sources.Dataset("x", conf).rows("nm IS NOT NULL"))
    assert len(got) == 30 and got[0] == {"name": "Org 0"}
