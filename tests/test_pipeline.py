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
