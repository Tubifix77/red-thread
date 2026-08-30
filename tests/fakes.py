"""A scripted backend, so the pipeline can be tested without an API key or a network call.

Dispatch is by a distinctive phrase from each prompt template rather than by call order, because
the pipeline's call order legitimately changes (candidates, repair rounds) and a test that
depends on it would break for the wrong reasons.
"""

from __future__ import annotations

import re as _re

import json

from redthread.llm import Backend, Models, Reply

# One distinctive marker per prompt template in verify.py / pipeline.py.
ROLES = {
    "continuity clerk": "extract",
    "checking a novel for continuity errors": "conflict",
    "whether a scene fulfilled its brief": "threads",
    "auditing a scene from a novel": "tells",
    "Write what you think happens in the very next scene": "forecast",
    "Fix ONLY the problems listed": "repair",
    "One sentence in a novel scene must be rewritten": "surgical",
    "It currently reuses wording from the": "reseam",
    "It has slipped out of the scene and": "unrecap",
    "One passage in a novel scene is too thin": "passage",
    "is missing something it was required to make happen": "fulfil",
    "discloses something the reader is not meant to know": "excise",
}


def classify(prompt: str) -> str:
    for marker, role in ROLES.items():
        if marker in prompt:
            return role
    return "draft"


# ---------------------------------------------------------------------------- canned replies

def facts_json(rows: list[tuple[str, str, str, str]]) -> str:
    return json.dumps({"facts": [
        {"subject": s, "predicate": p, "object": o, "kind": k} for s, p, o, k in rows]})


NO_CONFLICTS = json.dumps({"judgements": []})
NO_TELLS = json.dumps({"findings": []})


def threads_all_met(count: int = 12) -> str:
    return json.dumps({
        "requirements": [{"n": i, "verdict": "met", "evidence": "yes"} for i in range(count)],
        "prohibitions": [{"n": i, "violated": False, "quote": ""} for i in range(count)],
    })


def threads_one_missed(n: int = 0) -> str:
    rows = [{"n": i, "verdict": "met", "evidence": "yes"} for i in range(12)]
    rows[n] = {"n": n, "verdict": "missed", "evidence": ""}
    return json.dumps({"requirements": rows,
                       "prohibitions": [{"n": i, "violated": False} for i in range(12)]})


def threads_one_prohibition_violated(n: int = 0, quote: str = "she told him everything") -> str:
    prohibitions = [{"n": i, "violated": False} for i in range(12)]
    prohibitions[n] = {"n": n, "violated": True, "quote": quote}
    return json.dumps({"requirements": [{"n": i, "verdict": "met"} for i in range(12)],
                       "prohibitions": prohibitions})


def conflict_found(pair: int = 0, why: str = "the door cannot be both") -> str:
    return json.dumps({"judgements": [{"pair": pair, "contradiction": True, "why": why}]})


class ScriptedBackend(Backend):
    """Returns a queued reply per role, falling back to a default when the queue is empty."""

    name = "scripted"

    def __init__(self, defaults: dict[str, str] | None = None) -> None:
        self.defaults: dict[str, str] = {
            "extract": facts_json([("Siv", "has", "a notebook", "detail")]),
            "conflict": NO_CONFLICTS,
            "threads": threads_all_met(),
            "tells": NO_TELLS,
            "forecast": json.dumps({"prediction": "no idea", "closeness": 0.2}),
            "repair": "",
            "surgical": "She put the notebook away and said nothing about it.",
        # Long enough to clear the length floor in `_reseam`, which discards a
        # replacement shorter than 40% of the block it replaces.
        # Longer than any thin passage a test will hand it, so the "came back
        # shorter" guard in `_expand_passage` does not reject it.
        "passage": " ".join(_FILLER) + " " + " ".join(_combinatorial_filler(11)[:40]),
        "excise": "NONE",
        "fulfil": ("She put the vial on the bench and slid it across to him. He did not "
                   "pick it up. The tally sheet went into the stove and the stove door "
                   "clanged shut behind it."),
        "reseam": (
            "She set the wrench down on the bench, threads up, and wiped her hands on "
            "the rag hanging from the vice. Otto counted the washers back into their tin "
            "and pressed the lid on with his thumb. The yard door stuck the way it "
            "always stuck, and she put her shoulder to it and went out into the cold."),
        "unrecap": (
            "She set the second ledger on the bench and opened it to the middle. The "
            "spine cracked. Otto looked over and said nothing at all, and she wrote the "
            "date at the top of the page before she lost her nerve about it."),
        "draft": "",
        }
        self.defaults.update(defaults or {})
        self.queues: dict[str, list[str]] = {}
        self.calls: list[tuple[str, str]] = []

    def queue(self, role: str, *replies: str) -> "ScriptedBackend":
        self.queues.setdefault(role, []).extend(replies)
        return self

    def count(self, role: str) -> int:
        return sum(1 for r, _ in self.calls if r == role)

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 4096,
                 temperature: float = 1.0, stop: list[str] | None = None,
                 json_mode: bool = False) -> Reply:
        role = classify(prompt)
        self.calls.append((role, prompt))
        queue = self.queues.get(role)
        text = queue.pop(0) if queue else self.defaults[role]
        return Reply(text, 0, 0, "scripted")


