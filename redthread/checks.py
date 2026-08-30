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

from .models import (Scene, SceneSpec, Severity, StorySpec, Thread, ThreadKind,
                     ThreadMove, Violation)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# --------------------------------------------------------------------------------------
# text utilities
# --------------------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])[\s\"']+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


_SENTENCE_END = re.compile(r"[.!?…]+[\"'”’)]*", re.S)


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) character spans of sentences, covering the text in order.

    Span-aware so a repair can splice a single sentence out of a scene by offset instead of
    asking a model to reproduce the whole scene minus one line — which is the step small local
    models reliably fumble. Trailing text without terminal punctuation is one final span.

    Scans for the terminators and slices between them, rather than matching whole sentences with
    `[^.!?…]*[.!?…]+`. That pattern is quadratic on text containing no terminator at all: at every
    start position it consumes to the end, fails to find one, and backtracks the whole way. Four
    thousand unpunctuated words took 3.7 seconds, which is not hypothetical — a truncated draft is
    exactly that shape, and `check_truncated` and `_surgical` both land here.
    """
    spans: list[tuple[int, int]] = []
    pos = 0
    for m in _SENTENCE_END.finditer(text):
        if text[pos:m.end()].strip():
            spans.append((pos, m.end()))
        pos = m.end()
    if text[pos:].strip():
        spans.append((pos, len(text)))
    return spans


def normalise_quote(text: str) -> str:
    """Normalisation for locating a (possibly sloppily copied) quote inside a scene.

    Every replacement here is one-character-to-one-character, deliberately: `_denormalise_index`
    maps a normalised index back to a raw offset by walking both strings in step, and an n:1
    substitution (like "..." to one space) would desynchronise the walk. Whitespace collapse is
    the one n:1 rule, and the walk reproduces it exactly.
    """
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    text = text.replace("…", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def locate_quote(text: str, quote: str) -> tuple[int, int] | None:
    """Character span in `text` where `quote` occurs, tolerant of whitespace and curly quotes.

    Falls back to the quote's first eight words, because verifier quotes are often clipped at a
    fixed length mid-word. Returns None when the quote simply is not in the text — which, from a
    model-judge, means the evidence was invented and the finding should not be trusted.
    """
    if not quote or not quote.strip():
        return None
    hay = normalise_quote(text)
    full = normalise_quote(quote)
    clipped = " ".join(full.split()[:8])
    # The full quote may be short and exact — a forbidden phrase like "the truth" is nine
    # characters and trustworthy by construction. The *clipped* fallback keeps a higher floor,
    # because matching eight words of a judge's paraphrase against the text by accident is the
    # thing this function exists to refuse.
    for needle, floor in ((full, 6), (clipped, 12)):
        if len(needle) < floor:
            continue
        idx = hay.find(needle)
        if idx < 0:
            continue
        # Map the normalised index back to the raw text by walking both strings together.
        raw_idx = _denormalise_index(text, idx)
        raw_end = _denormalise_index(text, idx + len(needle))
        if raw_idx is not None and raw_end is not None:
            return (raw_idx, raw_end)

    # Third strategy: word-sequence match across punctuation. The repetition and style-leak
    # checks quote *token n-grams* ("up he turned the coupling a"), which can never contain the
    # sentence punctuation of the text they came from ("…look up. He turned the coupling a…"),
    # so a plain substring search misses exactly the quotes those checks produce.
    tokens = re.findall(r"[a-z0-9']+", full)[:10]
    if len(tokens) >= 3:
        pattern = r"\b" + r"\W+".join(re.escape(t) for t in tokens)
        m = re.search(pattern, text, re.I)
        if m:
            return m.span()
    return None


def _denormalise_index(raw: str, norm_index: int) -> int | None:
    count = 0
    previous_space = True
    for i, ch in enumerate(raw):
        mapped = ch.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
        if mapped in "…":
            mapped = " "
        is_space = mapped.isspace()
        if is_space and previous_space:
            continue
        if count == norm_index:
            return i
        count += 1
        previous_space = is_space
    return len(raw) if count == norm_index else None


def sentence_covering(text: str, span: tuple[int, int]) -> tuple[int, int]:
    """The full sentence span(s) containing a located quote."""
    start, end = span
    lo, hi = start, end
    for s_start, s_end in sentence_spans(text):
        if s_start <= start < s_end:
            lo = s_start
        if s_start < end <= s_end:
            hi = s_end
    return (lo, hi)


def words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


# --------------------------------------------------------------------------------------
# 1. length
# --------------------------------------------------------------------------------------

def check_length(scene: Scene, spec: SceneSpec, tolerance: float = 0.15,
                 runaway: float = 1.6) -> list[Violation]:
    """Under-generation is how a system fakes passing every other check.

    Over-generation needed a second threshold. A real run produced 5878 words against a 900-word
    target and, because overrun was scored MINOR, that draft *won* candidate selection over a
    correctly-sized one — fewer majors, and the scorer could not see that the scene had run six
    times past its brief. A modest overrun is a stylistic quibble; an overrun of this size means
    the model stopped following the brief and kept writing, usually straight through the end of
    the scene into material later scenes are supposed to cover.
    """
    n = scene.word_count()
    target = max(1, spec.word_target)
    lo, hi = target * (1 - tolerance), target * (1 + tolerance)
    if n < lo:
        return [Violation("length", Severity.MAJOR,
                          f"{n} words, target {target} (min {int(lo)}). Short scenes usually "
                          f"mean beats were skipped.", "check_length")]
    if n > target * runaway:
        return [Violation("length_runaway", Severity.MAJOR,
                          f"{n} words against a target of {target} — {n / target:.1f}x over. "
                          f"The scene did not stop where the brief ends, so it has probably "
                          f"written past its own material.", "check_length")]
    if n > hi:
        return [Violation("length", Severity.MINOR,
                          f"{n} words, target {target} (max {int(hi)}).", "check_length")]
    return []


def check_truncated(scene: Scene) -> list[Violation]:
    """A scene that stops mid-sentence was cut off, not ended.

    The counterpart of the bounded output budget: with the ceiling near 1.3x the word target, a
    runaway draft hits the cap instead of running to 2x, and what that looks like is a scene
    whose last character is not sentence-terminal. Deterministic, and repaired by the trim path,
    which ends at a sentence boundary by construction.
    """
    text = scene.text.rstrip().rstrip("\"'”’)")
    if not text:
        return []
    if text[-1] in ".!?…—":
        return []
    tail_words = " ".join(text.split()[-8:])
    return [Violation("truncated_scene", Severity.MAJOR,
                      "the scene stops mid-sentence — the draft hit its output ceiling",
                      "check_truncated", tail_words)]


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


def copied_runs(scene_text: str, source: str, n: int = 6,
                substantive: int = 0) -> list[str]:
    """Maximal word runs the scene shares with `source`, merged rather than counted as n-grams.

    Counting n-grams double-counts a single copy: "Ingrid exhales visible breath through the
    window" is seven words and therefore two overlapping six-grams, which read as two separate
    leaks and tripped a threshold meant to require two. Scene 9 of a live run was held on one
    copied phrase reported as two.

    `substantive` requires that many non-function words in a run before it counts, so a run that
    is mostly grammar — the shape any two sentences about the same event share — is not evidence
    of copying.
    """
    scene_tokens = words(scene_text)
    source_grams = set(ngrams(words(source), n))
    if not source_grams:
        return []
    hits = [i for i, gram in enumerate(ngrams(scene_tokens, n))
            if gram in source_grams
            and sum(1 for w in gram if w not in _FUNCTION_WORDS) >= substantive]
    runs: list[str] = []
    start = None
    previous = None
    for i in hits:
        if start is None:
            start, previous = i, i
        elif i == previous + 1:
            previous = i
        else:
            runs.append(" ".join(scene_tokens[start:previous + n]))
            start, previous = i, i
    if start is not None:
        runs.append(" ".join(scene_tokens[start:previous + n]))
    return runs


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
    out: list[Violation] = []
    for sample in story.style.samples:
        shared = copied_runs(scene.text, sample, n)
        # One violation per copied run. The third check to need this — after `check_somatic` and
        # `check_brief_leak` — and found the same way: `_surgical` rewrites the sentence a quote
        # falls in, so a single violation carrying one of seven runs gets one sentence rewritten
        # while the other six keep the check firing. Scene 6 of a live run spent four rounds
        # rewriting the same leak. Capped, because a draft with more than a handful has copied
        # the sample wholesale and wants redrafting.
        for run in shared[:6]:
            out.append(Violation(
                "style_leak", Severity.MAJOR,
                f"the draft reproduces this run from a style sample in its own brief "
                f"(one of {len(shared)}) — the samples show the register to match, not text "
                f"to copy",
                "check_style_leak", run))
    return out


# Function words carry no evidence of copying: a six-word run that is four of these and two
# nouns is what any two sentences about the same event look like.
_FUNCTION_WORDS = frozenset("""
a an and as at be been but by for from had has have he her him his in into is it its of on
or she that the their them then there they this to was were what when which who will with
would you your not no had's it's""".split())


def check_brief_leak(scene: Scene, spec: SceneSpec) -> list[Violation]:
    """The draft echoed its own beat summaries or scene summary back as prose.

    The sibling failure to `check_style_leak` — but it needs a looser threshold than its sibling,
    and originally did not have one. A style sample is text the scene has no business reproducing
    at all, so one shared run is proof. A beat summary *describes the scene's own events*, and a
    scene dramatising them will inevitably share content words with the sentence that ordered
    them. A live run held scene 4 back for the single run "his back to the council the" — the
    scene doing precisely what the beat told it to. Four of those six tokens are function words.

    So two conditions, both learned the same way `check_seam` learned its own: the shared run has
    to be substantive rather than grammar, and one of them is coincidence.
    """
    sources = [spec.summary, spec.notes] + [b.summary for b in spec.beats]
    out: list[Violation] = []
    for source in sources:
        if not source:
            continue
        shared = copied_runs(scene.text, source, n=6, substantive=4)
        if len(shared) < 2:
            continue
        # One violation per copied run, not one per source. The same lesson `check_somatic`
        # learned: `_surgical` rewrites the sentence a quote falls in, so a single violation
        # carrying one of seven runs gets one sentence rewritten and the check fires again on
        # the other six. Scene 26 of a live run spent every repair round that way. Capped,
        # because a draft with more than a handful is a draft that read its brief aloud and
        # wants redrafting rather than surgery.
        for run in shared[:6]:
            out.append(Violation(
                "brief_leak", Severity.MAJOR,
                f"the draft reproduces this run from its own brief (one of {len(shared)}) — "
                f"it is narrating the instruction rather than dramatising it",
                "check_brief_leak", run))
    return out


def check_forbidden(scene: Scene, story: StorySpec) -> list[Violation]:
    """One violation per occurrence, quoting the sentence rather than the phrase.

    The phrase alone is unusable as a repair target twice over. `locate_quote` refuses a needle
    shorter than six characters — a floor that exists so a judge's short paraphrase cannot match
    by accident — so a contract banning "truth" produced a violation that located nowhere,
    fell through to whole-scene repair, and held scene 1 of a live book with a five-letter word
    no repair could reach. And a phrase that appears three times needs three sentences rewritten,
    which is the same scope lesson `check_somatic` and `check_brief_leak` each learned.

    Quoting the containing sentence solves both: it is long enough to locate, and it is the exact
    span `_surgical` will rewrite.
    """
    out: list[Violation] = []
    lowered = scene.text.lower()
    if not any(p.strip() and p.strip().lower() in lowered
               for p in story.style.forbidden_phrases):
        return out
    spans = sentence_spans(scene.text)
    for phrase in story.style.forbidden_phrases:
        needle = phrase.strip().lower()
        if not needle:
            continue
        start = lowered.find(needle)
        seen: set[tuple[int, int]] = set()
        while start >= 0:
            covering = next(((lo, hi) for lo, hi in spans if lo <= start < hi), None)
            span = covering or (start, start + len(needle))
            if span not in seen:
                seen.add(span)
                out.append(Violation(
                    "forbidden_phrase", Severity.MAJOR,
                    f'style contract forbids "{phrase}", and this sentence uses it',
                    "check_forbidden", scene.text[span[0]:span[1]].strip()))
            start = lowered.find(needle, start + len(needle))
    return out


# --------------------------------------------------------------------------------------
# 4. somatic emotion  (RESEARCH.md section 6 — 81% AI vs 38% human)
# --------------------------------------------------------------------------------------

_BODY = (r"chest|stomach|throat|jaw|shoulders|spine|gut|ribs|heart|pulse|breath|hands|"
         r"fingers|skin|scalp|knees|lungs|blood")
_SOMATIC_VERB = (r"tighten\w*|clench\w*|drop\w*|lurch\w*|twist\w*|knot\w*|constrict\w*|"
                 r"seiz\w*|hammer\w*|race\w*|pound\w*|crawl\w*|prickl\w*|went cold|"
                 r"turned to ice|caught|hitch\w*|squeez\w*")

_SENSATION = (r"knot|tightness|ache|aching|lump|flutter|fluttering|chill|heat|warmth|pressure|"
              r"twist|twisting|hollow|hollowness|tremor|trembling|buzz|buzzing|sting|stinging|"
              r"burn|burning|tension|coldness|emptiness|pang|throb|throbbing|prickle|prickling|"
              r"shiver|quiver|catch|weight|heaviness|dryness|thickness|fist|clenching")

_SOMATIC_PATTERNS = [
    re.compile(rf"\b(?:her|his|their|its|the)\s+(?:{_BODY})\b[^.!?]{{0,40}}?\b(?:{_SOMATIC_VERB})\b",
               re.I),
    re.compile(rf"\b(?:{_SOMATIC_VERB})\b[^.!?]{{0,30}}?\b(?:her|his|their)\s+(?:{_BODY})\b", re.I),
    # "a knot in her stomach", "a tightness in his chest". The noun has to be a sensation:
    # matching any noun made "the pages in her hands" an emotion beat, which held scene 5 of a
    # live run through five repair rounds — the surgical rewrite kept the pages, because the
    # pages were the point of the sentence.
    re.compile(rf"\b(?:a|the)\s+(?:{_SENSATION})\s+(?:in|of)\s+(?:her|his|their)\s+"
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


def _pov_slips(scene: Scene, pattern: re.Pattern, detail: str,
               limit: int = 6) -> list[Violation]:
    """One violation per sentence containing a pronoun slip, quoting that sentence.

    A violation with no quote can only be answered by whole-scene repair, which on a small model
    is the repair that does not work. The sentence is what surgery rewrites, so the sentence is
    what the violation must point at.
    """
    out: list[Violation] = []
    seen: set[tuple[int, int]] = set()
    for lo, hi in sentence_spans(scene.text):
        sentence = scene.text[lo:hi]
        if not pattern.search(strip_dialogue(sentence)):
            continue
        if (lo, hi) in seen:
            continue
        seen.add((lo, hi))
        out.append(Violation("pov_person", Severity.MAJOR, detail, "check_pov", sentence.strip()))
        if len(out) >= limit:
            break
    return out


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
            # The pervasive case is deliberately quoteless, and that is the whole of its routing.
            # A quote is an invitation to sentence surgery, and surgery cannot fix narration
            # that is in the wrong person: gemma3:12b wrote scene 11 of a live run with 35
            # first-person uses outside dialogue, and the repair loop rewrote one sentence of
            # them three times before running out of budget. Without a quote the violation
            # cannot be located, which routes it to whole-scene repair and then to a redraft —
            # the only two things that can reach a register.
            quote = "" if pervasive else (
                narration[start:match.end() + 60].strip() if match else "")
            out.append(Violation(
                "pov_person", Severity.BLOCKER if pervasive else Severity.MAJOR,
                f"contract is '{story.style.pov}' but the narration uses first person "
                f"{len(first)} time(s) outside dialogue"
                + (" — the scene is written in the wrong person, so it needs redrafting rather "
                   "than repair" if pervasive else ""),
                "check_pov", quote))
        if len(second) > max_slips:
            # One violation per offending sentence, quoted. Reported as a bare count with no
            # quote, this routed to whole-scene repair — the only thing left when nothing can be
            # located — and scene 2 of a clean-slate run was held by three instances of a
            # generic "you" that surgery could have rewritten one sentence at a time.
            out += _pov_slips(scene, _SECOND_PERSON,
                              f"contract is '{story.style.pov}' but this sentence addresses the "
                              f"reader as 'you' (one of {len(second)} outside dialogue)")

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
    # One violation PER excess instance, each carrying its own quote. As a single violation
    # quoting only the first instance, surgical repair could fix one sentence per round and the
    # check re-fired on the remainder forever — a real scene with three beats burned its whole
    # repair budget that way. Per-instance violations become separate spans in one surgical
    # pass. The first `max_allowed` instances stay unflagged: they are the allowance.
    return [Violation("somatic_emotion", Severity.MAJOR,
                      f"bodily-sensation emotion beat {i + 1} of {len(unique)} "
                      f"(allowed {max_allowed}): \"{beat}\"",
                      "check_somatic", beat)
            for i, beat in enumerate(unique[max_allowed:], start=max_allowed)]


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

    # Added after measuring the gap between this check and the LLM probe across 89 committed
    # scenes: the probe called 85 of them glossy and these patterns fired on none of them. It
    # was right — "This wasn't just about the list. This was about something deeper, something
    # she couldn't yet name" is the tell in its purest form, and nothing here saw it. Each
    # pattern below fires on committed prose and on none of the reference drafts in
    # docs/evidence, and each was read in context before being kept.
    #
    # "had always known" was measured too, at 53 of 89 — and left out. It catches ordinary
    # description as readily as gloss ("his gaze was steady, the way it had always been"), and
    # a pattern firing on half the corpus needs to be right about all of it.
    re.compile(r"\b(?:this|it|that) (?:was|is)n?.{0,3}t? ?just (?:about|a|an|the)\b",
               re.I),
    re.compile(r"\bsomething (?:deeper|larger|bigger|older|else entirely)\b", re.I),
    re.compile(r"\b(?:could|did|can)\b.{0,4}(?:n.t|not) (?:yet )?(?:name|articulate|put into words)\b", re.I),
    re.compile(r"\bwas more than (?:a|just) (?!\d)\w+", re.I),
    # "as though the walls themselves held their breath" — read in a finished book and found to
    # be the same pattern one line up, under-matched twice: `as though` was already covered but
    # only with `the`, and the plural `themselves` was not covered at all. Across 119 committed
    # scenes the shipped form catches 8 hits in 7 scenes and these two catch 6 more in 5, at the
    # same rate and with the same zero occurrences in the reference drafts. Widened rather than
    # added, because it is one tell and not three.
    re.compile(r"\bas (?:if|though) (?:the|a|his|her|their) \w+ (?:itself|themselves)\b", re.I),
    re.compile(r"\ba kind of \w+", re.I),
]


def check_thematic_gloss(scene: Scene, max_allowed: int = 0) -> list[Violation]:
    """A cheap deterministic subset of thematic over-explanation.

    These patterns catch the narrator stepping out to name the point. They do not catch the
    subtle cases — that is what the LLM `theme_gloss` probe in verify.py is for. Two layers,
    because this is the loudest tell in the StoryScope data and worth catching twice.
    """
    found: list[tuple[int, str]] = []
    for pattern in _GLOSS_PATTERNS:
        for m in pattern.finditer(scene.text):
            start = max(0, m.start() - 40)
            found.append((m.start(), scene.text[start:m.end() + 60].strip()))
    if len(found) <= max_allowed:
        return []
    # One violation per construction. The fourth check to need this, after `check_somatic`,
    # `check_brief_leak` and `check_style_leak` — and found the same way, on a live run: scene 3
    # reported "5 narrator-explains-the-point construction(s)" as a single violation, `_surgical`
    # deleted the one sentence it quoted, four remained, and the check fired again on the
    # remainder until the budget ran out. A repair can only reach what a violation points at.
    found.sort()
    return [Violation("thematic_gloss", Severity.MAJOR,
                      f"the narration explains the point here (one of {len(found)} such "
                      f"constructions in the scene)",
                      "check_thematic_gloss", quote[:160])
            for _, quote in found[max_allowed:][:6]]


# --------------------------------------------------------------------------------------
# 6. the seam  (RESEARCH.md section 5)
# --------------------------------------------------------------------------------------

_OPENERS = [
    re.compile(r"^\s*(the (rain|sun|wind|air|morning|light|sky))\b", re.I),
    re.compile(r"^\s*\w+ (?:woke|awoke|opened (?:her|his|their) eyes)\b", re.I),
    re.compile(r"^\s*(?:later|afterwards?|the next (?:day|morning)),?\s", re.I),
    # Name-plus-stance: "Siv Alderman stood in the yard…". One is fine; as a habit it is scene
    # monotony — the first complete local manuscript opened eight of its ten scenes this way.
    re.compile(r"^\s*[A-Z][a-z]+(?: [A-Z][a-z]+)? (?:stood|was standing|sat|was sitting|"
               r"walked into|stepped into)\b"),
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
        # One shared 4-gram is not an echo. A real run flagged a scene for opening with "the
        # cold storage unit" — the story's central object, named in the previous scene's tail
        # because the story is about it. Entity names legitimately cross the boundary; an echo
        # is the *image* restated, which shows up as several shared runs.
        if len(shared) >= 2:
            echo = " ".join(next(iter(shared)))
            out.append(Violation(
                "seam_echo", Severity.MAJOR if len(shared) >= 3 else Severity.MINOR,
                f"opening repeats {len(shared)} four-word sequence(s) from the previous "
                f"scene's ending — it is restating instead of continuing",
                "check_seam", echo))

    for pattern in _OPENERS:
        m = pattern.search(scene.text)
        if m and previous_tail:
            out.append(Violation(
                "seam_reset", Severity.MINOR,
                "opens with a stock scene-opening move (weather / waking / time-skip / "
                "name-plus-stance) despite following directly on from the previous scene",
                "check_seam", m.group(0).strip()))
            break

    # The ending copied back. The brief hands each scene the previous one's tail as continuity
    # context, and the first complete local manuscript re-used that tail as its own closing
    # line, verbatim, in the very next scene — a refrain nobody wrote, logged only as a MINOR
    # repetition at the time. An ending duplicated across consecutive scenes is a MAJOR in its
    # own right.
    if previous_tail:
        # Windowed to the final 25 words: the observed failure was one full closing sentence
        # copied forward, and a wider window starts matching ordinary shared vocabulary from
        # mid-scene instead of the ending itself.
        closing = set(ngrams(words(" ".join(scene.text.split()[-25:])), 5))
        prev_close = set(ngrams(words(" ".join(previous_tail.split()[-25:])), 5))
        stolen = closing & prev_close
        if len(stolen) >= 3:
            out.append(Violation(
                "seam_tail_copy", Severity.MAJOR,
                f"the scene's ending repeats {len(stolen)} five-word run(s) of the previous "
                f"scene's ending — the closing line was copied forward",
                "check_seam", " ".join(next(iter(stolen)))))
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

_SPOKEN = re.compile(r"[\"“”]([^\"“”]{2,400})[\"“”]")


def dialogue_share(text: str) -> float:
    """Share of a scene's words spoken aloud."""
    words = len(text.split())
    if not words:
        return 0.0
    return sum(len(m.split()) for m in _SPOKEN.findall(text)) / words


