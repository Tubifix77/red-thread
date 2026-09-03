# The conflict judge misses 58% of wandering marks — baseline, then a pre-registered fix

*3 September 2026. The baseline below is measured. The criterion below it is fixed before the
revised prompt exists.*

## Why the judge, and rule VIII first

The brief-side fix failed ([wandering-mark-fix.md](wandering-mark-fix.md)), and its
pre-registration named the consequence in advance: *"putting the fact in front of the writer is
not sufficient, and the next lever is the gate or the conflict judge, not the brief."*

Rule VIII says confirm the thing happens before measuring a difference in it. It does. Rebuilding
the shipped book's ledger as of scene 39 and offering scene 40's temple fact as new:

    candidate pairs offered by scene 40   25
    of which mention a scar                5
    s15 "a scar along his palm"  vs  s40 "a scar running along his temple"   position 22
    s16 "a scar on his palm"     vs  s40 "a scar running along his temple"   position 23

**The pair is generated and it is judged.** It cleared the `max_pairs=25` cap by two slots, at the
very tail of the list. So the judge was asked the right question about the founding defect of this
whole investigation and answered no.

*Worth recording separately: two slots of headroom is not a margin. A slightly busier scene and
the real contradiction falls off the end of the cap — which is what `conflict_check_truncated`
now exists to make audible, and a reason list order deserves its own look.*

## Baseline

`scripts/judge_marks.py`, `qwen3:8b`, 3 repetitions, pairs shuffled every repetition because
position is a live confound at the tail of a 25-pair cap.

Eight pairs that are genuinely one permanent mark in two places — four verbatim from ledgers in
`runs/` — and nine that the prompt is **right** to wave through, several of them restatements of
the prompt's own exemptions. Both are scored, because a measure of recall alone rewards a prompt
that answers "contradiction" to everything (rule II).

    miss rate   14/24 = 58%   permanent marks let through
    false rate   1/27 =  4%   pairs wrongly called contradictions

| pair | flagged |
|---|---:|
| shipped palm->temple | 1/3 |
| shipped palm->arm | 1/3 |
| shipped arm->temple | 2/3 |
| var3 hand->cheek | 2/3 |
| tattoo shoulder->ankle | **0/3** |
| birthmark neck->knee | 2/3 |
| brand chest->palm | 1/3 |
| scar left->right hand | 1/3 |

**Not one of the eight was caught in all three repetitions.** The single false positive was "a
state that changed" (a door locked, then unlocked), caught once.

So this is not a judge that cannot tell contradictions from ordinary prose — 4% false is good. It
is a judge specifically blind to a mark changing place, and that leaves unusual headroom: recall
can rise a long way before precision becomes the binding constraint.

## The hypothesis, from reading the prompt rather than guessing

