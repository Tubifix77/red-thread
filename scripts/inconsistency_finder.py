"""Assemble audit packets for the inconsistency finder, and tally what it returns.

**Why this exists.** Its predecessor — a contradiction detector graded on one binary question —
was rejected after two pre-registered rounds despite catching 19 of 19 seeded contradictions
exactly (`docs/evidence/inspector-method.md`). It failed a 1-in-10 false-alarm ceiling twice, and
every flag in 40 trials pointed at something genuinely wrong. The diagnosis was a specification
error, not a capability one: the instrument reliably answers a *broader* question than "does this
scene contradict a listed fact", and it had one output slot for a question with several real
answers.

So this successor changes three things, and each one is traceable to a specific finding:

1. **Categories instead of a verdict.** The taxonomy below is derived from the six genuinely real
   findings across those 40 trials, not invented. Two of them were about the *fact ledger* rather
   than the prose, which no verdict slot existed for.
2. **Every fact carries the sentence it came from.** The ledger recorded "the donor was dead"
   from prose that reads "dead anyway. Not literally, not exactly" — a flattened hedge that only
   becomes checkable when the source sentence travels with the fact. The ledger does not store
   it, so it is located here, and a fact whose source cannot be located is *excluded* from the
   category that depends on it rather than guessed at.
3. **Recall is the metric; precision is a triage budget.** Fixed in
   `docs/evidence/inconsistency-finder.md` before any run.

**Rule VI is unchanged and absolute:** nothing here gates a commit, and nothing here runs in the
product. The writer stays `qwen3:8b` on Ollama with zero Claude calls. This prepares packets for a
session-side audit and tallies the answers; the model calls happen outside it, which is also why
no adopted verdict can quietly creep into the write path.

    python scripts/inconsistency_finder.py prepare <run> --scenes 40-45 --out DIR
    python scripts/inconsistency_finder.py score DIR --findings findings.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread import checks  # noqa: E402

CATEGORIES = {
    "SCENE_CONTRADICTS_FACT":
        "the scene states something incompatible with a durable fact established earlier",
    "FACT_MISREADS_SOURCE":
        "the recorded fact does not faithfully represent the sentence it was extracted from",
    "SCENE_INTERNALLY_INCOHERENT":
        "the scene contradicts itself, independent of any recorded fact",
    "CLEAN":
        "nothing of the above",
}
"""Derived from the six real findings across the predecessor's 40 trials.

`FACT_MISREADS_SOURCE` exists because of one: the ledger's flattened hedge about the donor.
`SCENE_INTERNALLY_INCOHERENT` exists because of another: a scene that restates its fact correctly
and then places a temple scar "beneath his shirt collar". Both were scored as false alarms by the
predecessor because it had nowhere to put them.
"""

DURABLE_KINDS = ("detail", "knowledge")
"""Transient `state` facts are excluded, and this is the one fix carried over verbatim.

All four of the predecessor's genuinely spurious flags — as opposed to its correctly-found,
wrongly-labelled ones — were transient states read as binding on a later scene: a scene-1 satchel,
a scene-7 ledger-holder. Excluding the kind removed the class entirely in round 2.
"""

MIN_SOURCE_COVERAGE = 0.6
"""Share of a fact's content words that must appear in a sentence for it to be called the source.