def check_scene_is_peopled(spec: SceneSpec, scene: Scene, floor: float = 0.02) -> list[Violation]:
    """The spec put two people in the room and the prose gave them nothing to say.

    Not a judgement about quality — a discrepancy between the spec and the prose, which is the
    kind of thing this orchestrator is allowed to have an opinion about. The plan declares who is
    present; a scene with two or three of them and no dialogue at all has quietly become a solo
    scene, whatever the spec says.

    Found by reading the middle of a 71-scene book. Scene 38 is Vael alone in a ruin touching
    statues and remembering, and it reads exactly as flat as that sounds — but every check passed
    it, including `summary_distance`, because the flashback it turns into is narrated in simple
    past. What the measurement then showed is that the emptying-out is a *shape*: dialogue runs
    at 21% of words in the opening eighteen scenes, 15% in the next, 10% in the third and 9% in
    the last, and silent scenes go from 2 of 18 to 9 of 18. Twenty of the 71 were populated by
    the plan and silent on the page, clustered in the second half — including all four
    three-character scenes of the climax.

    Advisory, and deliberately so. Two people can share a scene in silence, and there is no
    corpus here saying what rate is normal in good fiction, so this must not hold a gate on a
    number nobody has calibrated. It earns its place in candidate selection, where preferring the
    draft in which the people present actually speak costs nothing.
    """
    if len(spec.characters) < 2:
        return []
    share = dialogue_share(scene.text)
    if share >= floor:
        return []
    names = ", ".join(spec.characters)
    return [Violation(
        "unpeopled_scene", Severity.MINOR,
        f"the spec puts {len(spec.characters)} characters in this scene ({names}) and none of "
        f"them speaks — {share:.0%} of the scene is dialogue. It has become one person "
        f"remembering.",
        "check_scene_is_peopled")]


