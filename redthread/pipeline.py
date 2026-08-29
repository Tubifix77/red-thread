"""The scene pipeline: the deterministic state machine that writes one scene.

    brief → draft N candidates → deterministic checks → pick → LLM verify
          → localised repair (bounded) → commit gate

Three properties this shape guarantees, each borrowed from a source in docs/RESEARCH.md:

1. **Nothing enters dynamic memory until it passes.** ConWriter updates memory only after a
   scene clears its checks, so a bad scene leaves no residue for later scenes to build on. The
   commit gate lives in `Project.commit`; this module never touches the ledger directly.
2. **Repair is local.** ConWriter revises only the conflict-bearing sentences rather than
   regenerating the scene. Regeneration throws away the good prose along with the bad and, worse,
   resamples every other check.
3. **Candidates then selection.** Re3 generates multiple continuations and reranks them. Here the
   ranking is done by the deterministic checks, which cost nothing — so drafting three
   candidates and keeping the cleanest is cheaper than one draft plus two repair rounds.

The orchestrator is code, not an agent. Agents' Room uses an LLM orchestrator with a scratchpad;
we use a state machine with a store, because the whole point is that state survives the session.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import checks, verify
from .brief import render_brief, tail_of
from .llm import LLMError, Models, strip_reasoning
from .models import Scene, SceneSpec, Severity, Violation
from .progress import Progress
from .project import Project

WRITER_SYSTEM = (
    "You are a novelist writing one scene of a longer book. You will be given a brief that is "
    "binding: the continuity facts are what the reader already knows, the thread requirements "
    "are what this scene must accomplish, and the prohibitions are absolute. Write prose only. "
    "Do not summarise, do not comment on your work, do not use headings. Trust the brief — if "
    "something is not in it, it has not happened yet."
)

REPAIR_PROMPT = """Below is a scene from a novel, followed by specific problems found in it.

Fix ONLY the problems listed. Rewrite the smallest span of text that fixes each one — a phrase, a
sentence, at most two sentences. Everything else must come back word for word identical.

Do not improve prose that was not flagged. Do not add or remove events. Do not change the length
by more than a few words. If fixing a problem would require restructuring the scene, leave that
problem and fix the others.

PROBLEMS:
{problems}

SCENE:
---
{text}
---

Return the complete corrected scene as prose, nothing else."""

# What to actually *do* about each kind of violation. The checks are good at saying what is wrong
# and were saying nothing about the remedy, which left a weak model to infer it — and a real run
# spent all three repair attempts returning prose that had not changed. A violation with an
# instruction attached is a task; one without is a complaint.
REMEDIES = {
    "style_leak": ("Find the sentence lifted from the style samples and write a different "
                   "sentence in the same rhythm. The samples show the register to match, not "
                   "text to reuse."),
    "brief_leak": ("Replace the sentence that restates the brief with the thing itself: the "
                   "action, the object, the words spoken."),
    "tell_thematic_gloss": ("Delete the sentence that names what the scene means. Do not replace "
                            "it with anything. The scene means it without saying so."),
    "thematic_gloss": ("Delete the realisation or summary clause. Keep only what a camera could "
                       "record."),
    "somatic_emotion": ("Replace the bodily-sensation lines with what the character does, or "
                        "refuses to do. Keep at most one."),
    "forbidden_phrase": "Rewrite the phrase. Any wording will do except that one.",
    "pov_person": ("Convert the narration to the contracted person. Dialogue keeps its own "
                   "pronouns."),
    "format": "Delete the heading, label, or commentary. Return prose only.",
    "seam_echo": ("Rewrite the opening so it continues from the previous scene instead of "
                  "restating its ending."),
    "seam_reset": "Replace the opening move; do not start with weather, waking, or a time label.",
    "thread_obligation": ("This did not happen on the page. Make it happen, concretely, in the "
                          "smallest number of sentences that will carry it."),
    "thread_prohibition": "Remove what was revealed. The reader must not learn it in this scene.",
    "continuity_contradiction": "Change the new detail to match what was established earlier.",
    "truncated_scene": ("The scene was cut off mid-sentence. End it properly at its last "
                        "complete beat instead."),
    "internal_repetition": "Vary the repeated phrasing.",
    "slop": "Replace the flagged phrasing with something plainer.",
}

# Violation kinds whose remedy is deletion of the offending sentence. For these, when the quote
# locates in the text, no model is needed at all: the sentence is spliced out in code. That is
# the cheapest possible repair and — for narrator-gloss, which lives in self-contained sentences
# like "And she knew that no one else would ever see it." — usually the correct one.
DELETE_KINDS = {"thematic_gloss", "tell_thematic_gloss", "thread_prohibition"}

# Violation kinds handled by a dedicated repair action rather than by a REMEDIES prompt line,
# and the kinds no repair can address at all. Kept as data so `tests/test_repair_coverage.py`
# can assert that every blocking kind a scene check emits has *some* route to a repair that can
# reach it. That assertion is the one that was missing: `seam_tail_copy` had no REMEDIES entry
# and no route of its own, so it fell through to sentence-local surgery, which rewrites the
# sentence a quote lands in while the check compares a whole region. It could never converge,
# and 292 green tests said nothing about it because the fixtures were built not to trip it.
DEDICATED_REPAIRS = {
    "thread_obligation": "fulfil",
    "length": "expand",
    "length_runaway": "trim",
    "truncated_scene": "snap",
    "seam_echo": "deseam, then reseam",
    "seam_tail_copy": "deseam, then reseam",
}

# Kinds where the rule is a contract rather than a matter of craft: the phrase must not appear,
# the reveal must not happen. When a rewrite of one of these fails verification, the sentence is
# deleted whatever the scene's word count says, because the alternative is no progress at all.
ABSOLUTE_KINDS = {"forbidden_phrase", "thread_prohibition"}

NO_REPAIR = {"seam"}
"""Emitted only for an empty scene. There is nothing to repair, only to draft again."""

# What each repair action was chosen to fix. The repair loop accepts an action that cleared its
# own target even when the total violation count ties, so a repair is never discarded for
# trading the problem it was called for against one that has a repair of its own.
ACTION_TARGETS = {
    "expand": {"length"},
    "trim": {"length_runaway"},
    "snap": {"truncated_scene"},
    "deseam": {"seam_echo", "seam_tail_copy"},
    "reseam": {"seam_echo", "seam_tail_copy"},
}

SENTENCE_PROMPT = """One sentence in a novel scene must be rewritten.

Problem with it: {detail}
How to fix it: {remedy}

It sits in this context:

  …{before}
  >>> {sentence}
  {after}…

Write the replacement sentence only. No quotation marks around it, no commentary, no restating
the context sentences. Match the voice of the context. One sentence, two at most."""


RESEAM_PROMPT = """Rewrite the {position} of a novel scene. It currently reuses wording from the \
previous scene, which the reader has just read.

