# Which measures survive the crossing between books

*1 September 2026. PLAN2 step 26, executed on the corpus as it exists — zero GPU-hours. The
enforceable consequence of [step 25](fresh-premise-panel.md): if the floor is one novel's, then
code, not discipline, must stop cross-book verdicts on measures whose floor does not transfer.*

## The groups that actually exist

The step was designed believing four premises had replicates. Measurement corrected it before
anything was computed:

- *The Four-Minute Tide* ×4 are **four different plans** (7, 8, 11 and 8 scenes) — regression
  runs, not replicates.
- `keeper` and `keeper2` differ in **both plan and story** (checked field-for-field) — two books
  from one premise, not two runs of one book.

So the honest within-premise groups are exactly two: ***The Debt of Years*** (floor1–4, n=4, the
published `NOISE_FLOOR`) and ***The Ink of the Drowned*** (solo-b2-panel1–2, n=2), which share a
writer verified by `scripts/same_code.py`. Between-premise evidence is therefore **one premise
pair**, and everything below inherits that limit.

## The test

A measure is **portable** iff all four hold:

1. its floor is established and informative (not degenerate, not wider than its mean);
2. it is not length-sensitive (24 scenes against 71 would compare lengths);
3. the second book's internal spread fits inside the floor — the floor's *size* transfers;
4. the gap between the two books' group means fits inside the floor — the *value* transfers.

## The result: 3 of 13

| measure | Debt n=4 | Ink n=2 | Ink spread | floor | between | verdict |
|---|---:|---:|---:|---:|---:|---|
| `refusal_per_ask` | .644 | .944 | 3% | 53% | 38% | **PORTABLE** |
| `refusal_rate` | .763 | 1.236 | 7% | 69% | 47% | **PORTABLE** |
| `somatic_share` | .373 | .312 | 13% | 19% | 18% | **PORTABLE** |
| `dialogue_share` | .202 | .169 | 13% | 11% | 18% | spread and gap both outside |
| `gesture_rate` | 1.883 | 2.812 | 10% | 22% | 40% | gap outside |
| `recap_grammar` | .035 | .064 | 10% | 59% | 59% | gap outside, by a hair |
| `duplication_scene` | .001 | .000 | 29% | 189% | 74% | floor uninformative |
| `recap_block_share` | .000 | .000 | 0% | 0% | 0% | floor degenerate — vacuous |
| `words`, `scenes`, `duplication_manuscript`, `repetition_concentration`, `worst_refrain` | | | | | | length-sensitive |

Now in code as `checks.PORTABLE`, and enforced: `clears_noise(..., cross_book=True)` raises on
anything outside it, and `redthread measures` detects two different titles by itself and prints
the non-portable rows as numbers with **no verdict** rather than as comparisons.

## The pre-registration, checked against the outcome

PLAN2 committed an expectation before this ran. Score it:

- **Right:** `gesture_rate`, `recap_grammar` and `dialogue_share` fail, as step 25 said they
  would.
- **Wrong:** `recap_block_share` was named a candidate ("zero-anchored counts"). It is zero in
  every group, which is *vacuous stability* — there is no floor to transfer and nothing this test
  could confirm. A measure pinned at zero everywhere cannot be shown portable; it can only fail
  to be shown anything.
- **Wrong in the useful direction:** "shares" as a class was the prediction, and `dialogue_share`
  — a share — fails condition 3 outright: its 13% spread on the second book exceeds its own 11%
  floor. Being a share does not make a measure portable; having a floor wide enough to absorb
  premise-to-premise character does.

And the finding nobody predicted: **the two refusal measures — the pair phase 4 was stopped over,
the pair that shipped 56% contaminated and was rebuilt — are the most premise-stable numbers in
the panel** (internal spreads of 3% and 7% on the second book). An instrument that failed as a
quality lever turns out to be the panel's best-behaved cross-book descriptor.

## `somatic_share` is portable across premises and *not* across code revisions

Found the same night, by a different analysis
([code-drift-floor.md](code-drift-floor.md)), and it qualifies this table rather than overturning
it. On four runs of **the same plan** written at four **different code revisions**:

    current 0.423    replicate 0.211    ledgerfix 0.592    tally6 0.380
    spread 95% of mean — against 19% within one revision, and 13% on the second book

Both groups in the portability table above were written at a single revision each, so the table
measures **premise-portability with the code held fixed** — which is what it claims and all it
claims. For `somatic_share` the code axis is far worse than the premise axis: 0.211 to 0.592 is
nearly threefold, on identical scene specs.

