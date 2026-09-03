"""Build a fresh forced-choice sheet by sampling the corpus, not the old hundred.

`pairs.md` is spent: ChatGPT's 29 answers were shown to Tue, so his own choices would be
anchored (toward the null, since those answers are 79% A - it cannot manufacture a false
positive, but it can hide a real effect). The corpus is 1,700+ scenes, so the pool was never
the limit; the old sheet was one sample of it.

Three things are controlled by construction rather than argued about afterwards:

  ERA      re-derived mechanically per book, not read off a stale list of nine. A current-era
           book is one where no scene carries a run of 4 consecutive past-perfect sentences
           (`checks.recap_blocks`), which is the marker MEASUREMENTS.md defines.
  FORM     narration only. The old pool was 12% dialogue on one side and 42% on the other, and
           splitting to control for that left n=6 in a cell.
  LENGTH   each pair matched on word count, because the two eras differ in median length.

Usage:  python scripts/build_pairs2.py [--pairs 40] [--seed N]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import re
import statistics as st
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from redthread import checks

SENT = re.compile(r"[^.!?]+[.!?]+")
# A sentence is unusable as a blind stimulus if it cannot stand alone. Openers that point at
# something the rater cannot see ("But now,", "That was when") make the task about missing
# context rather than about the writing.
DANGLING = re.compile(
    r"^\s*(but|and|so|then|that|those|these|it|this|which|nor|yet|because|whereas"
    r"|or|also|though|although|instead|otherwise|still|even)\b", re.I)
# Unquoted dialogue is the trap the quote-mark filter misses entirely: "Tell me the name of the
# thief who stole these years" carries no quote marks and is plainly speech. Third-person past
# narration does not address anybody, so any first- or second-person pronoun disqualifies a
# sentence as a narration stimulus. It costs some legitimate free indirect style and is worth
# it — a rater comparing a line of dialogue against a line of narration is rating form, not prose.
PERSONAL = re.compile(r"\b(i|me|my|mine|you|your|yours|we|us|our|ours)\b", re.I)
# A verbless fragment ("A choice to live, to survive, to breathe another year") gives the rater
# nothing to prefer. Requiring a finite verb somewhere is crude but effective at excluding a
# stimulus that never predicates anything.
HAS_VERB = re.compile(
    r"\b(\w+ed|was|were|had|has|is|are|felt|saw|knew|said|stood|sat|held|kept|took|came|went"
    r"|made|gave|found|left|turned|moved|looked|watched|waited|began|seemed|lay|drew|shook)\b",
    re.I)


def classify_books(runs_dir="runs", min_scenes=6, title=None):
    """(current_era, pre_prose_work) book directories, by the mechanical marker.

    `title` holds the premise fixed, and it matters more than the sample size it costs. Without
    it the old side pulls in `glitch`, `register`, `verify` - different novels - and the rater is
    then comparing stories rather than prose. With it there is exactly ONE pre-prose-work book of
    *The Debt of Years*, `debt` at 27 scenes, so the whole old side comes from a single book.
    That is a real limitation of the corpus and not a choice: book-level variance cannot be
    estimated from one book, so a result here speaks for `debt` against the current era and not
    for the era in general. The original hundred-sentence sheet had the same constraint.
    """
    cur, pre = [], []
    for d in sorted(pathlib.Path(runs_dir).iterdir()):
        scenes = sorted((d / "scenes").glob("*.txt"))
        if len(scenes) < min_scenes:
            continue
        if title is not None:
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
        (cur if recappy == 0 else pre).append((d.name, texts, recappy / len(texts)))
    return cur, pre


def harvest(books, used, lo=9, hi=30):
    """Narrated, self-contained sentences of usable length, deduplicated."""
    out = []
    for name, texts, _rate in books:
        for t in texts:
            for raw in SENT.findall(t):
                s = " ".join(raw.split())
                if '"' in s or chr(8220) in s or chr(8221) in s:
                    continue                      # any dialogue at all -> not narration
                n = len(s.split())
                if not (lo <= n <= hi) or DANGLING.match(s):
                    continue
                if PERSONAL.search(s) or not HAS_VERB.search(s):
                    continue
                if s[:1].islower() or s.count(",") > 4:
                    continue        # a mid-sentence split, or a comma-spliced list
                k = s.lower()
                if k in used:
                    continue
                used.add(k)
                out.append((name, s, n))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=40)
    ap.add_argument("--seed", type=int, default=903)
    ap.add_argument("--title", default="The Debt of Years",
                    help="hold the premise fixed; '' to allow any")
    ap.add_argument("--out", default="docs/evidence/sentences/pairs2.md")
    ap.add_argument("--key", default="docs/evidence/sentences/pairs2-key.md")
    args = ap.parse_args(argv)

    cur_books, pre_books = classify_books(title=args.title or None)
    print(f"  current-era books  : {len(cur_books)}  "
          f"({', '.join(n for n, _t, _r in cur_books[:6])}...)")
    print(f"  pre-prose-work books: {len(pre_books)}  "
          f"({', '.join(n for n, _t, _r in pre_books[:6])}...)")

    # Every sentence already used on the old sheet is excluded, both sides.
    used = set()
    old = pathlib.Path("docs/evidence/sentences/sentences-key.md")
    if old.is_file():
        for line in old.read_text(encoding="utf-8").split("\n"):
            m = re.match(r"\s*\d+\s+\S+\s+(spoken|narrated)\s+(.*)$", line)
            if m:
                used.add(" ".join(m.group(2).split()).lower())
    print(f"  excluded as already seen: {len(used)} sentences")

    rng = random.Random(args.seed)
    cur_pool = harvest(cur_books, set(used))
    pre_pool = harvest(pre_books, set(used))
    print(f"  usable narrated sentences: current-era {len(cur_pool)}, "
          f"pre-prose-work {len(pre_pool)}")

    rng.shuffle(cur_pool)
    rng.shuffle(pre_pool)
    by_len = {}
    for name, s, n in pre_pool:
        by_len.setdefault(n, []).append((name, s))

    pairs = []
    for name, s, n in cur_pool:
        if len(pairs) >= args.pairs:
            break
        for delta in (0, 1, 2):                  # tight length match or skip it
            for cand in (n - delta, n + delta):
                if by_len.get(cand):
                    pname, ps = by_len[cand].pop()
                    pairs.append((name, s, pname, ps))
                    break
            else:
                continue
            break
    if len(pairs) < args.pairs:
        raise SystemExit(f"only matched {len(pairs)} pairs; lower --pairs")

    gaps = [abs(len(c.split()) - len(p.split())) for _a, c, _b, p in pairs]
    print(f"  {len(pairs)} pairs; word gap median {st.median(gaps):.1f}, max {max(gaps)}")

    n = len(pairs)
    sides = ["A"] * (n // 2) + ["B"] * (n - n // 2)
    import itertools
    while True:
        rng.shuffle(sides)
        if max(len(list(g)) for _k, g in itertools.groupby(sides)) <= 3:
            break

    sheet = [f"# {n * 2} sentences, in {n} pairs",
             "",
             "Every line is narration, machine-written, from the same novel by the same model at",
             "two different revisions. **There is no human side and nothing to detect.** Pairs are",
             "matched on form and word count, so the only thing left to prefer is the writing.",
             "",
             "For each pair write **A** or **B**: *which would you rather read on from?*",
             "",
             "Pick one. If they feel identical, take the one your eye went to first and move on -",
             "that first reaction is the measurement. A considered second look is you doing the",
             "instrument's job, and a tie is the one answer this cannot use.",
             "",
             f"About {max(10, n // 3)} minutes. Do not open the key until you are finished.",
             ""]
    key = [f"# Key - do not read before choosing",
           "",
           f"{n} forced choices, null 50%. Side assignment is balanced ({sides.count('A')}/"
           f"{sides.count('B')}) with no run over 3, so a rater who simply always picks the first",
           "option scores chance rather than drifting toward the threshold.",
           ""]

    for i, (cname, ctext, pname, ptext) in enumerate(pairs, 1):
        cur_is_a = sides[i - 1] == "A"
        a, b = (ctext, ptext) if cur_is_a else (ptext, ctext)
        sheet += [f"**{i}.**  [ ]", f"  - **A**  {a}", f"  - **B**  {b}", ""]
        key.append(f"  {i:>2}  current-era = {'A' if cur_is_a else 'B'}   "
                   f"[{cname} / {pname}]")

    from math import comb
    thresh = next(k for k in range(n // 2, n + 1)
                  if sum(comb(n, x) for x in range(k, n + 1)) / 2 ** n < 0.05)
    key += ["",
            "## A limitation of the corpus, not a choice",
            "",
            "The premise is held fixed at one novel, because letting it vary pulls different",
            "stories onto the old side and turns the task into story preference. The cost is that",
            "*The Debt of Years* has exactly **one** pre-prose-work book, `debt` at 27 scenes, so",
            "the whole old side comes from a single book. Book-level variance cannot be estimated",
            "from one book, so a result here speaks for `debt` against the current era and not for",
            "the era in general. The original hundred-sentence sheet had the same constraint and",
            "did not say so.",
            "",
            "## Reading the result, fixed before any choice is made",
            ""]
    for k in range(thresh - 1, min(n, thresh + 3)):
        p = sum(comb(n, x) for x in range(k, n + 1)) / 2 ** n
        key.append(f"    {k:>2} of {n} or more  ->  p = {p:.3f}"
                   + ("   <- threshold" if k == thresh else ""))
    key += ["",
            f"**The threshold is {thresh} of {n}.** Below it is not a result in either direction;",
            f"{n - thresh} or fewer is the same evidence reversed. A count in the middle means the",
            "two revisions are not distinguishable by a reader at this n - a real finding, and one",
            "that would retire a good deal of speculative work.",
            ""]

    pathlib.Path(args.out).write_text("\n".join(sheet), encoding="utf-8")
    pathlib.Path(args.key).write_text("\n".join(key), encoding="utf-8")
    print(f"  threshold {thresh}/{n}; wrote {args.out} and {args.key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