Every phrase and every image below must be replaced with a different one. Do not keep any run of
words from it. Do not end on the same object, gesture, or thought it ends on.

This is the passage to replace ({count} sentences, about {words} words):
---
{block}
---

It sits {adjacency}:
---
{context}
---

{guidance}

Write the replacement passage only — about {words} words, same voice, same events. No commentary."""


def _deseam(scene: Scene, previous_tail: str, violations: list[Violation],
            notes: list[str]) -> str | None:
    """Delete the copied block. No model call, and it cannot fail the way a rewrite can.

    A copied seam is the one violation whose repair is provably safe to do in code: the offending
    text is, by definition, something the reader has already read one scene ago, so deleting it
    removes nothing they do not have. Rewriting it is the harder job and — on a live run — the
    losing one. Handed the previous ending under a heading saying these words are forbidden, an
    8B copied them into its replacement twice in a row, in about a second each time. Showing a
    small model the text it must avoid is showing it the text to produce.

    So: drop whole sentences from the offending end until the check that flagged it stops firing.
    An ending that shrinks below the word target is a problem `_expand` already solves; an ending
    identical to the previous scene's is one nothing else solves.
    """
    if not previous_tail:
        return None
    kinds = {v.kind for v in violations}
    spans = checks.sentence_spans(scene.text)
    if len(spans) < 4:
        return None
    # One end per call. A scene can echo at both — scene 12 of a live run opened on the previous
    # scene's words and closed on them too — and trimming the ending can never clear the opening.
    # The first cut of this asked for both kinds to be gone before accepting, so every deletion
    # was rejected however well it worked, and the scene fell through to a rewrite that could not
    # help either. Fix the ending here; the next round sees the opening and fixes that.
    target = "seam_tail_copy" if "seam_tail_copy" in kinds else "seam_echo"
    if target not in kinds:
        return None
    from_end = target == "seam_tail_copy"

    original = len(scene.text.split())
    # Bounded by how much of the scene is duplicated, not by a sentence count. The first cut of
    # this stopped at four sentences and then met scene 7 of a live run, which reproduced the
    # whole of scene 6's closing — seven sentences, 150 words — before starting its own story.
    # Four sentences could not reach it, so nothing did. What actually matters is the fraction:
    # a quarter of a scene can be duplicate and the rest still be a scene, and the shortfall is
    # a job `_expand` already does. Past a quarter there is no scene here and a redraft is right.
    # Two bounds, not one. The word fraction alone let a live run cut 34 sentences — 253 words,
    # a quarter of the scene — off one opening to clear a single echo, which is not a seam repair
    # any more but a redraft with extra steps. The largest genuine case needed eleven.
    for drop in range(1, min(13, max(2, len(spans) - 2))):
        kept = spans[:-drop] if from_end else spans[drop:]
        if len(kept) < 3:
            return None
        candidate = scene.text[kept[0][0]:kept[-1][1]].strip()
        if len(candidate.split()) < original * 0.75:
            return None
        probe = Scene(spec_id=scene.spec_id, index=scene.index, text=candidate)
        still = {v.kind for v in checks.check_seam(probe, previous_tail)}
        if target in still or checks.check_truncated(probe):
            continue
        where = "ending" if from_end else "opening"
        notes.append(f"deseam: deleted {drop} sentence(s) of copied {where}; "
                     f"{original - len(candidate.split())} words removed")
        return candidate
    return None


def _reseam(scene: Scene, previous_tail: str, violations: list[Violation], models: Models,
            notes: list[str], round_no: int = 0) -> str | None:
    """Rewrite a whole opening or closing block that copied the previous scene.

    Sentence-surgical repair cannot fix a seam, and a real run proved it five rounds running:
    the checks compare *regions* — the first 60 words against the previous ending, the last 25
    against it — while a violation carries one n-gram, so `sentence_covering` rewrites one
    sentence of a two-sentence copy and the check fires again on the remainder. Scene 4 of a
    live book ended with two sentences lifted verbatim from scene 3 and could not be repaired.

    So the unit of repair matches the unit of detection: the whole block, replaced in one go,
    then verified with the very check that flagged it.
    """
    if not previous_tail:
        return None
    kinds = {v.kind for v in violations}
    spans = checks.sentence_spans(scene.text)
    if len(spans) < 3:
        return None

    if "seam_tail_copy" in kinds:
        position, adjacency = "ending", "at the very end of the scene, after this"
        block_spans = [s for s in spans if s[1] > len(scene.text) - 240][-3:]
        guidance = ("End on something concrete — an action completed, an object, words spoken. "
                    "Do not end on what anything means or on what the character knows.")
    elif "seam_echo" in kinds or "seam_reset" in kinds:
        position, adjacency = "opening", "at the very start of the scene, before this"
        block_spans = [s for s in spans if s[0] < 320][:3]
        guidance = ("Continue from the previous scene rather than re-establishing anything. Do "
                    "not open with weather, waking, a time label, or a name plus a stance verb.")
    else:
        return None

    if not block_spans:
        return None
    lo, hi = block_spans[0][0], block_spans[-1][1]
    block = scene.text[lo:hi].strip()
    if not block:
        return None

    context = (scene.text[max(0, lo - 400):lo].strip()[-380:] if position == "ending"
               else scene.text[hi:hi + 400].strip()[:380])

    prompt = RESEAM_PROMPT.format(
        position=position,
        count=len(block_spans), words=max(25, len(block.split())),
        block=block, adjacency=adjacency, context=context or "(nothing)",
        guidance=guidance)
    try:
        reply = models.writer.complete(prompt, system=WRITER_SYSTEM, max_tokens=700,
                                       temperature=min(1.0, 0.7 + 0.1 * round_no))
    except LLMError:
        return None

    replacement = strip_reasoning(reply.text).strip().strip('"').strip()
    if not replacement or len(replacement.split()) < len(block.split()) * 0.4:
        return None

    candidate = (scene.text[:lo].rstrip() + " " + replacement + " "
                 + scene.text[hi:].lstrip()).strip()
    # Verified with the same check that flagged it: a model told not to reuse the previous
    # ending will sometimes reuse it anyway, and splicing that in unchecked wastes the round.
    probe = Scene(spec_id=scene.spec_id, index=scene.index, text=candidate)
    still = {v.kind for v in checks.check_seam(probe, previous_tail)}
    if still & {"seam_tail_copy", "seam_echo"}:
        notes.append(f"reseam: the new {position} still echoes the previous scene; discarded")
        return None
    notes.append(f"reseam: rewrote the scene's {position} ({len(block_spans)} sentences)")
    return candidate


def _surgical(scene: Scene, spec: SceneSpec, violations: list[Violation], models: Models,
              notes: list[str], samples: list[str] | None = None,
              forbidden: list[str] | None = None, round_no: int = 0) -> str | None:
    """Sentence-local repair: splice out or rewrite only the offending sentences.

    This is what ConWriter's repair actually is — "revising only the conflict-bearing
    sentences" — and what the whole-scene REPAIR_PROMPT merely asked for. The difference
    matters on small local models: asked to return a full scene minus one flaw, an 8B
    regenerates the flaw or drifts elsewhere, and five consecutive whole-scene repairs on a
    real run changed nothing. Asked for one replacement sentence between two context
    sentences, the same model manages fine — and for DELETE_KINDS no model is needed at all.

    Returns the repaired text, or None when no violation's quote locates in the scene.
    """
    rank = {Severity.BLOCKER: 0, Severity.MAJOR: 1, Severity.MINOR: 2}
    spans: list[tuple[int, int, Violation]] = []
    for v in sorted(violations, key=lambda v: rank[v.severity]):
        if not v.quote:
            continue
        located = checks.locate_quote(scene.text, v.quote)
        if located is None:
            continue
        lo, hi = checks.sentence_covering(scene.text, located)
        # Skip a span already claimed by an earlier violation: two edits to one sentence
        # cannot both be applied, and the first is the more severe by sort order.
        if any(not (hi <= s_lo or lo >= s_hi) for s_lo, s_hi, _ in spans):
            continue
        spans.append((lo, hi, v))

    if not spans:
        return None

    text = scene.text
    # Deleting is free but costs words, and a real run deleted its way from 918 words to 772 —
    # under the length floor — while the judge kept finding new gloss. Delete only while the
    # scene can afford it; once at or below target, gloss sentences are rewritten into something
    # concrete instead, which holds the length while removing the tell.
    can_delete = scene.word_count() > spec.word_target
    for lo, hi, v in sorted(spans, key=lambda s: s[0], reverse=True):
        original = text[lo:hi].strip()
        # A BLOCKER outranks the length guard. Deleting gloss repeatedly can shrink a scene
        # under its floor, which is why `can_delete` exists — but a premature reveal cannot be
        # un-read by any later scene, while a short scene has `_expand` waiting for it. Scene 4
        # of a live book leaked a concealment, was under target, and so had its leaking sentence
        # *rewritten* instead of cut; the rewrite leaked it again and the scene was blocked.
        if v.kind in DELETE_KINDS and (can_delete or v.severity is Severity.BLOCKER):
            replacement = ""
            notes.append(f"surgical: deleted the {v.kind} sentence (no model call)")
        else:
            before = text[max(0, lo - 160):lo].strip()[-140:]
            after = text[hi:hi + 160].strip()[:140]
            remedy = REMEDIES.get(v.kind, "Rewrite it.")
            if v.kind == "forbidden_phrase":
                # The quote is the whole sentence now — `check_forbidden` quotes the sentence so
                # the span can be located at all — so the banned phrase itself comes from the
                # detail line, which names it.
                remedy = ("The phrase named above must not appear in your replacement, in any "
                          "form. Say the thing another way entirely.")
            elif v.kind in ("thematic_gloss", "tell_thematic_gloss"):
                remedy = ("Replace it with one concrete sentence: a physical action, a thing "
                          "seen, or words spoken. No meaning, no realisation, no summary.")
            prompt = SENTENCE_PROMPT.format(
                detail=v.detail[:220], remedy=remedy,
                before=before, sentence=original, after=after)
            try:
                # The temperature climbs with the round, past identical-prompt caching: a real
                # run got the same failed rewrite back in 0 seconds three rounds straight,
                # because nothing about the request had changed.
                reply = models.writer.complete(prompt, max_tokens=300,
                                               temperature=min(1.0, 0.6 + 0.15 * round_no))
            except LLMError:
                continue
            replacement = strip_reasoning(reply.text).strip().strip('"').strip()
            # A replacement three times the original has ignored the instruction; an empty one
            # is a deletion the kind did not ask for.
            if not replacement or len(replacement.split()) > 3 * max(4, len(original.split())):
                continue
            # Code-verified splices, wherever a deterministic test exists for the kind: the
            # writer that produced a flaw once tends to reproduce it inside its own "fix". A
            # real run rewrote a leaked sentence into one still sharing four 6-grams with the
            # sample, and rewrote gloss into fresh gloss. The checker decides, not the model's
            # promise; an unfixed replacement falls back to deletion when the length affords
            # it, else the span is skipped this round.
            failed_verify = False
            if v.kind == "style_leak" and samples:
                rep_grams = set(checks.ngrams(checks.words(replacement), 6))
                failed_verify = any(
                    rep_grams & set(checks.ngrams(checks.words(sample), 6))
                    for sample in samples)
            elif v.kind in ("thematic_gloss", "tell_thematic_gloss"):
                # Verified in context, not in isolation: a replacement can pass alone and still
                # form a fresh gloss construction across the splice seam — a real run spliced a
                # clean sentence after "…, but because" and produced "because she knew that…".
                spliced_region = (text[max(0, lo - 80):lo] + replacement
                                  + text[hi:hi + 80])
                probe = Scene(spec_id=scene.spec_id, index=scene.index, text=spliced_region)
                failed_verify = bool(checks.check_thematic_gloss(probe))
            elif v.kind == "forbidden_phrase":
                # Told "any wording will do except that one", a real run's writer returned the
                # sentence with the banned phrase intact, four rounds straight, each served
                # instantly from cache. The phrase's absence is checkable in one line.
                #
                # Against the contract's phrases, not against `v.quote`. `check_forbidden` quotes
                # the containing *sentence* now — it has to, or the span cannot be located — and
                # this line was still asking whether the whole original sentence came back, which
                # it never does. So every rewrite passed verification and scene 6 of a live run
                # spliced in two replacements that both still said "truth".
                lowered = replacement.lower()
                failed_verify = any(p.strip() and p.strip().lower() in lowered
                                    for p in (forbidden or []))
            elif v.kind == "somatic_emotion":
                # A writer that reaches for the body once reaches for it again in the rewrite:
                # "his gut twist" comes back as "his stomach knotted" and the check re-fires.
                # The replacement must contain no somatic beat at all — the scene's allowance is
                # already spent by the instance the check left unflagged.
                probe = Scene(spec_id=scene.spec_id, index=scene.index, text=replacement)
                failed_verify = bool(checks.check_somatic(probe, max_allowed=0))
            if failed_verify:
                # ABSOLUTE_KINDS are contract violations, not craft ones: the phrase must not
                # appear, the reveal must not happen. For those the length guard is the wrong
                # judge — scene 12 of a live run had the same banned word survive three rewrites
                # and be skipped every time, because the scene was under target and so deletion
                # was refused. Skipping makes no progress at all, while the shortfall a deletion
                # creates has `_expand` waiting for it.
                if can_delete or v.kind in ABSOLUTE_KINDS:
                    # A sentence that fails verification is better gone than kept.
                    replacement = ""
                    notes.append(f"surgical: {v.kind} rewrite failed verification; deleted")
                else:
                    notes.append(f"surgical: {v.kind} rewrite failed verification; skipped")
                    continue
            notes.append(f"surgical: rewrote the {v.kind} sentence")
        gap = " " if replacement else ""
        text = (text[:lo].rstrip() + gap + replacement + gap
                + text[hi:].lstrip()) if replacement else (
                text[:lo].rstrip() + " " + text[hi:].lstrip())

    text = text.strip()
    return text if text != scene.text.strip() else None


TRIM_PROMPT = """This scene is {actual} words. Its target is {target} words, so it has run
about {over} words past its brief — usually by continuing past where the scene should stop, or
by staging material that belongs to later scenes.

