"""Which books contradict themselves about a permanent physical mark?

`checks.wandering_details` answers this for one ledger and `redthread audit` prints it for one
run. This runs it across every run in `runs/` and splits the rate by book length, because that
split is the finding: **15 of 19 books at 60+ scenes carry a mark in two or more body regions,
against 1 of 20 shorter ones.**

**Do not call that a length defect.** Every 60+ scene book in `runs/` is *The Debt of Years* --
19 of 19 -- and the longest book of any other premise is 24 scenes, so this rate cannot separate
"appears at length" from "appears in this premise". An earlier version of this docstring said
length, which is exactly the drift this script exists to prevent, one level up. Settling it needs
one 71-scene run of a different premise.

The cause of the drift itself was traced rather than inferred: a `detail` fixing the mark's
location lost its slice slot to a `state` about the same mark that named no location, so the
writer was told there was a scar and not where it was
(`docs/MEASUREMENTS.md`, "Tracing the mechanism").

Kept as a script for the same reason `portability.py` is: the number is a claim, and a claim
nobody can re-derive rots. Re-run it after any change to the slice, the extractor or the noun
list.

    python scripts/wandering_audit.py [--long-threshold 60]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread import checks  # noqa: E402


class _Fact:
    """Ledger dicts, given the attribute access `wandering_details` expects."""

    def __init__(self, row: dict):
        self.subject = row.get("subject", "")
        self.predicate = row.get("predicate", "")
        self.object = row.get("object", "")
        self.scene = row.get("scene", 0)
        self.kind = row.get("kind", "")


def audit(run: Path):
    ledger = run / "ledger.json"
    if not ledger.is_file():
        return None
    try:
        facts = json.loads(ledger.read_text(encoding="utf-8")).get("facts", [])
    except (OSError, json.JSONDecodeError):
        return None
    if not facts:
        return None
    title = "?"
    story = run / "story.json"
    if story.is_file():
        try:
            title = json.loads(story.read_text(encoding="utf-8")).get("title", "?")
        except (OSError, json.JSONDecodeError):
            pass
    scenes = len(list((run / "scenes").glob("*.txt")))
    return {"run": run.name, "title": title, "scenes": scenes, "facts": len(facts),
            "found": checks.wandering_details([_Fact(f) for f in facts])}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--long-threshold", type=int, default=60,
                    help="scene count at or above which a book counts as long")
    ap.add_argument("--title", help="restrict to one premise, e.g. 'The Debt of Years'")
    args = ap.parse_args(argv[1:])

    rows = [r for r in (audit(p) for p in sorted(Path("runs").iterdir()) if p.is_dir())
            if r and (not args.title or r["title"] == args.title)]
    if not rows:
        print("No ledgers to audit. That is not a clean result - check the path and the filter.")
        return 2

    print(f"{'run':<26} {'scenes':>6} {'facts':>6}  wandering marks")
    for r in sorted(rows, key=lambda r: (-r["scenes"], r["run"])):
        if r["found"]:
            detail = "; ".join(
                f"{subj}'s {noun} in " + "/".join(sorted(where))
                for subj, noun, where in r["found"])
        else:
            detail = "-"
        print(f"{r['run']:<26} {r['scenes']:>6} {r['facts']:>6}  {detail}")

    long_rows = [r for r in rows if r["scenes"] >= args.long_threshold]
    short_rows = [r for r in rows if r["scenes"] < args.long_threshold]
    print()
    for label, group in ((f">={args.long_threshold} scenes", long_rows),
                         (f"< {args.long_threshold} scenes", short_rows)):
        if not group:
            continue
        hit = sum(1 for r in group if r["found"])
        print(f"  {label:<14} {hit} of {len(group)} carry a wandering mark "
              f"({hit / len(group):.0%})")

    if long_rows:
        clean = 1 - sum(1 for r in long_rows if r["found"]) / len(long_rows)
        print(f"\n  clean rate on long books: {clean:.3f} - so two clean runs would be "
              f"p = {clean * clean:.4f}")
        print("  That arithmetic is the only reason n=2 can confirm anything here: the outcome is\n"
              "  binary per book, unlike every continuous measure in the panel, where a two-run\n"
              "  condition may not be used for anything (docs/evidence/two-run-screen.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