def manuscript_refrains(committed_texts: list[str], n: int = 5, min_scenes: int = 3,
                        limit: int = 10) -> list[tuple[str, int]]:
    """Phrases this book has already used in several separate scenes, worst first.

    `check_repetition` finds these and reports them, and reporting is all it can do: a refrain
    is a property of the manuscript, and no repair applied to scene 37 removes a phrase from
    scenes 4, 9 and 22. The only place it can be acted on is *before* the next scene is written.

    Found by running 71 scenes instead of nine. Every scene of that book was individually clean
    — duplication .001 per scene — while the manuscript measured .030, thirty times higher, with
    "the blade at his side" in 8 of 37 scenes, "a pause stretched between them" in 4, and
    "casting long shadows across the" in 4. At nine scenes the same measure reads .015, so this
    is a defect that scales with length and is nearly invisible below it.

    The list stays short and appears late by construction: nothing at five scenes, three at ten,
    capped at `limit` after that. A five-word run is specific enough to route around — the same
    argument `check_ban_is_avoidable` makes for why a two-word ban is fair and a one-word ban is
    not — so this can be handed to the writer as a prohibition without starting a fight the
    prose loses.
    """
    if not committed_texts:
        return []
    seen: Counter[tuple[str, ...]] = Counter()
    for text in committed_texts:
        seen.update(set(ngrams(words(text), n)))
    hot = [(" ".join(g), c) for g, c in seen.items() if c >= min_scenes]
    hot.sort(key=lambda kv: (-kv[1], kv[0]))
    return hot[:limit]


