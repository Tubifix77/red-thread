# Does the brief-side fix stop the mark wandering? Pre-registered before the runs

*2 September 2026, evening. Committed before a single scene is written at the new revision.
Thresholds below cannot move afterwards.*

## What was changed, and why it should work

A permanent physical mark drifts across body regions in **15 of 19** 60+-scene runs of *The Debt
of Years*. The cause was traced rather than guessed
([MEASUREMENTS.md](../MEASUREMENTS.md)): scene 15 established both
`[detail] Kai has a scar along his palm` and `[state] Kai feels the scar still burns faintly`, the
stratified slice kept the location-free state and dropped the location-bearing detail, and the
writer — told there was a scar but not where — put one on his temple. From scene 40 the ledger
carried "temple" to the end of the book.

Two changes to what the writer is told, neither touching the gate:

1. **Old-band slots ranked by kind, then specificity, then recency** — a `detail` cannot be
   re-established, a `state` can, and between two details the one with more content words is the
   one that prevents a contradiction. Details per slice went 5.0 → 15.9.
2. **Permanent marks get a reserved floor** of `limit // 5` slots, the exemption `knows` already
   has. Scenes whose slice carries a fixed mark: 73% → 96%; mean 1.5 → 6.7.

Scene 40's brief now shows `[s16] Kai has a scar on his palm` beside the arm variants from 31 and
32, so the writer can see the conflict and `conflict_candidates` can pair them.

A third change, to the check rather than the brief, is in the same revision and could matter:
`Ledger._latest_only` stopped the conflict judge silently discarding 86% of its candidate pairs.

## The design, and why n=2 is enough here

**This is the one place in this project where two runs can confirm something**, and the reason is
worth stating because [step 27](two-run-screen.md)'s protocol says the opposite for continuous
measures. The outcome is **binary per book** — does any permanent mark appear in two or more body
regions — and its base rate under the old writer is known and high:

    same plan, 60+ scenes, old writer:  15 of 19 wander
    clean rate:                          0.211

So two clean runs is **p = 0.211² = 0.044** under the null that the rate is unchanged. A mean of a
continuous measure at n=2 tells you nothing; a repeated Bernoulli trial with p=0.79 tells you
quite a lot.

- **Two runs** of the *Debt of Years* plan at the current revision, `qwen3:8b`, ~2.5 GPU-hours.
- Measured by `checks.wandering_details` over each run's own ledger — the same function, unchanged,
  that produced the 15-of-19 control.

## Thresholds, fixed now

- **Both runs clean → the fix is confirmed** (p = 0.044). Recorded as a real effect, with the
  caveat that n=2 on a binary outcome is exactly as strong as the arithmetic above and no
  stronger.
- **One clean, one wandering → no effect demonstrated.** 1-of-2 is what the old rate predicts
  (expected 0.42 clean of 2), and it would be reported as a failure to demonstrate, not as
  "partially worked".
- **Both wander → the fix does not work at the level that matters**, whatever the slice
  measurements say. That outcome would be the important one: it would mean putting the fact in
  front of the writer is not sufficient, and the next lever is the gate or the conflict judge,
  not the brief.

**A confound stated in advance:** three write-path changes landed together, so a clean result
cannot be attributed to the slice changes alone — the conflict-judge fix is in the same revision
and could plausibly catch a drift the brief failed to prevent. Distinguishing them needs a third
condition and is not attempted. If both runs come back clean, the honest claim is *"this
revision"*, not *"the reservation"*.

**And the old floor is now historical.** Three write-path changes mean `runs/.floor-commit` no
longer describes this writer, so no panel measure from these runs may be compared against
`checks.NOISE_FLOOR`. This test uses only the binary outcome, which needs no floor.

## Clarification added mid-run: which revision these runs actually test

*Added 3 September 00:05, before any result was measured. **No threshold above is touched** —
this records a fact about the runs that would be worthless discovered afterwards.*

The runs do **not** test HEAD. Verified from process and commit timestamps rather than assumed:

    writer process started        2026-09-02 23:56:49
    ledger.py as loaded by it     61c6d21  (19:12) -- kind/specificity ranking + mark reservation
    a later ledger.py change      3925896  (00:00:46) -- contentless-detail demotion

Python imports at process start, so the running writer holds `ledger.py` as of **61c6d21** and
never saw the demotion commit that landed four minutes into the resumed run. `markfix1` was
written entirely under that same revision.

