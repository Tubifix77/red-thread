"""Deterministic checks. No model calls, no API key, no cost, no nondeterminism.

Everything that can be caught by counting is caught here, so the LLM verifier only spends
tokens on judgements that genuinely need reading comprehension. Each check maps to a specific
sourced failure mode (docs/RESEARCH.md); a check with no source behind it is marked as
engineering judgement in its docstring.

Checks return `Violation`s and never raise. Severity decides what the pipeline does:
BLOCKER refuses the commit, MAJOR triggers localised repair, MINOR is logged.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .models import (Scene, SceneSpec, Severity, StorySpec, ThreadKind, ThreadMove,
                     Violation)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# --------------------------------------------------------------------------------------
# text utilities
# --------------------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])[\s\"']+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


# --------------------------------------------------------------------------------------
# 1. length
# --------------------------------------------------------------------------------------

def check_length(scene: Scene, spec: SceneSpec, tolerance: float = 0.15) -> list[Violation]:
    """Under-generation is how a system fakes passing every other check."""
    n = scene.word_count()
    lo, hi = spec.word_target * (1 - tolerance), spec.word_target * (1 + tolerance)
    if n < lo:
        return [Violation("length", Severity.MAJOR,
                          f"{n} words, target {spec.word_target} (min {int(lo)}). Short scenes "
                          f"usually mean beats were skipped.", "check_length")]
    if n > hi:
        return [Violation("length", Severity.MINOR,
                          f"{n} words, target {spec.word_target} (max {int(hi)}).",
                          "check_length")]
    return []


# --------------------------------------------------------------------------------------
# 2. format leakage
# --------------------------------------------------------------------------------------

_META_PATTERNS = [
    (re.compile(r"^\s*#{1,6}\s", re.M), "markdown heading"),
    (re.compile(r"^\s*(scene|chapter)\s+\d+\s*[:.]?\s*$", re.I | re.M), "scene/chapter label"),
    (re.compile(r"\b(in this scene|this scene (shows|depicts|explores)|the scene ends)\b", re.I),
     "meta-narration about the scene"),
    (re.compile(r"^\s*(here is|here's|certainly|i've written|i have written)\b", re.I),
     "assistant preamble"),
    (re.compile(r"\b(word count|approximately \d+ words)\b", re.I), "word-count commentary"),
]


def check_format(scene: Scene) -> list[Violation]:
    """Prose only. Leaked structure is a blocker because it corrupts the manuscript file."""
    out = []
    for pattern, label in _META_PATTERNS:
        m = pattern.search(scene.text)
        if m:
            out.append(Violation("format", Severity.BLOCKER,
                                 f"output contains {label}", "check_format",
                                 m.group(0).strip()[:120]))
    return out


# --------------------------------------------------------------------------------------
# 3. slop phrases  (RESEARCH.md section 7)
# --------------------------------------------------------------------------------------

_slop_cache: list[str] | None = None


def load_slop(path: Path | None = None) -> list[str]:
    """Load the slop phrase list.

    Sourced from sam-paech/antislop-sampler rather than hand-written: the list is derived by
    measuring over-representation against a human baseline, which is not something intuition
    can reproduce. Missing file is not an error — the check simply becomes a no-op, and
    `data/README.md` says how to populate it.
    """
    global _slop_cache
    if _slop_cache is not None and path is None:
        return _slop_cache
    target = path or (DATA_DIR / "slop_phrases.txt")
    phrases: list[str] = []
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                phrases.append(line.lower())
    if path is None:
        _slop_cache = phrases
    return phrases


def slop_sample(n: int = 12) -> list[str]:
    """A sample of the slop list suitable for putting *in* a brief.

    The raw list is ordered by how it was generated, so its head is dominated by single words
    and over-represented character names (elara, lyra, kael). Naming those in a brief is noise —
    a writing session cannot act on "avoid the word canvas" the way it can act on "avoid a
    dance of". Multi-word entries are the ones that teach a register, so prefer them.
    """
    phrases = [p.strip() for p in load_slop()]
    multi = [p for p in phrases if " " in p and len(p) > 8]
    return (multi or phrases)[:n]


def check_slop(scene: Scene, story: StorySpec | None = None,
               slop: list[str] | None = None) -> list[Violation]:
    """Flag over-represented phrasings.

    The antislop list includes given names that are over-represented in LLM fiction (elara,
    lyra, kael…). A story legitimately using one would otherwise trip this check on every
    scene, so entries matching a character name in the spec are skipped.
    """
    lowered = scene.text.lower()
    exempt: set[str] = set()
    if story is not None:
        for c in story.characters:
            exempt.update(w for w in re.findall(r"[a-z']+", c.name.lower()) if w)

    hits: list[str] = []
    for phrase in (slop if slop is not None else load_slop()):
        needle = phrase.strip()
        if not needle or needle in exempt:
            continue
        # Single-word entries must match on word boundaries. Plain substring matching reported
        # "aria" inside "variance" on a real draft — and the list is full of short entries
        # ("shall", "realm", "canvas", "depths") that would each fire inside longer words.
        # Multi-word phrases are safe as substrings and cheaper to test that way.
        if " " in needle:
            if needle in lowered:
                hits.append(phrase)
        elif re.search(rf"\b{re.escape(needle)}\b", lowered):
            hits.append(phrase)

    if not hits:
        return []
    shown = ", ".join(f'"{h}"' for h in hits[:8])
    more = f" (+{len(hits) - 8} more)" if len(hits) > 8 else ""
    return [Violation("slop", Severity.MINOR,
                      f"{len(hits)} over-represented phrase(s): {shown}{more}",
                      "check_slop", hits[0])]


def check_style_leak(scene: Scene, story: StorySpec, n: int = 6) -> list[Violation]:
    """The draft reproduced a style sample from its own brief.

    Found by running a real local model against a real brief: qwen3:8b opened scene one with the
    style contract's first sample sentence, word for word. The brief presents samples as *the
    target register* — "match this prose" — and a model can read that as text to continue from.

    It is a MAJOR rather than a MINOR because it compounds: the same samples go into every brief,
    so an unchecked leak means the same sentence appears in scene after scene, and the manuscript
    develops a refrain nobody wrote.
    """
    if not story.style.samples:
        return []
    scene_grams = set(ngrams(words(scene.text), n))
    out: list[Violation] = []
    for sample in story.style.samples:
        sample_grams = set(ngrams(words(sample), n))
        shared = scene_grams & sample_grams
        if shared:
            out.append(Violation(
                "style_leak", Severity.MAJOR,
                f"the draft reproduces {len(shared)} {n}-word run(s) from a style sample in its "
                f"own brief — the samples show the register to match, not text to copy",
                "check_style_leak", " ".join(next(iter(shared)))))
    return out


def check_brief_leak(scene: Scene, spec: SceneSpec) -> list[Violation]:
    """The draft echoed its own beat summaries or scene summary back as prose.

    The sibling failure to `check_style_leak`, and the more damaging one: a model that narrates
    its instructions produces a scene that reads like its own outline.
    """
    scene_grams = set(ngrams(words(scene.text), 6))
    sources = [spec.summary, spec.notes] + [b.summary for b in spec.beats]
    out: list[Violation] = []
    for source in sources:
        if not source:
            continue
        shared = scene_grams & set(ngrams(words(source), 6))
        if shared:
            out.append(Violation(
                "brief_leak", Severity.MAJOR,
                "the draft reproduces wording from its own brief — it is narrating the "
                "instruction rather than dramatising it",
                "check_brief_leak", " ".join(next(iter(shared)))))
    return out


def check_forbidden(scene: Scene, story: StorySpec) -> list[Violation]:
    lowered = scene.text.lower()
    return [
        Violation("forbidden_phrase", Severity.MAJOR,
                  f'style contract forbids "{p}"', "check_forbidden", p)
        for p in story.style.forbidden_phrases if p.lower() in lowered
    ]


# --------------------------------------------------------------------------------------
# 4. somatic emotion  (RESEARCH.md section 6 — 81% AI vs 38% human)
# --------------------------------------------------------------------------------------

_BODY = (r"chest|stomach|throat|jaw|shoulders|spine|gut|ribs|heart|pulse|breath|hands|"
         r"fingers|skin|scalp|knees|lungs|blood")
_SOMATIC_VERB = (r"tighten\w*|clench\w*|drop\w*|lurch\w*|twist\w*|knot\w*|constrict\w*|"
                 r"seiz\w*|hammer\w*|race\w*|pound\w*|crawl\w*|prickl\w*|went cold|"
                 r"turned to ice|caught|hitch\w*|squeez\w*")

_SOMATIC_PATTERNS = [
    re.compile(rf"\b(?:her|his|their|its|the)\s+(?:{_BODY})\b[^.!?]{{0,40}}?\b(?:{_SOMATIC_VERB})\b",
               re.I),
    re.compile(rf"\b(?:{_SOMATIC_VERB})\b[^.!?]{{0,30}}?\b(?:her|his|their)\s+(?:{_BODY})\b", re.I),
    re.compile(r"\b(?:a|the)\s+\w+\s+(?:in|of)\s+(?:her|his|their)\s+"
               rf"(?:{_BODY})\b", re.I),
    re.compile(r"breath (?:she|he|they) (?:did ?n[o']t|hadn't) (?:know|realise|realize)", re.I),
]


# --------------------------------------------------------------------------------------
# point of view
# --------------------------------------------------------------------------------------

_DIALOGUE = re.compile(r"[\"“”«][^\"“”«»]*[\"“”»]")
# Case-insensitive: sentence-initial "My" and "Mine" are exactly the slips worth catching, and a
# case-sensitive alternation silently missed them, which skewed both severity thresholds.
_FIRST_PERSON = re.compile(r"\b(I|I'm|I'd|I'll|I've|me|my|mine|myself|we|us|our|ours)\b",
                           re.I)
_SECOND_PERSON = re.compile(r"\b(you|your|yours|yourself)\b", re.I)


def strip_dialogue(text: str) -> str:
    """Remove quoted speech, leaving narration.

    First-person pronouns inside dialogue are normal in a third-person narrative — characters say
    "I". Counting them would make the POV check fire on every scene containing conversation, so
    the quotes come out first.
    """
    return _DIALOGUE.sub(" ", text)


def check_pov(scene: Scene, story: StorySpec, max_slips: int = 2) -> list[Violation]:
    """Narration must be in the person the style contract specifies.

    Found by running a real local model: gemma3:12b wrote an entire scene in the first person
    against a third-limited contract, and every other check passed it. A POV break is not a
    stylistic quibble — it makes the scene unusable in the manuscript, and it is the cheapest
    possible thing to detect, so it is a BLOCKER when the narration is wholesale in the wrong
    person and a MAJOR for a handful of slips.

    `max_slips` exists for free indirect discourse: an italicised thought or a first-person aside
    is legitimate in close third. Wholesale first-person narration is not.
    """
    contract = (story.style.pov or "").lower()
    narration = strip_dialogue(scene.text)
    first = _FIRST_PERSON.findall(narration)
    second = _SECOND_PERSON.findall(narration)
    out: list[Violation] = []

    if "third" in contract:
        if len(first) > max_slips:
            # Scale severity by how pervasive it is: a few slips are repairable in place, but
            # narration that is simply in the wrong person needs rewriting, not patching.
            pervasive = len(first) > max(6, scene.word_count() // 120)
            match = _FIRST_PERSON.search(narration)
            start = max(0, match.start() - 50) if match else 0
            out.append(Violation(
                "pov_person", Severity.BLOCKER if pervasive else Severity.MAJOR,
                f"contract is '{story.style.pov}' but the narration uses first person "
                f"{len(first)} time(s) outside dialogue"
                + (" — the scene is written in the wrong person" if pervasive else ""),
                "check_pov", narration[start:match.end() + 60].strip() if match else ""))
        if len(second) > max_slips:
            out.append(Violation(
                "pov_person", Severity.MAJOR,
                f"contract is '{story.style.pov}' but the narration addresses the reader as "
                f"'you' {len(second)} time(s) outside dialogue", "check_pov"))

    elif "first" in contract and not first:
        out.append(Violation(
            "pov_person", Severity.MAJOR,
            f"contract is '{story.style.pov}' but the narration contains no first-person "
            f"pronouns at all", "check_pov"))

    return out


def check_somatic(scene: Scene, max_allowed: int = 1) -> list[Violation]:
    """AI fiction conveys emotion through bodily metaphor in 81% of stories, humans 38%.

    This is the most mechanical of the StoryScope tells and the easiest to catch by pattern.
    The threshold is engineering judgement, not a sourced number: one somatic beat per scene
    is deliberate, four is a tic.
    """
    found: list[str] = []
    for pattern in _SOMATIC_PATTERNS:
        found.extend(m.group(0).strip() for m in pattern.finditer(scene.text))
    # de-duplicate overlapping matches of the same span
    unique: list[str] = []
    for f in found:
        if not any(f in u or u in f for u in unique):
            unique.append(f)
    if len(unique) <= max_allowed:
        return []
    shown = "; ".join(f'"{u}"' for u in unique[:5])
    return [Violation("somatic_emotion", Severity.MAJOR,
                      f"{len(unique)} bodily-sensation emotion beats (allowed {max_allowed}): "
                      f"{shown}", "check_somatic", unique[0])]


# --------------------------------------------------------------------------------------
# 5. thematic gloss  (RESEARCH.md section 6 — 77% AI vs 52% human)
# --------------------------------------------------------------------------------------

_GLOSS_PATTERNS = [
    # The stem needs \w* attached, or "realised then that" slips past while "realise that" is
    # caught. Up to two intervening words covers "realised, only then, that".
    re.compile(r"\b(?:she|he|they)\s+(?:realis\w*|realiz\w*|understood|knew|saw)\s+"
               r"(?:\w+[,]?\s+){0,2}that\b", re.I),
    re.compile(r"\b(?:that|this) was what it (?:meant|was) to\b", re.I),
    re.compile(r"\bin that moment,? (?:she|he|they)\b", re.I),
    re.compile(r"\b(?:she|he|they) would (?:always )?remember\b", re.I),
    re.compile(r"\bwas,? (?:she|he|they) (?:thought|supposed),? (?:what|how|the)\b", re.I),
    re.compile(r"\bperhaps that was (?:the|all|what)\b", re.I),
    re.compile(r"\b(?:some|all) (?:things|people|loves|griefs) (?:are|were)\b", re.I),
]


def check_thematic_gloss(scene: Scene, max_allowed: int = 0) -> list[Violation]:
    """A cheap deterministic subset of thematic over-explanation.

    These patterns catch the narrator stepping out to name the point. They do not catch the
    subtle cases — that is what the LLM `theme_gloss` probe in verify.py is for. Two layers,
    because this is the loudest tell in the StoryScope data and worth catching twice.
    """
    found = []
    for pattern in _GLOSS_PATTERNS:
        for m in pattern.finditer(scene.text):
            start = max(0, m.start() - 40)
            found.append(scene.text[start:m.end() + 60].strip())
    if len(found) <= max_allowed:
        return []
    return [Violation("thematic_gloss", Severity.MAJOR,
                      f"{len(found)} narrator-explains-the-point construction(s)",
                      "check_thematic_gloss", found[0][:160])]


# --------------------------------------------------------------------------------------
# 6. the seam  (RESEARCH.md section 5)
# --------------------------------------------------------------------------------------

_OPENERS = [
    re.compile(r"^\s*(the (rain|sun|wind|air|morning|light|sky))\b", re.I),
    re.compile(r"^\s*\w+ (?:woke|awoke|opened (?:her|his|their) eyes)\b", re.I),
    re.compile(r"^\s*(?:later|afterwards?|the next (?:day|morning)),?\s", re.I),
]


def check_seam(scene: Scene, previous_tail: str) -> list[Violation]:
    """Cohesion, in STORYTELLER's sense: does this scene join the previous one?

    Two mechanical failures are detectable without a model. First, echo: the opening restates
    the closing image, which is what happens when a session is handed a tail and treats it as
    material to summarise rather than to continue. Second, the reset opener — weather, waking,
    or a time-skip label — which reads as a fresh start rather than a continuation.
    """
    out: list[Violation] = []
    if not scene.text.strip():
        return [Violation("seam", Severity.BLOCKER, "empty scene", "check_seam")]

    opening = " ".join(scene.text.split()[:60])

    if previous_tail:
        prev = set(ngrams(words(previous_tail), 4))
        new = set(ngrams(words(opening), 4))
        shared = prev & new
        if shared:
            echo = " ".join(next(iter(shared)))
            out.append(Violation(
                "seam_echo", Severity.MAJOR,
                f"opening repeats {len(shared)} four-word sequence(s) from the previous "
                f"scene's ending — it is restating instead of continuing",
                "check_seam", echo))

    for pattern in _OPENERS:
        m = pattern.search(scene.text)
        if m and previous_tail:
            out.append(Violation(
                "seam_reset", Severity.MINOR,
                "opens with a scene-reset move (weather / waking / time-skip label) despite "
                "following directly on from the previous scene",
                "check_seam", m.group(0).strip()))
            break
    return out


def check_character_overlap(spec: SceneSpec, previous_characters: list[str]) -> list[Violation]:
    """STORYTELLER enforces character overlap between consecutive scenes as a cohesion
    mechanism. This is a spec-level check, not a prose-level one: it flags a plan that hard-cuts
    the entire cast, which is legal but should be deliberate."""
    if not previous_characters:
        return []
    if set(spec.characters) & set(previous_characters):
        return []
    return [Violation("cohesion_cut", Severity.MINOR,
                      "no character carries over from the previous scene — full cast cut",
                      "check_character_overlap")]


# --------------------------------------------------------------------------------------
# 7. cross-manuscript repetition  (RESEARCH.md section 6 — homogeneity)
# --------------------------------------------------------------------------------------

def check_repetition(scene: Scene, committed_texts: list[str], n: int = 5,
                     max_repeats: int = 0) -> list[Violation]:
    """Imagery and phrasing reused from earlier scenes.

    Left unchecked, a model reaches for the same handful of images all manuscript long. This is
    invisible inside any single scene and only detectable across the corpus, which is exactly
    the kind of check a chunked architecture can do and a single long generation cannot.
    """
    if not committed_texts:
        return []
    corpus: Counter[tuple[str, ...]] = Counter()
    for text in committed_texts:
        corpus.update(set(ngrams(words(text), n)))
    repeats = [g for g in set(ngrams(words(scene.text), n)) if corpus[g] > max_repeats]
    if not repeats:
        return []
    shown = "; ".join(f'"{" ".join(g)}"' for g in repeats[:5])
    return [Violation("repetition", Severity.MINOR,
                      f"{len(repeats)} {n}-gram(s) already used earlier in the manuscript: "
                      f"{shown}", "check_repetition", " ".join(repeats[0]))]


def check_internal_repetition(scene: Scene, n: int = 4, max_repeats: int = 1) -> list[Violation]:
    """The same phrase twice inside one scene. Engineering judgement, not sourced."""
    counts = Counter(ngrams(words(scene.text), n))
    dupes = [(g, c) for g, c in counts.items() if c > max_repeats]
    if not dupes:
        return []
    dupes.sort(key=lambda gc: -gc[1])
    shown = "; ".join(f'"{" ".join(g)}" x{c}' for g, c in dupes[:5])
    return [Violation("internal_repetition", Severity.MINOR,
                      f"{len(dupes)} phrase(s) repeated within the scene: {shown}",
                      "check_internal_repetition", " ".join(dupes[0][0]))]


# --------------------------------------------------------------------------------------
# 8. sentence-rhythm monotony
# --------------------------------------------------------------------------------------

def check_rhythm(scene: Scene, min_stdev: float = 6.0) -> list[Violation]:
    """Uniform sentence length reads as machine cadence.

    Engineering judgement: StoryScope establishes that AI fiction is stylistically homogeneous
    but the specific threshold here is ours, tuned to flag obviously metronomic prose rather
    than to police style.
    """
    lengths = [len(words(s)) for s in sentences(scene.text)]
    if len(lengths) < 8:
        return []
    mean = sum(lengths) / len(lengths)
    stdev = (sum((x - mean) ** 2 for x in lengths) / len(lengths)) ** 0.5
    if stdev >= min_stdev:
        return []
    return [Violation("rhythm", Severity.MINOR,
                      f"sentence lengths are metronomic (mean {mean:.1f}, sd {stdev:.1f}); "
                      f"no short punch, no long run", "check_rhythm")]


# --------------------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------------------

def run_all(
    scene: Scene,
    spec: SceneSpec,
    story: StorySpec,
    previous_tail: str = "",
    previous_characters: list[str] | None = None,
    committed_texts: list[str] | None = None,
) -> list[Violation]:
    out: list[Violation] = []
    out += check_format(scene)
    out += check_length(scene, spec)
    out += check_seam(scene, previous_tail)
    out += check_character_overlap(spec, previous_characters or [])
    out += check_pov(scene, story)
    out += check_somatic(scene)
    out += check_thematic_gloss(scene)
    out += check_style_leak(scene, story)
    out += check_brief_leak(scene, spec)
    out += check_forbidden(scene, story)
    out += check_slop(scene, story)
    out += check_internal_repetition(scene)
    out += check_repetition(scene, committed_texts or [])
    out += check_rhythm(scene)
    return out


def worst(violations: list[Violation]) -> Severity | None:
    for level in (Severity.BLOCKER, Severity.MAJOR, Severity.MINOR):
        if any(v.severity is level for v in violations):
            return level
    return None


# ======================================================================================
# PLAN-LEVEL CHECKS
#
# These run on the spec tree before any prose exists. Both of the project's acceptance
# markers (docs/TESTING.md) are plan-level failures, and discovering after 90,000 words that
# the midpoint repeats the opening is the expensive way to learn it.
# ======================================================================================

def thread_scene_map(plan: list[SceneSpec]) -> dict[str, list[int]]:
    """thread id -> ordered scene indices in which the plan gives it work."""
    out: dict[str, list[int]] = {}
    for spec in sorted(plan, key=lambda s: s.index):
        for tid in spec.thread_ops:
            out.setdefault(tid, []).append(spec.index)
    return out


def check_subplot_independence(
    plan: list[SceneSpec], story: StorySpec, max_overlap: float = 0.8
) -> list[Violation]:
    """Marker 1: are there real sub-arcs, or one plot wearing several names?

    StoryScope measures no-subplots in 79% of AI stories against 57% of human ones
    (docs/RESEARCH.md section 6) — the largest structural gap it found. But a plan can look
    subplot-rich and contain none, because a thread that only ever advances alongside the main
    plot *is* the main plot. So the test is not "does a subplot exist" but "does any thread own
    scenes the main thread does not".
    """
    out: list[Violation] = []
    scene_map = thread_scene_map(plan)
    if not scene_map:
        return [Violation("no_threads", Severity.BLOCKER,
                          "no scene in the plan advances any thread",
                          "check_subplot_independence")]

    main_ids = [t.id for t in story.threads if t.kind is ThreadKind.MAIN]
    main_scenes = {i for tid in main_ids for i in scene_map.get(tid, [])}
    others = [t for t in story.threads if t.kind is not ThreadKind.MAIN and t.id in scene_map]

    if not others:
        return [Violation("no_subplots", Severity.MAJOR,
                          "every thread in the plan is kind=main — no subplot exists. This is "
                          "the single most common structural tell in machine-written fiction.",
                          "check_subplot_independence")]

    independent = []
    decorative = []
    for thread in others:
        scenes = set(scene_map[thread.id])
        overlap = len(scenes & main_scenes) / len(scenes) if scenes else 1.0
        (decorative if overlap > max_overlap else independent).append((thread, overlap))

    if not independent:
        detail = "; ".join(f"{t.id} ({o:.0%} of its scenes are main-thread scenes)"
                           for t, o in decorative)
        out.append(Violation(
            "decorative_subplots", Severity.MAJOR,
            f"no thread owns scenes of its own — every subplot rides along with the main "
            f"thread: {detail}. A subplot that never has the page to itself is set dressing.",
            "check_subplot_independence"))

    for thread, overlap in decorative:
        out.append(Violation(
            "decorative_subplot", Severity.MINOR,
            f"thread {thread.id} ({thread.name}) shares {overlap:.0%} of its scenes with the "
            f"main thread", "check_subplot_independence"))
    return out


def planned_state_sequence(plan: list[SceneSpec], thread_id: str) -> list[tuple[int, str]]:
    """(scene index, target state) for every state change the plan asks of a thread."""
    out: list[tuple[int, str]] = []
    for spec in sorted(plan, key=lambda s: s.index):
        op = spec.thread_ops.get(thread_id)
        if op and op.to_state:
            out.append((spec.index, op.to_state))
    return out


def check_stakes_progression(
    plan: list[SceneSpec], story: StorySpec, history: list[ThreadMove] | None = None
) -> list[Violation]:
    """Marker 2: does the midpoint shift the stakes, or restate the opening conflict?

    The author's observation is that weak models repeat early conflict at the midpoint instead of
    changing what is at risk. That turns out to be decidable from thread state history alone,
    with no model call and no reading — which is the clearest payoff of making thread state a
    machine instead of a description.

    Three distinct failures, in increasing order of how badly they mean the plan is broken:

    * **repeat** — a thread is asked to enter a state it has already occupied. The story is
      circling.
    * **regression** — a thread moves backwards through its states with no narrative reason the
      plan records.
    * **midpoint stall** — no state index increases across the middle third. If that holds for
      most threads, the manuscript's middle is treading water.
    """
    out: list[Violation] = []
    if not plan:
        return out

    indices = sorted(s.index for s in plan)
    lo, hi = indices[0], indices[-1]
    span = hi - lo + 1
    mid_start = lo + span // 3
    mid_end = lo + (2 * span) // 3

    stalled: list[str] = []
    active: list[str] = []

    for thread in story.threads:
        seq = planned_state_sequence(plan, thread.id)
        if not seq:
            continue
        active.append(thread.id)

        seen: dict[str, int] = {}
        prev_rank: int | None = None
        for scene_index, state in seq:
            if state in seen:
                out.append(Violation(
                    "state_repeat", Severity.MAJOR,
                    f"thread {thread.id} ({thread.name}) is asked to enter '{state}' again at "
                    f"scene {scene_index}, having already reached it at scene {seen[state]}. "
                    f"That is a repeat of the earlier conflict, not a complication.",
                    "check_stakes_progression"))
            else:
                seen[state] = scene_index

            rank = thread.state_index(state)
            if rank < 0:
                out.append(Violation(
                    "unknown_state", Severity.BLOCKER,
                    f"scene {scene_index} targets state '{state}' for thread {thread.id}, "
                    f"which is not in its state machine {thread.states}",
                    "check_stakes_progression"))
            elif prev_rank is not None and rank < prev_rank:
                out.append(Violation(
                    "state_regression", Severity.MAJOR,
                    f"thread {thread.id} moves backwards to '{state}' at scene {scene_index}",
                    "check_stakes_progression"))
            if rank >= 0:
                prev_rank = rank

        # did anything advance across the middle third?
        before = [thread.state_index(s) for i, s in seq if i < mid_start]
        during = [thread.state_index(s) for i, s in seq if mid_start <= i <= mid_end]
        entering = max(before) if before else -1
        leaving = max(during) if during else entering
        if leaving <= entering:
            stalled.append(thread.id)

    if active and len(stalled) > len(active) / 2:
        out.append(Violation(
            "midpoint_stall", Severity.MAJOR,
            f"{len(stalled)} of {len(active)} threads gain no ground between scenes "
            f"{mid_start} and {mid_end} ({', '.join(stalled)}). The middle of the manuscript "
            f"is restating its opening rather than raising the stakes.",
            "check_stakes_progression"))

    # unpaid threads are an error, not a mood
    for thread in story.threads:
        seq = planned_state_sequence(plan, thread.id)
        final = seq[-1][1] if seq else thread.current_state
        if thread.states and final != thread.states[-1]:
            out.append(Violation(
                "unpaid_thread", Severity.MAJOR,
                f"thread {thread.id} ({thread.name}) ends the plan at '{final}', never reaching "
                f"'{thread.states[-1]}'", "check_stakes_progression"))
        if thread.deadline_scene is not None:
            reached = next((i for i, s in seq if s == thread.states[-1]), None)
            if reached is None or reached > thread.deadline_scene:
                out.append(Violation(
                    "missed_deadline", Severity.MAJOR,
                    f"thread {thread.id} must resolve by scene {thread.deadline_scene}; the plan "
                    f"resolves it at {reached if reached is not None else 'never'}",
                    "check_stakes_progression"))

    return out


def _spec_text(plan: list[SceneSpec], story: StorySpec) -> str:
    """Everything the plan itself says, as one blob. Excludes the forbidden list itself."""
    parts = [story.title, story.premise, story.style.notes, *story.world_rules]
    for c in story.characters:
        parts += [c.name, c.description, c.voice]
    for t in story.threads:
        parts += [t.name, t.concealment, t.payoff]
    for spec in plan:
        parts += [spec.summary, spec.setting, spec.time, spec.notes]
        parts += [b.summary for b in spec.beats]
        for op in spec.thread_ops.values():
            parts += op.pre + op.post + op.forbid
    return " ".join(p for p in parts if p)


def check_spec_self_consistency(plan: list[SceneSpec], story: StorySpec) -> list[Violation]:
    """The plan must not violate its own style contract.

    Found by running the planner: asked to name what the premise rules out, a local model
    correctly listed `['xenomorph', 'creature', 'alien', 'sentient', 'hive mind']` in
    `forbidden_phrases` — and then described the ship as "sentient" in the premise it wrote two
    fields earlier. It authored the rule and broke it in the same output.

    This matters more than a stray word. Every scene brief is assembled from this text, so a
    prohibited term sitting in the premise is injected into all of them, and `check_forbidden`
    will then dutifully flag the prose for repeating what the brief told it.
    """
    if not story.style.forbidden_phrases:
        return []
    text = _spec_text(plan, story).lower()
    out: list[Violation] = []
    for phrase in story.style.forbidden_phrases:
        needle = phrase.strip().lower()
        if not needle:
            continue
        hit = (needle in text if " " in needle
               else re.search(rf"\b{re.escape(needle)}\b", text) is not None)
        if hit:
            out.append(Violation(
                "spec_self_violation", Severity.MAJOR,
                f'the plan forbids "{phrase}" and then uses it in its own text. Every brief is '
                f'built from this text, so the prohibited term goes into every scene.',
                "check_spec_self_consistency", phrase))
    return out


def check_cast_names(plan: list[SceneSpec], story: StorySpec) -> list[Violation]:
    """Character names that are over-represented in machine-written fiction.

    `check_slop` deliberately exempts character names, so a protagonist called Elara or Kael is
    invisible to it forever — every scene would trip on its own cast otherwise. That exemption
    has to be paid for here, once, at plan level, while the name can still be changed cheaply.

    A real planner run produced "Senna Kael"; `kael` is on the antislop list.
    """
    slop = {p.strip().lower() for p in load_slop() if p.strip() and " " not in p.strip()}
    if not slop:
        return []
    out: list[Violation] = []
    for character in story.characters:
        parts = re.findall(r"[A-Za-z']+", character.name)
        hits = [p for p in parts if p.lower() in slop]
        if hits:
            out.append(Violation(
                "slop_character_name", Severity.MINOR,
                f'"{character.name}" contains {", ".join(hits)}, which is over-represented in '
                f'LLM fiction. Rename now — once scenes are committed the name is in the prose.',
                "check_cast_names", character.name))
    return out


def check_concealment(plan: list[SceneSpec], story: StorySpec) -> list[Violation]:
    """Threads with nothing hidden produce predictable scenes.

    Tension is downstream of hidden information, and premature reveal yields prose that is
    "polished but flat" (docs/RESEARCH.md section 9). This is a weak structural proxy for the
    forecastability probe: a mystery-kind thread with an empty `concealment` field has nothing
    to withhold, so there is nothing for the reader to lean forward about.
    """
    out = []
    for thread in story.threads:
        if thread.kind in (ThreadKind.MYSTERY, ThreadKind.MAIN) and not thread.concealment:
            out.append(Violation(
                "no_concealment", Severity.MINOR,
                f"thread {thread.id} ({thread.kind.value}) declares nothing concealed from the "
                f"reader", "check_concealment"))
        if not thread.payoff:
            out.append(Violation(
                "no_payoff", Severity.MINOR,
                f"thread {thread.id} does not say what resolution looks like",
                "check_concealment"))
    return out


def audit_plan(plan: list[SceneSpec], story: StorySpec,
               history: list[ThreadMove] | None = None) -> list[Violation]:
    """Both acceptance markers plus the cheap structural checks, in one pass."""
    out: list[Violation] = []
    out += check_subplot_independence(plan, story)
    out += check_stakes_progression(plan, story, history)
    out += check_concealment(plan, story)
    out += check_spec_self_consistency(plan, story)
    out += check_cast_names(plan, story)

    # POV variety: a manuscript entirely in one head is legal but worth surfacing, since
    # StoryScope's homogeneity finding is about the absence of structural variation.
    povs = {s.pov for s in plan if s.pov}
    if len(plan) > 12 and len(povs) == 1:
        out.append(Violation("single_pov", Severity.MINOR,
                             f"all {len(plan)} scenes share one POV ({next(iter(povs))})",
                             "audit_plan"))

    targets = [s.word_target for s in plan]
    if targets and len(set(targets)) == 1 and len(targets) > 6:
        out.append(Violation(
            "uniform_scene_length", Severity.MINOR,
            f"every scene targets exactly {targets[0]} words — uniform scene length is a pacing "
            f"tell; vary it deliberately", "audit_plan"))
    return out
