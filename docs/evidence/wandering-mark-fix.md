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

---

*Result appended below after the runs. Nothing above changes.*