Cut it to roughly {target} words. Rules:

- Remove whole sentences and whole passages; do not compress good sentences into worse ones.
- Anything after the scene's last required beat is the first candidate to go: find where the
  scene should have ended, and end it there.
- Keep every beat listed below. Do not add anything new.
- The sentences you keep must survive word for word.

The beats this scene owes, in order:
{beats}

SCENE:
---
{text}
---

Return the complete trimmed scene as prose, nothing else."""

EXPAND_PROMPT = """This scene is {actual} words. Its target is {target} words, so it is short by
about {short}. A short scene almost always means beats were skipped or summarised.

Expand it to the target. Rules:

- Keep every sentence already written. You are deepening, not rewriting.
- Add nothing new to the plot: no new events, no new characters, no new facts about the world.
  Anything you add must be a closer look at something already there.
- Spend the words on the beats that are thinnest — where the scene currently summarises an action
  in one line, stage it instead: the physical steps, what is said, what is not said.
- Do not pad with reflection or interiority. Do not explain what anything means.

The beats this scene owes, in order:
{beats}

SCENE:
---
{text}
---

Return the complete expanded scene as prose, nothing else."""


PASSAGE_PROMPT = """One passage in a novel scene is too thin. Stage it properly.

This is the passage. Rewrite it at about {want} words — it is currently {have}:
---
{passage}
---

