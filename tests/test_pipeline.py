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