def manuscript_gestures(committed_texts: list[str], min_scenes: int = 4,
                        limit: int = 6) -> list[tuple[str, int]]:
    """Movements this book keeps reaching for, across separate scenes.

    `manuscript_refrains` does this for wording and cannot see these, because what repeats is the
    movement and the words differ every time. Both feed the same brief section for the same
    reason: a refrain belongs to the manuscript, and nothing done to scene 60 removes a gesture
    from scenes 4, 9 and 22.

    Measured on two 71-scene books. The first has a jaw tightening in 13 separate scenes; the
    second, written after the dialogue fix, has eyes flicking in 13, a gaze lingering in 12 and
    fingers curling in 10 — and 11 distinct gestures reaching four or more scenes, against 5 in
    the first. More dialogue means more beats between lines, and the model draws them from the
    same short stock. A nine-scene book has none, so like the phrase refrains this is a defect
    that only appears with length.
    """
    if not committed_texts:
        return []
    scenes_with: Counter[tuple[str, str]] = Counter()
    # The verb half of a pair is a five-character stem, which groups "curled", "curling" and
    # "curls" together and is unreadable as English. Keep one real spelling per stem for the
    # label: this list goes into a brief, and telling a model to stop writing "fingers curle"
    # asks it to avoid a word nobody wrote.
    spelling: dict[tuple[str, str], str] = {}
    for text in committed_texts:
        for part, stem, where in gesture_pairs(text):
            spelling.setdefault((part, stem), _GESTURE_VERB.search(text, where,
                                                                   where + 60).group(1).lower())
        for pair in {(p, v) for p, v, _ in gesture_pairs(text)}:
            scenes_with[pair] += 1
    hot = [(f"{part} {spelling.get((part, stem), stem)}", c)
           for (part, stem), c in scenes_with.items() if c >= min_scenes]
    hot.sort(key=lambda kv: (-kv[1], kv[0]))
    return hot[:limit]


def check_repetition(scene: Scene, committed_texts: list[str], n: int = 5,
                     max_repeats: int = 0, refrain: int = 4) -> list[Violation]:
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

    # A refrain is not the same failure as an echo, and only one of them is worth stopping for.
    #
    # Some overlap between scenes of one book is the book: the same characters, the same objects,
    # the same room. The count of shared runs grows with the manuscript for that reason alone and
    # says little. What says a great deal is one phrase turning up in scene after scene — and a
    # live 15-scene run produced "she had not meant to" in ten of them, "the register was more
    # than a ledger" in six, "she had always believed in the data" in five. That is the failure
    # this check was written for, described in its own docstring, and it has been reported as an
    # aggregate MINOR and passed over every time.
    # Report the worst refrain by name, because the aggregate count hides it. Some overlap
    # between scenes of one book is the book — the same characters, objects and room — and the
    # count grows with the manuscript for that reason alone. What matters is one phrase turning
    # up scene after scene: a live 15-scene run produced "she had not meant to" in ten of them,
    # "the register was more than a ledger" in six, "she had always believed in the data" in
    # five. Reported as "48 5-grams already used earlier", none of that is visible.
    #
    # Advisory, and the reason is a limit of the test bed rather than of the finding. Making it
    # a MAJOR is tempting and probably right for real prose — every refrain measured in a live
    # book was stylistic, not the book's own vocabulary — but any fixture assembled from a pool
    # of components repeats those components across scenes as a matter of arithmetic, so the
    # suite cannot tell a refrain from a fixture. Shipping a gate the tests cannot represent is
    # how a green suite comes to prove nothing, which this project has already paid for once.
    worst = max(repeats, key=lambda g: corpus[g])
    lead = (f'"{" ".join(worst)}" has now appeared in {corpus[worst] + 1} scenes'
            if corpus[worst] >= refrain else
            "; ".join(f'"{" ".join(g)}"' for g in repeats[:5]))
    return [Violation("repetition", Severity.MINOR,
                      f"{len(repeats)} {n}-gram(s) already used earlier in the manuscript. "
                      f"{lead}", "check_repetition", " ".join(worst))]


def duplication_ratio(text: str, n: int = 4) -> float:
    """Fraction of the text's n-grams that are repeats. 0 is all fresh, 1 is one phrase looping.

    The clearest quality signal this project can count, and it was not being counted. Measured
    over 84 committed scenes plus the three single-scene model comparisons in `docs/evidence`:

        gemma3:12b, phi4:14b   0.000 – 0.002
        qwen3:8b, one scene    0.026
        committed scenes       median 0.289, p75 0.566, p90 0.630

    More than a quarter of the median committed scene is repeated material, and a quarter of
    scenes are more than half repeated. Counting *distinct* repeated phrases instead — the first
    version of this — scored a page that says one sentence thirty times as cleaner than varied
    prose, which is backwards.
    """
    grams = ngrams(words(text), n)
    if not grams:
        return 0.0
    return 1 - len(set(grams)) / len(grams)


def check_internal_repetition(scene: Scene, n: int = 4, max_repeats: int = 1,
                              tic: int = 5) -> list[Violation]:
    """The same phrase twice inside one scene. Engineering judgement, not sourced.

    Advisory on purpose, and the reasoning is worth recording because the obvious move is wrong.
    The duplication ratio discriminates beautifully — clean drafts sit at 0.00, the median scene
    an 8B commits at 0.29 — so the temptation is to make a high ratio a MAJOR and let repair fix
    it. But repeated phrasing is not localised: 29% duplication is not six bad sentences, it is
    the model's whole register, and no sentence-local repair reaches it. Gating would halt books
    over something nothing in the loop can mend.

    So the ratio is reported here and *acted on* where it costs nothing and cannot deadlock: in
    candidate selection, where the cleanest of several drafts wins. See `_score` in pipeline.py.
    """
    counts = Counter(ngrams(words(scene.text), n))
    dupes = [(g, c) for g, c in counts.items() if c > max_repeats]
    if not dupes:
        return []
    dupes.sort(key=lambda gc: -gc[1])
    ratio = duplication_ratio(scene.text, n)

    # A tic is not the same failure as a register, and only one of them is repairable.
    #
    # Diffuse duplication — a scene where 29% of the 4-grams recur, spread everywhere — is the
    # model's whole voice. No sentence-local repair reaches it, so it stays advisory and selection
    # handles it. But one phrase used five times in six hundred words is a verbal tic sitting in
    # five specific sentences, and rewriting four of them fixes it. A scene read from a live run
    # said "the way she always" five times and "the way she kept" three more; the aggregate ratio
    # was 3%, so it was reported as nothing.
    #
    # The line is drawn from the reference drafts in docs/evidence: gemma3:12b never repeats a
    # four-word run, phi4:14b manages two, and qwen3:8b's cleanest single scene reaches four.
    tics = [(g, c) for g, c in dupes if c >= tic]
    if tics:
        # One violation per *excess* sentence, quoting the sentence — not the phrase. Quoting the
        # phrase gives every violation the same span, `_surgical` collapses them to one edit, and
        # a single rewrite drops the count from five to four and clears the threshold without
        # fixing anything. Quoting sentences is what `check_forbidden` learned to do for the same
        # reason, and it lets one round take the tic down to the allowance.
        out: list[Violation] = []
        spans = sentence_spans(scene.text)
        for gram, count in tics[:3]:
            phrase = " ".join(gram)
            carriers = [scene.text[lo:hi].strip() for lo, hi in spans
                        if phrase in " ".join(words(scene.text[lo:hi]))]
            # Reduce to the allowance, not to one. `tic` is where a repetition becomes a tic,
            # so `tic - 1` uses is the target — which is also where qwen3:8b's cleanest measured
            # scene sat. Demanding the gemma3 standard of never repeating a four-word run would
            # churn every scene without reaching it.
            for sentence in carriers[1:1 + (count - tic + 1)]:
                out.append(Violation(
                    "internal_repetition", Severity.MAJOR,
                    f'"{phrase}" appears {count} times in {len(words(scene.text))} words — a '
                    f"verbal tic, not a register. Rewrite this one without it.",
                    "check_internal_repetition", sentence))
        # Overlapping grams of one repeated phrase ("watched the way he", "the way he moved")
        # each raise their own tic, so the same sentence arrives more than once. One edit per
        # sentence is all `_surgical` can apply anyway.
        seen: set[str] = set()
        unique = [v for v in out if not (v.quote in seen or seen.add(v.quote))]
        if unique:
            return unique[:6]

    shown = "; ".join(f'"{" ".join(g)}" x{c}' for g, c in dupes[:5])
    return [Violation("internal_repetition", Severity.MINOR,
                      f"{len(dupes)} phrase(s) repeated within the scene "
                      f"({ratio:.0%} of it is repeated material): {shown}",
                      "check_internal_repetition", " ".join(dupes[0][0]))]


