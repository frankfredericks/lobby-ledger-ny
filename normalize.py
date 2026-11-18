"""Name cleaning used to match the same entity or person across datasets."""
from __future__ import annotations

import re
import unicodedata

LEGAL_SUFFIXES = {
    "INC", "INCORPORATED", "LLC", "L L C", "LLP", "LP", "L P", "CORP", "CORPORATION",
    "CO", "COMPANY", "LTD", "LIMITED", "PC", "P C", "PLLC", "NA", "N A", "THE",
}
ABBREV = {
    "ASSN": "ASSOCIATION", "ASSOC": "ASSOCIATION", "NATL": "NATIONAL", "INTL": "INTERNATIONAL",
    "DEPT": "DEPARTMENT", "SVCS": "SERVICES", "SVC": "SERVICE", "MGMT": "MANAGEMENT",
    "NY": "NEW YORK", "NYS": "NEW YORK STATE", "NYC": "NEW YORK CITY", "COMM": "COMMITTEE",
    "CTTE": "COMMITTEE", "CMTE": "COMMITTEE", "POL": "POLITICAL", "UNIV": "UNIVERSITY",
    "&": "AND", "CTR": "CENTER", "HOSP": "HOSPITAL", "INDEP": "INDEPENDENT", "EXP": "EXPENDITURE",
}
PERSON_TITLES = {
    "SENATOR", "SEN", "ASSEMBLY", "MEMBER", "ASSEMBLYMEMBER", "ASSEMBLYMAN", "ASSEMBLYWOMAN",
    "COUNCIL", "COUNCILMEMBER", "COUNCILMAN", "COUNCILWOMAN", "MEMBERS", "HON", "HONORABLE",
    "MR", "MRS", "MS", "DR", "GOVERNOR", "GOV", "LIEUTENANT", "LT", "MAYOR", "COMPTROLLER",
    "PUBLIC", "ADVOCATE", "BOROUGH", "PRESIDENT", "ATTORNEY", "GENERAL", "STAFF", "THE",
    "JR", "SR", "II", "III", "IV", "ESQ", "NYC", "NYS", "OF",
}
COMMITTEE_BOILERPLATE = [
    r"\bFRIENDS (?:OF|FOR)\b", r"\bCITIZENS (?:FOR|TO ELECT)\b", r"\bCOMMITTEE TO (?:RE ?)?ELECT\b",
    r"\bPEOPLE FOR\b", r"\b(?:RE ?)?ELECT\b", r"\bFOR (?:NEW YORK|NY|NYC|SENATE|ASSEMBLY|GOVERNOR|STATE SENATE|COUNCIL|MAYOR|COMPTROLLER|ATTORNEY GENERAL|PUBLIC ADVOCATE)\b.*$",
    r"\b\d{4}\b", r"\bINC\b", r"\bCOMMITTEE\b", r"\bCAMPAIGN\b", r"\bTEAM\b",
]


def ascii_upper(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return s.upper()


def clean(s: str) -> str:
    s = ascii_upper(s).replace("&", " AND ")
    s = re.sub(r"['\u2019`]", "", s)          # O'Dwyer -> ODWYER, not O DWYER
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # rejoin dotted abbreviations: "L L C" -> "LLC"
    for spaced, joined in (("L L C", "LLC"), ("L L P", "LLP"), ("P L L C", "PLLC"), ("L P", "LP"),
                           ("P C", "PC"), ("N A", "NA"), ("U S A", "USA"), ("U S", "US")):
        s = re.sub(rf"\b{spaced}\b", joined, s)
    return s


AFFILIATE_SUFFIX = re.compile(
    r"\s+(?:PAC|COPE|POLITICAL ACTION (?:COMMITTEE|FUND)|POLITICAL (?:FUND|COMMITTEE)|"
    r"POLITICAL ACTION COMMITTEE FUND|ACTION FUND|VOTE COMMITTEE)$")


def parent_key(key: str) -> str:
    """'EMPIRE GAMING COALITION PAC' -> 'EMPIRE GAMING COALITION' (the sponsoring organization)."""
    k = AFFILIATE_SUFFIX.sub("", key)
    return k if k != key else ""


def entity_key(name: str) -> str:
    """Comparable key for an organization name."""
    s = ascii_upper(name)
    s = re.split(r"\b(?:D/?B/?A|A/?K/?A|F/?K/?A)\b", s)[0]  # keep the legal name before d/b/a
    s = clean(s)
    toks = [ABBREV.get(t, t) for t in s.split()]
    s = " ".join(toks)
    toks = s.split()
    while toks and toks[-1] in LEGAL_SUFFIXES:
        toks.pop()
    while toks and toks[0] == "THE":
        toks.pop(0)
    return " ".join(toks)


def person_tokens(name: str) -> tuple[str, str, list[str]]:
    """Return (last, first, all_tokens) for 'Last, First M' or 'First M Last'."""
    raw = ascii_upper(name)
    if "," in raw:
        last_part, first_part = raw.split(",", 1)
        last = [t for t in clean(last_part).split() if t not in PERSON_TITLES]
        first = [t for t in clean(first_part).split() if t not in PERSON_TITLES and len(t) > 1]
        toks = first + last
        return (last[-1] if last else ""), (first[0] if first else ""), toks
    toks = [t for t in clean(raw).split() if t not in PERSON_TITLES]
    toks_no_init = [t for t in toks if len(t) > 1]
    if len(toks_no_init) < 2:
        return (toks_no_init[0] if toks_no_init else ""), "", toks
    return toks_no_init[-1], toks_no_init[0], toks


def person_key(name: str) -> str:
    last, first, _ = person_tokens(name)
    return f"{last}|{first}" if last and first else ""


def candidate_from_committee(name: str) -> str:
    """'Friends of Jessica Ramos' -> 'JESSICA RAMOS'. Best effort."""
    s = clean(name)
    for pat in COMMITTEE_BOILERPLATE:
        s = re.sub(pat, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def display_name(name: str) -> str:
    """Readable casing for names that arrive in all caps."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    if name and name == name.upper():
        keep = {"LLC", "LLP", "LP", "PAC", "NY", "NYC", "NYS", "USA", "US", "IBEW", "SEIU",
                "UFT", "PBA", "CWA", "AFL", "CIO", "DC", "II", "III", "IV", "MTA", "CUNY", "SUNY"}
        parts = []
        for t in name.split(" "):
            core = re.sub(r"[^A-Z]", "", t)
            parts.append(t if core in keep else "-".join("'".join(x.capitalize() for x in w.split("'")) for w in t.split("-")))
        name = " ".join(parts)
    return name


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:80] or "x"