**Practical consequence:** a `somatic_share` figure quoted from an older evidence file must not be
compared against a current run. Of the three portable measures it is the one to distrust across
time, and the other two are the reverse — `refusal_rate` and `refusal_per_ask` spread only 21% and
12% across those same four revisions.

## Limits, stated before anyone quotes this

- The Ink side is **n=2**, which systematically understates spread — the same reason the floor
  went to n=4. Condition 3 is therefore *easier* to pass today than it should be, and
  `recap_grammar`'s one-point miss could flip either way at n=4.
- Between-premise spread is estimated from **one pair of premises**. A third premise group is the
  cheapest upgrade with real information in it.
- Both books are the same writer, same code, same genre register. Portability here means
  *across these two premises*, not across fiction — and, per the section above, not across code
  revisions either.
- **A `PORTABLE` comment in `checks.py` is owed and deliberately not yet written.** Phase 8 was on
  the GPU when this was found, and the night's own headline finding was a guard that read a
  different artefact than the one under test. Editing `checks.py` mid-experiment is exactly the
  thing this project has spent the night learning not to do, so it waits for the chain.

PLAN2 step 30 (+2 runs of `solo-b2`, ~1.5 GPU-h) upgrades the weakest of these three limits and
re-runs this table at n=4/n=4. `PORTABLE` errs toward refusing until then.

---

# The n=4 re-run: the set shrinks to two, and the stated limit is why

*2 September 2026, 03:15. Panels 3 and 4 written; both books now at n=4. The limit named above —
"the Ink side is n=2, which systematically understates spread, so condition 3 is easier to pass
today than it should be" — turned out to be the whole story.*

| measure | Debt n=4 | Ink n=4 | Ink spread | floor | between | verdict |
|---|---:|---:|---:|---:|---:|---|
| `refusal_per_ask` | .644 | .821 | 40% | 53% | 24% | **PORTABLE** |
| `refusal_rate` | .763 | 1.100 | 41% | 69% | 36% | **PORTABLE** |
| **`somatic_share`** | .373 | .323 | **52%** | 19% | 14% | **spread outside — drops out** |
| `dialogue_share` | .202 | .158 | 43% | 11% | 24% | both outside |
| `gesture_rate` | 1.883 | 2.858 | 23% | 22% | 41% | both outside |
| `recap_grammar` | .035 | .068 | 21% | 59% | 64% | between outside |

**`PORTABLE` = `refusal_rate`, `refusal_per_ask`. Two of thirteen, not three.**

`somatic_share` did not change its *value* between the books — the gap between means is 14%,
comfortably inside its 19% floor, and slightly *tighter* than at n=2. It failed on the other
condition: its spread *within* the second book is 52%, nearly three times its floor. The measure
is not disagreeing across premises; it is unstable inside one. That is exactly what condition 3
exists to catch, and at n=2 there were not enough samples to see it.

## How badly n=2 understated the spread

| measure | Ink n=2 | Ink n=4 | ×wider |
|---|---:|---:|---:|
| `refusal_per_ask` | 3% | 40% | **13.1×** |
| `refusal_rate` | 7% | 41% | 6.1× |
| `somatic_share` | 13% | 52% | 3.9× |
| `dialogue_share` | 13% | 43% | 3.5× |
| `gesture_rate` | 10% | 23% | 2.3× |
| `recap_grammar` | 10% | 21% | 2.2× |

Median **3.7×**. [Step 27](two-run-screen.md) measured the same direction on the *Debt* floor and
put it at about 2×; on a 24-scene book it is nearly four times, and for one measure thirteen.

**So step 27's protocol was right and its number was book-specific.** *An n=2 screen may kill and
may never confirm* holds a fortiori here — but "half the floor" is a *Debt*-of-Years figure, not a
constant, and quoting 2× on another book would understate the problem by a factor of two.

## What this cost, and what it saved

The change removes a measure from the set of things this project may compare across books. That is
a loss of reach and a gain in honesty: `somatic_share` was in `PORTABLE` for four hours on the
strength of a two-run spread, and any cross-book claim made on it in that window would have been
judged against a floor 3.9× too narrow.

The instrument caught it rather than a person: `scripts/portability.py` prints its set beside
`checks.PORTABLE`, saw them disagree, and **refused to authorise the edit** — requiring this
write-up first. That refusal is the only reason the sequence was write-up-then-code rather than
the reverse.