It sits between these, which you must NOT rewrite or repeat:

  BEFORE: …{before}
  AFTER:  {after}…

The beats this scene owes, for context — the passage covers part of this, not all of it:
{beats}

Rules:
- Add no new events, no new characters, no facts the scene has not already established. Every
  added word is a closer look at what is already happening here.
- Where the passage summarises an action in one line, stage it: the physical steps, what is said,
  what is not said, what is done instead of said.
- Do not pad with reflection or interiority. Do not explain what anything means.

Write the replacement passage only. No commentary."""


@dataclass
class SceneResult:
    scene: Scene
    violations: list[Violation] = field(default_factory=list)
    committed: bool = False
    attempts: int = 0
    candidates_drafted: int = 0
    repairs: int = 0
    notes: list[str] = field(default_factory=list)

    def blockers(self) -> list[Violation]:
        return [v for v in self.violations if v.severity is Severity.BLOCKER]

    def majors(self) -> list[Violation]:
        return [v for v in self.violations if v.severity is Severity.MAJOR]

    def summary(self) -> str:
        state = "committed" if self.committed else "REJECTED"
        counts = f"{len(self.blockers())} blocker, {len(self.majors())} major"
        return (f"scene {self.scene.index}: {state} — {self.scene.word_count()} words, "
                f"{counts}, {self.candidates_drafted} draft(s), {self.repairs} repair(s)")


@dataclass
class Config:
    candidates: int = 3
    """Drafts per scene. Selection is by deterministic check score, which is free."""
    max_repairs: int = 2
    """ConWriter repairs within bounded retry loops. Unbounded repair loops oscillate."""
    temperature: float = 1.0
    slop_sample: int = 12
    """How many slop phrases to name in the brief. The full list would swamp the prompt; the
    check catches the rest afterwards."""
    with_forecast: bool = False
    """The tension probe costs an extra call per scene. Off by default; worth running on
    midpoint scenes."""
    allow_commit_with_majors: bool = False
    """If a scene still has MAJOR violations after the repair budget, commit anyway or stop.
    Default is to stop: a manuscript that silently accumulates majors is the failure mode this
    whole architecture exists to prevent."""
    allow_out_of_order: bool = False
    """Write a scene whose predecessor is not committed. Off by default — see `write_scene`."""


def _prose_budget(words: int, backend=None) -> int:
    """Output budget for a call that must return a whole scene.

    Two tokens per word plus a small margin, and then whatever the backend needs for inline
    reasoning. Both halves came from real failures pulling in opposite directions: repair failed
    in twelve seconds on an 897-word scene because the budget covered the prose but not the
    reasoning that preceded it, and a draft ran to 5702 words against a 900-word target because a
    budget loose enough for reasoning is also loose enough to ramble — a minute of generation
    spent on a scene that was going to be rejected anyway.

    Asking the backend closes the gap: where reasoning is switched off, or returned in its own
    field, the overhead is zero and the budget can be tight.
    """
    overhead = getattr(backend, "reasoning_overhead", 4000) if backend is not None else 4000
    # 1.5 tokens per word puts the ceiling near 1.3x the target. That makes a 2x runaway
    # physically impossible — the climax scenes of a real run came back at 2973 and 3062 words
    # against a 1300 target, and five trims could not close a gap that size. A draft that hits
    # the ceiling ends mid-sentence instead, which `check_truncated` catches deterministically
    # and the trim path repairs at a sentence boundary. Bounded-and-detectable beats unbounded.
    return min(32000, int(words * 1.5) + 250 + overhead)


def _score(violations: list[Violation]) -> tuple[int, int, int]:
    """Sort key for candidate selection. Lower is better."""
    return (
        sum(1 for v in violations if v.severity is Severity.BLOCKER),
        sum(1 for v in violations if v.severity is Severity.MAJOR),
        sum(1 for v in violations if v.severity is Severity.MINOR),
    )


def _preceding_gap(project: Project, spec: SceneSpec) -> int | None:
    """The index of the nearest earlier planned scene that is not committed, if any."""
    earlier = [s for s in project.plan if s.index < spec.index]
    for candidate in sorted(earlier, key=lambda s: s.index, reverse=True):
        scene = project.scene(candidate.id)
        if scene is None or not scene.committed:
            return candidate.index
    return None


def write_scene(project: Project, spec: SceneSpec, models: Models,
                config: Config | None = None,
                progress: "Progress | None" = None) -> SceneResult:
    config = config or Config()
    # A quiet Progress rather than None-checks at every call site: the stage hooks are on the
    # hot path of a long run and littering them with `if progress:` obscures the pipeline.
    progress = progress or Progress(quiet=True)

    # Order matters more here than it looks. Every brief is assembled from committed state, so
    # writing scene 7 before scene 6 means writing against a ledger that is missing a scene's
    # facts and a seam that has no previous text — the two things this architecture exists to
    # supply. Fail loudly rather than produce a scene that looks fine and is unmoored.
    gap = _preceding_gap(project, spec)
    if gap is not None and not config.allow_out_of_order:
        result = SceneResult(scene=Scene(spec_id=spec.id, index=spec.index))
        result.violations = [Violation(
            "out_of_order", Severity.BLOCKER,
            f"scene {gap} is not committed, so scene {spec.index} would be written with no "
            f"previous text and an incomplete ledger. Write scenes in order, or set "
            f"allow_out_of_order if you know why you want this.", "pipeline")]
        result.scene.violations = result.violations
        return result

    previous = project.previous_committed(spec.index)
    previous_tail = tail_of(previous.text) if previous else ""
    previous_spec = project.spec(previous.spec_id) if previous else None
    previous_characters = previous_spec.characters if previous_spec else []
    committed_texts = project.committed_texts(before=spec.index)

    slop_sample = checks.slop_sample(config.slop_sample)

    brief = render_brief(spec, project.story, project.ledger, previous_tail,
                         previous_characters, slop_sample)
    progress.stage("brief", f"{len(brief.split()):,} words in, "
                            f"{len(project.ledger.as_of(spec.index - 1))} facts available")

    result = SceneResult(scene=Scene(spec_id=spec.id, index=spec.index))

    # ---------------------------------------------------------------- draft candidates
    def run_deterministic(text: str) -> tuple[Scene, list[Violation]]:
        candidate = Scene(spec_id=spec.id, index=spec.index, text=strip_reasoning(text))
        found = checks.run_all(candidate, spec, project.story, previous_tail,
                               previous_characters, committed_texts)
        return candidate, found

    scored: list[tuple[tuple[int, int, int], Scene, list[Violation]]] = []
    wanted = max(1, config.candidates)
    for attempt in range(wanted):
        try:
            reply = models.writer.complete(
                brief, system=WRITER_SYSTEM,
                max_tokens=_prose_budget(spec.word_target, models.writer),
                temperature=config.temperature)
        except LLMError as exc:
            result.notes.append(f"draft failed: {exc}")
            progress.stage(f"draft {attempt + 1}/{wanted}", f"failed: {exc}")
            continue
        result.candidates_drafted += 1
        candidate, found = run_deterministic(reply.text)
        scored.append((_score(found), candidate, found))
        blockers, majors, minors = _score(found)
        progress.stage(f"draft {attempt + 1}/{wanted}",
                       f"{candidate.word_count()}w · {blockers}B/{majors}M/{minors}m")

    if not scored:
        result.violations = [Violation("no_draft", Severity.BLOCKER,
                                       "every draft attempt failed", "pipeline")]
        result.scene.violations = result.violations
        return result

    # Violation tuples tie often (two drafts, one major each). Distance to the word target
    # breaks the tie — a real run kept a 2.4x runaway over an on-length draft because the sort
    # was stable and the runaway arrived first.
    scored.sort(key=lambda row: (row[0], abs(row[1].word_count() - spec.word_target)))
    _, scene, det_violations = scored[0]
    result.scene = scene
    if len(scored) > 1:
        result.notes.append(
            f"selected best of {len(scored)} candidates (scores: "
            + ", ".join(str(s) for s, _, _ in scored) + ")")

    # ------------------------------------------------- phase A: deterministic repair loop
    # The repair loop is driven by deterministic checks alone. It used to re-run the full LLM
    # verify after every attempt, and that shape deadlocked a real run four rounds straight: the
    # surgical fix removed the one deterministic major, then the judge — on near-identical
    # text — flipped a binary verdict it had passed before, injecting a fresh MAJOR that made
    # every attempt score as "no improvement". Judges are for judging, once; loops need stable
    # measures. This is also most of the scene's latency: one LLM verify instead of 1+N.
    story_so_far = "\n\n".join(t[-800:] for t in committed_texts[-3:])

    # Two consecutive failures of one action sideline it, so it cannot monopolise the budget.
    # A real scene burned all five rounds on expansions that came back unusable while two
    # style leaks — surgically fixable in one pass — never got a turn.
    sidelined: set[str] = set()
    failure_streak: dict[str, int] = {}
    redrafted = False

    def try_redraft(why: str) -> bool:
        """Draft the scene once more. Returns True when the new draft replaced the old one.

        Some violations are properties of the draft rather than of a span inside it, and the
        scene has only ever been attacked from the candidates drawn before the first check ran.
        Scene 7 of a clean-slate run opened on a long stretch resembling the previous scene:
        deletion could not reach it inside its bounds, rewriting it came back echoing twice, and
        whole-scene repair introduced a truncation. A new draft is the same operation the scene
        began with, and the only one left that can change what it is made of.
        """
        nonlocal redrafted, scene, det_violations
        if redrafted or result.repairs >= config.max_repairs:
            return False
        redrafted = True
        try:
            reply = models.writer.complete(
                brief, system=WRITER_SYSTEM,
                max_tokens=_prose_budget(spec.word_target, models.writer),
                temperature=min(1.2, config.temperature + 0.2))
        except LLMError as exc:
            result.notes.append(f"redraft failed: {exc}")
            return False
        result.repairs += 1
        result.candidates_drafted += 1
        fresh, fresh_det = run_deterministic(reply.text)
        blocked, majored, minored = _score(fresh_det)
        if _score(fresh_det) < _score(det_violations):
            scene, result.scene = fresh, fresh
            det_violations = fresh_det
            result.violations = fresh_det
            # The actions that failed did so against different text.
            sidelined.clear()
            failure_streak.clear()
            result.notes.append(f"{why}, so the scene was drafted again; the new draft scores "
                                f"better and replaces it")
            progress.stage("redraft", f"{fresh.word_count()}w · "
                                      f"{blocked}B/{majored}M/{minored}m")
            return True
        result.notes.append(f"{why}, so the scene was drafted again; the new draft was no "
                            f"better and was discarded")
        progress.stage("redraft", f"no better · {blocked}B/{majored}M/{minored}m")
        return False

    def attempt_fix(fixable: list[Violation]) -> str | None:
        short = next((v for v in fixable if v.kind == "length"
                      and scene.word_count() < spec.word_target), None)
        if short is not None and "expand" not in sidelined:
            return (_expand(scene, spec, models, result.notes,
                            round_no=result.repairs), "expand")
        if any(v.kind == "truncated_scene" for v in fixable):
            # Snap to the last complete sentence, in code. A truncated draft is the budget cap
            # doing its job; asking a model to "trim" it just regenerates at length — a real
            # finale burned four rounds that way. The cap sits near 1.3–1.5x target, so the
            # snapped scene lands in at worst minor-over territory.
            terminal = set('.!?…"\'') | {"”", "’"}
            complete = [hi for _, hi in checks.sentence_spans(scene.text)
                        if scene.text[:hi].rstrip()[-1:] in terminal]
            return (scene.text[:complete[-1]] if complete else None), "snap"
        if any(v.kind == "length_runaway" for v in fixable) and "trim" not in sidelined:
            return _trim(scene, spec, models, round_no=result.repairs), "trim"
        # Seams are region problems, not sentence problems, so surgical must never see one: it
        # rewrites the sentence a quote falls in, while the check compares a whole region, and a
        # live run spent five rounds nibbling one sentence off a two-sentence copy. Deletion
        # first — it needs no model and cannot come back still copying — then the rewrite.
        if any(v.kind in ("seam_tail_copy", "seam_echo") for v in fixable):
            if "deseam" not in sidelined:
                cut = _deseam(scene, previous_tail, fixable, result.notes)
                if cut is not None:
                    return cut, "deseam"
            if "reseam" not in sidelined:
                return (_reseam(scene, previous_tail, fixable, models, result.notes,
                                round_no=result.repairs), "reseam")
        quoteless = [v for v in fixable
                     if not (v.quote and checks.locate_quote(scene.text, v.quote))]
        if quoteless and "repair" not in sidelined:
            return _repair(scene, fixable, models, config), "repair"
        if "surgical" not in sidelined:
            repaired = _surgical(scene, spec, fixable, models, result.notes,
                                 samples=project.story.style.samples,
                                 forbidden=project.story.style.forbidden_phrases,
                                 round_no=result.repairs)
            if repaired is not None:
                return repaired, "surgical"
        if "repair" not in sidelined:
            return _repair(scene, fixable, models, config), "repair"
        # Every action that could address these violations has failed twice. Spending the rest
        # of the budget re-running them is how a scene burns five rounds changing nothing.
        return None, "exhausted"

    for _ in range(config.max_repairs):
        fixable = [v for v in det_violations
                   if v.severity in (Severity.BLOCKER, Severity.MAJOR)]
        if not fixable:
            break
        # The last round of a budget that has not converged is better spent on a new draft than
        # on one more repair of the same shape. Without this the redraft was unreachable in
        # practice: a live scene ran out of budget one round before every action had been
        # sidelined, which is the only other thing that triggers it.
        if (not redrafted and result.repairs >= 3
                and result.repairs == config.max_repairs - 1
                and any(v.severity is Severity.MAJOR for v in fixable)):
            if try_redraft("the repair budget was nearly spent without converging"):
                continue
            break

        repaired, action = attempt_fix(fixable)
        if action == "exhausted":
            if try_redraft("every repair had failed twice"):
                continue
            result.notes.append("every repair action for these violations has been tried twice "
                                "and failed; stopping early rather than spending the budget")
            progress.stage("repairs", "all actions exhausted")
            break
        if repaired is None:
            # Consume a round and try again with the temperature bumped, rather than forfeiting
            # the whole budget: a single unusable trim reply used to `break` here, leaving a
            # runaway scene unrepaired with three rounds still in hand.
            result.repairs += 1
            failure_streak[action] = failure_streak.get(action, 0) + 1
            if failure_streak[action] >= 2:
                sidelined.add(action)
                result.notes.append(f"{action} sidelined after {failure_streak[action]} "
                                    f"failures; other repairs get the remaining rounds")
            result.notes.append(f"{action} attempt {result.repairs} unusable; retrying")
            progress.stage(f"{action} {result.repairs}", "call failed or unusable · retrying")
            continue
        result.repairs += 1

        candidate, new_det = run_deterministic(repaired)
        improved = _score(new_det) < _score(det_violations)
        # An action that resolved the exact problem it was chosen for is accepted even when the
        # violation tuple ties, because trading one MAJOR for another is progress when the new
        # one has a repair and the old one has just exhausted its own. `_deseam` cut 155 copied
        # words off scene 21, cleared the seam, dropped the scene under its target, and was
        # discarded as "no improvement" — twice, then sidelined — leaving the copy in place.
        # It must never buy a BLOCKER in, though: without that clause an "expansion" carrying a
        # markdown heading was accepted for reaching the word target, and the blocker it
        # smuggled in held the scene anyway.
        no_new_blockers = not any(v.severity is Severity.BLOCKER for v in new_det)
        targets = ACTION_TARGETS.get(action, set())
        had = {v.kind for v in det_violations} & targets
        fixed_length = no_new_blockers and bool(had) and not ({v.kind for v in new_det} & targets)
        # A repair that fixes one thing and breaks another is not a repair. Whole-scene `_repair`
        # regenerates the prose, so it can undo work a dedicated action already did: on a live
        # run it cleared a style leak and handed back an ending copied from the previous scene,
        # two rounds after `deseam` had cut exactly that. Scoring alone accepted it, because the
        # totals improved. An action that cleared its own declared target is exempt — that is
        # `deseam` trading a seam for a shortfall, which is the trade it is *for*.
        # Partial progress toward a length target counts. `_expand_passage` caps how far one
        # passage may grow, so reaching a large shortfall is meant to take two rounds — but an
        # expansion that added 101 of the 121 words needed scored identically to no expansion at
        # all, was discarded, and after twice was sidelined. Scene 12 of a live run then had its
        # seam cut, which made the shortfall worse, with the only repair for it switched off.
        closer = False
        if action in ("expand", "trim"):
            before = abs(spec.word_target - scene.word_count())
            after = abs(spec.word_target - candidate.word_count())
            closer = after < before
        introduced = ({v.kind for v in new_det if v.severity is Severity.MAJOR}
                      - {v.kind for v in det_violations if v.severity is Severity.MAJOR})
        if introduced and not fixed_length:
            failure_streak[action] = failure_streak.get(action, 0) + 1
            if failure_streak[action] >= 2:
                sidelined.add(action)
            result.notes.append(f"{action} attempt {result.repairs} introduced "
                                f"{', '.join(sorted(introduced))}; discarded")
            progress.stage(f"{action} {result.repairs}",
                           f"introduced {', '.join(sorted(introduced))} · discarded")
            continue
        if not (improved or fixed_length or (closer and no_new_blockers)):
            failure_streak[action] = failure_streak.get(action, 0) + 1
            if failure_streak[action] >= 2:
                sidelined.add(action)
            result.notes.append(f"{action} attempt {result.repairs} did not improve; discarded")
            progress.stage(f"{action} {result.repairs}", "no improvement · discarded")
            continue
        failure_streak[action] = 0
        sidelined.discard(action)
        scene, result.scene = candidate, candidate
        det_violations = new_det
        blockers, majors, minors = _score(new_det)
        progress.stage(f"{action} {result.repairs}",
                       f"{candidate.word_count()}w · {blockers}B/{majors}M/{minors}m"
                       + ("  (length resolved)" if fixed_length and not improved else ""))

    # ------------------------------------------------- phase B: one LLM verify
    facts, llm_violations = verify.verify_scene(
        scene, spec, project.story, project.ledger, models, story_so_far,
        with_forecast=config.with_forecast)
    scene.facts = facts
    result.violations = det_violations + llm_violations
    blockers, majors, minors = _score(result.violations)
    progress.stage("verify", f"{len(facts)} facts extracted · {blockers}B/{majors}M/{minors}m")

    # ------------------------------------------------- phase C: one bounded response pass
    # The judge gets one answer, not a negotiation. Its evidence-located findings get a single
    # surgical pass plus one re-verify; quoteless "missed" obligations get one whole-scene
    # repair. Whatever remains after that decides the gate.
    serious = [v for v in llm_violations
               if v.severity in (Severity.BLOCKER, Severity.MAJOR)]
    if serious and config.max_repairs > 0:
        located = [v for v in serious
                   if v.quote and checks.locate_quote(scene.text, v.quote)]
        repaired = None
        if located:
            repaired = _surgical(scene, spec, serious, models, result.notes,
                                 samples=project.story.style.samples,
                                 forbidden=project.story.style.forbidden_phrases)
            action = "surgical"
        if repaired is None and any(v.kind == "thread_obligation" for v in serious):
            repaired = _fulfil(scene, serious, models, result.notes)
            action = "fulfil"
        if repaired is None:
            # Two tries, because the first can fail on the call rather than on the answer — a
            # live run lost scene 13's only response pass to one LLMError. Retrying a failed
            # call is not a negotiation with the judge; it is asking the question once.
            repaired = _repair(scene, serious, models, config)
            if repaired is None:
                repaired = _repair(scene, serious, models, config)
            action = "repair"
        if repaired is None:
            result.notes.append(f"{action} call failed; keeping previous draft")
            progress.stage(f"{action} {result.repairs + 1}", "call failed or unusable")
        if repaired is not None:
            result.repairs += 1
            candidate, new_det = run_deterministic(repaired)
            if not [v for v in new_det if v.severity is Severity.BLOCKER]:
                try:
                    facts, llm_violations = verify.verify_scene(
                        candidate, spec, project.story, project.ledger, models,
                        story_so_far, with_forecast=False)
                except LLMError as exc:
                    result.notes.append(f"re-verify failed: {exc}")
                else:
                    candidate.facts = facts
                    new_all = new_det + llm_violations
                    if _score(new_all) < _score(result.violations):
                        scene, result.scene = candidate, candidate
                        det_violations = new_det
                        result.violations = new_all
                        blockers, majors, minors = _score(new_all)
                        progress.stage(
                            f"{action} {result.repairs}",
                            f"{candidate.word_count()}w · "
                            f"{blockers}B/{majors}M/{minors}m")
                    else:
                        result.notes.append(
                            f"{action} response to the verify did not improve; discarded")
                        progress.stage(f"{action} {result.repairs}",
                                       "no improvement · discarded")

    # ---------------------------------------------------------------- commit gate
    scene.violations = result.violations
    scene.attempts = result.candidates_drafted + result.repairs
    result.attempts = scene.attempts

    if result.blockers():
        project.rollback(scene)
        project.put_scene(scene)
        return result
    if result.majors() and not config.allow_commit_with_majors:
        project.rollback(scene)
        project.put_scene(scene)
        result.notes.append(
            "held back: MAJOR violations remain after the repair budget. Re-run with a revised "
            "spec, or set allow_commit_with_majors to accept it.")
        return result

    project.commit(scene)
    result.committed = True
    progress.stage("commit", f"{len(scene.facts)} facts into the ledger")
    return result


def _repair(scene: Scene, violations: list[Violation], models: Models,
            config: Config) -> str | None:
    """Rewrite only the flagged spans.

    The quotes carried on each Violation are what make this possible — a violation that says
    "the prose explains the theme" is unactionable, while one that quotes the offending sentence
    localises the fix to a span. That is why `Violation.quote` exists.
    """
    lines = []
    for i, v in enumerate(violations, 1):
        lines.append(f"{i}. {v.detail}")
        if v.quote:
            lines.append(f'   Offending text: "{v.quote}"')
        remedy = REMEDIES.get(v.kind)
        if remedy:
            lines.append(f"   Fix: {remedy}")
    prompt = REPAIR_PROMPT.format(problems="\n".join(lines), text=scene.text)
    try:
        reply = models.writer.complete(prompt, system=WRITER_SYSTEM,
                                       max_tokens=_prose_budget(scene.word_count(), models.writer),
                                       temperature=0.6)
    except LLMError:
        return None
    text = strip_reasoning(reply.text)
    # A "repair" that returns a third of the scene has rewritten, not repaired.
    if len(text.split()) < scene.word_count() * 0.6:
        return None
    return text


def _trim(scene: Scene, spec: SceneSpec, models: Models, round_no: int = 0) -> str | None:
    """Shrink a runaway scene toward its target.

    The counterpart of `_expand`, and just as necessary: the whole-scene repair prompt forbids
    changing the length, so a runaway scene sent there is unfixable by construction — a real run
    burned four 52-second repairs on a 2.4x overrun that none of them were allowed to fix.
    """
    beats = "\n".join(f"  {i}. {b.summary}"
                      for i, b in enumerate(spec.beats, 1)) or "  (none)"
    prompt = TRIM_PROMPT.format(
        actual=scene.word_count(), target=spec.word_target,
        over=max(0, scene.word_count() - spec.word_target), beats=beats, text=scene.text)
    try:
        reply = models.writer.complete(
            prompt, system=WRITER_SYSTEM,
            max_tokens=_prose_budget(spec.word_target, models.writer),
            temperature=min(1.0, 0.4 + 0.2 * round_no))
    except LLMError:
        return None
    text = strip_reasoning(reply.text)
    # A "trim" that grew is not a trim. One that over-cut is still progress — the length checks
    # flag it and the expand path pulls it back up — so the floor is generous: a real run
    # rejected a usable trim, hit `break`, and forfeited the whole repair budget over it.
    if not (spec.word_target * 0.5 <= len(text.split()) < scene.word_count()):
        return None
    return text


FULFIL_PROMPT = """A scene of a novel is missing something it was required to make happen.

