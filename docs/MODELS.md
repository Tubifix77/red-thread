# Choosing models

Researched 2026-08-27 under the zero-assumption contract. Sourced facts and my reasoning are kept
separate below, because the interesting part of this question is a judgement call and pretending
otherwise would be dishonest.

---

## First, what the test suite actually uses

**No model.** `tests/fakes.py` provides a scripted backend returning canned JSON and fixture
prose. That is why the full suite (421 tests at the time of writing) runs in seconds with no API
key and no network.

This is deliberate, not a shortcut. The tests verify that the machinery composes — briefs carry
the seam forward, the commit gate holds, thread state advances, a rejection halts cleanly. None of
that is a question about any model, and mixing a real model into it would make the suite slow,
expensive, and flaky for reasons unrelated to what it is testing.

The corollary: the suite cannot tell you whether the prose is any good. That question is answered
by running it — see "The night it finished" below for what a completed all-local manuscript
actually looks like, structure and sentences both.

A second corollary, learned the hard way and worth stating plainly: **the fixtures are prose I
wrote, and I wrote them to pass the checks.** `_CLOSINGS` in that file still carries a comment
explaining that the closings are kept distinct so `check_seam` does not fire on the fixture's own
filler. Test data shaped around a failure mode cannot detect it, and the second manuscript found
twelve defects with 292 of these tests green behind it — every one of them in a repair path, which
a clean run barely exercises. `tests/test_repair_coverage.py` is the response: it asserts a
structural property of the checks rather than a behaviour of any fixture.

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

## The second book: what changes when the run is not clean

2026-08-29: *The Debt of Years*, 27 scenes, 30,046 words, planner-driven from a one-page premise,
`qwen3:8b` in every role again. Two and a half times the first book, and the first run where the
checks fired constantly. Twelve defects, all of them in repair paths — which the first, cleaner
run had barely executed. The full record is in
[evidence/debt-of-years-run.md](evidence/debt-of-years-run.md); three findings are about the model
rather than about our code.

**Showing a small model the text it must not reuse is showing it the text to produce.** The first
seam repair rewrote a copied ending, and its prompt included the previous scene's ending under a
heading saying none of these words may appear. qwen3:8b returned that ending, near-verbatim, twice
in a row, in about a second each time — faster than it writes anything original, which is the tell.
The working repair deletes the copied block in code and verifies with the check that flagged it.
Generalised: on an 8B, prefer the repair that needs no model; where one is needed, do not put the
negative example in front of it.

**Whole-output operations keep failing, at every size.** The first run established that whole-scene
*repair* fails on an 8B and moved to sentence splicing. This run found the same thing for
whole-scene *expansion*: asked to reproduce 876 words verbatim and add 270 more, the model rewrote
and came back shorter, twice, and the attempt was discarded both times. Expansion is now one
paragraph — the interior one closest in size to the shortfall — rewritten between two the model can
see but must not touch, and spliced back. Same shape as surgical repair, same reason it works.

**Growth needs a ceiling as much as a floor.** Given a large shortfall and the thinnest paragraph
in the scene, the model turned 47 words into 467, and the padding tripped three other checks. A
passage may now at most double, and a scene needing more gets it over two rounds.

The prose verdict is unchanged and, if anything, clearer at length: the structure held completely
across 27 scenes and 397 ledger facts, and the sentences are an 8B's. Most scenes committed
carrying six or seven MINOR violations; one draft repeated "he had no right" four times inside a
single scene. That is the designed division of labour — the machine guarantees the book's shape and
itemises its prose debt scene by scene — and raising the sentence ceiling remains one `--local`
flag away.

## Scene length is a model setting, and it is the biggest quality lever found so far

Repeated phrasing is the sharpest quality signal this project can count: the fraction of a
scene's 4-grams that are duplicates (`checks.duplication_ratio`). Across 87 committed scenes and
the single-scene comparisons in `evidence/`, it separates prose by two orders of magnitude —
gemma3:12b and phi4:14b at 0.000–0.002, qwen3:8b's best single scene at 0.026, the median scene
this project committed at 0.289.

It rises steeply with scene length on an 8B. Correlation is **r = 0.68** across those 87 scenes,
and positive within every individual book (r = +0.35 to +0.90), so it is not a between-book
artefact:

