"""Officials and candidates, keyed by 'LAST|FIRST'.

The list is built from campaign recipients (everyone who raised money) plus
officials named in lobbying filings. A lobbying target is linked to an official
only when both the first and last name appear in the target text; anything else
is kept as an unlinked target so nothing is dropped.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .normalize import clean, display_name, person_key, person_tokens, slug

STAFF = re.compile(r"\bSTAFF\b")


class OfficialIndex:
    def __init__(self):
        self.names: dict[str, Counter] = defaultdict(Counter)
        self.offices: dict[str, Counter] = defaultdict(Counter)
        self.by_last: dict[str, set] = defaultdict(set)
        self.ambiguous: set[str] = set()

    def add(self, raw_name: str, office: str = "") -> str:
        k = person_key(raw_name)
        if not k:
            return ""
        last, first, _ = person_tokens(raw_name)
        self.names[k][raw_name.strip()] += 1
        if office:
            self.offices[k][office] += 1
        self.by_last[last].add(k)
        return k

    def id_for(self, key: str) -> str:
        return slug(key.replace("|", "-")) if key else ""

    def match_text(self, text: str) -> tuple[str, bool]:
        """Return (official key, via_staff) for the first official named in text."""
        toks = set(clean(text).split())
        hits = []
        for t in toks:
            for k in self.by_last.get(t, ()):
                first = k.split("|")[1]
                if first in toks:
                    hits.append(k)
        if not hits:
            return "", False
        hits = sorted(set(hits))
        if len(hits) > 1:
            # Two officials named in one target string (rare). Keep the first
            # and record the ambiguity for the audit.
            self.ambiguous.add(text)
        return hits[0], bool(STAFF.search(clean(text)))

    def export(self) -> dict[str, dict]:
        out = {}
        for k, c in self.names.items():
            raw = c.most_common(1)[0][0]
            last, first, toks = person_tokens(raw)
            if "," in raw:
                pretty = display_name(" ".join(toks))
            else:
                pretty = display_name(re.sub(r"(?i)^(senator|assembly member|council member|staff member)\s+", "", raw))
            office = self.offices[k].most_common(1)[0][0] if self.offices[k] else ""
            out[self.id_for(k)] = {"name": pretty, "office": office}
        return out
