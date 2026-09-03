"""Build a forced-choice sheet from the hundred-sentence pool.

Why not the 3-point sheet: absolute ratings with no anchor are hard, and the pool turns out to
carry a confound that absolute ratings cannot escape - pre-prose-work is 12% dialogue and
current-era is 42%. Splitting the 3-point result on form to control for that leaves n=6 on one
cell. Forced choice inside matched pairs removes the confound by construction instead.

Legitimate to switch now for one reason only: no ratings exist yet. This is instrument design
before data, not a re-score after seeing it.
"""
import pathlib
import random
import re
import statistics as st

KEY = pathlib.Path("docs/evidence/sentences/sentences-key.md")
OUT = pathlib.Path("docs/evidence/sentences/pairs.md")
OUTKEY = pathlib.Path("docs/evidence/sentences/pairs-key.md")

rows = {}
for line in KEY.read_text(encoding="utf-8").split("\n"):
    m = re.match(r"\s*(\d+)\s+(\S+)\s+(spoken|narrated)\s+(.*)$", line)
    if m:
        rows[int(m.group(1))] = (m.group(2), m.group(3), m.group(4).strip())

pre = [(n, rows[n][2]) for n in sorted(rows)
       if rows[n][0] == "pre-prose-work" and rows[n][1] == "narrated"]
cur = [(n, rows[n][2]) for n in sorted(rows)
       if rows[n][0] == "current-era" and rows[n][1] == "narrated"]

def words(s):
    return len(s.split())

# Greedy length matching: each current-era sentence takes the closest unused pre-prose-work one.
# Length is a real confound here (medians 17 against 14) and it is free to remove.
pool = list(pre)
pairs = []
for n_cur, t_cur in sorted(cur, key=lambda p: -words(p[1])):
    best = min(pool, key=lambda p: abs(words(p[1]) - words(t_cur)))
    pool.remove(best)
    pairs.append((n_cur, t_cur, best[0], best[1]))

deltas = [abs(words(c) - words(p)) for _nc, c, _np, p in pairs]
print(f"  {len(pairs)} matched narrated pairs")
print(f"  word-count gap within a pair: median {st.median(deltas):.1f}, max {max(deltas)}")
print(f"  current-era median {st.median([words(c) for _a, c, _b, _d in pairs]):.1f} words, "
      f"pre-prose-work median {st.median([words(p) for _a, _c, _b, p in pairs]):.1f}")

rng = random.Random(20260903)
rng.shuffle(pairs)

sheet = ["# Fifty-eight sentences, in twenty-nine pairs",
         "",
         "Each pair is two sentences of narration from the same novel, written by the same model",
         "at two different revisions. Both are machine-written; there is no human side and nothing",
         "to detect. The pairs are matched on form and on length so the only thing left to prefer",
         "is the writing.",
         "",
         "For each pair, circle or write **A** or **B**: *which one would you rather read on from?*",
         "",
         "You must pick one. If they feel identical, pick the one your eye went to first and move",
         "on - that is the measurement. Ties are the one answer this cannot use, and a considered",
         "second look is you doing the instrument's job.",
         "",
         "Should take ten minutes. Do not open `pairs-key.md` until you are finished.",
         ""]
key = ["# Key - do not read before choosing",
       "",
       "`A` / `B` gives which side held the current-era sentence. Original sheet numbers in",
       "brackets. All pairs are narrated and length-matched, so form and length are controlled",
       "by construction rather than by a post-hoc split.",
       ""]

# Side assignment is balanced and de-clustered rather than left to the coin. An unbalanced
# split interacts with position bias, which is a real effect in forced choice: a rater who
# simply prefers the first option scores whatever the A-count happens to be, and the first
# draft of this sheet put current-era on side A 17 times of 29 against a threshold of 20. A
# 15/14 split makes pure position bias score 15, which is chance. The run cap is for the
# rater's benefit - eight pairs in a row with the answer on one side reads as a pattern.
sides = ["A"] * 15 + ["B"] * 14
while True:
    rng.shuffle(sides)
    longest = max(len(list(g)) for _k, g in __import__("itertools").groupby(sides))
    if longest <= 3:
        break

for i, (n_cur, t_cur, n_pre, t_pre) in enumerate(pairs, 1):
    cur_is_a = sides[i - 1] == "A"
    a, b = (t_cur, t_pre) if cur_is_a else (t_pre, t_cur)
    sheet.append(f"**{i}.**  [ ]")
    sheet.append(f"  - **A**  {a}")
    sheet.append(f"  - **B**  {b}")
    sheet.append("")
    key.append(f"  {i:>2}  current-era = {'A' if cur_is_a else 'B'}   "
                f"[#{n_cur} current-era, #{n_pre} pre-prose-work]")

key += ["",
        "## Reading the result",
        "",
        "29 forced choices, null 50%. Under the null that the two revisions are indistinguishable,",
        "the count of current-era wins is Binomial(29, 0.5):",
        "",
        "    20 of 29 or more  ->  p = 0.031",
        "    21 of 29 or more  ->  p = 0.014",
        "    22 of 29 or more  ->  p = 0.005",
        "",
        "Fewer than 20 is not a result in either direction; 9 or fewer would be the same evidence",
        "the other way round. **The threshold is 20 and it is fixed here, before any choice is",
        "made.** A count of 15 to 19 means the revisions are not distinguishable by a reader at",
        "this n, which is a real finding and kills a good deal of speculative work.",
        ""]

OUT.write_text("\n".join(sheet), encoding="utf-8")
OUTKEY.write_text("\n".join(key), encoding="utf-8")
print(f"  wrote {OUT} and {OUTKEY}")
