"""Build the site's data files.

    python -m pipeline.run                    # live data
    python -m pipeline.run --fixtures tests/fixtures --out site/data   # offline demo
"""
from __future__ import annotations

import argparse
import json
import sys

import yaml

from .bill_titles import enrich
from .build import build_city, build_state, write


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", help="read local fixture files instead of the live APIs")
    ap.add_argument("--out", default="site/data")
    ap.add_argument("--only", choices=["city", "state"])
    args = ap.parse_args(argv)

    sources = yaml.safe_load(open("config/sources.yml"))
    settings = yaml.safe_load(open("config/settings.yml"))

    manifest = {}
    failed = False
    for j, fn in (("city", build_city), ("state", build_state)):
        if args.only and args.only != j:
            continue
        data = fn(sources[j], settings, args.fixtures)
        enrich(data, j, args.fixtures)
        write(data, f"{args.out}/{j}.json")
        m = data["meta"]
        manifest[j] = {"generated": m["generated"], "years": m["years"], "warnings": m["warnings"],
                       "officials": len(data["officials"]), "entities": len(data["entities"]),
                       "bills": len(data["bills"]), "lobbying_records": len(data["lobby"]),
                       "contribution_links": len(data["contribs"])}
        print(f"[{j}] officials={len(data['officials'])} entities={len(data['entities'])} "
              f"bills={len(data['bills'])} lobbying={len(data['lobby'])} contribs={len(data['contribs'])}")
        for w in m["warnings"]:
            print(f"  warning: {w}")
        if any("required fields not found" in w for w in m["warnings"]):
            failed = True
    with open(f"{args.out}/manifest{'-' + args.only if args.only else ''}.json", "w") as f:
        json.dump(manifest, f, indent=2)
    if failed:
        print("Build stopped: a dataset's columns changed. Run `python -m pipeline.audit` and update config/sources.yml.")
        sys.exit(1)


if __name__ == "__main__":
    main()