| scene length | duplicated phrasing |
|---|---|
| 506–931 words | 0.13 |
| 939–1009 | 0.20 |
| 1013–1109 | 0.22 |
| 1114–1184 | 0.33 |
| 1186–1346 | 0.48 |
| 1354–1619 | 0.59 |

`DEFAULT_SCENE_WORDS` was 1100, which put the planner's assigned targets at a mean of 1115 across
five books — most of a manuscript in the band where this model stops writing and starts looping.
Setting it to 850 and re-running the same premise on the same model:

```
before (1100-word default)   mean 1197 words   duplication 0.330
after  ( 850-word default)   mean  880 words   duplication 0.108
```

A 67% reduction in repeated prose from one number, and the number came from measurement rather
than taste. It is a property of the writer, not of prose in general — re-measure before raising
it for a stronger model, and `bench` is the place to do that.

**Two things that did *not* work**, recorded because the negative results cost as much to get:

- *Trimming the brief.* Duplication climbs by scene position, so the ledger slice looked like a
  copy attractor. Drafting the same scene three times with the full brief and three with the
  ledger cut to ten facts gave 0.306 against 0.414 — the slim brief was worse, and with a
  0.124–0.574 spread inside each condition the experiment settles nothing either way. The
  position effect was length in disguise.
- *Gating on the ratio.* The obvious move is to make a high ratio a MAJOR and let repair fix it.
  It cannot: 29% duplication is not six bad sentences, it is the model's whole register, and no
  sentence-local repair reaches it. There is no threshold justifiable from real prose that does
  not halt most scenes.

**What does work besides length: drafting more candidates.** Six drafts of one brief, same model,
same temperature, spread wide on identical input — one scene ranged 0.044 to 0.447. Selection
breaks ties on the ratio, so the cleanest draft wins for nothing extra. Expected best-of-k, exact
over every subset of six drafts across two scenes:

| candidates | expected duplication |
|---|---|
| 1 | 0.107 |
| 2 | 0.058 |
| 3 | 0.045 |
| 4 | 0.038 |

One to two halves it; two to three takes another fifth; past three it flattens. **Three is the
default and it is the right one** — worth stating because every run in the session that produced
these numbers was launched with `--candidates 2`, which is strictly worse than leaving the flag
alone.

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

---

## The writer model is the prose ceiling (29 August 2026)

Scene 9 of a live plan would not commit on `qwen3:8b`. Four drafts, six repairs, every one
unusable: "she had not asked" 77 times in 1,490 words, a 46-sentence run of past perfect, 97.9%
of the scene narrated at summary distance. The obvious reading was that the beats gave the model
nothing to dramatise — three of scene 9's four are *watches and notes*, *reflects on*, *is
revealed to be*.

That reading is wrong, and measuring it said so twice.

**First, across the corpus.** Correlating the share of a scene's beats that use a cognition or
state verb against its recap density, over all 108 scenes with both a spec and prose: **r =
0.141**. Against duplication, r = 0.006. The group means lean the right way (.378 → .410 → .466)
but the top group is n = 3. Nothing to build a check on, so nothing was built.

**Second, by swapping one flag.** Same plan, same brief, same orchestrator, one draft each:

| | qwen3:8b | gemma3:12b |
|---|---:|---:|
| scene 9 — repeated phrasing | .29 | **.015** |
| scene 9 — recap grammar | .979 | **.046** |
| scene 9 — longest past-perfect run | 46 sentences | **1 sentence** |
| scene 9 — outcome | held back, 4 drafts, 6 repairs | committed, 1 draft, 2 minors |
| scene 10 — repeated phrasing | — | **.002** |
| scene 10 — recap grammar | — | **.058** |
| scene 10 — outcome | — | committed, 1 draft, **0 majors, 0 repairs** |
| scene 11 — outcome | — | **held back: 35 first-person uses** |

For comparison, the five `qwen3:8b` scenes written under the full check set run .051–.316 on
duplication and .143–.590 on recap, with up to five blocks of recap in a single scene. The two
committed `gemma3:12b` scenes sit at .002–.015 and .046–.058 with none. That is the reference
band in `docs/evidence`, reached inside the orchestrator rather than by a cold single scene.

### Both models fail, and the failures are not equally safe

