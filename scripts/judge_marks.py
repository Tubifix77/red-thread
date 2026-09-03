"""Does the conflict judge recognise a permanent mark that has moved?

The wandering-mark fix failed on the brief side (docs/evidence/wandering-mark-fix.md), and the
pre-registration named the judge as the next lever. This measures the judge directly.

Two things are measured together, because measuring only the first would reward a prompt that
answers "contradiction" to everything (rule II):

  MISS RATE   on pairs that really are a permanent mark in two places
  FALSE RATE  on pairs the prompt is right to wave through - the same region at two
              resolutions, two regions meeting at a joint, a moved object, a changed state

Pairs are shuffled per repetition. That is deliberate: in the shipped book the palm/temple pair
arrived at list position 22 of a 25-pair cap, so position is a live confound, and rotating it is
cheaper than pretending it is not there.

Usage:  python scripts/judge_marks.py --local qwen3:8b [--reps 3] [--prompt current|revised]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread import verify
from redthread.llm import Models
from redthread.models import Fact, FactKind

D = FactKind.DETAIL
S = FactKind.STATE


def _f(subject, obj, scene, kind=D, predicate="has"):
    return Fact(subject=subject, predicate=predicate, object=obj, scene=scene, kind=kind)


# Should be flagged. The first four are verbatim from ledgers in runs/.
SHOULD_FLAG = [
    ("shipped palm->temple", _f("Kai", "a scar along his palm", 15),
     _f("Kai", "a scar running along his temple", 40)),
    ("shipped palm->arm", _f("Kai", "a scar on his palm", 16),
     _f("Kai", "scar on arm", 31)),
    ("shipped arm->temple", _f("Kai", "scar on arm", 32),
     _f("Kai", "a scar on his temple", 42)),
    ("var3 hand->cheek", _f("Mirra", "a scar across her hand", 12),
     _f("Mirra", "a scar across her cheek", 44)),
    ("tattoo shoulder->ankle", _f("Vay", "a tattoo on his shoulder", 8),
     _f("Vay", "a tattoo on his ankle", 30)),
    ("birthmark neck->knee", _f("Sera", "a birthmark on her neck", 5),
     _f("Sera", "a birthmark on her knee", 27)),
    ("brand chest->palm", _f("Ilias", "a brand burned into his chest", 3),
     _f("Ilias", "a brand burned into his palm", 19)),
    ("scar left->right hand", _f("Kai", "a scar on his left hand", 6),
     _f("Kai", "a scar on his right hand", 33)),
]

# Should NOT be flagged. Several are the prompt's own stated exemptions, restated as fact pairs.
SHOULD_NOT_FLAG = [
    ("same region, resolutions", _f("Kai", "a scar on his hand", 3),
     _f("Kai", "a scar along his palm", 21)),
    ("regions meeting at a joint", _f("Kai", "a scar on his wrist", 51),
     _f("Kai", "a scar on his forearm", 58)),
    ("a span, restated", _f("Kai", "a scar from wrist to elbow", 4),
     _f("Kai", "a scar from wrist to elbow, pale now", 30)),
    ("an object somebody moved", _f("Vay", "the register on the table", 7, predicate="keeps"),
     _f("Vay", "the register in a drawer", 25, predicate="keeps")),
    ("what somebody is holding", _f("Kai", "a blade", 9, predicate="carries"),
     _f("Kai", "a bundle of files", 22, predicate="carries")),
    ("a state that changed", _f("Vay", "the door unlocked", 3, kind=S, predicate="finds"),
     _f("Vay", "the door locked", 19, kind=S, predicate="finds")),
    ("one fact, two wordings", _f("Sera", "read the records", 11, predicate="has"),
     _f("Sera", "records", 24, predicate="has read")),
    ("a second, separate scar", _f("Ilias", "a scar on his palm", 8),
     _f("Ilias", "a second scar, newer, on his palm", 26)),
    ("transient description", _f("Kai", "hands damp with rain", 12, kind=S, predicate="has"),
     _f("Kai", "hands dry and warm", 29, kind=S, predicate="has")),
]


def run_once(models, prompt_template, cases, rng):
    """One judge call over all cases in a fresh random order. Returns label -> flagged."""
    order = list(cases)
    rng.shuffle(order)
    rendered = "\n".join(
        f"{i}. EARLIER {old.as_line()}\n   NEW     {new.as_line()}"
        for i, (_label, old, new) in enumerate(order))
    prompt = prompt_template.format(pairs=rendered, json_only=verify.JSON_ONLY)
    reply = models.critic.complete(prompt, max_tokens=verify.STRUCTURED_BUDGET,
                                   temperature=0.0, json_mode=True)
    data = verify.parse_json(reply.text)
    rows = data.get("judgements", []) if isinstance(data, dict) else data
    flagged = set()
    for row in rows:
        if not isinstance(row, dict) or not row.get("contradiction"):
            continue
        try:
            idx = int(row.get("pair", -1))
        except (TypeError, ValueError):
            continue
        # Range-checked rather than caught: a model-returned index used raw is the bug this
        # project has already found three times in one hour.
        if 0 <= idx < len(order):
            flagged.add(order[idx][0])
    return {label: (label in flagged) for label, _o, _n in order}, order


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", required=True)
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--prompt", choices=("current", "revised"), default="current")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    template = verify.CONFLICT_PROMPT
    if args.prompt == "revised":
        template = getattr(verify, "CONFLICT_PROMPT_REVISED", None)
        if template is None:
            raise SystemExit("no CONFLICT_PROMPT_REVISED in redthread.verify yet")

    models = Models.local(args.local, args.local, args.base_url, native=True)
    cases = list(SHOULD_FLAG + SHOULD_NOT_FLAG)
    rng = random.Random(args.seed)
    tally = {lbl: 0 for lbl, _o, _n in cases}
    positions = {lbl: [] for lbl, _o, _n in cases}

    for rep in range(args.reps):
        got, order = run_once(models, template, cases, rng)
        for i, (lbl, _o, _n) in enumerate(order):
            positions[lbl].append(i)
        for lbl, flagged in got.items():
            tally[lbl] += int(flagged)
        print(f"  rep {rep + 1}/{args.reps} done", flush=True)

    print(f"\n  prompt: {args.prompt}   model: {args.local}   reps: {args.reps}\n")
    print("  SHOULD FLAG (a permanent mark in two places)")
    misses = 0
    for lbl, _o, _n in SHOULD_FLAG:
        got = tally[lbl]
        misses += args.reps - got
        pos = ",".join(str(p) for p in positions[lbl])
        print(f"    {'OK  ' if got == args.reps else 'MISS'} {lbl:26} flagged {got}/{args.reps}"
              f"   list pos {pos}")

    print("\n  SHOULD NOT FLAG (the prompt is right to wave these through)")
    false_pos = 0
    for lbl, _o, _n in SHOULD_NOT_FLAG:
        got = tally[lbl]
        false_pos += got
        print(f"    {'OK   ' if got == 0 else 'FALSE'} {lbl:26} flagged {got}/{args.reps}")

    n_true = len(SHOULD_FLAG) * args.reps
    n_false = len(SHOULD_NOT_FLAG) * args.reps
    print(f"\n  miss rate  {misses}/{n_true} = {misses / n_true:.0%}"
          f"   (permanent marks the judge let through)")
    print(f"  false rate {false_pos}/{n_false} = {false_pos / n_false:.0%}"
          f"   (pairs it wrongly called contradictions)")

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"prompt": args.prompt, "model": args.local, "reps": args.reps,
             "tally": tally, "positions": positions,
             "miss_rate": misses / n_true, "false_rate": false_pos / n_false},
            indent=2), encoding="utf-8")
        print(f"\n  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
