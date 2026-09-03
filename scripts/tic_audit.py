"""Which phrases are this model's tics, as opposed to a story's own vocabulary?

`duplication_ratio` takes ONE scene, so it measures repetition inside a scene and is blind by
construction to a phrase the writer reaches for once every ten scenes - which is the granularity
at which a reader notices a tic. The antislop list catches stock phrasing but is sourced from
sam-paech/antislop-sampler, i.e. derived from other models; measured here it covers none of the
phrases qwen3:8b actually repeats.

The hard part is telling a tic from premise vocabulary. "the ledger of time" recurs in 14% of
*Debt of Years* scenes and must - it is the novel's central object. "the weight of the" recurs in
22% and should not. No frequency threshold separates those two, and this project has already
shipped two contaminated measures that a threshold-only approach produced.

The separator used here needs no external corpus: **a phrase that also recurs in books of a
different premise cannot be this story's vocabulary.** Same logic as `checks.PORTABLE` and
`clears_noise(cross_book=True)`, applied to phrasing rather than to panel measures. It is not
perfect and the leak is known and one-directional: a tic that happens to carry a character name
("vay tilted his head") is classified premise-bound, so this UNDER-reports. Every phrase it does
report is cross-premise by construction.

Usage:  python scripts/tic_audit.py [--n 4] [--min-scenes 40] [--top 25] [--json OUT]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

WORD = re.compile(r"[a-z']+")


def load_corpus(runs_dir="runs"):
    """Scene text grouped by story title, so premises can be held apart."""
    by_title = collections.defaultdict(list)
    for d in sorted(pathlib.Path(runs_dir).iterdir()):
        story = d / "story.json"
        if not story.is_file():
            continue
        try:
            title = json.loads(story.read_text(encoding="utf-8")).get("title", "?")
        except (OSError, json.JSONDecodeError):
            continue
        for f in sorted((d / "scenes").glob("*.txt")):
            by_title[title].append(f.read_text(encoding="utf-8", errors="replace"))
    return by_title


def scene_frequency(scenes, n):
    """How many scenes each n-gram appears in - document frequency, not raw count.

    Document frequency rather than total occurrences on purpose: a phrase said six times in one
    scene is a within-scene problem `duplication_ratio` already reports. What is wanted here is
    the phrase the writer returns to across the book.
    """
    counts = collections.Counter()
    for text in scenes:
        words = WORD.findall(text.lower())
        counts.update({tuple(words[j:j + n]) for j in range(len(words) - n + 1)})
    return counts


def audit(by_title, main_title, n=4, min_scenes=40):
    main = by_title[main_title]
    other = [t for title, scenes in by_title.items() if title != main_title for t in scenes]
    main_df, other_df = scene_frequency(main, n), scene_frequency(other, n)

    tics, bound = [], []
    for gram, k in main_df.items():
        if k < min_scenes:
            continue
        elsewhere = other_df.get(gram, 0)
        row = {"phrase": " ".join(gram),
               "main_scenes": k, "main_rate": k / len(main),
               "other_scenes": elsewhere, "other_rate": elsewhere / max(1, len(other))}
        (tics if elsewhere else bound).append(row)
    tics.sort(key=lambda r: -r["other_rate"])
    bound.sort(key=lambda r: -r["main_rate"])
    return {"main_title": main_title, "n": n, "min_scenes": min_scenes,
            "main_scene_count": len(main), "other_scene_count": len(other),
            "tics": tics, "premise_bound": bound}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--min-scenes", type=int, default=40)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    by_title = load_corpus(args.runs)
    if not by_title:
        raise SystemExit(f"no runs with story.json under {args.runs}/")
    main_title = max(by_title, key=lambda t: len(by_title[t]))
    res = audit(by_title, main_title, args.n, args.min_scenes)

    print(f"  main premise : {res['main_title']}  ({res['main_scene_count']} scenes)")
    print(f"  held apart   : {len(by_title) - 1} other premises "
          f"({res['other_scene_count']} scenes)")
    print(f"  {args.n}-grams in >= {args.min_scenes} scenes of the main premise\n")

    print("  MODEL TIC - recurs in the main premise AND in unrelated ones")
    print(f"    {'phrase':32} {'main':>14} {'other premise':>16}")
    for r in res["tics"][:args.top]:
        print(f"    {r['phrase']:32} {r['main_scenes']:>5} {r['main_rate']:6.1%}"
              f"   {r['other_scenes']:>5} {r['other_rate']:6.1%}")

    print("\n  PREMISE VOCABULARY - absent from every other premise, correctly not a tic")
    for r in res["premise_bound"][:8]:
        print(f"    {r['phrase']:32} {r['main_scenes']:>5} {r['main_rate']:6.1%}"
              f"   {'0':>5}   0.0%")

    print(f"\n  {len(res['tics'])} cross-premise phrases, "
          f"{len(res['premise_bound'])} premise-bound")
    print("  Under-reports by design: a tic carrying a character name lands in the second list.")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"\n  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
