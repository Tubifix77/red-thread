"""Score this project's prose on EQ-Bench's slop list, and calibrate against their own numbers.

The only external comparison available to this project ([docs/evidence/slop-benchmark.md]).
Deterministic, no API key, no LLM judge - it counts words, so it is not the quality measurement
that was cut on 3 September.

Algorithm reproduced from `js/metrics.js` in sam-paech/slop-score, read rather than described:

    tokens       = lowercase, findall [a-z]+(?:'[a-z]+)?
    wordScore    = (tokens present in slop_list.json)           / len(tokens) * 1000
    trigramScore = (consecutive 3-token windows in trigram list) / len(tokens) * 1000

Whole-token matching, every occurrence counted.

**Their sibling "repetition" metric is deliberately not implemented.** It is not this project's
`duplication_ratio` despite the shared word - theirs sums over-representation against the
`wordfreq` English corpus across a multi-prompt corpus, ours is within one scene. Reporting them
side by side would be the rule II error.

Two arms, because red-thread `check_slop`-gates 138 phrases from the same author's antislop list:

    FULL      their 1,648 words. Partly a measurement of our own gate. Completeness only.
    HELD-OUT  their list minus every phrase red-thread enforces. The arm that counts.

The calibration gate runs first and can void everything: the implementation must reproduce their
published figures for three models, whose raw sample text it re-scores, to within a tolerance
fixed in the pre-registration. A reimplementation that cannot reproduce known values is measuring
something else.

Usage:
  python scripts/slop_benchmark.py --data DIR [--tolerance 0.05]

DIR must hold slop_list.json, slop_list_trigrams.json, leaderboard_results.json and the
per-model result files being used for calibration.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from redthread import checks

TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?")

CALIBRATION = {
    "qwen3-4b.json": "qwen/qwen3-4b",
    "gemma-3-12b-it.json": "google/gemma-3-12b-it",
    "claude-sonnet-4-5.json": "claude-sonnet-4-5",
}


def load_lists(data: pathlib.Path):
    """Their lists are arrays of single-element arrays; flatten and lowercase."""
    def flat(name):
        raw = json.loads((data / name).read_text(encoding="utf-8"))
        out = set()
        for row in raw:
            term = row[0] if isinstance(row, list) else row
            out.add(str(term).strip().lower())
        return out
    return flat("slop_list.json"), flat("slop_list_trigrams.json")


def score(text: str, words: set, trigrams: set) -> tuple[float, float, int]:
    toks = TOKEN.findall(text.lower())
    n = len(toks)
    if n == 0:
        return 0.0, 0.0, 0
    word_hits = sum(1 for t in toks if t in words)
    tri_hits = 0
    if trigrams:
        for i in range(n - 2):
            if f"{toks[i]} {toks[i+1]} {toks[i+2]}" in trigrams:
                tri_hits += 1
    return word_hits / n * 1000, tri_hits / n * 1000, n


def their_text(path: pathlib.Path) -> str:
    """Concatenate every sample's output from one of their result files."""
    d = json.loads(path.read_text(encoding="utf-8"))
    inner = d[next(iter(d))] if len(d) == 1 else d
    return "\n\n".join(str(s.get("output", "")) for s in inner.get("samples", []))


def our_text() -> tuple[str, int, int]:
    """Every committed scene in runs/, which is the prose this project actually produced."""
    files = sorted(pathlib.Path("runs").glob("*/scenes/*.txt"))
    books = {f.parent.parent.name for f in files}
    parts = [f.read_text(encoding="utf-8", errors="replace") for f in files]
    return "\n\n".join(parts), len(files), len(books)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--tolerance", type=float, default=0.05)
    args = ap.parse_args(argv)
    data = pathlib.Path(args.data)

    words, trigrams = load_lists(data)
    print(f"  their lists: {len(words)} words, {len(trigrams)} trigrams")

    published = {}
    lb = json.loads((data / "leaderboard_results.json").read_text(encoding="utf-8"))
    for row in lb["results"]:
        published[row["model"]] = row["metrics"]

    # ---- the calibration gate, before any figure of ours is computed --------------------
    print("\n  CALIBRATION - reproduce their published slop/1k on their own text")
    print(f"  {'model':26} {'published':>10} {'mine':>8} {'delta':>8}  verdict")
    failures = []
    for fname, key in CALIBRATION.items():
        path = data / fname
        if not path.is_file():
            print(f"  {key[:26]:26} {'-':>10} {'-':>8} {'-':>8}  MISSING FILE")
            failures.append(key)
            continue
        want = published[key]["slop_list_matches_per_1k_words"]
        got, _tri, _n = score(their_text(path), words, trigrams)
        delta = abs(got - want) / want
        ok = delta <= args.tolerance
        if not ok:
            failures.append(key)
        print(f"  {key[:26]:26} {want:10.2f} {got:8.2f} {delta:7.1%}  "
              f"{'pass' if ok else 'FAIL'}")

    if failures:
        print(f"\n  CALIBRATION FAILED for {failures}.")
        print("  The pre-registration says: no comparison is reported at all - not a corrected")
        print("  one, not a caveated one. A reimplementation that cannot reproduce known values")
        print("  is measuring something else.")
        return 1
    print(f"\n  calibration passed within +/-{args.tolerance:.0%}. Proceeding.")

    # ---- our corpus, two arms -----------------------------------------------------------
    ours, n_scenes, n_books = our_text()
    enforced = {p.strip().lower() for p in checks.load_slop()}
    overlap = words & enforced
    held_out = words - enforced
    print(f"\n  red-thread corpus: {n_scenes} scenes across {n_books} books")
    print(f"  red-thread enforces {len(enforced)} phrases; {len(overlap)} of them are on their "
          f"word list")
    print(f"  held-out list: {len(held_out)} of {len(words)} words "
          f"({len(held_out)/len(words):.0%} unaddressed by anything in this codebase)")

    full_w, full_t, n_tok = score(ours, words, trigrams)
    held_w, _ht, _n = score(ours, held_out, set())
    print(f"\n  our tokens: {n_tok:,}")
    print(f"  FULL      slop/1k = {full_w:6.2f}   trigram/1k = {full_t:.3f}")
    print(f"  HELD-OUT  slop/1k = {held_w:6.2f}   <- the arm that counts")

    # ---- the same two arms for the calibration models, so held-out is comparable --------
    print(f"\n  HELD-OUT comparison, same code and same held-out list on their raw text")
    print(f"  {'model':26} {'full':>8} {'held-out':>9}")
    print(f"  {'red-thread (pipeline)':26} {full_w:8.2f} {held_w:9.2f}")
    rows = []
    for fname, key in CALIBRATION.items():
        t = their_text(data / fname)
        f_w, _a, _b = score(t, words, trigrams)
        h_w, _c, _d = score(t, held_out, set())
        rows.append((key, f_w, h_w))
    for key, f_w, h_w in sorted(rows, key=lambda r: r[2]):
        print(f"  {key[:26]:26} {f_w:8.2f} {h_w:9.2f}")

    print(f"\n  human baseline, their published full-list figure: "
          f"{published['human-baseline']['slop_list_matches_per_1k_words']:.2f}")
    print("  (published only - their human corpus is not in the repo, so it cannot be")
    print("   re-scored on the held-out list and does NOT appear in the column above)")
    print("\n  Reminder from the pre-registration: this compares a gated, repaired,")
    print("  best-of-three PIPELINE against ungated single-pass model output. It favours the")
    print("  pipeline and is not a model-versus-model result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
