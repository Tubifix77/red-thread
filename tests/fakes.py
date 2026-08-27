"""A scripted backend, so the pipeline can be tested without an API key or a network call.

Dispatch is by a distinctive phrase from each prompt template rather than by call order, because
the pipeline's call order legitimately changes (candidates, repair rounds) and a test that
depends on it would break for the wrong reasons.
"""

from __future__ import annotations

import json

from redthread.llm import Backend, Models, Reply

# One distinctive marker per prompt template in verify.py / pipeline.py.
ROLES = {
    "continuity clerk": "extract",
    "checking a novel for continuity errors": "conflict",
    "whether a scene fulfilled its brief": "threads",
    "auditing a scene from a novel": "tells",
    "Before reading what happens next": "forecast",
    "Fix ONLY the problems listed": "repair",
    "One sentence in a novel scene must be rewritten": "surgical",
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


def threads_one_prohibition_violated(n: int = 0) -> str:
    prohibitions = [{"n": i, "violated": False} for i in range(12)]
    prohibitions[n] = {"n": n, "violated": True, "quote": "she told him everything"}
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


def clean_prose(words: int = 900, variant: int | None = None) -> str:
    """Prose that passes every deterministic check, at roughly the requested length.

    Pass `variant` to get a distinct opening — required for any test that writes consecutive
    scenes, or the seam check will reject everything after scene one. Callers that only write a
    single scene can leave it unset.
    """
    opening = _OPENINGS[(variant or 0) % len(_OPENINGS)]
    out: list[str] = [opening]
    count = len(opening.split())
    i = 0
    while count < words:
        sentence = _FILLER[i % len(_FILLER)]
        i += 1
        length = len(sentence.split())
        if count + length > words * 1.12:
            break
        out.append(sentence)
        count += length
    return " ".join(out)


def prose_with_somatic_tics(words: int = 900, variant: int | None = None) -> str:
    """Clean prose plus four bodily-emotion beats — a MAJOR under `check_somatic`."""
    return clean_prose(words, variant) + (
        " Her chest tightened. His stomach dropped. Something twisted in her throat. "
        "She let out a breath she didn't know she was holding.")


def prose_with_heading(words: int = 900, variant: int | None = None) -> str:
    """A BLOCKER under `check_format`."""
    return "## Chapter One\n\n" + clean_prose(words, variant)