# Two gaps, found by a fixture that deliberately wrote past perfect and was not detected: an
# adverb between the auxiliary and the participle ("had never seen", "had already gone"), and
# irregular participles missing from the list ("had hung", "had held", "had stood" — the last of
# which is what a live scene repeated nine times). Both mean the corpus figures published before
# this widening understate past perfect rather than overstating it.
_ADVERB = r"(?:\w+ly|just|never|ever|already|also|not|still|long|once|almost|nearly|only)\s+"
_PARTICIPLE = (
    r"been|had|got|gone|come|seen|known|taken|written|made|left|kept|run|begun|put|set|told|"
    r"said|done|felt|found|given|hung|held|stood|sat|brought|thought|caught|meant|lost|won|"
    r"spoken|broken|driven|drawn|grown|thrown|worn|torn|shaken|risen|fallen|forgotten|chosen|"
    r"eaten|drunk|sung|swum|sunk|struck|stuck|sent|spent|built|bent|lent|dealt|slept|swept|"
    r"wept|crept|led|fed|bled|met|shut|split|spread|cut|hit|let|cost|hurt|beaten|bitten|"
    r"hidden|ridden|laid|paid|sold|understood|withdrawn|\w+ed")
_PAST_PERFECT = re.compile(
    rf"\bhad\s+(?:{_ADVERB})?(?:{_PARTICIPLE})\b", re.IGNORECASE)


def summary_distance(text: str) -> float:
    """Share of sentences narrated in past perfect — the grammar of recap rather than scene.

    "She had run the new system through its first cycle, and it had settled" is a report of
    things already over. A scene is what happens now; past perfect is what happened before now,
    and a page made mostly of it is a summary wearing a scene's clothes.

    It discriminates like the duplication ratio does, on the same corpus: the reference drafts in
    `docs/evidence` sit at 0.085 (gemma3:12b), 0.100 (phi4:14b) and 0.129 (qwen3:8b), while the
    107 scenes this project has committed run to a median of 0.382 and a maximum of 0.979 — one
    scene in which every sentence but one is narrated at distance. StoryScope's
    "narrated at summary distance" tell was firing on every scene of a live book and only the
    LLM probe could see it, which by policy makes it advisory — this is the countable half.
    """
    sents = sentences(text)
    if not sents:
        return 0.0
    return sum(1 for s in sents if _PAST_PERFECT.search(s)) / len(sents)


def check_summary_distance(scene: Scene, heavy: float = 0.35) -> list[Violation]:
    """Report a scene that is mostly recap. Advisory, for the same reason diffuse duplication is.

    Past perfect is not localised in a few sentences that could be rewritten — it is how the
    whole passage is narrated, and switching one sentence to simple past leaves the register
    unchanged. So this is reported to the author and used where it costs nothing: candidate
    selection, which prefers the draft that is happening over the draft that is recapping.
    """
    density = summary_distance(scene.text)
    if density < heavy:
        return []
    return [Violation(
        "summary_distance", Severity.MINOR,
        f"{density:.0%} of sentences are in past perfect — the scene is largely recapping "
        f"rather than happening (the cleanest drafts measured sit near 10%)",
        "check_summary_distance")]


def recap_blocks(text: str, run: int = 4) -> list[tuple[int, int, int]]:
    """Spans of `run` or more consecutive sentences narrated in past perfect.

    `summary_distance` measures the register and cannot be repaired, because switching one
    sentence to simple past leaves the other forty untouched. But the register is not uniform.
    Measured across 107 committed scenes, past perfect arrives in *blocks*: the median scene has
    a run of 4 consecutive past-perfect sentences, 68 of 107 reach 4 or more, and the worst has
    46 in a row — a page of backstory dictated into the middle of a scene, which in that case
    also repeated "she had not asked" 77 times in 1,490 words.

    The three reference drafts in `docs/evidence` reach runs of 2, 1 and 2. None of them has
    three in a row. So a run of four is nothing a clean draft does, and unlike the diffuse
    register it occupies a contiguous span a passage repair can replace.

    Returns (start, end, sentences) character spans, longest first.
    """
    spans = sentence_spans(text)
    out: list[tuple[int, int, int]] = []
    start = count = 0
    for i, (lo, hi) in enumerate(spans + [(len(text), len(text))]):
        hit = i < len(spans) and bool(_PAST_PERFECT.search(text[lo:hi]))
        if hit:
            if count == 0:
                start = lo
            count += 1
            end = hi
        else:
            if count >= run:
                out.append((start, end, count))
            count = 0
    out.sort(key=lambda b: -b[2])
    return out


def check_recap_block(scene: Scene, run: int = 4) -> list[Violation]:
    """The repairable half of summary distance: a paragraph of recap inside a scene.

    Its sibling `check_summary_distance` stays advisory on purpose — a whole scene narrated at
    distance is the model's register and no local edit reaches it. This one is the opposite
    case and is the reason that distinction is worth drawing rather than shrugging at: the
    block has edges, so it can be cut out and rewritten, and the check that found it can verify
    the replacement.
    """
    # Uncapped, unlike the other per-occurrence checks here, because the repair loop measures
    # progress by counting a kind's violations: a live scene held seven blocks, the check
    # reported the first three, and `cutrecap` deleting one correctly left three — so a repair
    # that had done exactly its job was discarded as "no improvement", twice, then sidelined.
    # A capped check cannot be used to tell whether there is less of something than there was.
    out: list[Violation] = []
    for lo, hi, count in recap_blocks(scene.text, run):
        out.append(Violation(
            "recap_block", Severity.MAJOR,
            f"{count} sentences in a row are narrated in past perfect — this is a block of "
            f"recap, not a passage of scene. Nothing the reader is watching happens in it.",
            "check_recap_block", scene.text[lo:hi].strip()))
    return out


_GESTURE_PART = re.compile(
    r"\b(?:his|her|their|its)\s+(fingers?|hand|hands|palm|palms|thumb|knuckles|jaw|chin|head|"
    r"shoulders?|eyes|gaze|brow|lips|mouth|spine|arms?|wrist|breath|voice)\b", re.I)

_GESTURE_VERB = re.compile(
    r"\b(tilt\w*|trac\w*|brush\w*|hover\w*|press\w*|curl\w*|tighten\w*|flex\w*|clench\w*|"
    r"cross\w*|fold\w*|shift\w*|settl\w*|linger\w*|flicker\w*|narrow\w*|steady\w*)\b", re.I)


def gesture_pairs(text: str) -> list[tuple[str, str, int]]:
    """Body-part-plus-small-movement pairs, with where each one starts.

    Found by reading a finished book rather than by measuring one. *The Keeper's Fourth Book*
    scored .000 duplication and zero recap blocks and still read as repetitive, because what
    repeated was never the words. It was the gestures: fingers tracing, hovering and brushing,
    a jaw tightening, arms crossing and folding, a head tilting, a gaze settling — the same
    handful of movements, freshly worded every time, so every check here was blind to them.

    That blindness is structural. `duplication_ratio` counts repeated n-grams and a repetition
    penalty at the sampler suppresses repeated tokens; both of them push the model toward
    *rewording* the thing it keeps doing, which is why the gesture rate went slightly up when
    the sampler was fixed (3.6 to 4.1 per thousand words) while duplication went to nearly zero.
    """
    out: list[tuple[str, str, int]] = []
    for m in _GESTURE_PART.finditer(text):
        verb = _GESTURE_VERB.search(text, m.start(), m.start() + 60)
        if verb:
            out.append((m.group(1).lower(), verb.group(1).lower()[:5], m.start()))
    return out