def scripted_models(defaults: dict[str, str] | None = None) -> tuple[Models, ScriptedBackend]:
    """One backend serving every role, so `backend.calls` is a full transcript of the run."""
    backend = ScriptedBackend(defaults)
    return Models(writer=backend, critic=backend, extractor=backend), backend


# ---------------------------------------------------------------------------- prose fixtures

# Distinct opening blocks, one per scene position. `check_seam` compares the first 60 words of a
# scene against the last 150 of the previous one using 4-grams, so a fixture that reuses its
# opening text trips `seam_echo` on every scene after the first — which is the check working, not
# a bug. Each block shares no four-word run with any other block or with the filler below.
_OPENINGS = [
    "Otto had the intake housing open and both hands inside it. He did not look up when she "
    "came in. Siv set her bag down by the door, where it would be in the way of nobody, and "
    "waited to be noticed. That took a while. The bulb over the bench had gone amber at the "
    "ends the way they did before they failed, and she made a note to bring a spare, and then "
    "made a second note because the first one was on the back of something she would throw "
    "away.",

    "The yard smelled of diesel and cut grass, which meant Renner had been at the verges again "
    "instead of the pumps. Siv found him behind number two with a bucket of couplings sorted "
    "by nothing she could identify. He had his sleeves rolled to the elbow in weather that did "
    "not warrant it. There was a mug balanced on the housing with three inches of cold tea in "
    "it, and it had been there long enough to leave a ring.",

    "Beata had the gate wedged open with a fence post because the hinge had dropped in the "
    "spring and neither of them had fixed it. She was counting something in the near field and "
    "did not stop counting when her sister arrived. The dog came over instead, which was the "
    "closest thing to a welcome on offer. Above the parcel the sky had gone the flat white "
    "that meant nothing at all would happen for hours.",

    "The grain store had been an archive for eleven years and still smelled of grain. Siv "
    "worked from the bottom shelf upward, which was wrong, and knew it was wrong, and kept "
    "doing it because the top shelves were where the indexes had been water-damaged and she "
    "wanted the easy boxes behind her before she got tired. Somebody had labelled four "
    "consecutive crates MISC in the same hand. She opened them in order anyway.",

    "Otto's kitchen had one bulb and a table too big for the room. He put a mug in front of "
    "her without asking whether she wanted one. Siv turned it a quarter turn on the oilcloth "
    "and left it there. On the dresser behind him were twenty-two years of calendars from the "
    "same supplier, hung one over another, and she had never once asked him why he kept them "
    "or whether he knew he was keeping them.",

    "The registry office opened at nine and Lund was there at ten to, which Beata had counted "
    "on. There was a queue of one man with a dog licence and it took nineteen minutes. Beata "
    "spent them reading the noticeboard, which had a poster about drainage grants dated two "
    "years earlier and a hand-written card offering a plough. She copied the plough number "
    "onto her wrist and then thought better of wanting it.",

    "They used the small hearing room because the large one had chairs stacked in it from the "
    "harvest meeting. Siv laid the folder on the table square to the edge. Nobody had told her "
    "where to sit, so she stood, and then everyone else stood too, which was worse. Lund "
    "arrived with a second folder of her own and set it down at a careful distance from the "
    "first, as though the two might react.",

    "The kettle had boiled twice and been forgotten twice. Beata was at the sink with her back "
    "to the room, which was how she conducted arguments she intended to win, and Siv had "
    "learned as a child not to answer that back. The window over the sink looked out at the "
    "byre and the byre needed re-roofing and they both knew whose job that had been for the "
    "last four years.",

    "Substation four at night was warmer than the house. The reader terminal threw enough "
    "light to work by and nothing else did. Siv had the founders' folder open at the page she "
    "no longer needed to look at, and she looked at it, because the alternative was looking at "
    "the screen. Behind her the door was propped with the same fire extinguisher that had "
    "propped it since before she was qualified.",

    "Six weeks on, the near field was cut and baled and somebody else's problem. Beata walked "
    "the fence line out of habit rather than duty, stopping where the wire had been spliced so "
    "many times it was mostly splice. The well head sat where it had always sat, capped, "
    "registered wrong, and working perfectly. Somebody from the council had painted a number "
    "on the cap in yellow. Nobody had explained the number.",
]

