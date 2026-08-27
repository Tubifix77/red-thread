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

## Open questions the research did not settle

1. **Optimal generation-unit size for prose quality.** Re3 drafts 256-token passages; ConWriter
   works at scene level; no source found compares unit sizes for *reader-perceived* quality. Our
   choice of scene-sized units with beat-sized specs is reasoning, not a cited result.
2. **Whether the chunk-buffer prefix trick helps prose.** Validated in a different modality only.
3. **Whether bottom-up amendment improves quality.** DOME shows dynamic outlining beats rigid
   outlining on conflict rate; nothing found isolates *upward* revision (prose amending its own
   spec) as a quality win. Still unbuilt.
4. **Local-model viability for the structured stages.** Partly answered by running it: see
   [MODELS.md](MODELS.md). Word-target adherence, not prose quality, turned out to be the
   discriminator between local models, and four checks exist because of what they did to a real
   brief. Whether a local model can carry the *planner* — the most structured stage of all — is
   the open half.
5. **Whether scheduling structure deterministically costs anything creatively.** Making both
   acceptance markers hold by construction (`schedule.py`) is our design, not a cited result. It
   removes a whole class of failure, but it also removes the model's freedom to put a turn where
   it wants one. No source found compares *scheduled* against *proposed* structure for
   reader-perceived quality, and a plan that never surprises its own scheduler may be worse in
   ways the audit cannot see. This is the largest unexamined assumption in the project.