Scene 11 is the same defect the scene-1 bench found in this document months ago: `gemma3:12b`
drifts into first person against a third-limited contract. It is not an anomaly, it is the
model's signature failure, and any plan to switch writers has to account for it.

But the two failure modes are not equivalent to a manuscript:

- `qwen3:8b` fails by **recapping**. That is a MAJOR and a register, so a scene can commit
  carrying some of it and the book degrades quietly.
- `gemma3:12b` fails by **breaking POV**. That is a BLOCKER, detected in code with no model call,
  and nothing carrying it can ever reach the manuscript.

A loud failure the gate catches is worth more than a quiet one it half-catches. That is an
argument for the swap, not against it.

### What this costs

`gemma3:12b` took 2–3 minutes per draft against 15–18 seconds for `qwen3:8b` on the same card —
roughly **eight times slower**. A 27-scene book goes from about half an hour to four hours. For
an unattended overnight run that is affordable; for iterating on the machinery it is not, which
is why the test suite and the fixture work stay where they are.

### What is not settled

Three scenes. One plan. One card. The candidate count was 1 rather than the measured default of
3, so these are single draws rather than best-of-three, which flatters neither model in
particular but makes every figure noisier than the tables suggest. `bench` across a full book,
and a POV-drift rate measured over more than one scene, are what would settle it.

---

## The sampler was the ceiling, not the model (29 August 2026)

The section above concluded that the writer model was the prose ceiling. That conclusion was
premature, and the thing that refuted it was checking a setting nobody had looked at.

**Ollama's `repeat_penalty` defaults to 1.0, which is disabled.** Verified against
`ollama/ollama` `docs/modelfile.mdx`: *"(Default: 1.0, disabled)"*. And `qwen3:8b`'s own
Modelfile pins it there explicitly — `PARAMETER repeat_penalty 1`. The companion setting
`repeat_last_n` defaults to 64 tokens, a lookback of roughly forty-five words.

So every scene this project has ever generated was sampled with no repetition penalty and a
window too short to see a phrase recurring every twenty words. The worst scene measured repeated
one four-word phrase 77 times in 1,490 words. Nothing in the brief and nothing in the 29 checks
could reach that, because the cause was underneath both of them.

### The sweep

Two scenes that had failed worst, two seeds each, everything else held constant:

| repeat_penalty | duplication | recap grammar | blocks | type-token |
|---:|---:|---:|---:|---:|
| 1.10 | .163 | .361 | 2.5 | .391 |
| 1.15 | .030 | .306 | 1.2 | .456 |
| **1.20** | **.004** | **.103** | **0.0** | **.542** |
| 1.30 | .025 | .060 | 0.0 | .810 |

1.20 is the lowest value that cleared every draft on both scenes. **1.30 was rejected on
evidence**: character-name occurrences fell from about 17 per scene to 5, because a penalty that
strong suppresses the legitimate repetition a scene is made of. Type-token ratio is the tell —
`gemma3:12b` writing these scenes inside the orchestrator sits at .474–.478, and .810 is a model
straining for novelty rather than writing.

`num_ctx` was raised to 8192 in the same pass, for a smaller but real reason: Ollama's runtime
default is 4096, a scene brief measures about 2,470 tokens, and a 1,500-word draft is another
2,000 — so a runaway draft overflows the window and the front of the brief, where the voice
contract and the task sit, scrolls out mid-generation. On its own it helped little (the middle
column of the three-way test), but it removes a failure mode that would otherwise return at
longer scene lengths.

### The result

Scenes 9–11 of the same plan, `qwen3:8b`, the writer role carrying `repeat_penalty 1.2`,
`repeat_last_n 512`, `num_ctx 8192`:

| | duplication | recap | longest run | blocks | type-token |
|---|---:|---:|---:|---:|---:|
| qwen3:8b, before | .118 | .376 | 4.4 | 2.0 | .327 |
| **qwen3:8b, after** | **.004** | **.078** | **1.3** | **0.0** | .572 |
| reference drafts | .009 | .105 | ≤2 | 0 | — |
| gemma3:12b, in-orchestrator | .002–.015 | .046–.058 | 1 | 0 | .474–.478 |