**So both runs share one writer and remain comparable to each other**, which is what the binary
test needs — but the result speaks for 61c6d21, not for HEAD. A later change to the slice needs
its own runs.

*This is the on-disk-versus-running distinction that
[the guard hole](../MEASUREMENTS.md) was about, arriving from the other direction: there it meant
an uncommitted edit silently reached the writer, here it means a committed one silently did not.
Either way the only trustworthy question is what the process loaded.*

---

*Result appended below after the runs. Nothing above changes.*
## Result: FAIL on the pre-registered criterion

*Appended 3 September. Both runs completed 71 scenes with no halts, at revision `61c6d21`.*

Scored with `checks.wandering_details` unchanged, the function that produced the control:

    current-markfix1: 979 facts -> WANDERS
        Kai's scar: arm [1,4,7,12,15,32,33,42,47,52,53,59,65]; hand [12]
    current-markfix2: 999 facts -> WANDERS
        Kai's scar: arm [53,55,58,59,63,68,69]; hand [51,52]
        Vay's scar: arm [56]; hand [32,61]

**Both wander. The pre-registered threshold for this outcome was "the fix does not work at
the level that matters, whatever the slice measurements say."** That is the verdict, and it
stands. The slice measurements did move — details per slice 5.0 to 15.9, scenes carrying a
fixed mark 73% to 96% — and the pre-registration said in advance that this would not save
the fix. It does not. The next lever is the gate or the conflict judge, not the brief.

## A separate finding: the check over-fires, and the 15-of-19 headline was inflated

Auditing the flags above turned up two defects in `wandering_details` itself. Both are
statements about the check, not about the writer, and both would be true had the runs come
back clean:

1. **Plurals.** markfix1's scene 12 holds `scar along inner elbow` and `scars on hands`.
   `scars` is in `_MARK_NOUNS`, so a general remark about hands is read as a claim about
   *the* scar's location. A plural mark noun is not a claim about one mark.
2. **Contiguous regions.** `wrist` sits in the `hand` region while `forearm` sits in `arm`,
   but they meet at a joint. markfix2 has `a scar on his wrist` (51) and `a scar on his
   forearm` (58) - one scar near a boundary, described from either side. Vay's is explicit:
   a scar running `from elbow to wrist`, which spans the two regions by construction.

Correcting both, on the same 19 control runs:

    as shipped              17 of 21 long books flagged (81%)
    + plural-aware          15 of 21                    (71%)
    + adjacency-aware       13 of 21                    (62%)
    + both                  12 of 21                    (57%)

    control only (19 pre-fix runs), both fixes: 12 of 19 wander (63%)

**So the published 15 of 19 (79%) was wrong; the rate is 63%.** About three in ten flags
were the check's own artefacts. This is the third correction to this finding - first the
length attribution was withdrawn, now the rate itself - and the pattern is the one already
on the record as Rule I's cousin: a number nobody has read the matches for is not yet a
measurement.

The adjacency correction is **not fitted to tonight's flags**. Extending it from the single
`hand/arm` pair to a complete anatomical graph (`arm/torso`, `head/torso`, `torso/leg` as
well) changes no run's classification in either direction - those pairs never fire in 21
books. The correction rests on anatomy, not on what happened to be flagged.

## What is deliberately not concluded

Under the corrected check, both new runs are clean and `current` still wanders across three
regions including `head`, which is adjacent to nothing in the flag. That looks like the fix
working.

**It is not reported as evidence, because the correction was derived from these two runs'
own flags.** Re-reading the same data with an instrument reshaped after seeing it is the
move [step 28](step28-preregistration.md) exists to forbid; there the pre-registered screen
gave a false negative and the answer was *more runs*, never a softer screen. It is recorded
here rather than omitted because a suppressed favourable number is worse than a labelled
one, but it settles nothing.

**The n=2 design is also dead for this measure.** Two clean runs was worth p=0.044 only
because the control rate was believed to be 0.79. At the corrected 0.63 the clean rate is
0.368 and:

    2 clean runs by chance   0.136
    3 clean runs by chance   0.050
    4 clean runs by chance   0.018   <- first n reaching p<0.05

A clean re-test needs **four runs**, roughly five GPU-hours, against the corrected check
with the control rate re-derived above. That is pre-registered separately and has not been
run. Fixing the instrument cost this test its statistical power, which is the honest price
of having measured the instrument at all.
