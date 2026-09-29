#!/usr/bin/env python3
"""Find warm paths into a company from your LinkedIn connections export.

    python3 network.py "Stripe"
    python3 network.py "Stripe" --second-degree data/second_degree_stripe.csv
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from warmpath.report import best_path_per_target, render_markdown, write_csv
from warmpath.workflow import run

ROOT = Path(__file__).resolve().parent


def _default(path: str) -> Path | None:
    p = ROOT / path
    return p if p.exists() else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("company", help="Target company, e.g. 'Stripe'")
    ap.add_argument("--connections", type=Path, default=ROOT / "data/Connections.csv", help="LinkedIn Connections.csv export")
    ap.add_argument("--profile", type=Path, default=_default("config/profile.json"), help="Your profile JSON")
    ap.add_argument("--aliases", type=Path, default=ROOT / "config/company_aliases.json", help="Company family/sister map")
    ap.add_argument("--second-degree", type=Path, help="CSV of 2nd-degree people + mutual connections")
    ap.add_argument("--notes", type=Path, default=_default("data/notes.csv"), help="CSV of personal shared-history notes")
    ap.add_argument("--templates", type=Path, default=ROOT / "templates", help="Message template directory")
    ap.add_argument("--top", type=int, default=5, help="How many drafts to write per section")
    ap.add_argument("--out", type=Path, default=ROOT / "reports", help="Output directory")
    ap.add_argument("--today", type=date.fromisoformat, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if not args.connections.exists():
        print(f"Connections export not found at {args.connections}.\n"
              "Download it from LinkedIn (Settings > Data privacy > Get a copy of your data > Connections) "
              "and save it as data/Connections.csv.", file=sys.stderr)
        return 2
    if args.second_degree and not args.second_degree.exists():
        print(f"--second-degree file not found: {args.second_degree}", file=sys.stderr)
        return 2

    result = run(args.company, args.connections, args.profile, args.aliases, args.second_degree, args.notes, args.today)

    args.out.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", args.company.lower()).strip("-")
    md_path = args.out / f"{slug}-{result.today.isoformat()}.md"
    csv_path = md_path.with_suffix(".csv")
    md_path.write_text(render_markdown(result, args.templates, args.top), encoding="utf-8")
    write_csv(result, csv_path)

    confirmed = [s for s in result.insiders if s.match != "name-match"]
    print(f"{args.company}: {len(confirmed)} 1st-degree, "
          f"{len(best_path_per_target(result.paths))} 2nd-degree targets with paths, {len(result.bridges)} bridges")
    for s in confirmed[:args.top]:
        print(f"  • {s.person.name} - {s.person.position} ({'; '.join(s.reasons[:2])})")
    for w in result.warnings:
        print(f"  ! {w}")
    print(f"Report: {md_path.relative_to(ROOT) if md_path.is_relative_to(ROOT) else md_path}")
    print(f"CSV:    {csv_path.relative_to(ROOT) if csv_path.is_relative_to(ROOT) else csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