All three scenes committed. Scene 9 — which had been held back on three separate attempts, once
after four drafts and six repairs — committed in 1m37s with a single deterministic repair, and
every thread reached its terminal state. The 8B is now **below the reference band on both
axes**, at roughly an eighth of `gemma3:12b`'s time per draft, and it committed the scene
`gemma3:12b` failed on a POV break.

### What this changes

The swap is off the table, and the reasoning matters more than the result. A small model under
strict orchestration and a large model under light orchestration are different products, and
only the first one is worth building here: it is the configuration where the machinery earns its
keep, and the one that stays true when the models underneath change. Reaching for a bigger model
is the move that makes the checks redundant — which is a way of abandoning the project rather
than finishing it. Every other avenue has to be exhausted first, and this one had not even been
looked at.

The `gemma3:12b` comparison was still worth running. It is what established how much of the
remaining defect was model-attributable, and the honest answer turned out to be: almost none of
it, once the sampler is right.

### Not settled

Three scenes on one plan. The type-token ratio at 1.20 is .572 against `gemma3:12b`'s .474–.478
— above the healthy band, well short of the .810 damage point, and unexamined. Whether prose at
that variety reads as *rich* or as *restless* is not something any check here measures, and it is
the obvious thing to watch when reading the output. The penalty should also be re-swept for any
new writer model: `gemma3:12b`'s Modelfile sets no `repeat_penalty` at all, so it inherits the
same disabled default and may well have headroom of its own.

---

## Three wordings of one instruction (30 August 2026)

A finding about prompt design, measured rather than argued, and recorded because the failure mode
is not obvious and cost several plans to find.

**The problem.** Reading the middle of the 71-scene book found scene 38: one character alone in a
ruin, touching statues and remembering. Measuring outward, 20 of the 71 scenes the plan had
populated with two or three characters came back with no dialogue at all, and dialogue across the
book declined by quarter — 21% of words, 15%, 10%, 9%.

The cause was upstream. Across those 70 two-character scenes, correlation between beats naming a
spoken act and dialogue in the prose is **r = +0.672**; 20 of the 33 scenes whose beats named
nothing spoken came back silent, against 0 of the 10 whose beats named two. The planner's own
spoken-beat rate declines through the book on the same curve (77% of peopled scenes in the first
quarter, 50%, 38%, 44%) while the cast size does not. It keeps putting people in rooms and
progressively stops giving them anything to say.

**Wording 1 — conditional.** *"IF two or more characters are present, at least one beat must name
something said between them."*

The planner satisfied it by removing the characters. Solo scenes went from 10 of 71 to **34**.
A conditional instruction invites the model to falsify the antecedent, and the result was worse
than the defect: a book half made of one person alone is *more* of what the rule was written to
prevent.

**Wording 2 — unconditional, with the exception explained.** The rule was made unconditional, and
a note added to the `characters` field saying most scenes have two or more, that a solo scene
needs a reason, and never more than a handful in a book.

Solo scenes fell to a mean of **19.7** across three plans — better than 34, still double the
original 10. **Discussing the exception is what made it salient.** Three sentences on when a solo
scene is justified produced four times as many of them.

**Wording 3 — say the expectation, stop.** *"ids of everyone present, and there are nearly always
two or more. A novel is people doing things to each other; a character by themselves has nobody
to be surprised by."*

| wording | n | solo scenes | peopled naming a spoken act |
|---|---:|---:|---:|
| original (no instruction) | 1 | 10 | 51% |
| 1 — conditional | 1 | 34 | 78% |
| 2 — exception explained | 3 | 19.7 | 83% |
| 3 — expectation only | 3 | **11.3** | **89%** |

### What is and is not established

**Established:** the spoken-beat rate rises from 51% to 89% and holds across three plans. The
conditional wording is actively harmful. Explaining the exception roughly doubles it.

**Not established:** the solo-scene count. Wording 3 produced 5, 5 and **24** — mean 11.3 against
the original 10, unchanged on average with far larger variance, and the outlier is unexplained.

**The method note matters as much as the result.** An hour was spent drawing conclusions from
single plans before the plan-to-plan variance was measured, and it turns out to be large enough
that one plan settles nothing. Any future comparison of planner prompts needs at least three
plans per condition, and this document's earlier single-plan comparisons should be read with that
in mind.
