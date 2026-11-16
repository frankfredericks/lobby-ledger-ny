"""Turn free-text lobbying descriptions into standard bill IDs.

State bills: "S929@2025-2026" (chamber + number + two-year session). Amendment
letters (S929A) are kept as versions but collapse to one bill page, because
lobbyists cite whichever print was current.

City bills: "Int 30@2026-2029" / "Res 12@2026-2029". Intro numbers restart
every Council session, so the session is part of the ID.

Lobbyists sometimes add SUPPORT / OPPOSE / AMEND to the description. Neither
NYS nor NYC requires that, so the site shows it only as a "self-described
position" when present.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

POSITION_PATTERNS = [
    ("oppose", re.compile(r"\bOPPOS(?:E|ED|ING|ITION)\b")),
    ("support", re.compile(r"\bSUPPORT(?:ED|ING|S)?\b")),
    ("amend", re.compile(r"\b(?:REQUESTED|SEEK(?:ING)?|PROPOSED)?\s*AMENDMENTS?\b")),
]

STATE_BILL = re.compile(
    r"(?<![A-Z0-9])(?<!PART )(?<!PART-)"
    r"(SENATE BILL|ASSEMBLY BILL|SB|AB|S|A)\s*[\.\-#:]?\s*(?:NO\.?\s*)?"
    r"(\d{1,5})([A-F])?(?![0-9])"
)
SLASH_BARE = re.compile(r"\s*/\s*(\d{2,5})([A-F])?(?![0-9])")
PART = re.compile(r"\bPART\s*[-:]?\s*([A-Z]{1,3})\b")

CITY_INTRO = re.compile(
    r"\b(INT(?:RO)?(?:DUCTION)?|RES(?:OLUTION)?|T)\s*\.?\s*(?:NO\.?|NUMBER|#)?\s*"
    r"(\d{1,4})(?:\s*-\s*([A-Z]))?(?:\s*-\s*(\d{4}))?(?:\s*-\s*([A-Z]))?\b"
)


@dataclass(frozen=True)
class Bill:
    id: str
    label: str
    session: str
    chamber: str
    number: int
    part: str = ""
    version: str = ""
    inferred: bool = False


def state_session(year: int) -> str:
    start = year if year % 2 == 1 else year - 1
    return f"{start}-{start + 1}"


def _chamber(tok: str) -> str:
    return "S" if tok.startswith("S") else "A"


def parse_state(text: str, year: int) -> list[Bill]:
    if not text:
        return []
    t = text.upper()
    sess = state_session(int(year))
    out: list[Bill] = []
    all_parts = sorted(set(PART.findall(t)))
    for m in STATE_BILL.finditer(t):
        ch = _chamber(m.group(1))
        num = int(m.group(2))
        if num == 0:
            continue
        ver = m.group(3) or ""
        if len(all_parts) == 1:
            part = all_parts[0]
        else:
            pm = PART.search(t[m.end(): m.end() + 25])
            part = pm.group(1) if pm else ""
        out.append(Bill(f"{ch}{num}@{sess}", f"{ch}{num}", sess, ch, num, part, ver))
        # "S8706B / 9581B": the bare number after a slash is the same-as bill in
        # the other house.
        sm = SLASH_BARE.match(t[m.end():])
        if sm:
            other = "A" if ch == "S" else "S"
            n2 = int(sm.group(1))
            out.append(Bill(f"{other}{n2}@{sess}", f"{other}{n2}", sess, other, n2, part,
                            sm.group(2) or "", inferred=True))
    seen, uniq = set(), []
    for b in out:
        if b.id not in seen:
            seen.add(b.id)
            uniq.append(b)
    return uniq


def city_session(year: int, sessions: list[list[int]]) -> str:
    for a, b in sessions:
        if a <= year <= b:
            return f"{a}-{b}"
    return str(year)


def parse_city(text: str, year: int, sessions: list[list[int]]) -> list[Bill]:
    if not text:
        return []
    t = text.upper()
    out: list[Bill] = []
    for m in CITY_INTRO.finditer(t):
        kind_tok, num = m.group(1), int(m.group(2))
        if kind_tok == "T":
            continue  # "T2024-..." are Council transcript numbers, not bills
        kind = "Res" if kind_tok.startswith("RES") else "Int"
        if num == 0:
            continue
        ver = m.group(3) or m.group(5) or ""
        intro_year = int(m.group(4)) if m.group(4) else int(year)
        sess = city_session(intro_year, sessions)
        out.append(Bill(f"{kind} {num}@{sess}", f"{kind} {num}", sess, kind, num, "", ver,
                        inferred=not m.group(4)))
    seen, uniq = set(), []
    for b in out:
        if b.id not in seen:
            seen.add(b.id)
            uniq.append(b)
    return uniq


def detect_position(text: str) -> str:
    """Self-described position, if the filer wrote one. '' when absent or mixed."""
    if not text:
        return ""
    t = text.upper()
    found = [name for name, pat in POSITION_PATTERNS if pat.search(t)]
    if "support" in found and "oppose" in found:
        return "mixed"
    return found[0] if found else ""
