"""Do model raters of different lineage separate the two prose eras, on passages?

Replaces the cut human sheet ([docs/evidence/no-human-rater.md]). Three things distinguish this
from the sheets that failed:

  UNIT        passages of ~130 words, not decontextualised sentences. That was the flaw that
              killed all three human designs, in Tue's words: choosing between a police cruiser
              and a fire engine without being told whether it is for a party, a fire or a crime.
              A sentence has no job, so its fitness cannot be judged - and the largest measured
              defect in this prose (`the weight of` in ~72% of scenes) is invisible in any single
              sentence because every instance of it reads fine.

  ORDER       every pair is asked TWICE with the sides swapped. ChatGPT picked the first option
              23 times in 29, so position bias is not hypothetical - it was the dominant signal
              in the only rater tried so far. A pair counts only if the model picks the same
              PASSAGE in both orders; otherwise it is position-bound and excluded, and the
              exclusion rate is reported as that rater's reliability rather than hidden.

  LINEAGE     several unrelated model families, plus the writer itself as a control. qwen3:8b
              wrote this prose, so it is the rater that SHOULD show self-preference (rule II). If
              only qwen3 favours the current era, the effect is self-preference and not a property
              of the prose; if unrelated families agree, it is not.

What a positive result licenses, stated before running: "model families of different lineage
consistently prefer current-era passages". NOT "the prose is better", and NOT "readers prefer
it". No human reader has ever been measured here and none will be.

Usage:
  python scripts/rater_panel.py --pairs 24 --models gemma3:12b,phi4:14b,deepseek-r1:8b,qwen3:8b
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import random
import re
import statistics as st
import sys
from math import comb

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from redthread import checks
from redthread.llm import Models

SENT = re.compile(r"[^.!?]+[.!?]+")

PROMPT = """Below are two passages, A and B, from a novel.

Read both. Then answer with one letter only: which passage would you rather keep reading?

PASSAGE A
{a}

PASSAGE B
{b}

