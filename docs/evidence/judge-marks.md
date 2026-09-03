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
