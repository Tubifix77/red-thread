"""Sentences, with no context and no scores.

Phase 5 of docs/PLAN.md, and the only part of this project that asks a person a question. Every
other measure here says whether the prose *scores* better. A hundred sentences read blind is the
only thing that can say whether it *is* better — and if the answer is no, most of the instrument
panel needs rethinking rather than extending.

So this module is deliberately incapable of scoring anything. It draws sentences, it strips
every cue about where they came from, and it writes the key to a separate file the rater is not
meant to open. The temptation it exists to resist is showing the rater the numbers first, which
would produce a hundred confirmations of what the panel already says.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

from . import checks

# Names, place names and thread vocabulary are the giveaway. A rater who has read this project's
# output knows which book "Kvitmyr" is from, and half the point of a blind sheet is that the two
# eras of one premise cannot be told apart by their furniture. This does not anonymise them —
# that would mean rewriting the sentence, and the sentence is the thing being rated.
_UNRATEABLE = re.compile(r"^[^A-Za-z]*$")


def restore_quotes(sentence: str) -> str:
    """Put back the quotation mark the sentence splitter ate.

    `checks.sentences` breaks after terminal punctuation, which inside dialogue falls *before*
    the closing mark — so a drawn sentence routinely begins mid-speech, with a stray `”` and no
    opener, or opens a quote it never closes.

    This is not cosmetic and it is not neutral. The artefact tracks dialogue, and the two sides of
    this project's sheet differ in dialogue share by threefold: **10.9% of current-era sentences
    begin inside a quote against 5.4% of the older ones**. Left alone it would bias a blind rating
    against exactly the prose the work was meant to improve, for a reason that is not the prose.

    Restoration, not editing. The mark was in the book; the splitter removed it. No word changes.
    """
    opened, closed = sentence.find("“"), sentence.find("”")
    if closed != -1 and (opened == -1 or closed < opened):
        sentence = "“" + sentence
    last_open = sentence.rfind("“")
    if last_open != -1 and sentence.find("”", last_open) == -1:
        sentence = sentence + "”"
    return sentence


def sentences_from(texts: list[str], min_words: int = 8) -> list[str]:
    """Rateable sentences from a group of scenes.

    The floor matters and is arguable. Below about eight words this project's prose is mostly
    dialogue fragments — "Gift?", "Recorded elsewhere?" — which are exchange, not craft, and a
    rater asked whether they would read them again has been asked nothing. Sampling without the
    floor is available (`--min-words 1`) and produces a sheet that is roughly a third
    monosyllables.
    """
    out: list[str] = []
    for text in texts:
        for sentence in checks.sentences(text):
            clean = " ".join(sentence.split())
            if len(clean.split()) < min_words or _UNRATEABLE.match(clean):
                continue
            out.append(restore_quotes(clean))
    return out


def draw(texts: list[str], n: int, seed: int = 0, min_words: int = 8) -> list[str]:
    """`n` sentences drawn without replacement, or all of them if there are fewer."""
    pool = sentences_from(texts, min_words)
    rng = random.Random(seed)
    if len(pool) <= n:
        rng.shuffle(pool)
        return pool
    return rng.sample(pool, n)


def blind_sheet(groups: list[tuple[str, list[str]]], per_group: int, seed: int = 0,
                min_words: int = 8) -> tuple[list[str], list[tuple[int, str, str]]]:
    """A shuffled, unlabelled rating sheet and its key.

    Returns (sentences in sheet order, key rows of (number, group label, sentence)). The two are
    separate objects so the caller can write them to separate files — a key in the same file as
    the sheet is not a blind.
    """
    rng = random.Random(seed)
    drawn: list[tuple[str, str]] = []
    for i, (label, texts) in enumerate(groups):
        for sentence in draw(texts, per_group, seed=seed + i, min_words=min_words):
            drawn.append((label, sentence))
    rng.shuffle(drawn)
    sheet = [s for _label, s in drawn]
    key = [(i + 1, label, s) for i, (label, s) in enumerate(drawn)]
    return sheet, key


def render_sheet(sheet: list[str]) -> str:
    """The sheet a person actually fills in.

    One question, asked the same way every time. "Would you read another page of this" is the
    only judgement this project has no other way of getting, and adding a second axis — is it
    vivid, is it clichéd — would invite the rater to reconstruct the instrument panel by hand.
    """
    lines = [
        "# A hundred sentences",
        "",
        "Each line below is one sentence, drawn at random from finished prose, with no context.",
        "Half come from one condition and half from another; the order is shuffled and the key",
        "is in a separate file. Do not open it until you are finished.",
        "",
        "For each, write a single digit in the brackets:",
        "",
        "    3  I would read another page of this",
        "    2  fine; I would not stop, and I would not notice",
        "    1  I would put the book down",
        "",
        "Read fast. First reaction is the measurement — a considered second look is you doing",
        "the instrument's job, and the instrument already has an opinion.",
        "",
    ]
    for i, sentence in enumerate(sheet, start=1):
        lines.append(f"[ ]  {i:>3}.  {sentence}")
    return "\n".join(lines) + "\n"


def is_spoken(sentence: str) -> bool:
    """Does this sentence contain speech?

    Recorded in the key because the first real sheet built from this project came back 12%
    spoken on one side and 42% on the other. That is the axis that has moved most here — the
    planner instruction took dialogue share from .077 to .223 — so a rating difference between
    the two eras could as easily be a rater's preference about dialogue as a judgement about
    prose. The fix is not to balance the draw, which would make the sheet unrepresentative of
    the books; it is to record the flag and let the analysis split on it.
    """
    return any(mark in sentence for mark in ('"', "“", "”"))


def render_key(key: list[tuple[int, str, str]]) -> str:
    lines = ["# Key — do not read before rating", "",
             "The `spoken` column is a control, not a category: the two sides of this sheet can "
             "differ",
             "in dialogue share by threefold, so a difference in ratings has to survive being "
             "split on it.",
             ""]
    for number, label, sentence in key:
        lines.append(f"{number:>3}  {label:<18}  {'spoken' if is_spoken(sentence) else 'narrated'}"
                     f"  {sentence}")
    return "\n".join(lines) + "\n"


_RATING = re.compile(r"^\[\s*([0-9])\s*\]\s*(\d+)\.")


def parse_ratings(sheet_text: str) -> dict[int, int]:
    """Read a filled-in sheet back. Unrated lines are simply absent, not defaulted."""
    out: dict[int, int] = {}
    for line in sheet_text.splitlines():
        match = _RATING.match(line.strip())
        if match:
            out[int(match.group(2))] = int(match.group(1))
    return out


_KEY_ROW = re.compile(r"^\s*(\d+)\s+(\S+)\s+(spoken|narrated)\s+(.*)$")


def parse_key(key_text: str) -> dict[int, tuple[str, str]]:
    """Read a key file back as number -> (group label, spoken/narrated)."""
    out: dict[int, tuple[str, str]] = {}
    for line in key_text.splitlines():
        match = _KEY_ROW.match(line)
        if match:
            out[int(match.group(1))] = (match.group(2), match.group(3))
    return out


# --------------------------------------------------------------------------------------
# Step 22: does anything in the instrument panel correspond to what a reader notices?
#
# This is written to be able to return "no". If none of the signals below correlates with a
# hundred hand ratings, that is the finding, and a valuable one — it says the panel is
# orthogonal to the reading experience, and most of it needs rethinking rather than extending.
# --------------------------------------------------------------------------------------

def sentence_signals(sentence: str) -> dict[str, float]:
    """Every per-sentence signal the instrument panel is built from, as 0/1 or a count.

    Deliberately only the signals that can be evaluated on one sentence in isolation. Duplication,
    refrains and gesture *repeats* are properties of a manuscript and cannot be asked of a single
    line — which is itself worth stating, because it means a hundred rated sentences can never
    test the measures this project has spent most of its effort on.
    """
    from . import checks
    from .models import Scene

    scene = Scene(spec_id="sample", index=0, text=sentence)
    return {
        "words": float(len(sentence.split())),
        "spoken": float(is_spoken(sentence)),
        "gesture": float(bool(checks.gesture_pairs(sentence))),
        "somatic": float(bool(checks.somatic_beats(sentence))),
        "gloss": float(bool(checks.check_thematic_gloss(scene))),
        "slop": float(bool(checks.check_slop(scene))),
        "past_perfect": float(checks.summary_distance(sentence) > 0),
    }


def correlate(xs: list[float], ys: list[float]) -> float:
    """Pearson r, or 0.0 where a variable does not vary.

    Zero for a constant is the honest answer rather than a division by zero: a signal that is
    the same on every rated sentence has told you nothing about any of them.
    """
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def bootstrap_ci(values: list[float], iterations: int = 4000, seed: int = 0,
                 alpha: float = 0.05) -> tuple[float, float]:
    """A percentile bootstrap interval for a mean.

    Hand-rolled because this project has no runtime dependencies, and a bootstrap rather than a
    t-interval because a three-point rating scale is not normal and n is a hundred at most. The
    interval is the whole point: a mean rating quoted without one would be the same mistake as
    every claim retracted on 30 August, made in a new place.
    """
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(iterations))
    lo = means[int(alpha / 2 * iterations)]
    hi = means[min(iterations - 1, int((1 - alpha / 2) * iterations))]
    return lo, hi