Answer with a single character, A or B, and nothing else."""


def classify(runs_dir="runs", title="The Debt of Years", min_scenes=6):
    """(current_era, pre_prose_work) books of one premise, by the mechanical era marker."""
    cur, pre = [], []
    for d in sorted(pathlib.Path(runs_dir).iterdir()):
        scenes = sorted((d / "scenes").glob("*.txt"))
        if len(scenes) < min_scenes:
            continue
        story = d / "story.json"
        if not story.is_file():
            continue
        try:
            if json.loads(story.read_text(encoding="utf-8")).get("title") != title:
                continue
        except (OSError, json.JSONDecodeError):
            continue
        texts = [f.read_text(encoding="utf-8", errors="replace") for f in scenes]
        recappy = sum(1 for t in texts if checks.recap_blocks(t))
        (cur if recappy == 0 else pre).append((d.name, texts))
    return cur, pre


def passages(books, lo=110, hi=160):
    """Contiguous runs of whole sentences in the target word range, from mid-scene.

    Mid-scene on purpose: a scene opening does structural work an excerpt cannot show, so
    including openings would have the rater comparing scene-setting against continuous prose.
    """
    out = []
    for name, texts in books:
        for t in texts:
            sents = [" ".join(s.split()) for s in SENT.findall(t)]
            if len(sents) < 12:
                continue
            i = len(sents) // 4                     # skip the opening quarter
            while i < len(sents) - 1:
                chunk, n = [], 0
                j = i
                while j < len(sents) and n < lo:
                    chunk.append(sents[j])
                    n += len(sents[j].split())
                    j += 1
                if lo <= n <= hi and len(chunk) >= 3:
                    out.append((name, " ".join(chunk), n))
                i = j if j > i else i + 1
    return out


def build_pairs(cur_books, pre_books, n_pairs, rng, tol=0.15):
    cur = passages(cur_books)
    pre = passages(pre_books)
    rng.shuffle(cur)
    rng.shuffle(pre)
    print(f"  passages available: current-era {len(cur)}, pre-prose-work {len(pre)}")
    pairs, used = [], set()
    for cname, ctext, cn in cur:
        if len(pairs) >= n_pairs:
            break
        best = None
        for k, (pname, ptext, pn) in enumerate(pre):
            if k in used:
                continue
            if abs(pn - cn) / cn <= tol:
                best = k
                break
        if best is None:
            continue
        used.add(best)
        pname, ptext, pn = pre[best]
        pairs.append({"cur_book": cname, "cur": ctext, "cur_words": cn,
                      "pre_book": pname, "pre": ptext, "pre_words": pn})
    return pairs


# A reasoning model needs room to finish thinking before it can emit an answer at all, and some
# ignore `think=False` entirely. Measured on deepseek-r1:8b: at num_predict 8, 64, 512 and 1024
# the content field comes back EMPTY with done_reason "length" - it is still reasoning when the
# budget runs out - and only at 4096 does it stop and answer, having spent 10,557 characters of
# scratchpad to produce "A". An 8-token budget silently produced no data from that rater for a
# whole run, which is the same class of failure as a check that reports clean when it cannot read
# its input: no error, no answer, and nothing in the output saying which.
REASONING_BUDGET = 4096
STRAIGHT_BUDGET = 8


def budget_for(name):
    return REASONING_BUDGET if re.search(r"r1|reason|think|qwq", name, re.I) else STRAIGHT_BUDGET


def ask(model, a, b, max_tokens=STRAIGHT_BUDGET):
    """One forced choice. Returns 'A', 'B' or None if the reply is not a clean letter."""
    reply = model.critic.complete(PROMPT.format(a=a, b=b),
                                  max_tokens=max_tokens, temperature=0.0)
    m = re.search(r"\b([AB])\b", (reply.text or "").strip().upper())
    return m.group(1) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=24)
    ap.add_argument("--models", default="gemma3:12b,phi4:14b,deepseek-r1:8b,qwen3:8b")
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--seed", type=int, default=903)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    cur_books, pre_books = classify()
    print(f"  books: current-era {len(cur_books)}, pre-prose-work {len(pre_books)}")
    pairs = build_pairs(cur_books, pre_books, args.pairs, rng)
    if len(pairs) < args.pairs:
        print(f"  WARNING: only built {len(pairs)} pairs")
    gaps = [abs(p["cur_words"] - p["pre_words"]) for p in pairs]
    print(f"  {len(pairs)} pairs; word gap median {st.median(gaps):.0f}, max {max(gaps)}\n")

    results = {}
    for name in [m.strip() for m in args.models.split(",") if m.strip()]:
        model = Models.local(name, name, args.base_url, native=True)
        tokens = budget_for(name)
        consistent = cur_wins = position_bound = unparsed = 0
        first_choice = collections.Counter()
        for p in pairs:
            # Order 1: current-era as A. Order 2: current-era as B. A real preference picks the
            # same PASSAGE both times; position bias picks the same LETTER both times.
            r1 = ask(model, p["cur"], p["pre"], tokens)
            r2 = ask(model, p["pre"], p["cur"], tokens)
            if r1 is None or r2 is None:
                unparsed += 1
                continue
            first_choice[r1] += 1
            if r1 == r2:                       # same letter twice = position-bound
                position_bound += 1
                continue
            consistent += 1
            if r1 == "A":                      # chose current-era in order 1, and B in order 2
                cur_wins += 1
        results[name] = {"consistent": consistent, "cur_wins": cur_wins,
                         "position_bound": position_bound, "unparsed": unparsed,
                         "budget": tokens,
                         "first_A": first_choice["A"], "first_B": first_choice["B"]}
        n = consistent
        if n:
            p_val = 2 * min(
                sum(comb(n, x) for x in range(cur_wins, n + 1)) / 2 ** n,
                sum(comb(n, x) for x in range(0, cur_wins + 1)) / 2 ** n)
            p_val = min(1.0, p_val)
        else:
            p_val = float("nan")
        results[name]["p"] = p_val
        bound_rate = position_bound / len(pairs)
        flag = ("  UNUSABLE: no parseable answer" if consistent + position_bound == 0
                else f"  EXCLUDED: {bound_rate:.0%} position-bound" if bound_rate > 0.50
                else "")
        print(f"  {name:22} usable {n:>2}/{len(pairs)}  current-era {cur_wins:>2}/{n or 1}"
              f"  bound {position_bound:>2} ({bound_rate:>3.0%})  unparsed {unparsed:>2}"
              f"  p={p_val:.3f}{flag}")

    print("\n  usable = picked the same passage in both orders. position-bound = same letter")
    print("  twice, i.e. the rater answered by position and not by prose.")
    print("  qwen3 wrote this prose: it is the self-preference control, not a panel member.")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(
            {"pairs": pairs, "results": results, "seed": args.seed}, indent=2),
            encoding="utf-8")
        print(f"\n  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