def gesture_rate(text: str) -> float:
    """Gestures per thousand words."""
    words = len(text.split())
    return len(gesture_pairs(text)) / words * 1000 if words else 0.0


def check_gesture_density(scene: Scene, base: float = 3.0, per_dialogue: float = 12.0
                          ) -> list[Violation]:
    """A scene made of small movements. Advisory, because it is a register.

    Same shape as `check_summary_distance` and for the same reason: it is not localised in a few
    sentences that could be rewritten, it is how the whole passage is written, and cutting one
    hand-brush leaves the other eleven. So it is reported to the author and used where it costs
    nothing — candidate selection, which prefers the draft that is doing something to the draft
    that is fidgeting.

    **The threshold allows for dialogue, and the first version did not.** It was set at a flat
    3.0 per thousand words from a five-scene clean cohort — and four of those five scenes contain
    *no dialogue at all*, because they are cold opening scenes. Applied to a book that is 15%
    dialogue it fired on 34 of 71 scenes, and the scenes it fired on had *higher* dialogue than
    the ones it spared. It was penalising the scenes that had got better.

    Dialogue genuinely carries more physical business, and that is measured rather than assumed:
    across 160 scenes of four books, correlation between dialogue share and gesture rate is
    r = +0.303, and the group means run 1.9 (silent) → 2.4 → 3.5 (dialogue-led) → 3.4. Gestures
    are the beats between lines. So the allowance rises with dialogue: at no dialogue the
    threshold is 3.0, at 15% it is 4.8.

    Two honest limits. The slope is fitted to this project's own scenes, not to a corpus of good
    fiction, so it says what is unusual *here* rather than what is too much. And within-scene
    variety turns out not to discriminate at all — measured across four books it sits at ~1.0
    everywhere, because the repetition is between scenes, not inside them. A gesture used in
    nine separate scenes is what `manuscript_refrains` is shaped for and this check cannot see.
    """
    rate = gesture_rate(scene.text)
    limit = base + per_dialogue * dialogue_share(scene.text)
    if rate < limit:
        return []
    return [Violation(
        "gesture_density", Severity.MINOR,
        f"{rate:.1f} small physical gestures per thousand words — fingers tracing, a jaw "
        f"tightening, a head tilting — against {limit:.1f} allowed for a scene with this much "
        f"dialogue. The scene is fidgeting rather than acting.",
        "check_gesture_density")]


def check_gesture_tic(scene: Scene, limit: int = 3) -> list[Violation]:
    """The same gesture, over and over, in one scene. Unlike the density, this has a location.

    The tic-versus-register split that `check_internal_repetition` draws for phrasing, drawn
    again for movement — and the two halves really are separate defects, which reading one book
    beside the corpus made plain. *The Keeper's Fourth Book* has a high gesture *rate* and no
    scene in it repeats a single gesture more than once. Twenty-three of 121 committed scenes do
    repeat one, and the worst repeats it ten times. No scene in the clean cohort repeats one at
    all.

    A repeated gesture sits in a sentence, so surgery can reach it; the register cannot be
    reached and is not asked to be.
    """
    counts: dict[tuple[str, str], list[int]] = {}
    for part, verb, where in gesture_pairs(scene.text):
        counts.setdefault((part, verb), []).append(where)

    out: list[Violation] = []
    for (part, verb), places in sorted(counts.items(), key=lambda kv: -len(kv[1])):
        if len(places) < limit:
            continue
        for where in places[limit - 1:]:
            lo, hi = sentence_covering(scene.text, (where, where + 1))
            out.append(Violation(
                "gesture_tic", Severity.MAJOR,
                f'"{part}" with a "{verb}"-type movement appears {len(places)} times in this '
                f"scene. Rewording it is not the fix — the character has to do something else, "
                f"or nothing.",
                "check_gesture_tic", scene.text[lo:hi].strip()))
    return out


_ANAPHORA = re.compile(
    r"(\b(?:the|a|his|her|their) \w+)[^.!?]{5,70},\s*\1\b[^.!?]{5,70},\s*\1\b", re.I)


def check_anaphora(scene: Scene) -> list[Violation]:
    """The rhetorical triple: one phrase opening three clauses of a single sentence.

    "the way his back remained straight, the way his fingers did not falter, the way he did not
    look at her" — and "the silence was a kind of language, a kind of code, a kind of failure",
    which manages to be a triple and an abstraction at once. It is a distinctive move: measured
    across 91 committed scenes it appears in a handful and reaches 13.7 per thousand words in the
    worst, while none of the reference drafts in `docs/evidence` contains a single one.

    Rare enough to be worth stopping for, and unlike a register it sits in one sentence, so
    surgery can reach it.
    """
    out: list[Violation] = []
    for lo, hi in sentence_spans(scene.text):
        sentence = scene.text[lo:hi].strip()
        match = _ANAPHORA.search(sentence)
        if not match:
            continue
        out.append(Violation(
            "anaphora", Severity.MAJOR,
            f'three clauses of this sentence open with "{match.group(1)}" — a rhetorical '
            f"triple. Keep one and write the others differently, or cut two.",
            "check_anaphora", sentence))
        if len(out) >= 4:
            break
    return out


_ABSOLUTE = re.compile(r",\s+(?:his|her|its|their)\s+\w+\s+\w+", re.I)


def check_absolute_stack(scene: Scene, limit: int = 3) -> list[Violation]:
    """Sentences that pile up possessive absolutes: "her posture rigid, her hands clasped".

    The dominant tic in this project's own prose, and the one that survived every other check.
    One absolute phrase is ordinary writing — "she turned back to the screen, her fingers moving
    over the keys" is fine. Two or more in a sentence is a camera panning across body parts
    instead of a scene happening, and it stacks: one committed sentence ran "his back to her, his
    head bowed over the paper, the pen moving, the ink filling the lines, the numbers forming a
    pattern".

    Measured across 91 committed scenes and the three reference drafts in `docs/evidence`:
    stacked sentences appear in 71 of the 91 and in none of the three, with a median of 2 per
    scene and a maximum of 13. The threshold is three, where it stops being a moment and becomes
    a habit — one or two read as deliberate.
    """
    stacked = [scene.text[lo:hi].strip() for lo, hi in sentence_spans(scene.text)
               if len(_ABSOLUTE.findall(scene.text[lo:hi])) >= 2]
    if len(stacked) < limit:
        return []
    return [Violation(
        "stacked_absolutes", Severity.MAJOR,
        f"this sentence hangs two or more descriptive phrases off commas, and the scene does it "
        f"{len(stacked)} times — a camera panning across body parts rather than a scene "
        f"happening",
        "check_absolute_stack", sentence)
        for sentence in stacked[:4]]


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
    out += check_truncated(scene)
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
    out += check_summary_distance(scene)
    out += check_recap_block(scene)
    out += check_gesture_density(scene)
    out += check_gesture_tic(scene)
    out += check_scene_is_peopled(spec, scene)
    out += check_anaphora(scene)
    out += check_absolute_stack(scene)
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


_NEGATIONS = re.compile(
    r"\b(?:not|n't|never|no longer|without|fails? to|refuses? to|cannot|neither)\b",
    re.IGNORECASE)

_NEITHER_NOR = re.compile(r"\bneither\b(.*?)\bnor\b", re.IGNORECASE | re.DOTALL)

_LEFT_UNDONE = re.compile(
    r"\b(?:left|leaves|remains?|stays?|goes)\s+(un\w+)\b", re.IGNORECASE)

_AVOIDANCE = re.compile(r"\b(?:avoids?|avoided|avoiding)\s+(\w+ing\b.*)", re.IGNORECASE | re.S)
""""Ingrid avoids discussing the register" — an obligation to not do something.

Kept separate from the other two because the inversion is exact and needs no grammar: as a
prohibition it is "discussing the register", which is a question a judge answers by reading. As
an obligation it asks the judge to confirm an absence in context, which it cannot, and a live
run's scene 5 was reported missed however the scene went. `refuses to` is deliberately not here
— a refusal is something a reader can watch happen.
"""


_WITHOUT_CLAUSE = re.compile(r"\s*\bwithout\b.*$", re.IGNORECASE | re.DOTALL)


def verifiable_post(text: str) -> str:
    """Strip a trailing "without …" clause from an obligation, keeping the event.

    "Sofie makes the change without detection" contains a real event and an absence hung off it.
    The event is something a judge confirms by reading; the absence is not, and a live run
    reported the whole line missed however the scene went. Dropping the qualifier leaves an
    obligation the judge can answer.

    Only when something survives the cut. A post that is nothing but a "without" clause is an
    absence outright, and `is_absence_post` sends it to the prohibition list instead.
    """
    stripped = _WITHOUT_CLAUSE.sub("", text).strip().rstrip(",")
    return stripped if len(stripped.split()) >= 3 else text


