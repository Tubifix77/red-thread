# Step 28, pre-registered before the ablated runs existed

*2 September 2026, 00:19. The `--no-model-refrains` runs are in flight: **run 1 at 10 of 71
scenes, run 2 at 0** — 10 of 142, verified at commit time, not estimated. No measurement of them
has been taken. Everything below is committed before any result
exists, which is the only thing that makes the added statistic a test rather than a story. Same
discipline as step 6's accumulation statistic, and for the same reason.*

## First: this mechanism is not the last one

Step 29's stage 1 found the re-people pass has never run on a measured book, because it is gated
at 15% and the corpus plan sits at 14.08% ([repeople-never-fired.md](repeople-never-fired.md)).
The obvious next question is whether the mechanism now on the GPU has the same problem. It does
not, and this was checked before the runs were left alone:

`load_model_refrains()` is **unconditional** — `pipeline.py` loads it whenever
`config.model_refrains` is true (the default), and `brief.py` injects it whenever the list is
non-empty. The list is three phrases: *"the edge of the"*, *"the weight of the"*, *"eyes fixed on
the"*. They go into **every brief of every scene**. Step 28 is therefore a real ablation of a
mechanism that fires 100% of the time, and the contrast with step 29 is the point: two mechanisms,
both "untested", one inert and one maximally active.

The same audit clears both mechanisms phase 1 kept, replaying each floor book's committed prefix
to see what its briefs actually said:

| mechanism | scenes where it named something | first fires |
|---|---|---|
| refrain feedback | 77–96% | scene 4–17 |
| gesture feedback | 62–83% | **scene 13–28** |

**And that last column is independent corroboration of step 6.** The gesture feedback is *silent
for the first fifth to third of every book* — mean first fire at scene 22 of 71 — because it needs
four recurrences before it can name anything. Q1 is largely untreated by construction. That is
exactly why a first-quarter-to-last-quarter statistic sees the effect and a whole-book mean cannot,
and it is derived here from the mechanism's own behaviour rather than from the outcome data that
originally suggested it.

## The pre-registered addition

PLAN2's kill criterion stands unchanged and is still primary: **`duplication_manuscript` (floor
19%) and `repetition_concentration` (floor 38%) both inside their floors → the list comes out of
the brief.**

Added now, as a *secondary, targeted* statistic, because those two are manuscript-wide aggregates
and this mechanism has three named targets — a panel measure could easily miss a real effect
confined to three phrases:

**Statistic:** occurrences of the three listed phrases per 10,000 words, whole manuscript,
case-insensitive. Manuscript-level aggregate, so accumulation is already in the number
(rule VII typed).

**Control, measured now from the four floor runs (list ON):**

| run | hits | words | per 10k |
|---|---:|---:|---:|
| floor1 | 34 | 60,573 | 5.61 |
| floor2 | 36 | 61,352 | 5.87 |
| floor3 | 29 | 61,189 | 4.74 |
| floor4 | 38 | 61,712 | 6.16 |

**mean 5.59 per 10k, range 4.74–6.16, spread 25% of mean (n=4).**

**Prediction:** if naming these constructions suppresses them, the ablated runs sit **higher**,
by more than the 25% floor — i.e. above ~7.0 per 10k.

**How it will be read, decided now:**

- *Both panel measures inside their floors AND the targeted rate inside 25%* → the list does
  nothing measurable. It comes out of the brief. (The data file stays; it is a measurement.)
- *Panel inside, targeted rate outside* → the list suppresses its own three phrases without
  moving book-level repetition. It **stays**, restated honestly as a narrow phrase filter rather
  than a repetition mechanism — and PLAN2's claim for it shrinks accordingly.
- *Panel outside* → the pre-registered criterion answers on its own terms and this statistic is
  a footnote.

**The trap this is written to avoid:** if the targeted rate comes back higher and the panel does
not, the tempting move is to call the mechanism confirmed. It would not be. It would be confirmed
*at suppressing three phrases*, which is a smaller claim than the one the brief text makes
("they are yours, and a reader meets them on every page"), and the difference between those two
claims is the whole lesson of the 56%-contaminated refusal measures.

## One number worth noticing before any of that

Even with the list **on**, these three phrases appear 5.59 times per 10,000 words — roughly once
every two scenes. The prohibition is explicit, arrives in every brief, and is not obeyed. Whatever
step 28 concludes about the *difference*, the absolute level says the mechanism is at best
partial, and that is visible in the control alone.