# Shared body. Varied sentence length on purpose: a block of same-length sentences would trip
# `check_rhythm` and every pipeline test would fail for an unrelated reason.
# Combinatorial filler. The handwritten pool below is 24 sentences, and a 900-word scene needs
# roughly seventy — so `clean_prose` used to cycle it three times and scored 351 repeated
# 4-grams per 1000 words, worse than the median scene an 8B commits. A fixture called
# `clean_prose` that is measurably the least clean prose in the repository cannot test a
# repetition check, which is how `check_internal_repetition` went years without one.
#
# Three independent lists multiply out to several hundred sentences sharing almost no 4-grams,
# which is enough to build a long scene without cycling.
# Sixteen of each, not eight. With eight subjects across sixty-four sentences every subject
# opened eight of them, so "The night crew had" recurred eight times — which is exactly the
# verbal tic `check_internal_repetition` now flags at five. A fixture cannot carry the defect
# it is used to test for.
_SUBJECTS = [
    "The night crew",
    "Whoever worked the shift before her",
    "The relief driver",
    "Somebody in the office upstairs",
    "The man from the depot",
    "Her predecessor",
    "The inspector who came in March",
    "One of the yard hands",
    "A contractor nobody recognised",
    "The woman who did the accounts",
    "Two of the loaders",
    "Whoever answered the phone that morning",
    "An auditor from the county",
    "The apprentice",
    "Someone on the early rota",
    "The foreman before this one",
]

_VERBS = [
    "signed off on",
    "left a pencil note beside",
    "queried",
    "stopped bothering with",
    "re-taped the corner of",
    "filed a duplicate of",
    "crossed out and reinstated",
    "pinned a reminder over",
    "mislaid",
    "photocopied",
    "once scribbled a date on",
    "wedged a receipt into",
    "asked twice about",
    "rewrote the heading of",
    "folded and put away",
    "counted the pages of",
]

_OBJECTS = [
    "the intake log for that week",
    "the spare-parts requisition",
    "the wall chart by the door",
    "the shift handover book",
    "the calibration slip in the drawer",
    "the delivery docket from Tuesday",
    "the noticeboard behind the kettle",
    "the folder nobody opened all spring",
    "a stack of weighbridge tickets",
    "the maintenance card taped inside the lid",
    "last quarter's fuel returns",
    "the roster pinned above the sink",
    "an envelope of receipts from the ferry",
    "the index card system in the back office",
    "three pages of pump readings",
    "the visitors' book at the gate",
]

_TAILS = [
    "and nobody asked about it since.",
    "which explained nothing and was filed anyway.",
    "and the ink went brown at the edges.",
    "without writing down why.",
    "and the entry stayed where it was.",
    "which was how these things usually went.",
    "and it stayed that way.",
    "before the end of the month.",
    "then put it back exactly where it lived.",
    "and said so to nobody in particular.",
    "on a Friday, according to the date.",
    "and left the cap off the pen.",
    "twice, in two different colours.",
    "and nothing came of it either time.",
    "while the kettle was still going.",
    "and that was the end of that.",
]


_NOUNS = [
    "log", "requisition", "wall chart", "handover book", "calibration slip", "docket",
    "noticeboard", "folder", "weighbridge ticket", "maintenance card", "fuel return",
    "roster", "receipt", "index card", "pump reading", "visitors' book", "tally sheet",
    "delivery note", "inspection form", "spare-parts list",
]

_QUALIFIERS = [
    "for that week", "from the back office", "by the door", "in the second drawer",
    "nobody signed", "from the Tuesday run", "with the corner torn", "kept above the sink",
    "from before the changeover", "that lived on the nail", "under the till",
    "the auditor had asked for", "pinned to the frame", "in the green folder",
    "from the previous quarter", "wedged behind the pipe",
]