_IGNORING = re.compile(
    r"\b(?:ignor\w+|overlook\w*|disregard\w*)\b", re.IGNORECASE)
"""An obligation whose whole content is a not-noticing, with nothing to invert it into.

"Nils ignores the thermometer's reading" cannot be confirmed by reading — the judge would have
to find an absence — and unlike "avoids discussing X" there is no gerund phrase to hand to the
prohibition list either. `positive_prohibition` returns nothing for these, and the caller drops
them: an obligation always reported missed, with no repair that can satisfy it, blocks a scene
permanently while pretending to be a requirement.

Deliberately three verbs. "withhold" was here for one commit and caught the reference plan's
"Siv withholds what she found, and the withholding is visible as behaviour rather than stated"
— a withholding staged as behaviour is exactly the thing a reader watches, and a refusal is
too. Only a character failing to register something has nothing to show.
"""


def is_absence_post(text: str) -> bool:
    """Is this `post` line entirely a thing not happening?

    Deliberately narrow. The first version of this flagged any negation in a post and caught
    four legitimate lines in the reference plan on the spot — "Otto acts, and the action is
    neither betrayal nor rescue", "Beata commits to a course of action that does not depend on
    Siv". Each has a real event and a qualifier, and each is perfectly dramatisable; the
    negation is describing the event, not replacing it.

    What is not dramatisable is a post whose whole predicate is an absence, with no event before
    it — scene 24 of a live run required "the allegiances of the bailiff and fugitive are
    neither resolved nor abandoned" and was reported missed however the scene went. The
    distinguishing mark is a `neither … nor` reached without passing a clause boundary.
    """
    match = _NEITHER_NOR.search(text)
    if match and "," not in text[:match.start()]:
        return True
    # The other ways a plan writes an absence without a negation word: "the bailiff's past is
    # left unspoken", "the question remains unanswered", "Ingrid avoids discussing the register".
    # A scene cannot be shown not saying something, so the judge reports it missed — as it did
    # for the finale of one live run and scene 5 of another.
    return bool(_LEFT_UNDONE.search(text) or _AVOIDANCE.search(text)
                or _IGNORING.search(text))

# "nothing" and "none" are how a plan writes an *empty* forbid list, not how it writes a
# negation. Flagging those reports a placeholder as a malformed rule.
_EMPTY_FORBID = {"", "-", "n/a", "na", "none", "nothing", "no prohibitions"}


def is_negated_prohibition(text: str) -> bool:
    """Is this Forbid entry phrased as a negation, and therefore unenforceable?

    A Forbid says what must not appear. Phrased as a negation it becomes a double negative and
    inverts: a live plan wrote `forbid: "Dain's decision is not finalized"` alongside
    `post: "Dain's allegiance shifts to the enclave"`. Read literally, the prohibition demands
    the very thing the post demands, and the scene that correctly finalised the decision was
    blocked for it — by a judge asked whether a negative statement had been violated, which is a
    question no model answers reliably and this one answered wrong for eight scenes' worth of
    generation before anyone saw it.
    """
    if text.strip().strip(".").lower() in _EMPTY_FORBID:
        return False
    return bool(_NEGATIONS.search(text))


_UNNEGATE = [
    (re.compile(r"\bis not yet\b", re.I), "is"),
    (re.compile(r"\bare not yet\b", re.I), "are"),
    (re.compile(r"\bis not\b", re.I), "is"),
    (re.compile(r"\bare not\b", re.I), "are"),
    (re.compile(r"\bwas not\b", re.I), "was"),
    (re.compile(r"\bwere not\b", re.I), "were"),
    (re.compile(r"\bhas not\b", re.I), "has"),
    (re.compile(r"\bhave not\b", re.I), "have"),
    (re.compile(r"\b(?:does|do|did) not\b", re.I), ""),
    (re.compile(r"\bcannot\b|\bcan not\b|\bcan't\b", re.I), ""),
    (re.compile(r"\b(?:is|are|was|were|does|do|did|has|have)n't\b", re.I), ""),
    (re.compile(r"\b(?:never|no longer|without)\b", re.I), ""),
    (re.compile(r"\b(?:fails?|failed|refuses?|refused) to\b", re.I), ""),
    (re.compile(r"\bnot\b", re.I), ""),
]


def positive_prohibition(text: str) -> str:
    """Turn a negated Forbid into the event it is actually forbidding.

    The planner writes concealment as an invariant — "The fugitive's true purpose is not
    revealed" — meaning *keep this true*. A Forbid list means the opposite: these things must not
    happen. Strip the negation and the two say the same thing: the forbidden event is "the
    fugitive's true purpose is revealed", which is a question a judge can answer by reading the
    scene. Left as written, the judge is asked whether a negative statement was violated, and a
    live run blocked scene 8 for finalising a decision its own `post` line required.

    Rewriting is better than dropping. Dropping would discard a real constraint — most of these
    entries are the only thing holding a reveal back — so the phrasing is repaired rather than
    the rule discarded. `check_prohibition_phrasing` still reports the plan, so the next plan
    is written correctly instead of repaired forever.
    """
    # "neither X nor Y" needs both halves rewritten together, so it is handled before the
    # one-substitution loop below: scene 24 of a live run required "the allegiances are neither
    # resolved nor abandoned", which is two forbidden events written as one absence.
    out = _NEITHER_NOR.sub(lambda m: m.group(1).strip() + " or ", text)
    if out != text:
        return re.sub(r"\s+", " ", out).strip()

    # "Ingrid avoids discussing the register" forbids "discussing the register" — exactly, and
    # with no grammar needed, which is why this one is tried before the others.
    # Nothing to invert an ignoring into: "Nils ignores the reading" forbids no event, and
    # forwarding it as a prohibition would forbid the ignoring itself — the opposite of the
    # intent. Reported as unenforceable so the caller drops it.
    if _IGNORING.search(text):
        return ""

    avoidance = _AVOIDANCE.search(text)
    if avoidance:
        return re.sub(r"\s+", " ", avoidance.group(1)).strip().rstrip(".")

    # "the bailiff's past is left unspoken" forbids the event "the bailiff's past is spoken".
    out = _LEFT_UNDONE.sub(lambda m: "is " + re.sub(r"^un", "", m.group(1), flags=re.I), text)
    if out != text:
        # "is left unspoken" already carries its copula, so the substitution doubles it.
        out = re.sub(r"\b(is|are|was|were)\s+is\b", r"\1", out, flags=re.I)
        return re.sub(r"\s+", " ", out).strip()

    for pattern, replacement in _UNNEGATE:
        new = pattern.sub(replacement, out)
        if new != out:
            out = new
            break
    return re.sub(r"\s+", " ", out).strip()


_DISCLOSURE = re.compile(
    r"\b(?:reveal(?:s|ed|ing)?|disclos(?:e|es|ed|ing)|discover(?:s|ed|ing)|"
    r"uncover(?:s|ed|ing)|expos(?:e|es|ed|ing)|learn(?:s|ed|ing)?|told|tells|"
    r"know(?:s|n|ing)?|made (?:public|explicit|clear))\b",
    re.IGNORECASE)
"""Verbs of a fact becoming available to the reader — verbs only.

The noun forms are deliberately absent. A live plan forbade "Ingrid is thanked for her
discovery", which is a prohibition on the village being grateful, not on anything being
disclosed; matching the noun dropped a real constraint as though it were a stale concealment.
"exposure", "revelation" and "disclosure" go the same way.

"Explain" is deliberately absent. A Forbid saying "the founders' motives being explained" is a
craft rule — do not have the narrator gloss the story — and it holds for every scene of the book
however much the reader already knows. Reading it as a stale concealment would switch off a
prohibition that was never about concealment at all.
"""


def is_disclosure_prohibition(text: str) -> bool:
    """Does this Forbid entry prohibit the reader or a character finding something out?

    Those are the entries a planner writes as per-scene copies of a thread's `concealment`, and
    they go stale the moment the concealment is lifted. Everything else a Forbid can say — "Dain
    kills Riven", "the door is opened" — stays true for the whole book and is left alone.
    """
    return bool(_DISCLOSURE.search(text))


_STATE_FILLER = {"reaches", "reach", "reached", "enters", "enter", "entered", "becomes",
                 "become", "moves", "move", "shifts", "shift", "is", "are", "now", "to", "into",
                 "state", "the", "a", "an", "at", "in", "of", "its", "this", "scene"}


