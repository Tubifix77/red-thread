# Choosing models

Researched 2026-08-27 under the zero-assumption contract. Sourced facts and my reasoning are kept
separate below, because the interesting part of this question is a judgement call and pretending
otherwise would be dishonest.

---

## First, what the test suite actually uses

**No model.** `tests/fakes.py` provides a scripted backend returning canned JSON and fixture
prose. That is why the full suite (285 tests at the time of writing) runs in seconds with no API
key and no network.

This is deliberate, not a shortcut. The tests verify that the machinery composes — briefs carry
the seam forward, the commit gate holds, thread state advances, a rejection halts cleanly. None of
that is a question about any model, and mixing a real model into it would make the suite slow,
expensive, and flaky for reasons unrelated to what it is testing.

The corollary: the suite cannot tell you whether the prose is any good. That question is answered
by running it — see "The night it finished" below for what a completed all-local manuscript
actually looks like, structure and sentences both.

---

## Sourced facts

### The benchmark that matches this use case

EQ-Bench's **Longform Creative Writing** benchmark has a model brainstorm and plan a novella from
a minimal prompt, reflect and revise, then compose **eight 1,000-word chapters**. It scores 0–100
across 14 dimensions including negative factors like weak dialogue and purple prose, with "Forced
Poetry or Metaphor" weighted as `(Σ other criteria) + 5 × FPM^1.7`. Separately reported:
**n-gram repetition**, a **slop score** (frequency of LLM-typical phrases, lower better), and a
**degradation** sparkline showing quality dropping across the eight chapters, with an automatic
penalty for excessive single-sentence paragraphs in long outputs.
([eqbench.com](https://eqbench.com/creative_writing_longform.html))

Creative Writing v3 is the short-form sibling: 32 prompts × 3 iterations at temperature 0.7 and
min_p 0.1, judged per piece against a rubric, hybrid rubric + Elo from pairwise Glicko-2 matchups,
outputs truncated to 4,000 characters to limit length bias.
([eqbench.com](https://eqbench.com/), [repo](https://github.com/EQ-bench/creative-writing-bench))

### Small open-weight models score closer than expected

On Creative Writing v3, as of 2026-08-27
([llm-stats](https://llm-stats.com/benchmarks/creative-writing-v3)):

| Model | Params | Score | Rank |
|---|---|---|---|
| Qwen3-235B-A22B-Instruct-2507 *(best open)* | 235B | 0.875 | — |
| Qwen3 VL 32B Instruct | 32B | 0.856 | 6 |
| Qwen3 VL 30B A3B Instruct | 31B | 0.846 | 9 |
| Qwen3 VL 32B Thinking | 33B | 0.833 | 10 |
| **Qwen3 VL 8B Thinking** | **9B** | **0.824** | **12** |
| Qwen3 VL 4B Thinking | 4B | 0.761 | 13 |

Claude Opus 5 leads the overall board at Elo 2105, ahead of Kimi K3 (2060) and GPT-5.6 Sol (1959).

**The 9B model is within about 6% of the 235B on this benchmark.** That is the single most
encouraging number for a 10GB card, and it is the reason the local path is worth taking seriously
rather than treating as a compromise.

### Instruction following

IFEval is built from ~500 prompts over 25 types of *verifiable* instructions — "write in more than
400 words", "mention the keyword AI at least 3 times" — checked programmatically rather than
judged. Mistral Small 3.2 24B Instruct leads the tracked board at 84.8%, MiniMax M2 at 72.0%.
([llm-stats IF](https://llm-stats.com/benchmarks/if)) Coverage of the 8–14B range on that board
was sparse, so this does not answer the question for the models that fit your card.

### VRAM sizing — a gap, not an answer

Every source found for "what fits in 10GB" was a low-authority auto-generated hardware-affiliate
site, several naming models I could not independently confirm exist. Their consensus was Q4_K_M as
the quality/speed sweet spot, 7–8B comfortable, 12–14B with reduced context.

**I am not presenting that as fact.** It is uncorroborated, from sources whose interest aligns
with the claim, and the KV-cache arithmetic that actually decides it depends on context length,
which those pages handle vaguely. Measure it on the card instead — see below.

---

## My reasoning on the real question

You asked whether to prefer a good prose writer or an obedient instruction-follower. My view, and
this is judgement rather than something a citation can carry:

### The architecture already resolves most of the tension, because the roles are split

`redthread.llm.Models` has three seats, and they want opposite things:

- **writer** — dominates token spend, and its failures are **loud**. A writer that ignores the
  forbid list gets caught by `check_somatic`, `check_thematic_gloss`, `check_seam`, and the
  thread-satisfaction probe. You will know.
- **critic / extractor** — small outputs, and its failures are **silent**. A malformed fact
  extraction does not raise; it just quietly stops protecting continuity, and every later brief is
  built on a ledger with a hole in it. `verify.extract_facts` treats extraction failure as a
  BLOCKER precisely because of this.

So the answer is not one model in principle. **Obedient-and-flat belongs in the critic seat.
Good-prose-and-wilful belongs in the writer seat.** `Models.local(writer, critic)` encodes exactly
that split across two local models — with the measured caveat that on a 10GB card two models
thrash (an 8B writer beside a 14B critic ran the critic 18% spilled to CPU and evicted the writer
between calls), so in practice the seats share one model that fits entirely, and the calibration
policy below is what makes a single 8B safe in the judging seat.

### For the writer, instruction-following is a floor, not an axis to maximise

Above some threshold, spend your model budget on prose. Below it, throughput collapses: three
candidates plus two repairs per scene, and the scene still gets held back. The repair loop is
bounded and reverts non-improving repairs, so a wilful writer does not corrupt the manuscript — it
just costs you money and never converges.

The floor is specifically: can it hold the **prohibition list** and the **word target**? Not "can
it follow complex reasoning instructions." Those are much easier constraints than IFEval tests,
which is why I would not pick a writer on IFEval score.

### The degradation axis matters much less here than the benchmark implies

This is the part worth noticing. The longform benchmark's headline weakness for most models is
**degradation across eight chapters** — and red-thread is structurally immune to it. Every scene is
a fresh session with a bounded brief. There is no accumulating context to drift in.

So for this project, the axes that matter are:

1. **short-form prose quality** — Creative Writing v3 is the closer proxy, not longform
2. **slop score** — and we already have Antislop's list, with sampler-level suppression available
3. **prohibition adherence** — which no public benchmark measures

Which means a model with poor longform stamina but good per-scene prose is a *better* fit for
red-thread than its longform rank suggests. That reframing is the practical payoff of the chunked
architecture, and it widens what a 10GB card can attempt.

### What I would actually do

Stop guessing, including at me. `redthread bench` (below) drafts a real scene from a real brief
against however many models you name and scores them on the axis that matters — brief adherence —
for free, on your card. The EQ-Bench harness also runs against any OpenAI-compatible endpoint, so
you can get a prose-quality number from the same models with the same interface.

Candidates worth putting in the harness, on the evidence above: the Qwen3 VL 8B class (the 0.824
data point), and one 12–14B at reduced context to see whether the size buys anything on adherence.
I am not going to tell you which quantization fits until you have measured it, because the only
sources I could find for that were not worth citing.

---

## What the first real run actually found

Three local models, one draft each, against the real scene-1 brief (900-word target) on an
RTX 3080 10GB. This produced more usable information than all the leaderboard research above,
because none of it is measurable from outside.

| Model | Words | Blockers | Majors | Verdict |
|---|---|---|---|---|
| qwen3:8b | 948 | 0 | 2 | on target; lifted the style samples |
| gemma3:12b | 542 | **1** | 1 | wrote the whole scene in **first person** |
| phi4:14b | 506 | 0 | 1 | short; closed on pure thematic gloss |

`gemma4:12b` was excluded: it ran over twenty minutes on this one scene at 100% VRAM occupancy
without finishing. That is a result too, and it prompted `bench --timeout`.

Every one of these findings was invisible to the checks as they stood. Four gaps closed:

**1. Style samples reproduced verbatim.** qwen3:8b opened with the style contract's first sample
sentence word for word, and reused a second one later in the same draft. The brief said "match
this prose" and the model read that as text to continue from. This compounds badly: the same
samples go into *every* brief, so unchecked, the same sentences surface scene after scene and the
manuscript grows a refrain nobody wrote — invisible within any single scene, detectable only
across the corpus. Fixed at both ends: `check_style_leak` (MAJOR on any shared 6-word run) plus
`check_brief_leak` for beat and scene summaries, and the brief now says explicitly that the
samples show rhythm and diction, come from elsewhere in the book, and must not be reused, quoted,
or opened with.

**2. Point of view unenforced.** gemma3:12b wrote an entire scene in the first person — 22
first-person pronouns in narration — against a `third limited` contract, and *every check passed
it*. A POV break makes a scene unusable in the manuscript and is among the cheapest things to
detect. `check_pov` now strips dialogue (characters legitimately say "I") and counts what remains:
BLOCKER when the narration is wholesale in the wrong person, MAJOR for a handful of slips, since
free indirect discourse admits the occasional first-person thought.

**3. Word targets are the real discriminator.** Both 12B/14B models produced *complete* scenes at
roughly 55% of target — not truncated, just short, which means beats were skipped. This is the
"instruction-following floor" from the reasoning section arriving as data: adherence to the length
constraint separated the models far more sharply than prose quality did.

**4. Two false positives in the checks themselves.** `check_slop` matched "aria" inside
"variance", and the list is full of short single-word entries — shall, realm, canvas, depths —
that would each fire inside longer words. Single-word entries now match on word boundaries;
multi-word phrases stay substring matches.

The general lesson, and the reason not to trust the research section above on its own: every
failure that mattered lived in **the interaction between this project's brief and a specific
model**, which no external benchmark can see. Run your own briefs.

## Running the full loop locally: what broke

The first end-to-end write run — plan, brief, draft, verify, repair, commit gate — was done with
`qwen3:8b` in every role. The commit gate correctly refused the scene and nothing entered the
ledger, which is the behaviour the architecture promises. Underneath that, four defects, and the
first one is the important one.

**1. Reasoning blocks silently destroyed structured output.** The run reported
`0 facts extracted`. The obvious reading is that an 8B cannot do structured extraction — the exact
risk this document warned about. It was wrong. Called directly with the same prompt on the same
text, `qwen3:8b` extracts **18 clean facts**. The bug was ours: qwen3 is a thinking model and emits
`<think>` blocks on the *structured* calls as readily as on prose, and `strip_reasoning` was only
applied to writer output. The reasoning derailed the brace matching in `parse_json`, the parse
failed, and the only visible symptom was a scene reporting no facts.

The lesson generalises past this bug: **"the local model can't do it" is a hypothesis, not an
observation.** Test the capability in isolation before designing around its absence. Stripping now
happens inside `parse_json`, so every probe is covered at once.

**2. An empty extraction passed the commit gate.** Only a parse *failure* blocked. An empty facts
list did not, so a scene could have committed with the ledger blind to it — every later brief
saying "nothing established yet" while the manuscript filled up. Now a BLOCKER above 150 words.

**3. Under-length scenes were unrepairable by construction.** The repair prompt says "do not change
the length by more than a few words", and length violations were being sent to it. A 564-word scene
"repaired" to 591 and was held back anyway. Short scenes now take a separate expansion path — which
worked on the next run: **689 → 897 words**, length resolved, minor violations down from three to
one.

**4. Token budgets ignored reasoning.** Repair failed in twelve seconds on an 897-word scene
because the budget was sized for the prose alone, the reply was cut off, and the truncation guard
correctly rejected it. Every whole-scene call now carries 4000 tokens of headroom.

And one tuning problem rather than a bug: extraction returned **59 facts for a 689-word scene**,
mostly atmosphere — "the screen was flickering", "her fingers were calloused". That compounds
badly, because the ledger goes into every later brief and `conflict_candidates` would start
manufacturing contradictions out of how the light was falling. The prompt now says to be sparing
and the cap is 30.

### What this says about local viability

`qwen3:8b` can carry the extractor role. That was the biggest open question in this document and
the answer is yes, once the reasoning-block problem is out of the way. What it struggles with is
holding the *prohibitions* — somatic emotion, the forbidden-phrase list, thematic gloss survive
into the draft and repair does not reliably remove them. Which is consistent with the bench: word
targets and adherence, not capability, are where the small models lose.

## Calibrating the judge — the finding that unlocked commits

Every earlier run deadlocked the same way: the repair loop fixed what it was told, and the
LLM judge found a fresh, well-evidenced MAJOR in every round. The open question was whether the
judge was right (the prose is inexhaustibly flawed) or unreliable (the gate can never open).
Answer, by experiment rather than argument — qwen3:8b as judge, temperature 0, three samples per
fixture:

| Fixture | Expected | Judge said (3 runs) |
|---|---|---|
| deliberately glossy text ("In that moment she finally understood…") | flag | flagged, 3/3 ✔ |
| clean behavioural text | pass | **flagged "The tally sheet had been photocopied so often that the column headings had closed up" as thematic gloss, 3/3** ✘ |

A judge with a hard false-positive floor finds a MAJOR in any scene. As a blocking gate, that
means nothing ever commits — not because the prose fails, but because the gate is broken. And the
same run had it flag *"She didn't like the fact that she had to keep a paper notebook"* — plain
third-limited interiority — as theme-explaining.

**Policy, from the evidence:**

- **The judge's binary judgments are usable.** Its violated-prohibition calls located three real
  concealment leaks in one scene, and surgical repair fixed all three. "Missed" obligations block.
- **Its graded and aesthetic judgments are advisory.** Tell findings and "partial" verdicts are
  recorded as MINOR in `scenes/NNNN.json` for the human, and never block. Blocking power for
  gloss belongs to the deterministic check, which passes the clean fixture and catches the glossy
  one.
- **Evidence is validated before any judgment counts.** A finding whose quote does not locate in
  the scene text is dropped outright — the judge sometimes "quotes" a paraphrase of its own
  reasoning.

The first scene ever to commit on a fully local pipeline did so twenty minutes after this policy
landed: 924 words, zero blockers, zero majors, 14 facts, 34 seconds.

## The night it finished: a complete manuscript on one 8B

2026-08-28, overnight, fully autonomous: *The Inherited Glitch*, 10/10 scenes, 12,169 words,
`qwen3:8b` in every role, RTX 3080 10GB, zero API calls. Scene times 29s–2m42s once the machinery
stabilised. The full defect log lives in the commit history; the pattern behind it is worth more
than the list:

**Every deadlock traced to asking a model for a judgement code could make, or asking it in a form
it could not satisfy.** The judge re-run inside the repair loop (flipped verdicts poisoned every
comparison — now it judges once). The state-name pseudo-requirement ("thread must end in state
'chosen'" — our bookkeeping label, not a textual event; the judge could only hallucinate a
mapping). The concealment enforced on the reveal scene itself (a brief that simultaneously
required and forbade the same disclosure). Whole-scene rewrites asked of a model that can manage
one sentence (surgical splicing, code-verified in context). Trims asked of a model that
regenerates at length (the output budget now makes runaway physically impossible, and truncation
snaps to the last sentence in code). Each fix moved work from the model to code, and each one is
a test.

**The honest prose verdict** is in [evidence/manuscript-run.md](evidence/manuscript-run.md): the
structure held completely — threads, seams, facts, concealments — and the sentences are an 8B's.
The system's own cross-corpus audit caught the tics (27 recurring 5-grams; a closing line copied
verbatim into the next scene's ending; name-plus-stance openings on eight of ten scenes), logged
them as MINOR per the calibration policy, and two of them became deterministic checks the same
night. That is the designed division of labour: the machine guarantees the book's *shape* and
surfaces its prose debt scene by scene; raising the sentence ceiling is a writer-model upgrade,
one `--local` flag away.

## Measuring adherence yourself

```bash
python -m redthread bench runs/glitch --scene 1 \
    --local qwen3-vl:8b --local qwen3:14b --candidates 2
```

This runs the *real* scene-1 brief through each model and reports the deterministic check results
per model — length compliance, somatic tics, thematic gloss, slop hits, rhythm, format leakage.
No API key and no judge model, so it costs nothing but GPU time.

It measures adherence, **not** prose quality. Read the drafts it saves. A model that scores well
here and writes lifelessly is the wrong choice, and no automated check will tell you that — which
is the honest limit of the whole approach.