# One per fixture scene. Any text assembled from a fixed pool of components repeats those
# components across scenes — that is arithmetic, not a bug in the generator — and
# `check_repetition` reads it as the refrain it is. Real prose varies far more than a
# combinatorial fixture can, so rather than write six hundred genuinely distinct sentences, each
# scene gets its own place name and every sentence carries it. Artificial, and openly so: the
# point of this fixture is to be clean under the checks, not to read well.
_PLACES = ["at Hald", "at Braaten", "at Vinge", "at Skare", "at Molde", "at Rud", "at Ness",
           "at Sund", "at Bern", "at Kvam", "at Foss", "at Aal"]


def _combinatorial_filler(variant: int = 0) -> list[str]:
    """Sentences that share almost no four-word runs, in a deterministic order."""
    out = []
    for i in range(len(_SUBJECTS) * 40):
        subject = _SUBJECTS[i % len(_SUBJECTS)]
        verb = _VERBS[(i * 7 + 3) % len(_VERBS)]
        # The object is combinatorial too. With sixteen fixed objects across six hundred
        # sentences each one turned up forty times, so every scene shared them however the pool
        # was sliced — a refrain, which is the defect this fixture is used to test for.
        noun = _NOUNS[(i * 3 + 1) % len(_NOUNS)]
        qualifier = _QUALIFIERS[(i * 11 + 5) % len(_QUALIFIERS)]
        tail = _TAILS[(i * 13 + 2) % len(_TAILS)]
        place = _PLACES[variant % len(_PLACES)]
        out.append(f"{subject} {place} {verb} the {noun} {qualifier}, {tail}")
    return out


_FILLER = [
    "The pump cycled, caught, and settled.",
    "She counted eleven seconds before it went again.",
    "The log claimed nine.",
    "She wrote that down in pencil, under the line number from the night before, and then drew "
    "a box around both figures the way she had been taught to mark a reading she did not yet "
    "trust.",
    "A truck went past on the access road without slowing.",
    "Otto asked for the smaller wrench.",
    "She passed him the smaller wrench.",
    "The coupling came free with a sound like a knuckle cracking and he stood it on the bench, "
    "threads up, and considered it for longer than the job required.",
    "Neither of them mentioned the cold store.",
    "Somewhere under the floor a valve shut with the flat knock it had made for twenty years.",
    "It held.",
    "There would be a form to fill in about all of this, and she would fill it in badly.",
    "The tally sheet had been photocopied so often that the column headings had closed up.",
    "Nobody had signed the bottom of it since March.",
    "She checked the figure twice and then checked the sheet she was checking it against.",
    "A dog barked once, a long way off, and stopped.",
    "Outside, the light had gone the colour it went before it went entirely.",
    "He wiped his hands on the cloth that lived on the nail and hung it back on the nail.",
    "The second gauge had been reading two low for as long as anyone could remember, and "
    "everyone who used it subtracted two without thinking about it, which was the kind of "
    "arrangement that worked until the day somebody new read it.",
    "She said the number out loud to hear whether it sounded wrong.",
    "It did not.",
    "That was the part she disliked.",
    "The kettle in the far room clicked off on its own.",
    "Nothing else happened for a while, and then the housing rattled and settled again.",
]


# Distinct closings, one per scene position, for the same reason as the openings: consecutive
# fixture scenes must not share their final 5-grams, or `seam_tail_copy` — which exists to catch
# a scene re-using the previous ending — fires on the fixture's own filler. Each entry is two
# sentences totalling more than the check's 25-word window, so no cycled filler is ever inside
# the compared endings.
_CLOSINGS = [
    "The spare bulb went into her pocket against every rule about pockets. She hung the "
    "clipboard back on its nail and pulled the door to behind her.",
    "One of the couplings still had paint on the thread from the factory. He carried the "
    "bucket inside and did not sort them any further.",
    "The count came to forty-one, which was one more than the ledger wanted. The dog followed "
    "her as far as the gate and no further.",
    "The MISC labels came off in strips and she balled them into her apron. She stacked the "
    "four crates back in their wrong order and left them so.",
    "Neither of them had touched the biscuits and neither would mention it. The mug of tea "
    "went cold on the oilcloth between them.",
    "The plough number had smudged on her wrist into something useless. Beata folded the "
    "licence into her coat and took the long way home.",
    "The chairs from the harvest meeting stayed stacked where they had been. Lund gathered "
    "both folders under one arm and turned the lamp off.",
    "The byre roof ticked as the day's heat went out of the iron. The kettle clicked off a "
    "third time and nobody in the kitchen moved.",
    "The fire extinguisher had rusted a ring into the concrete years ago. Siv propped the "
    "door with it again on her way out into the dark.",
    "A splice she had made herself in her first year still held tight. She walked the last "
    "stretch of wire without stopping and let herself out.",
]