MISSING: {missing}

Write the passage that makes it happen — {want} words, three or four sentences. Show it: the
action, the object, what is said. Do not summarise it, do not have the narrator announce it, and
do not explain what it means.

If what is missing is a refusal, an avoidance, or a choice not to act, it is still something a
reader watches happen — stage what the character does instead. The paper they put back in the
tray, the door they walk past, the question they answer with a different question. A character
ignoring something is a character doing something else, deliberately, in front of us.

It goes here, between these two passages, which you must NOT rewrite or repeat:

  BEFORE: …{before}
  AFTER:  {after}…

Write the new passage only. No commentary."""


def _fulfil(scene: Scene, violations: list[Violation], models: Models, notes: list[str],
            round_no: int = 0) -> str | None:
    """Write the missing beat and splice it in, rather than asking for the scene back.

    A missed obligation is the one violation with nothing to point at: the judge says the scene
    never delivered X, so there is no quote, no sentence to rewrite, and `_surgical` has no
    purchase. That left whole-scene repair — which on an 8B returns a shortened rewrite that
    drops something else, and did so on the finale of a live run three times running.

    What the scene needs is not a rewrite but an addition, so this asks for the addition. It goes
    before the final passage, where a missing beat almost always belongs and where it cannot
    disturb an ending the seam checks have already cleared.
    """
    missing = [v for v in violations if v.kind == "thread_obligation"]
    paragraphs = [p for p in scene.text.split("\n\n") if p.strip()]
    if not missing or len(paragraphs) < 2:
        return None

    want = max(60, min(140, 900 - scene.word_count()) if scene.word_count() < 900 else 90)
    prompt = FULFIL_PROMPT.format(
        missing="\n".join(f"  - {v.detail.removeprefix('missed: ')}" for v in missing[:3]),
        want=want,
        before=" ".join(paragraphs[-2].split()[-50:]),
        after=" ".join(paragraphs[-1].split()[:50]))
    try:
        reply = models.writer.complete(prompt, system=WRITER_SYSTEM,
                                       max_tokens=_prose_budget(want + 200, models.writer),
                                       temperature=min(1.0, 0.7 + 0.1 * round_no))
    except LLMError:
        return None

    addition = strip_reasoning(reply.text).strip()
    if len(addition.split()) < 20:
        return None
    candidate = "\n\n".join(paragraphs[:-1] + [addition, paragraphs[-1]])
    if checks.check_format(Scene(spec_id=scene.spec_id, index=scene.index, text=candidate)):
        return None
    notes.append(f"fulfil: wrote {len(addition.split())} words staging "
                 f"{len(missing)} missed obligation(s)")
    return candidate


def _expand_passage(scene: Scene, spec: SceneSpec, models: Models, notes: list[str],
                    round_no: int = 0) -> str | None:
    """Grow the thinnest passage and splice it in, instead of asking for the whole scene back.

    The same lesson as `_surgical`. Whole-scene expansion asks an 8B to reproduce 876 words
    verbatim and add 270 more; it rewrites instead, comes back shorter, and the attempt is
    discarded. A live run lost a scene that way after `_deseam` had correctly cut a copied
    opening and left the scene under its target — the seam was fixed and the length was not.

    Asked for one paragraph between two it can see but must not touch, the same model manages.
    The first and last paragraphs are never chosen, so an expansion cannot reintroduce the seam
    violation that caused the shortfall.
    """
    shortfall = spec.word_target - scene.word_count()
    paragraphs = [p for p in scene.text.split("\n\n") if p.strip()]
    if shortfall <= 0 or len(paragraphs) < 3:
        return None

    # The paragraph closest in size to the shortfall, so the rewrite roughly doubles it. Picking
    # the thinnest regardless of the gap asked an 8B to turn 47 words into 467, and what came
    # back was padding that tripped three other checks. Growth is capped per round; a scene that
    # needs more than this gets it over two rounds instead of one distorted paragraph.
    interior = list(range(1, len(paragraphs) - 1))
    pick = min(interior, key=lambda i: abs(len(paragraphs[i].split()) - shortfall))
    passage = paragraphs[pick]
    have = len(passage.split())
    want = min(have + shortfall, have * 2 + 60)

    prompt = PASSAGE_PROMPT.format(
        passage=passage, have=have, want=want,
        before=" ".join(paragraphs[pick - 1].split()[-40:]),
        after=" ".join(paragraphs[pick + 1].split()[:40]),
        beats="\n".join(f"  {i}. {b.summary}" for i, b in enumerate(spec.beats, 1)) or "  (none)")
    try:
        reply = models.writer.complete(
            prompt, system=WRITER_SYSTEM,
            max_tokens=_prose_budget(want + 200, models.writer),
            temperature=min(1.0, 0.8 + 0.1 * round_no))
    except LLMError:
        return None

    replacement = strip_reasoning(reply.text).strip()
    if len(replacement.split()) <= have:
        return None

    rebuilt = list(paragraphs)
    rebuilt[pick] = replacement
    candidate = "\n\n".join(rebuilt)
    if checks.check_truncated(Scene(spec_id=scene.spec_id, index=scene.index, text=candidate)):
        return None
    notes.append(f"expand: staged the thinnest passage, {have} words to "
                 f"{len(replacement.split())}")
    return candidate


def _expand(scene: Scene, spec: SceneSpec, models: Models, notes: list[str],
            round_no: int = 0) -> str | None:
    """Grow an under-length scene toward its target without adding plot.

    Kept separate from `_repair` because the two instructions are contradictory: repair must not
    change the length, and this must. Conflating them meant a short scene could never be salvaged.
    """
    local = _expand_passage(scene, spec, models, notes, round_no=round_no)
    if local is not None:
        return local
    beats = "\n".join(f"  {i}. {b.summary}"
                      for i, b in enumerate(spec.beats, 1)) or "  (none)"
    prompt = EXPAND_PROMPT.format(
        actual=scene.word_count(), target=spec.word_target,
        short=max(0, spec.word_target - scene.word_count()), beats=beats, text=scene.text)
    try:
        reply = models.writer.complete(
            prompt, system=WRITER_SYSTEM,
            max_tokens=_prose_budget(spec.word_target, models.writer),
            temperature=min(1.0, 0.8 + 0.1 * round_no))
    except LLMError:
        return None
    text = strip_reasoning(reply.text)
    # An "expansion" that came back shorter has rewritten rather than expanded.
    if len(text.split()) <= scene.word_count():
        return None
    return text


def write_all(project: Project, models: Models, config: Config | None = None,
              start: int = 1, stop: int | None = None,
              on_result=None, progress: Progress | None = None) -> list[SceneResult]:
    """Write every planned scene in order, halting on the first scene that will not commit.

    Halting is deliberate. Every later scene's brief is built from committed state, so
    continuing past a rejected scene means writing against a ledger that is missing a scene's
    worth of facts — which manufactures exactly the incoherence the system is for.

    The project is saved after every scene, so an interrupted run resumes from where it stopped
    rather than starting over. On a manuscript-length run that is the difference between an
    inconvenience and losing hours of generation.
    """
    progress = progress or Progress.for_project(project, quiet=True)
    results: list[SceneResult] = []
    for spec in sorted(project.plan, key=lambda s: s.index):
        if spec.index < start or (stop is not None and spec.index > stop):
            continue
        existing = project.scene(spec.id)
        if existing and existing.committed:
            continue

        progress.scene_start(spec, project.story)
        result = write_scene(project, spec, models, config, progress)
        results.append(result)
        project.save()
        progress.scene_done(result)
        if on_result:
            on_result(result)
        if not result.committed:
            break
    project.write_manuscript()
    progress.summary(project.story)
    return results