def is_state_restatement(text: str, thread: Thread) -> bool:
    """Is this `post` line just the thread's name and a state label?

    `verify.check_threads` already refuses to show the judge `op.to_state`, because state names
    are this system's bookkeeping ("chosen", "paid_off") and a judge asked whether prose "ends
    the thread in state paid_off" can only guess. A live planner then wrote the label into the
    post line itself — `post: ["The Allegiance reaches 'reoriented'"]` — and the same
    unanswerable question reached the judge through the other door. Scene 19 was held back for
    missing two obligations that name no event at all.

    The state change is applied by `Project.commit` regardless. What a post line is *for* is
    saying what happens on the page.
    """
    # No apostrophes in the token class: the planner quotes the label — reaches 'reoriented' —
    # and a token of "'reoriented'" matches nothing in `thread.states`.
    word = re.compile(r"[a-z0-9]+")
    tokens = set(word.findall(text.lower()))
    if not tokens:
        return False
    allowed = set(_STATE_FILLER) | set(word.findall(thread.name.lower()))
    for state in thread.states:
        allowed |= set(word.findall(state.lower()))
    return tokens <= allowed


def check_post_is_an_event(plan: list[SceneSpec], story: StorySpec) -> list[Violation]:
    """A scene obligation must name something that happens, not a state the bookkeeping enters."""
    out: list[Violation] = []
    for spec in plan:
        for tid, op in spec.thread_ops.items():
            thread = story.thread(tid)
            if thread is None:
                continue
            for item in op.post:
                if is_state_restatement(item, thread):
                    out.append(Violation(
                        "post_names_a_state", Severity.MINOR,
                        f"scene {spec.index} [{thread.name}] requires \"{item}\", which names a "
                        f"state rather than an event. Nothing on the page can satisfy it, and no "
                        f"repair can add it. Say what happens.",
                        "check_post_is_an_event", item))
                elif is_absence_post(item):
                    out.append(Violation(
                        "post_names_an_absence", Severity.MINOR,
                        f"scene {spec.index} [{thread.name}] requires \"{item}\", which is a "
                        f"thing not happening. No prose can evidence an absence, so the judge "
                        f"reports it missed however the scene goes. This belongs in \"forbid\".",
                        "check_post_is_an_event", item))
    return out


_BEAT_PROSE = re.compile(
    # Double quotes are unambiguous. Single quotes are not: a beat reading "She connects pass's
    # history to register's altered entries" has two apostrophes with twenty characters between
    # them, and the first version of this read that as a line of dialogue — flagging a perfectly
    # good beat and sending it off to be rewritten. So a single-quoted span must open at a word
    # boundary and close at one, which a possessive never does.
    r"[\"“”][^\"“”]{12,}[\"“”]"
    r"|(?:^|[\s(\[—-])['‘][^'’\n]{12,}['’](?=$|[\s.,;:!?)\]—-])")


def check_beats_are_intent(plan: list[SceneSpec], story: StorySpec) -> list[Violation]:
    """A beat says what happens. A beat written as prose guarantees the scene reproduces it.

    Scene 26 of a live run had ten beats like "Dain steps forward, his boots crunching over dry
    leaves, his voice steady and low" and "Dain speaks, his words cutting through the silence,
    'You will not take these years.'" The writer did what it was told, `check_brief_leak` found
    seven copied runs, and no repair could fix a scene whose brief was the scene.

    Quoted speech is the unambiguous mark and the only one checked here: a beat carrying a line
    of dialogue has stopped planning and started writing.
    """
    out: list[Violation] = []
    for spec in plan:
        for beat in spec.beats:
            if not _BEAT_PROSE.search(beat.summary):
                continue
            out.append(Violation(
                "beat_is_prose", Severity.MINOR,
                f"scene {spec.index} has a beat containing written dialogue — \"{beat.summary}\". "
                f"A beat names what happens so the scene can dramatise it; written out, the "
                f"scene copies it back and `check_brief_leak` is right to flag the copy.",
                "check_beats_are_intent", beat.summary))
    return out


def check_stale_prohibitions(plan: list[SceneSpec], story: StorySpec) -> list[Violation]:
    """A scene forbidding a disclosure the plan has already scheduled.

    `Thread.reveal_scene` exists because a scene once got a brief that simultaneously required
    and forbade a reveal. Per-scene Forbid entries never got the same treatment, and scene 13 of
    a live run was held back for revealing an enclave the plan's own schedule had unsealed at
    scene 10 — three scenes and four thousand words earlier. The judge was right that the scene
    disclosed it; the rule was wrong to still be asking.
    """
    out: list[Violation] = []
    for spec in plan:
        for tid, op in spec.thread_ops.items():
            thread = story.thread(tid)
            if thread is None or thread.reveal_scene is None:
                continue
            if spec.index < thread.reveal_scene:
                continue
            for item in op.forbid:
                if not is_disclosure_prohibition(item):
                    continue
                out.append(Violation(
                    "stale_prohibition", Severity.MINOR,
                    f"scene {spec.index} [{thread.name}] forbids a disclosure — \"{item}\" — but "
                    f"the plan lifts this thread's concealment at scene {thread.reveal_scene}. "
                    f"The prohibition contradicts the schedule and is not enforced.",
                    "check_stale_prohibitions", item))
    return out


def check_prohibition_phrasing(plan: list[SceneSpec], story: StorySpec) -> list[Violation]:
    """Forbid entries must name what must not happen, positively.

    Caught at plan time, this costs one re-plan. Caught at run time it costs however many scenes
    were generated before the malformed prohibition's scene came up, and no repair can clear it:
    the scene is not wrong, the rule is.
    """
    out: list[Violation] = []
    for spec in plan:
        for tid, op in spec.thread_ops.items():
            thread = story.thread(tid)
            label = thread.name if thread else tid
            for item in op.forbid:
                if not is_negated_prohibition(item):
                    continue
                out.append(Violation(
                    "negated_prohibition", Severity.MINOR,
                    f"scene {spec.index} [{label}] forbids a negative — \"{item}\". A "
                    f"prohibition must name the thing that must not happen; phrased this way it "
                    f"reads as a requirement, and the scene that obeys the plan is the one that "
                    f"gets blocked.",
                    "check_prohibition_phrasing", item))
    return out


# Abstractions a novel reaches for constantly. Banning one is not a style constraint, it is a
# running battle the prose loses in every scene — and each loss costs a repair round.
_UNAVOIDABLE = frozenset("""
truth right reason feeling memory silence hope fear love death time light dark change power
choice knowledge secret story word thing moment place life world day night sense mind heart
""".split())


def is_unavoidable_ban(phrase: str) -> bool:
    """Is this a word the prose is made of, rather than the vocabulary of a trope?"""
    word = phrase.strip().lower()
    return " " not in word and word in _UNAVOIDABLE


def check_ban_is_avoidable(plan: list[SceneSpec], story: StorySpec) -> list[Violation]:
    """A forbidden phrase must be avoidable, or the book fights it in every scene.

    `forbidden_phrases` exists to keep a premise off the shape it is trying not to be: ban
    "conspiracy", "hacker", "sentient" and the prose never misses them. A live plan banned
    "truth" in a story about a falsified record, and "right" as well. One scene came back with
    six `forbidden_phrase` violations, each needing its own repair, on a word the story is
    actually about.

    Single common abstractions only. A two-word phrase is specific enough to route around, and
    a rarer word is the kind of ban this feature is for.

    This gates rather than advising, which is the one exception among the rule-shape checks. The
    others describe how a rule is phrased; this one predicts a cost the book pays in every scene.
    A live plan banning "truth", "right" and "silence" produced scenes carrying three
    `forbidden_phrase` majors each, every one needing its own repair round, and no amount of
    rewriting makes those words avoidable. Reported as a MINOR it changed nothing and the run
    simply suffered — which is what an advisory is worth to a process nobody is watching. The
    plan is still not edited: `write` refuses and the author decides.
    """
    out: list[Violation] = []
    for phrase in story.style.forbidden_phrases:
        if not is_unavoidable_ban(phrase):
            continue
        out.append(Violation(
            "unavoidable_ban", Severity.MAJOR,
            f'the style contract forbids "{phrase}", which is a word a novel needs. Every scene '
            f'will trip it and every trip costs a repair round. Ban the vocabulary of the thing '
            f'the premise is avoiding, not the words the prose is made of.',
            "check_ban_is_avoidable", phrase))
    return out


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
    out += check_ban_is_avoidable(plan, story)
    out += check_prohibition_phrasing(plan, story)
    out += check_stale_prohibitions(plan, story)
    out += check_post_is_an_event(plan, story)
    out += check_beats_are_intent(plan, story)
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