Below this the fact is published with `[source sentence not locatable]` and the audit is told not
to judge `FACT_MISREADS_SOURCE` on it. A located-by-guesswork source would manufacture exactly the
defect class this tool was built to find.
"""


def _content_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z']+", text.lower()) if len(w) > 3]


def locate_source(fact: dict, scene_text: str) -> str | None:
    """The sentence a fact was most plausibly extracted from, or None if it cannot be pinned.

    Scored by share of the fact's content words present, not by any similarity metric, so the
    threshold means something a reader can check by eye.
    """
    words = _content_words(f"{fact['predicate']} {fact['object']}")
    if not words:
        return None
    # Word-boundary PREFIX match, and the boundary is the whole point. A plain substring test
    # located the fact "Kai has scar" to a sentence about "discarded watches" -- because
    # di-SCAR-ded contains it -- and three independent auditors reported the mismatch before
    # anyone noticed the locator was at fault. That is this project's oldest defect class
    # (the refusal regex that was 56% ordinary English) in a new place.
    #
    # A prefix rather than a full word match, because requiring both boundaries loses
    # ordinary inflection: "mean" would stop matching "meant", "stiff" would stop matching
    # "stiffened". Measured over 254 durable facts, the two disagree on 9.
    patterns = [re.compile(r"\b" + re.escape(w)) for w in words]
    best, best_score = None, 0.0
    for sentence in checks.sentences(scene_text):
        low = sentence.lower()
        score = sum(1 for pat in patterns if pat.search(low)) / len(patterns)
        if score > best_score:
            best, best_score = sentence, score
    return best if best_score >= MIN_SOURCE_COVERAGE else None


def durable_facts_before(facts: list[dict], scene_index: int) -> list[dict]:
    return [f for f in facts
            if f.get("scene", 0) < scene_index and f.get("kind") in DURABLE_KINDS]


def build_packet(run: Path, scene_index: int, limit: int = 12) -> str | None:
    """One scene's audit packet: durable earlier facts with their sources, then the scene."""
    ledger = json.loads((run / "ledger.json").read_text(encoding="utf-8"))
    facts = ledger.get("facts", [])
    scene_files = {int(p.stem): p for p in (run / "scenes").glob("*.txt")}
    if scene_index not in scene_files:
        return None
    scene_text = scene_files[scene_index].read_text(encoding="utf-8")

    earlier = durable_facts_before(facts, scene_index)
    # Nearest-first: a fact from scene 39 bears on scene 40 more than one from scene 2, and a
    # packet is a fixed size, so the ordering decides what gets audited at all.
    earlier.sort(key=lambda f: -f.get("scene", 0))
    chosen, located = [], 0
    for fact in earlier[:limit]:
        src_text = scene_files.get(fact["scene"])
        source = (locate_source(fact, src_text.read_text(encoding="utf-8"))
                  if src_text else None)
        located += source is not None
        chosen.append((fact, source))

    lines = [f"DURABLE FACTS ESTABLISHED IN EARLIER SCENES (scene {scene_index} is under audit)",
             ""]
    for fact, source in chosen:
        lines.append(f"- [scene {fact['scene']}] {fact['subject']} {fact['predicate']} "
                     f"{fact['object']}")
        lines.append(f"    source: {source}" if source
                     else "    source: [source sentence not locatable — "
                          "do not judge FACT_MISREADS_SOURCE on this fact]")
    lines += ["", f"SCENE {scene_index} TEXT:", "", scene_text]
    return "\n".join(lines)


def cmd_prepare(args) -> int:
    run = Path(args.run)
    if not (run / "ledger.json").exists():
        print(f"no ledger at {run}")
        return 2
    lo, _, hi = args.scenes.partition("-")
    indices = range(int(lo), int(hi or lo) + 1)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    written = 0
    for i in indices:
        packet = build_packet(run, i, limit=args.facts)
        if packet is None:
            print(f"  scene {i}: no committed text, skipped")
            continue
        (out / f"scene{i:04d}.txt").write_text(packet, encoding="utf-8")
        missing = packet.count("not locatable")
        written += 1
        print(f"  scene {i}: packet written, {args.facts - missing}/{args.facts} "
              f"facts have a located source")
    if not written:
        print("\n  Nothing written. An empty prepare is not a clean result — check the run "
              "and the scene range.")
        return 2
    print(f"\n{written} packet(s) in {out}")
    print("Categories the audit may return: " + ", ".join(CATEGORIES))
    return 0


def cmd_score(args) -> int:
    """Tally returned findings. Adjudication is a separate, blind step — see the evidence file."""
    findings = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    by_cat: dict[str, int] = {}
    for f in findings:
        cat = f.get("category", "?")
        by_cat[cat] = by_cat.get(cat, 0) + 1
    unknown = sorted(set(by_cat) - set(CATEGORIES))
    total = len(findings)
    flagged = sum(v for k, v in by_cat.items() if k != "CLEAN")

    print(f"{total} packet(s) audited")
    for cat in list(CATEGORIES) + unknown:
        if cat in by_cat:
            print(f"  {cat:<30} {by_cat[cat]}")
    if unknown:
        print(f"\n  ⚠ categories not in the taxonomy: {', '.join(unknown)} — a finding the "
              f"taxonomy\n    cannot express is a result about the taxonomy, not a parse error.")
    if total:
        print(f"\n  flag rate {flagged}/{total} = {flagged / total:.2f} per packet")
        print("  Precision is NOT computed here. Every flag must be adjudicated blind before any "
              "\n  rate is claimed for it — that is the whole difference between this instrument "
              "\n  and the one it replaces.")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare", help="write one audit packet per scene")
    p.add_argument("run")
    p.add_argument("--scenes", required=True, help="index or range, e.g. 40 or 40-45")
    p.add_argument("--out", required=True)
    p.add_argument("--facts", type=int, default=12, help="durable facts per packet")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("score", help="tally returned findings by category")
    p.add_argument("dir")
    p.add_argument("--findings", required=True, help="JSON list of {packet, category, ...}")
    p.set_defaults(func=cmd_score)

    args = ap.parse_args(argv[1:])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
