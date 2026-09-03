"""Did the new mark BLOCKER hold a live run, or did the writer repair it?

Added 3 September, after the pre-flag shipped. The suite was green and the corpus precision was
perfect (13 of 13 wandering books fire, 0 of 15 clean ones), and neither of those facts answers
the question that matters for shipping: `checks:mark_conflict` is a BLOCKER, it fires on 13 of 13
wandering books, and a scene that trips a blocker its repair cannot fix spends its whole budget
and never commits. A gate that turns an unattended writer into one that stops is a regression, no
matter how precise it is.

Three things are read out of a finished run, all from artefacts the pipeline writes itself:

  HALTS       `halts.json` exists only when a halt happened, and records the violation kinds.
              A run with no such file completed.
  REPAIRS     `repair_log` on each scene (step 31's instrumentation) says which violation kinds
              a scene was sent back for and how many rounds it took.
  RESULT      the finished ledger, re-scored with `checks.wandering_details` - the same
              book-level check the corpus figures come from.

Usage:  python scripts/preflag_verify.py runs/current-preflag1 [runs/other ...]
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from redthread import checks
from redthread import models as M


def load_facts(run: pathlib.Path):
    led = run / "ledger.json"
    if not led.is_file():
        return []
    try:
        raw = json.loads(led.read_text(encoding="utf-8")).get("facts", [])
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for d in raw:
        try:
            out.append(M.Fact(subject=d["subject"], predicate=d["predicate"],
                              object=d["object"], kind=M.FactKind(d["kind"]),
                              scene=int(d["scene"])))
        except (KeyError, ValueError):
            continue
    return out


def report(run: pathlib.Path):
    scenes = sorted((run / "scenes").glob("*.txt"))
    print(f"\n  === {run.name} ===")
    print(f"  scenes written: {len(scenes)}")

    halts_file = run / "halts.json"
    if halts_file.is_file():
        try:
            halts = json.loads(halts_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            halts = []
        print(f"  HALTED: {len(halts)} halt(s)")
        for h in halts:
            print(f"    scene {h.get('scene')}: {h.get('kinds')}")
        mark_halts = [h for h in halts if "continuity_contradiction" in (h.get("kinds") or [])]
        print(f"  halts involving a continuity contradiction: {len(mark_halts)}"
              + ("   <- THE PRE-FLAG BROKE THE RUN" if mark_halts else ""))
    else:
        print("  no halts.json -> completed with ZERO halts")

    # Which violation kinds sent a scene back, from step 31's repair_log.
    project = run / "project.json"
    kinds = collections.Counter()
    rounds = collections.Counter()
    if project.is_file():
        try:
            data = json.loads(project.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for sc in data.get("scenes", []):
            for entry in sc.get("repair_log", []) or []:
                for k in (entry.get("kinds") or []):
                    kinds[k] += 1
                rounds[sc.get("index")] = sc.get("repairs", 0)
    if kinds:
        print("  repairs by violation kind:")
        for k, n in kinds.most_common():
            flag = "   <- the new gate" if k == "continuity_contradiction" else ""
            print(f"    {n:>3}  {k}{flag}")
        print(f"  scenes needing any repair: {sum(1 for v in rounds.values() if v)}")
    else:
        print("  no repair_log found (older run, or no repairs needed)")

    facts = load_facts(run)
    wandering = checks.wandering_details(facts) if facts else []
    print(f"  final ledger: {len(facts)} facts, book-level check: "
          f"{'WANDERS' if wandering else 'clean'}")
    for subj, noun, where in wandering:
        print(f"    {subj}'s {noun}: {dict(where)}")

    print("\n  What this run does and does not establish:")
    if not halts_file.is_file() and not kinds.get("continuity_contradiction"):
        print("    Completed with no halts, and the new gate never fired. The gate is shown")
        print("    HARMLESS on this run and its repair path remains UNTESTED in the live")
        print("    pipeline - firing is stochastic (13 of 28 corpus books), so this is a")
        print("    negative observation, not a pass.")
    elif kinds.get("continuity_contradiction") and not halts_file.is_file():
        print("    The gate fired AND the run completed - the repair walked the route. This is")
        print("    the outcome that licenses shipping it as a BLOCKER.")
    elif halts_file.is_file():
        print("    The run halted. If a continuity contradiction is among the kinds, today's")
        print("    change is a regression: drop the severity rather than keep a gate the")
        print("    writer cannot satisfy.")


def main(argv=None):
    args = (argv or sys.argv[1:]) or ["runs/current-preflag1"]
    for a in args:
        run = pathlib.Path(a)
        if not run.is_dir():
            print(f"  no such run: {a}")
            continue
        report(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
