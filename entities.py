"""Cluster organization names that refer to the same entity.

1. Exact match on a normalized key ("Uber Technologies, Inc." -> "UBER TECHNOLOGIES").
2. Fuzzy match within blocks that share a first word. Pairs at or above
   `auto_merge` are merged; pairs between `review` and `auto_merge` are written
   to a review file and NOT merged until a person confirms them.
3. Manual overrides in config/entity_overrides.csv always win:
     action=merge  -> alias is the same entity as canonical
     action=split  -> never merge these two names
"""
from __future__ import annotations

import csv
import os
from collections import Counter, defaultdict

from rapidfuzz import fuzz

from .normalize import display_name, entity_key, parent_key, slug


class EntityResolver:
    def __init__(self, auto_merge: int = 95, review: int = 88,
                 overrides_path: str = "config/entity_overrides.csv"):
        self.auto_merge = auto_merge
        self.review = review
        self.names: dict[str, Counter] = defaultdict(Counter)  # key -> raw name counts
        self.roles: dict[str, set] = defaultdict(set)
        self.merge_to: dict[str, str] = {}
        self.never: set[frozenset] = set()
        self.review_rows: list[dict] = []
        self.parent: dict[str, str] = {}
        if os.path.exists(overrides_path):
            with open(overrides_path, newline="") as f:
                for r in csv.DictReader(f):
                    a, b = entity_key(r.get("alias", "")), entity_key(r.get("canonical", ""))
                    if not a or not b:
                        continue
                    if (r.get("action") or "merge").strip().lower() == "split":
                        self.never.add(frozenset((a, b)))
                    else:
                        self.merge_to[a] = b

    def add(self, raw: str, role: str) -> str:
        k = entity_key(raw)
        if not k:
            return ""
        self.names[k][raw.strip()] += 1
        self.roles[k].add(role)
        return k

    # union-find
    def _find(self, k: str) -> str:
        self.parent.setdefault(k, k)
        while self.parent[k] != k:
            self.parent[k] = self.parent[self.parent[k]]
            k = self.parent[k]
        return k

    def _union(self, a: str, b: str):
        ra, rb = self._find(a), self._find(b)
        if ra == rb:
            return
        # keep the more frequently seen key as the root
        if sum(self.names[ra].values()) >= sum(self.names[rb].values()):
            self.parent[rb] = ra
        else:
            self.parent[ra] = rb

    def resolve(self):
        keys = list(self.names)
        for k in keys:
            self._find(k)
        for a, b in self.merge_to.items():
            if a in self.names:
                self.names.setdefault(b, Counter())
                self._find(b)
                self._union(b, a)
        blocks: dict[str, list[str]] = defaultdict(list)
        for k in keys:
            blocks[k.split()[0]].append(k)
        for block in blocks.values():
            if len(block) < 2 or len(block) > 3000:
                continue
            for i, a in enumerate(block):
                for b in block[i + 1:]:
                    if frozenset((a, b)) in self.never:
                        continue
                    # very short keys ("ABC") collide too easily
                    if min(len(a), len(b)) < 6:
                        continue
                    if parent_key(a) == b or parent_key(b) == a:
                        continue  # org and its PAC: linked as affiliates, not merged
                    score = fuzz.token_sort_ratio(a, b)
                    if score >= self.auto_merge:
                        self._union(a, b)
                    elif score >= self.review:
                        self.review_rows.append({"name_a": self.best_raw(a), "name_b": self.best_raw(b),
                                                 "score": round(score, 1)})

    def best_raw(self, k: str) -> str:
        c = self.names.get(k)
        return c.most_common(1)[0][0] if c else k

    def canonical(self, raw_or_key: str, is_key: bool = False) -> str:
        k = raw_or_key if is_key else entity_key(raw_or_key)
        if not k:
            return ""
        return self._find(k)

    def entity_id(self, raw: str) -> str:
        root = self.canonical(raw)
        return slug(root) if root else ""

    def export(self) -> dict[str, dict]:
        groups: dict[str, list[str]] = defaultdict(list)
        for k in self.names:
            groups[self._find(k)].append(k)
        out = {}
        for root, members in groups.items():
            raw = Counter()
            roles = set()
            for m in members:
                raw.update(self.names[m])
                roles |= self.roles[m]
            name = display_name(raw.most_common(1)[0][0]) if raw else root
            aliases = sorted({display_name(n) for n in raw} - {name})[:12]
            out[slug(root)] = {"name": name, "aliases": aliases, "roles": sorted(roles)}
        # Affiliates: an organization and its PAC / political fund.
        roots = {self._find(k) for k in self.names}
        for k in self.names:
            pk = parent_key(k)
            if pk and pk in self.names:
                a, b = slug(self._find(k)), slug(self._find(pk))
                if a != b and a in out and b in out:
                    out[a].setdefault("affiliates", []).append(b)
                    out[b].setdefault("affiliates", []).append(a)
        for v in out.values():
            if "affiliates" in v:
                v["affiliates"] = sorted(set(v["affiliates"]))
        return out

    def write_review(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["name_a", "name_b", "score"])
            w.writeheader()
            for r in sorted(self.review_rows, key=lambda r: -r["score"]):
                w.writerow(r)