_RECAP_BLOCK = [
    "She had come to the depot in the spring, before the changeover.",
    "The office had been three rooms then, and the third had been full of chairs.",
    "Nobody had told her what the second ledger was for.",
    "She had asked twice and had been given the same answer both times.",
    "The answer had been that it was not her ledger.",
]


_RECAP_BLOCK_B = [
    "The tide table had hung by the door since before her time.",
    "Someone had pencilled corrections down the margin of it.",
    "Nobody had ever rubbed them out or written them up properly.",
    "The corrections had been right, which was the awkward part of it.",
    "She had checked them once against the harbour record and said nothing.",
]


def recap_prose(words: int = 900, variant: int | None = None, sentences: int = 5,
                blocks: int = 1) -> str:
    """Clean prose with one block of consecutive past-perfect sentences buried in the middle.

    The shape `check_recap_block` exists for, and the shape `clean_prose` deliberately does not
    have: a paragraph of backstory dictated into a scene, with edges a repair can find.
    """
    body = clean_prose(words, variant)
    spans = _re.compile(r"[.!?]+\s+").split(body)
    n = max(1, sentences)
    first = " ".join(_RECAP_BLOCK[:n])
    if blocks < 2:
        cut = max(1, len(spans) // 2)
        return ". ".join(spans[:cut]) + ". " + first + " " + ". ".join(spans[cut:])
    # Two blocks far enough apart that one repair cannot reach both, and worded differently so
    # they are separately locatable — a scene that repeats the *same* recap verbatim is a real
    # thing (scene 9 of a live run did it) but makes a poor fixture, because both violations
    # then carry one quote.
    second = " ".join(_RECAP_BLOCK_B[:n])
    a, b = max(1, len(spans) // 3), max(2, 2 * len(spans) // 3)
    return (". ".join(spans[:a]) + ". " + first + " " + ". ".join(spans[a:b]) + ". "
            + second + " " + ". ".join(spans[b:]))


def clean_prose(words: int = 900, variant: int | None = None) -> str:
    """Prose that passes every deterministic check, at roughly the requested length.

    Pass `variant` to get a distinct opening and closing — required for any test that writes
    consecutive scenes, or the seam checks reject everything after scene one. Callers that only
    write a single scene can leave it unset.
    """
    opening = _OPENINGS[(variant or 0) % len(_OPENINGS)]
    closing = _CLOSINGS[(variant or 0) % len(_CLOSINGS)]
    out: list[str] = [opening]
    count = len(opening.split()) + len(closing.split())
    # Handwritten filler first, then the combinatorial pool, and each sentence used at most
    # once. Cycling a 24-sentence list to reach 900 words put this fixture at 351 repeated
    # 4-grams per 1000 — worse than the median scene an 8B commits, and enough to make it
    # useless for testing a repetition check.
    pool = _FILLER + _combinatorial_filler(variant or 0)
    # A *disjoint slice* per variant, not a rotation. Ten fixture scenes rotating three
    # sentences apart in one pool share almost every sentence, which is a refrain running through
    # the manuscript — the exact defect `check_repetition` now flags. A fixture cannot carry the
    # defect it is used to test for; that has now been true of this file three times.
    start = (variant or 0) * 60
    # Two passes at most: the pool holds roughly 1,300 words, and the runaway-length fixtures
    # ask for 2,300. Repeating is what those tests are *for* — they need an over-long scene, not
    # a clean one — so the second lap is allowed and the first is not.
    for offset in range(len(pool) * 3):
        if count >= words:
            break
        sentence = pool[(start + offset) % len(pool)]
        length = len(sentence.split())
        if count + length > words * 1.12:
            continue
        out.append(sentence)
        count += length
    out.append(closing)
    return " ".join(out)


def prose_with_somatic_tics(words: int = 900, variant: int | None = None) -> str:
    """Clean prose plus four bodily-emotion beats — a MAJOR under `check_somatic`."""
    return clean_prose(words, variant) + (
        " Her chest tightened. His stomach dropped. Something twisted in her throat. "
        "She let out a breath she didn't know she was holding.")


def prose_with_heading(words: int = 900, variant: int | None = None) -> str:
    """A BLOCKER under `check_format`."""
    return "## Chapter One\n\n" + clean_prose(words, variant)
