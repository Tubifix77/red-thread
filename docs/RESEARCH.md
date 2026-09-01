# Research basis

Every claim here was fetched live on 2026-08-27 under the zero-assumption contract.
Ledger: `.claude/zero-assumption/memory.md`. Nothing in this file comes from model memory.

---

## 1. Hierarchical plan-then-write is the established shape

**Re3** (Yang, Tian, Peng, Klein — EMNLP 2022, pp. 4393–4479) generates stories over 2000 words
with four stages: construct a structured overarching plan; generate passages by repeatedly
injecting plan + current story state into the prompt; rerank candidate continuations for plot
coherence and premise relevance; edit the best continuation for factual consistency. Human
evaluators judged +14% absolute more Re3 stories as having a coherent overarching plot and +20% as
relevant to the premise, versus direct generation from the same base model.
([ACL Anthology](https://aclanthology.org/2022.emnlp-main.296/))

Implementation specifics: Plan defaults to 3 outline items; Draft defaults to four 256-token
passages per item; two `allenai/longformer-base-4096` rerankers (relevance, coherence) trained on
WritingPrompts; the Edit module offers `entailment`, `structured` (GPT-3), and `entailment-DPR`
contradiction detection.
([repo README](https://github.com/yangkevin2/emnlp22-re3-story-generation/blob/main/README.md))

**Design consequence.** Candidate-and-rerank at the passage level, plus a distinct
consistency-editing stage, are load-bearing — not polish. We keep both.

---

## 2. A rigid outline is a known failure, not a safe default

DOME's framing: existing methods "rely on rigid outlines or lack macro-level planning", and
treating the outline as a rigid constraint "restricts the flexibility required for complex
revisions". ([DOME](https://arxiv.org/html/2412.13575v1))

**DOME** alternates outline and writing: a five-stage rough outline (Campbell), each stage
expanded into 3 detailed outlines *dynamically* using the memory module, each detailed outline
generating a segment that is stored back into memory, repeating across all five stages.
Submodules: DHO (dynamic hierarchical outline), MEM (memory-enhancement), Temporal Conflict
Analyzer.

**Design consequence.** The spec tree is expanded just-in-time from committed state, never fully
materialised up front.

---

## 3. Memory representation: quadruples, not prose notes

DOME's memory is a temporal knowledge graph of quadruples `<subject, action, object,
chapter_index>`. Conflict detection groups quadruples by structural-similarity rules and then
applies LLM evaluation against temporal logic. Retrieval is semantic filtering at cosine
similarity threshold 0.75, supplying "concise relevant content" rather than the full context
window. ([DOME](https://arxiv.org/html/2412.13575v1))

Reported: conflict rate 0.56% (DOME) vs 0.77% (Re3) vs 1.21% (DOC); Entropy-2 12.29 vs 11.56 vs
11.55; claimed "reduces conflicts by 87.61%". Human evaluation ranked DOME first on all five
qualitative dimensions including plot coherence and *expression* coherence. Single source
(authors' own paper); the paper's "Plot Completeness" row could not be read unambiguously in our
fetch and is not relied on here.

**Design consequence.** The ledger is a quadruple store with structural grouping for conflict
detection. Adopted directly.

---

## 4. Threads as state-transition operators — the central borrow

**ConWriter** models long-form story writing as an incremental state-transition process: each
scene must induce a valid transition, represented as symbolic operators
`(Pre_t, Post_t, Forbid_t)` — preconditions, postconditions, forbidden states.
([ConWriter](https://arxiv.org/html/2608.05169v1))

Memory splits into **static** (premise, world rules, character attributes, style constraints, task
instructions — immutable) and **dynamic** (accumulated events, entity states and relations,
temporal information, unresolved future constraints), where dynamic memory is **updated only after
a scene passes consistency checks**.

Consistency control is dual assurance: structured validation with explicit violation scoring
against the symbolic constraints, plus uncertainty-aware risk monitoring that flags
weakly-grounded segments for stronger inspection. Checking runs after draft generation and before
commit. Violations trigger **localised sentence-level repair within bounded retry loops** —
revising only conflict-bearing sentences rather than regenerating the scene.

Reported: 50–87% reduction in consistency-error density versus direct generation across
Qwen3.5-Plus, DeepSeek-V4-Flash and GPT-5.4-nano at 3K/6K/12K word targets; outperformed DOME;
output length maintained. Single source (authors' own paper).

**Design consequence.** This is the formal shape of a "red thread". A thread carries a state
machine; a scene spec carries `pre` / `post` / `forbid`; the commit gate and sentence-local repair
are adopted as architecture, not as options.

---

## 5. The seam problem — cohesion is a named, separate concern

**STORYTELLER** distinguishes **coherence** (logical consistency and semantic meaningfulness
within a narrative) from **cohesion** (smooth, interconnected flow between consecutive segments),
and targets cohesion specifically with a dedicated Cohesion Enforcement module alongside a
Coherence Refinement module. Cohesion is enforced through character-overlap constraints between
consecutive scenes, shared contextual elements bridging sequential segments, and explicit
transitions derived from a Scene-Character graph.
([STORYTELLER](https://arxiv.org/pdf/2506.02347))

From the long-form generation literature, the **chunk-buffer** technique: drop the last generated
chunk of the preceding sequence and use it as the *prefix* for the next, so information flows
across the boundary. (Surfaced via search summary of long-form TTS/chunking work —
[MagpieTTS-LF](https://arxiv.org/pdf/2606.18485) — cross-domain, not fiction-specific. Treated as a
technique to try, not a validated result for prose.)

**Design consequence.** Cohesion gets its own checks and its own brief fields, kept separate from
coherence: verbatim tail of the previous scene, a required character overlap or an explicit
hand-off, and a transition contract. Cohesion failures are repaired at the seam only.

---

## 6. What actually makes AI fiction recognisable — the design-changing finding

**StoryScope** (Russell, Rajendhran, Pham, Iyyer, Wieting) measures five idiosyncrasies of AI
fiction against human fiction: ([StoryScope](https://arxiv.org/html/2604.03136v1))

| Idiosyncrasy | Measure | AI | Human |
|---|---|---|---|
| Thematic over-explanation | narrator explicitly explains theme | 77% | 52% |
| | dialogue serves philosophical debate | 59% | 34% |
| Linear plot | **no subplots** | 79% | 57% |
| | resolution favours protagonist agency | 69% | 46% |
| Sensory over-description | emotion via physical sensation / bodily metaphor | 81% | 38% |
| | smell-based imagery | 82% | 57% |
| | explicit emotion labels | 8% | 29% |
| Reduced intertextuality | named references | 24% | 47% |
| | vague allusions | 72% | 50% |
| | fourth-wall break | 39% | 67% |
| Homogeneity | mean narrative-rarity percentile | 0.49 | 0.71 |

Narrative features **alone** classify human vs AI at 93.2% macro-F1 (84.8% on a core 30-feature
subset), and still 93.9% after style-artifact removal.

**Design consequence — this reorders the priorities.** The tell is *narrative-structural*, not
prose-stylistic; scrubbing style does not remove it. Continuity, which sections 3–4 show is largely
solvable, is not what gives AI fiction away. Therefore:

- Subplots become a **hard structural obligation**, not an option. A thread architecture is
  literally a subplot architecture — the 79% / 57% row is the strongest single argument for this
  project's premise.
- The verifier needs **negative** constraints (do not explain the theme, do not route every
  emotion through the body, do not resolve everything through protagonist agency, name things
  concretely), not only positive ones.
- Rarity and variety must be measured across the whole manuscript, not per scene.

---

## 7. Prose-level repetition has a released solution

**Antislop** (Paech, Roush, Goldfeder, Shwartz-Ziv; submitted 2025-10-16) defines "slop" as
characteristic repetitive phraseology that degrades quality and makes AI text immediately
recognisable. Three components: an **Antislop Sampler** using backtracking at inference to
suppress unwanted strings without damaging the vocabulary; an automated pipeline profiling
model-specific patterns against human baselines; and **FTPO** (Final Token Preference
Optimization) adjusting individual token logits. Suppresses 8000+ patterns with ~90% reduction in
repetitive output, GSM8K/MMLU held steady. MIT-licensed.
([arXiv](https://arxiv.org/abs/2510.15061))

Usable artifacts: [`antislop-sampler`](https://github.com/sam-paech/antislop-sampler) including
`slop_phrase_prob_adjustments.json` (auto-generated from over-represented words in a large
LLM-generated story dataset), `antislop-vllm` (any OpenAI-compatible `/v1/completions` endpoint
returning top logprobs), `auto-antislop`, `slop-forensics`.

**Design consequence.** Do not hand-write a slop list. Use theirs as a data dependency, check at
the phrase level after drafting, and treat backtracking-at-sampling as the eventual local-model
path.

---

## 8. Pacing has an algorithm

**CONCOCT** (Wang, Yang, Liu, Klein — arXiv 2311.04459) targets "unnatural pacing, whether
glossing over important events or over-elaborating on insignificant details". Method: a trained
**concreteness evaluator** that judges which of two events is more detailed or abstract; a
**vaguest-first** hierarchical expansion that expands the most abstract outline items first,
aiming at uniform pacing; and filtering of new outline elements by predicted concreteness. Human
evaluators found more consistent pacing over 57% of the time versus baselines.
([arXiv](https://arxiv.org/abs/2311.04459))

**Design consequence.** This answers "how do I know when a node is small enough to write?" — do
not expand depth-first to a fixed depth; expand the vaguest frontier node until concreteness is
uniform. Implemented in `schedule.vaguest_first` / `schedule.score_spec`, driven by
`planner.expand_beats`.

**Where we deviate, and why.** CONCOCT trains a pairwise concreteness evaluator. We keep the
*algorithm* and substitute a deterministic proxy (`schedule.concreteness`): concrete nouns, proper
names and numerals raise the score, abstraction nouns and interiority verbs lower it, and
readiness is that density multiplied by how well the beats cover the scene's target length. The
algorithm only ever asks "which of these is least specified", so a ranker suffices where a
measurement is not needed. Swapping in a trained comparator changes one function.

Two bugs in that proxy are worth recording, because each made it silently useless rather than
merely inaccurate. Sentence-initial capitalised words counted as proper nouns, so *"The
protagonist comes to an understanding…"* scored as concrete as a scene full of named machinery and
both saturated at 1.0 — a frontier whose every item scores 1.0 cannot be ordered. And scoring
density alone meant *deleting* beats raised the score, ranking *"Things happen."* above a real
beat. A proxy that cannot rank is worse than no proxy, because the algorithm above it still runs.

---

## 9. Tension is measurable as unpredictability

Narrative tension can be metered by having an LLM forecast upcoming plot events at each segment
and measuring the **entropy** of those predictions: high entropy = high tension, low entropy =
predictable = low tension. The paper argues tension is downstream of hidden information (secrets,
delayed revelation) and that premature reveal produces stories that are "polished but flat"; it
recommends monitoring forecasting entropy during generation.
([arXiv](https://arxiv.org/pdf/2604.09854))

**Design consequence.** A forecastability probe: given the story so far, ask a model what happens
next. If it nails the next scene confidently, the scene is under-tensioned. Also implies threads
need an explicit *concealment* field — what the reader must not yet know.

**Implementation status, 31 August 2026: the concealment field ships and works. The probe does
not.** Two versions have failed. The first put the actual scene in its own prompt and asked the
model to "predict it before reading what happens next", then had the model score its own
closeness — a rationalisation with the answer supplied. The second predicts blind and compares
lexically, and calibration killed it: a prediction matches the scene it predicted 41% of the time
against a random other scene from the same book, which is worse than chance. Rarity weighting
reaches 51%. A two-sentence prediction and an 800-word scene share too little distinctive
vocabulary, and what they do share is the book's furniture.

Note what the paper actually specifies, which neither version implemented: the entropy of a
forecasting **distribution**, not the accuracy of one sample. Measuring how much *k* predictions
disagree with each other never touches the scene, so shared vocabulary cannot confound it. That is
step 12 of [PLAN.md](PLAN.md) and is the version that should have been built first.

**The third attempt has now run, with embeddings, and it fails the same control.** 35 scenes of a
finished 71-scene novel, five blind predictions each, scored against the scene predicted and
against a random other scene from the same book:

| scorer | on target | on control | win rate |
|---|---:|---:|---:|
| lexical overlap | 0.549 | 0.543 | **51%** |
| embedding cosine | 0.749 | 0.739 | **54%** |

The bar was 65%. Meaning overlap separates a right guess from a wrong one no better than word
overlap did. Read the absolute cosines rather than the win rate — **.749 against .739**: a raw
similarity between any two scenes of one novel is high and says nothing at all, which is the
whole reason the control exists.

So the failure was never the *representation*. It is the comparison. A two-sentence prediction and
an eight-hundred-word scene from the same book are dominated by the book, in words and in meaning
alike, and no amount of better embedding removes that. The paper's own formulation — the entropy
of a forecasting distribution, which never touches the scene — is the only version left standing,
and it is now the one being measured.

**The more useful lesson came from setting the experiment up.** The plan assumed the 35
calibration predictions were on disk and a re-score with embeddings would be free. They were
not. `probe_forecast` records a Violation only when the overlap clears its threshold,
none ever did across the whole corpus, so the calibration lived in a throwaway script and left
nothing behind — the generation had to be paid for twice.

**An experiment whose only output is a pass/fail verdict cannot be re-analysed.** This project's
most expensive negative result was stored that way, and the fix generalises past this section:
`redthread/forecast.py` persists each prediction with the context that produced it, so a re-score
cannot silently change what the model was shown, and `score` computes its control in the same
pass as its result rather than as a later step somebody might skip.

---

## 10. Orchestration shape

**Agents' Room** (Google DeepMind, ICLR 2025) decomposes narrative writing into subtasks handled
by specialised agents — planning agents and writing agents — with a central **orchestrator** that
calls agents and consolidates their contributions into a shared **scratchpad**. Preferred by
expert evaluators over baselines. ([arXiv](https://arxiv.org/abs/2410.02603))

**Design consequence.** Confirms orchestrator + shared state + specialised single-purpose calls.
Our orchestrator is deterministic code rather than an agent, so the state is a store on disk
instead of a scratchpad in context.

---

## What one night of running it settled (2026-08-28)

The first full manuscript run — all local, one 8B in every role — turned four of this file's
design commitments into measured findings. Recorded here because they qualify sections above.

**Section 4's "localised sentence repair" needs to be literal.** ConWriter revises only the
conflict-bearing sentences. Our first implementation asked the model to return the *whole
corrected scene*, and on an 8B that is a different operation: five consecutive whole-scene
repairs changed nothing. Splicing single sentences by character offset — deletion in code for
narrator-gloss, a one-sentence rewrite between two context sentences otherwise — converges, and
its outputs can be code-verified before splicing (a model that lifted a style sample once lifts
it again inside its own "fix").

**The verifier must not sit inside the repair loop.** Re-running the LLM verify after every
repair attempt let single flipped verdicts on near-identical text poison the improvement
comparison: a real scene had its one deterministic major genuinely fixed four times, and each
time the judge invented a different new one. The loop is now driven by deterministic checks
alone; the judge verifies once at the end and its findings get one bounded response. Judges are
for judging, once — loops need stable measures.

**A local judge must be calibrated, not trusted — and the split is binary vs graded.**
qwen3:8b at temperature 0, three samples per fixture: flags deliberately glossy text 3/3, and
also flags "The tally sheet had been photocopied so often that the column headings had closed
up" — pure physical description — as thematic gloss, 3/3. Its *binary* judgments held up in
practice (its violated-prohibition calls located three real concealment leaks that repair then
fixed); its *graded* and aesthetic judgments ("partial", the StoryScope-derived tells) are noise
at this size. Policy: binary blocks, graded advises. The deterministic checks carry the tells.

**Concealment needs a lifetime.** Enforcing a thread's concealment as a prohibition on every
scene includes the scene whose post-conditions are the reveal — a brief that simultaneously
requires and forbids the same disclosure, which no writer can satisfy and which the judge
correctly flags from both sides. `Thread.reveal_scene` bounds it; the reveal scene's brief flips
from "still concealed" to "THIS is the scene that discloses".

## What the second book settled (2026-08-29)

*The Debt of Years* — 27 scenes, 30,046 words, planner-driven, one 8B — was two and a half times
longer than the first run and, unlike it, was not clean. Twelve defects. Two findings generalise
past this codebase.

**Section 4's "localised repair" needs a second qualifier: the repair must be sized like the check
that raised it.** The first run established that repair should be local rather than regenerative.
This one established that *local* is not one size. `check_seam` compares a scene's last
twenty-five words against the previous scene's ending; sentence-local surgery rewrites the one
sentence a violation's quote falls in. Scene 4 copied two sentences forward, surgery rewrote one
per round, the check re-fired on the remainder, and the scene exhausted a five-round budget five
times over without converging. The same mismatch appeared four more times in the same run — a
check counting seven copied n-grams and reporting one; a deletion capped at four sentences meeting
a 172-word copy; a missed obligation with no quote and therefore no repair at all. ConWriter's
formulation does not distinguish sentence-scoped from region-scoped conflicts, and the distinction
turns out to decide whether the loop terminates.

The mitigation that generalises is not a better repair but a structural assertion:
`tests/test_repair_coverage.py` parses the checks' own source, enumerates every blocking violation
kind they can emit, and fails if any lacks a repair route. A check added without one now breaks
the suite rather than a book.

**A constraint a judge cannot answer is worse than no constraint.** Section 4's `Forbid` operators
are symbolic in ConWriter and natural language here, and that gap has a cost nothing in the
literature names. A planner writing `forbid: "the decision is not finalized"` means *keep this
true*; read as a prohibition it demands the very thing it prevents, and the scene obeying the plan
is the one that gets blocked. Fifty of this plan's prohibitions were phrased that way. Three
sibling failures share the shape — an obligation naming a thread state ("reaches 'reoriented'"), an
obligation naming an absence ("neither resolved nor abandoned", "left unspoken"), and a
"do not reveal X" surviving past the scene where the schedule discloses X. In every case the prose
was fine and the rule was broken, which is invisible to a scene-level check and diagnosable only
at plan level. The audit now carries all four, and inverts the ones whose intent is unambiguous.

A third, smaller: **a beat written as prose is prose.** The planner produced beats like "Dain steps
forward, his boots crunching over dry leaves, his voice steady and low", the writer wrote what it
was given, and `check_brief_leak` correctly found seven copied runs. CONCOCT's vaguest-first
expansion (section 8) sharpens beats toward specificity with no ceiling on it; the ceiling is that
a beat must stay an instruction. Beats are now de-prosed at plan time.

## Open questions the research did not settle

1. **Optimal generation-unit size for prose quality.** Re3 drafts 256-token passages; ConWriter
   works at scene level; no source found compares unit sizes for *reader-perceived* quality. Our
   choice of scene-sized units with beat-sized specs is reasoning, not a cited result.
2. **Whether the chunk-buffer prefix trick helps prose.** Validated in a different modality only —
   and the second run showed it has a cost the source does not mention. Handing a small model the
   previous scene's last 150 words as continuity context makes that text an attractor: five of 27
   scenes opened or closed on it verbatim, one reproducing 172 words before starting its own
   story. The prefix is still fed forward, because the alternative is scenes that do not join,
   but it now arrives with an explicit prohibition on both ends and a deterministic repair behind
   that.
3. **Whether bottom-up amendment improves quality.** DOME shows dynamic outlining beats rigid
   outlining on conflict rate; nothing found isolates *upward* revision (prose amending its own
   spec) as a quality win. Still unbuilt.
4. **Local-model viability for the structured stages.** Answered by running it to completion
   twice, the second time from a premise rather than a hand-authored plan: an 8B carried every
   role — planner, writer, extractor, judge — through 27 scenes and 30,046 words, with three
   provisos that are now architecture. Extraction and planning work once reasoning is kept out of
   the output channel and JSON is constrained at the decoder. Judging works only within the
   calibrated envelope: binary verdicts block, graded and aesthetic ones advise. And *rewriting*
   works only when the model is not shown the text it must avoid — asked to replace a copied
   ending, and given that ending under a heading marking it forbidden, it returned the forbidden
   text twice in a row. Prefer a repair that needs no model at all. See
   [MODELS.md](MODELS.md), "The night it finished" and "The second book".
5. **Whether scheduling structure deterministically costs anything creatively.** Making both
   acceptance markers hold by construction (`schedule.py`) is our design, not a cited result. It
   removes a whole class of failure, but it also removes the model's freedom to put a turn where
   it wants one. No source found compares *scheduled* against *proposed* structure for
   reader-perceived quality, and a plan that never surprises its own scheduler may be worse in
   ways the audit cannot see. This is the largest unexamined assumption in the project.

---

## What two days of measuring settled (2026-08-30 / 31)

Four architectural findings, each of which changed code.

**A cap the prompt states and the code does not enforce is a quota.** The extraction prompt said
"AT MOST 15 FACTS" while `extract_facts` allowed 30; 301 of 376 scenes returned exactly 15 and
100% returned 14 or more. A model asked for a count will hit it. The limit is now enforced in
code and cuts by durability — knowledge first, then fixed details, then states, then events.

**A retrieval cap silently decides what a book can remember.** `Ledger.about` sorted
most-recent-first and truncated at 40, so at scene 71 of a 71-scene novel 888 facts matched the
scene's subjects, 40 survived, and the oldest came from scene 68. The final scene of the book
could see three scenes of its own history. The slice is now stratified — most of it recent, the
rest spread across everything older — and superseded placements are retired, because a `STATE` is
"true until changed" and nothing ever changed it.

**Everything in the brief arrives in every scene.** Three separate refrains traced back to the
brief *asking* for them: a catchphrase written into a character's voice reached 27 scenes of 71, a
figure of speech in a style sample reached 15, and a character steered at the story's own central
object put that object in 17. The general rule: before adding anything to the brief, ask what it
looks like repeated seventy times.

**Quality is addressed at the plan, never at the gate.** The rule that gating must only use what
code can check is what keeps this orchestrator honest, and it was read for two days as "quality
cannot be addressed at all". It cannot be *gated* on. Every quality gain here came through the
plan instead: one line in `SCENES_PROMPT` took dialogue from .077 to .223 of words and scenes
where the plan put people in a room and the prose left them silent from 23 of 71 to zero. A bad
plan costs a re-ask; a bad gate costs a book that never finishes.

### And one finding about the method itself

The project compared runs for two days before measuring what a comparison is worth. Two runs of
one plan with no change between them differ by 4% on dialogue share and word count, 12% on
manuscript duplication, 31–33% on gesture rate and recap, and **44% on the worst refrain**. Three
claims published on 30 August were retracted the next day for sitting inside that floor.

The rule that follows — *two runs of one plan, or no claim* — costs an hour of GPU per condition
and would have prevented every one of them. The corollary is narrower and more useful: **maxima
are the least trustworthy statistic here and were the ones quoted most often.** Full floor in
[evidence/replicate-noise-floor.md](evidence/replicate-noise-floor.md).

---

# Sources fetched 1 September 2026 — the PLAN2 pass

*Same contract, same ledger. These trace the design choices in [PLAN2.md](PLAN2.md).*

## 9. Self-correction works on external feedback, and only there

The critical survey of LLM self-correction (Kamoi, Zhang, Zhang, Han, Sasano — TACL 2024) finds
self-correction succeeds when **reliable external feedback** exists (code with interpreters, QA
with search), with large-scale fine-tuning (~100K+ instances), or on decomposable tasks — and
that "no prior work demonstrates successful self-correction with feedback from prompted LLMs,
except for studies in tasks that are exceptionally suited for self-correction." Its diagnosis:
"the bottleneck is in feedback generation."
([arXiv 2406.01297v3](https://arxiv.org/html/2406.01297v3))

**Design consequence.** PLAN2 step 32 improves the repair ladder by injecting the check's own
located evidence span — strengthening the external-feedback channel the literature says works —
and explicitly bans adding an LLM self-critique rung, which is the channel it says does not.

## 10. Zero-shot LLM judges are a measured ceiling; trained preference models beat it

LitBench (arXiv 2507.00769, EACL 2026): 2,480 held-out debiased human-labeled story comparisons
plus a 43,827-pair training corpus. The strongest off-the-shelf judge (Claude-3.7-Sonnet) reaches
**73%** agreement with human preference; trained Bradley–Terry and generative reward models reach
**78%**, beating every zero-shot judge, and an online human study confirms the trained rankings
generalize to new LLM-generated stories.
([arXiv 2507.00769](https://arxiv.org/abs/2507.00769))

At book length, LongStoryEval (Yang & Jin, arXiv 2512.12839) builds 600 books averaging 121K
tokens with reader reviews organized by aspect, finds aggregation- and summary-based evaluation
beat incremental judging, and shows an 8B summary-based judge (NovelCritique) outperforming
GPT-4o in aligning with human evaluations.
([arXiv 2512.12839](https://arxiv.org/abs/2512.12839))

**Design consequence.** PLAN2 phase 10 is gated on the human sheet, and any machine judging that
follows it is a *trained* judge used advisory-only (rule VI), never a zero-shot one — the 73%
ceiling is why "ask a big model what it thinks" is not on the plan. Anthropic's eval guidance
adds the separation rule: "use a different model to evaluate than the model used to generate"
([define success](https://platform.claude.com/docs/en/test-and-evaluate/define-success)) — the
writer must never be its own judge.

## 11. Ollama exposes no logprobs — token-level sampler work is out of reach locally

Verified against three primary sources: the official OpenAI-compatibility docs list `Logprobs`
(and `Logit_bias`) as unsupported on `/v1/chat/completions` and `/v1/completions`; the word
"logprobs" does not appear in the native `docs/api.md` at all; and the feature request is closed
as not planned.
([docs.ollama.com](https://docs.ollama.com/api/openai-compatibility),
[api.md](https://github.com/ollama/ollama/blob/main/docs/api.md),
[ollama#16117](https://github.com/ollama/ollama/issues/16117))

A search-result summary claiming v0.12.11 added logprobs was **contradicted by every primary
source** and is recorded in the ledger as such — the zero-assumption contract catching a
plausible falsehood mid-design.

**Design consequence.** The Antislop sampler's backtracking and FTPO's logit adjustment
(ledger row, arXiv 2510.15061) cannot be ported to this stack. Anti-repetition work stays at the
string level: the model-refrain list (its ablation is PLAN2 step 28), the refrain feedback, and
brief-side machinery.