`CONFLICT_PROMPT` does name the defect — *"the same unchanging detail given two different values
(eye colour, a scar's location, a name)"*. But that sits in a three-item list, after an eight-item
list of exemptions written far more emphatically, two of which a mark's location falls squarely
inside:

- *"**WHERE** something or someone is. ... **Position is never a contradiction.**"* — stated
  absolutely, and a scar on the palm versus the temple is, read literally, a question of where.
- *"Facts many scenes apart have had a great deal of story in between; **assume time passed**
  unless the pair is from adjacent scenes."* — scene 15 against scene 40 is 25 scenes apart, so
  the model is explicitly instructed to assume change is legitimate.

A permanent mark is the one kind of "where" that cannot move, and the prompt never says so.

## The criterion, fixed now

Both arms run fresh in the same session at **5 repetitions** (40 true trials, 45 control trials),
same shuffle seed sequence, same model. The baseline above is 3 reps and is *not* the comparator —
it is what motivated the work.

- **Success requires BOTH:** miss rate falls to **10/40 (25%) or lower**, and false rate stays at
  **5/45 (11%) or lower**. On Fisher's exact test, 23/40 against 10/40 is p ≈ 0.004, so the
  recall half is detectable at this n; the precision half is a guardrail, not a hypothesis.
- **Miss rate falls but false rate exceeds 11% → the fix is rejected.** That is the outcome rule
  II exists for, and it would mean the exemptions were doing real work and the wording traded
  precision for recall rather than adding anything.
- **Miss rate does not reach 25% → the prompt is not the lever either**, and the next candidate is
  structural: a deterministic pre-flag on mark nouns handed to the judge as an assertion rather
  than a question, or `wandering_details` promoted from report to gate.

**Stated in advance:** this measures the judge on a fixed set of pairs, not the system. A better
judge only helps if the pair reaches it, and the palm/temple pair cleared the cap by two slots.
**A pass here does not license any claim about the wandering rate in a book** — that needs the
four fresh runs the corrected check already demands, and those are separate and unpurchased.

---

*Result appended below after both arms run. Nothing above changes.*

## Result: the fix is REJECTED, and the recall half worked

*Both arms run 3 September, same session, `qwen3:8b`, 5 repetitions, pairs reshuffled per
repetition. Criterion as committed in `f2a7b0d` and untouched.*

| | arm A (current) | arm B (revised) | registered bound | |
|---|---:|---:|---|---|
| miss rate | 26/40 — 65% | **9/40 — 22%** | <= 10/40 | **PASS** (p = 2.6e-4) |
| false rate | 2/45 — 4% | **7/45 — 16%** | <= 5/45 | **FAIL** |

**Success required both. It is rejected.**

The pre-registration named this outcome and its meaning: *"it would mean the exemptions were
doing real work and the wording traded precision for recall rather than adding anything."* That
is what happened, and the per-case detail says so rather than merely being consistent with it.

### The damage landed exactly where the wording was loosened

    arm A false positives:  an object somebody moved 1/5, a state that changed 1/5
    arm B false positives:  regions meeting at a joint 2/5, an object somebody moved 2/5,
                            a span restated 1/5, what somebody is holding 1/5,
                            a state that changed 1/5

Revision 1 weakened *"Position is never a contradiction"* by hanging an exception on it. The two
controls that newly broke are **an object somebody moved** and **what somebody is holding** — the
position exemption and the clause that explicitly rests on it (*"for the same reason position is
not"*). Qualifying an absolute rule cost the rule its force for cases the qualifier never
mentioned. That is mechanism, not noise.

And **the explicit carve-out did not take**: the revised prompt says in as many words that *"a
wrist and a forearm meet"*, and the wrist/forearm control was still flagged 2/5 — up from 0/5.
Naming an exception inside a strengthened rule did not protect the exception.

### What the recall number is worth, and what it is not

65% to 22% is real: p = 2.6e-4 on Fisher's exact, and the shipped palm/temple pair went 1/5 to
**5/5**. The hypothesis was right — the judge *was* misreading a mark's location as a position
question, and telling it otherwise fixes that specific blindness.

**One honesty note that does not change the verdict.** The precision loss is 2/45 against 7/45,
p = 0.157 — not itself statistically established. The rejection therefore rests on the
pre-registered absolute bound, not on a demonstrated regression. The bound is what it is because
it was chosen before the numbers existed, which is the entire point; arguing the verdict down now
on a p-value computed afterwards is the move [step 28](step28-preregistration.md) forbids, and the
answer there was more trials, never a softer line.

**A real defect in my own criterion, recorded because it will recur:** 45 control trials give
2.2 points of resolution, so a single extra false positive moves the rate by half the distance
between the arms. An absolute bound at that resolution is close to a coin-flip on one trial. A
re-test needs materially more control trials, and that has to be registered in advance too.

### The next lever, which this result points at cleanly

Do not touch the general prompt. The exemptions are load-bearing and were measured to be so.

**Pre-flag mark pairs deterministically and ask about them separately.** `checks._MARK_NOUNS`,
`_BODY_REGIONS` and `_ADJACENT_REGIONS` already identify a mark-in-two-regions pair with no model
call at all — that is what `wandering_details` does over a finished book. Applying the same test
to a candidate pair at write time splits the judge's job in two: mark pairs get a narrow question
that presumes the rule, everything else gets today's prompt with its exemptions intact and
unqualified.

That is a structural change rather than a wording change, it is the second option this document
listed in advance, and it is cheap. **It needs its own pre-registration, with more control trials
than this one had.**
## Live verification: the gate fires, the writer satisfies it, the book completes

*3 September, `runs/current-preflag1`, 71 scenes, 60,806 words, `qwen3:8b`, at revision
`6107ba1` with a clean working tree.*

The suite was green and the corpus precision was perfect before this ran, and **neither fact
answered the shipping question.** `checks:mark_conflict` is a BLOCKER that fires on 13 of 13
wandering books; a scene that trips a blocker its repair cannot satisfy spends its whole budget
and never commits. A gate that turns an unattended writer into one that stops is a regression
however precise it is.

    scenes                                  71/71
    halts                                   ZERO (no halts.json written)
    continuity_contradiction repairs        3, all outcome "accepted"
    scenes needing any repair               15
    most repair rounds any scene used       2  (budget is 3)
    final ledger                            989 facts, book-level check CLEAN

**The gate fired three times, the writer satisfied it three times, and the wrong location never
entered the ledger** — so it cannot propagate the way `temple` did from scene 40 of the shipped
book. That is the outcome that licenses shipping it as a BLOCKER.

Two details worth keeping:

- **Repair headroom is real but not generous.** The worst scene used 2 of 3 rounds. Nothing came
  within one round of halting on a mark conflict specifically, but the margin is one round, and a
  future check that adds pressure to the same budget should be measured against this figure
  rather than assumed to fit.
- **The adjacency rule earned its place on live data.** This book's scar sits on the *wrist* —
  the `hand` region — so a draft placing it on the forearm would correctly not fire, those
  regions meeting at a joint. The rule was derived from anatomy before this run existed.

### A power cut, and an unplanned robustness result

The run died at scene 37 when mains power failed mid-draft. Nothing was lost: 36 scenes and 492
facts were intact and contiguous, no scene file was truncated, the ledger parsed and agreed with
the scene files, and `python -m redthread write` resumed at scene 37 with no manual repair. For a
system whose entire purpose is running unattended, surviving a hard kill mid-draft and picking up
cleanly is worth knowing — learned by accident rather than by testing for it, which is stated
plainly because an accident is weaker evidence than a test.

### And the verifier lied first

`scripts/preflag_verify.py` initially reported **"the new gate never fired"** for this run. It
read `project.json`, which this pipeline does not write, and looked for a `kinds` field where the
records use `targets`. Both misses were silent, the counter came back empty, and the script
treated an empty counter as evidence.

**That is the third instance today of one failure shape** — `wandering_details` reporting clean
for dict input, the rater panel's 8-token budget silently deleting a rater, and now this. In every
case a component that could not read its input returned the reassuring answer instead of an
error, and in every case the reassuring answer was wrong. The fix each time is the same and it is
not cleverness: **make absence loud.** The verifier now prints how many records it actually
parsed and says outright that its figures mean nothing when that count is zero.
