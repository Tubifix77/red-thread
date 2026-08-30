"""Dynamic memory: the fact ledger.

Representation is DOME's temporal knowledge graph — quadruples
`<subject, predicate, object, scene_index>` — and conflict detection is DOME's two-stage
approach: group structurally-similar quadruples deterministically, then hand only the
suspicious groups to a model for judgement (RESEARCH.md section 3).

The deterministic grouping is the important half. It is cheap, it is reproducible, and it
means the expensive LLM judgement only ever sees a handful of candidate pairs instead of the
whole manuscript.
"""

from __future__ import annotations

import re
from collections import defaultdict

from .models import Fact, FactKind

_STOP = {
    "a", "an", "the", "of", "to", "in", "on", "at", "for", "with", "and", "or", "is", "was",
    "be", "been", "her", "his", "their", "its", "that", "this", "it", "as", "by", "from",
}


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def content_tokens(text: str) -> set[str]:
    return {t for t in normalise(text).split() if t and t not in _STOP}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


_PLACE = re.compile(
    r"\b(?:in|on|under|behind|beside|between|at|inside|outside|over|near|beneath|atop|"
    r"against|by|from|across|through|onto|into|within|below|above|next to|"
    r"in front of)\b", re.IGNORECASE)


_IDENTITY = re.compile(r"^(?:a|an|the)\s+\w+", re.IGNORECASE)


def claim_class(fact: Fact) -> str:
    """What kind of claim this fact's object makes: identity, position, or condition.

    Two facts only contradict if they answer the same question. A live run blocked scene 9 on
    "the register cannot be both open on the table and a book with worn leather" — which of
    course it can. The pairing key is `(subject, predicate)`, and a bare copula carries no
    meaning at all: `the register | is | ...` groups where it lies with what it is made of with
    whether it is open. Classifying the object separates them, and it is the object that says
    what attribute is being claimed.
    """
    obj = fact.object.strip()
    if _IDENTITY.match(obj):
        return "identity"
    if _PLACE.search(obj):
        return "position"
    return "condition"


def is_moveable_pair(a: Fact, b: Fact) -> bool:
    """Do these two facts just say where something was at two different moments?

    A `STATE` is defined in this codebase as "something now true that stays true until something
    changes it" — the kind of fact that is *supposed* to change. So two states placing the same
    subject somewhere are a subject that moved, not a contradiction. A live run blocked scene 8
    on `The register | is | open on the table` against `the register | is | in the drawer`, three
    scenes apart, and on `is | still cool from the night air` against the same. The judge was
    asked and said contradiction; it should never have been asked.

    Restricted to `STATE` on purpose. A `DETAIL` is "a concrete particular the prose has now
    fixed and cannot change" — a scar on the left hand against one on the right is exactly the
    contradiction this system exists to catch, and it stays checked.
    """
    if a.kind is not FactKind.STATE or b.kind is not FactKind.STATE:
        return False
    return bool(_PLACE.search(a.object) and _PLACE.search(b.object))


_POSSESSION = re.compile(
    r"\b(?:carry|carries|carrying|hold|holds|holding|wear|wears|wearing|grip|grips|gripping|"
    r"clutch\w*|grasp\w*|touch\w*|bear|bears|bearing|keeps? in|has in|had in)\b", re.IGNORECASE)


def is_possession_pair(a: Fact, b: Fact) -> bool:
    """Do these two facts just say what somebody was carrying at two different moments?

    The same argument as `is_moveable_pair`, for the other half of the same idea: that guard
    covers where a thing *is*, and this one covers who is *holding* it. Both are `STATE`, which
    this codebase defines as "something now true that stays true until something changes it" —
    the kind of fact that is supposed to change.

    The 71-scene run halted at scene 37 on `Vael | is carrying | a blade` from scene 27 against
    `Vael | is carrying | a bundle`. Ten scenes apart, a character who has put one thing down
    and picked another up is not a contradiction; it is the story. The judge was asked and said
    contradiction, which is what a judge will always say to two different objects — it has no
    notion of elapsed time. It should never have been asked.

    This is the failure mode that only appears at length. Across every ledger in the project
    there are 35 possession facts and just three subject-and-predicate keys carrying more than
    one object, so nine-scene books never met it. One of the three stopped a book at scene 37.

    Restricted to `STATE`, like its sibling, and that restriction is load-bearing: `Vael | has a
    | scar on his wrist` is a `DETAIL`, so a scar that moves to the other wrist is still caught.

    Matched across the predicate *and* the object together, the way `is_belief_pair` does, and
    the first version of this guard did not. It only read the predicate, which caught `Vael | is
    carrying | a blade` and then missed `Vael | is | holding a dagger` twelve scenes later —
    same claim, same book, the verb landing on the other side of a boundary that is an artefact
    of extraction rather than of meaning. The same run halted twice on one bug.
    """
    if a.kind is not FactKind.STATE or b.kind is not FactKind.STATE:
        return False
    return bool(_POSSESSION.search(f"{a.predicate} {a.object}")
                and _POSSESSION.search(f"{b.predicate} {b.object}"))


_MIND = re.compile(
    r"\b(?:believ\w*|belief|beliefs|think\w*|thought|thoughts|assum\w*|suspect\w*|"
    r"doubt\w*|know|knows|known|knew|understand\w*|understood|convinced|certain|unsure|"
    r"question\w*|wonder\w*|notic\w*|realis\w*|realiz\w*|accept\w*|expect\w*|"
    r"trust\w*|suspicion)\b", re.IGNORECASE)


def is_belief_pair(a: Fact, b: Fact) -> bool:
    """Are these two facts both about what somebody believes or knows?

    A mind changing across a story is the story. A live run blocked scene 7 on
    `Marta | has | belief that the register is correct` against
    `Marta | has known | system is broken` — the arc the book exists to trace, reported as a
    detail given two different values.

    The genuine knowledge failure is different in shape: a character acting on what they have
    not been told yet. That is what `Ledger.knows` and the brief's knowledge section are for,
    and neither goes through this pairing.
    """
    return bool(_MIND.search(f"{a.predicate} {a.object}")
                and _MIND.search(f"{b.predicate} {b.object}"))


def same_claim(a: Fact, b: Fact) -> bool:
    """Do these two quadruples assert the same thing, differently split?

    Where the predicate ends and the object begins is an artefact of extraction, not of meaning.
    A live run blocked scene 6 on `Dain Korr | has | read the records` against
    `Dain Korr | has read | records` — one proposition, extracted twice, two scenes apart, with
    the verb landing on opposite sides of the boundary. The judge was asked whether they
    contradicted and answered "same action given twice", which is true and is not a
    contradiction; the pair should never have reached it.

    So compare the predicate and object together. If one fact's content words are a subset of
    the other's, it is the same claim restated or narrowed — never a contradiction, which needs
    two claims that differ.
    """
    ta = content_tokens(f"{a.predicate} {a.object}")
    tb = content_tokens(f"{b.predicate} {b.object}")
    if not ta or not tb:
        return False
    return ta <= tb or tb <= ta


class Ledger:
    """Append-only store of facts, with conflict candidate detection and scoped retrieval."""

    def __init__(self, facts: list[Fact] | None = None) -> None:
        self.facts: list[Fact] = list(facts or [])

    # ---------------------------------------------------------------- writing

    def add(self, fact: Fact) -> None:
        self.facts.append(fact)

    def extend(self, facts: list[Fact]) -> None:
        self.facts.extend(facts)

    def drop_scene(self, scene: int) -> None:
        """Roll back an uncommitted scene's facts. Commit gate support: nothing enters
        dynamic memory until the scene passes, so a failed scene must leave no trace."""
        self.facts = [f for f in self.facts if f.scene != scene]

    # ---------------------------------------------------------------- reading

    def as_of(self, scene: int) -> list[Fact]:
        return [f for f in self.facts if f.scene <= scene]

    def knows(self, character: str, scene: int) -> list[Fact]:
        """What `character` knows entering `scene`.

        Character knowledge state is the single field that breaks most often in machine-written
        fiction: a character acting on information they do not have yet, or being surprised by
        something established two chapters back. It gets its own accessor for that reason.
        """
        who = normalise(character)
        return [
            f for f in self.facts
            if f.kind is FactKind.KNOWLEDGE
            and f.scene < scene
            and normalise(f.subject) == who
        ]

    def about(self, subjects: list[str], scene: int, limit: int = 40) -> list[Fact]:
        """The ledger slice for a brief: facts touching these subjects, most recent first.

        DOME retrieves by embedding similarity at cosine 0.75. We retrieve by subject-name
        overlap, which needs no embedding model and is exact for the thing that actually
        matters — the entities in this scene. Semantic retrieval is a later upgrade for
        thematic recall, not for entity state.

        Matching is bidirectional on purpose, and that is not a detail. Specs carry full names
        ("Siv Alderman") while extraction produces the name the prose uses ("Siv"), so a
        one-directional substring test silently matches nothing: the ledger fills up and every
        brief still says "nothing established yet". Continuity then fails with no error anywhere.
        Token overlap catches both directions, at the cost of occasionally retrieving a fact that
        merely shares a word — which costs a few lines of prompt and is the right trade.
        """
        wanted_full = {normalise(s) for s in subjects if s}
        wanted_tokens: set[str] = set()
        for s in subjects:
            wanted_tokens |= content_tokens(s)

        hits = []
        for f in self.as_of(scene - 1):
            subj, obj = normalise(f.subject), normalise(f.object)
            if (subj in wanted_full
                    or any(w and (w in subj or subj in w) for w in wanted_full)
                    or (content_tokens(f.subject) & wanted_tokens)
                    or (content_tokens(f.object) & wanted_tokens)):
                hits.append(f)
        hits.sort(key=lambda f: f.scene, reverse=True)
        if len(hits) <= limit:
            return hits

        # Recency alone empties the book out from under its own ending.
        #
        # Sorting by scene and truncating is fine while the ledger is small and catastrophic
        # once it is not. Measured on a finished 71-scene novel: at scene 71, 888 facts match
        # the scene's subjects, 40 survive, and the oldest kept is from scene 68. The final
        # scene of the book could see scenes 68, 69 and 70 and nothing else — every revelation,
        # promise and relationship from the first 67 scenes was invisible to it.
        #
        # That is a structural reason a middle cannot earn an ending: the ending was never told
        # what the middle was. So the slice is stratified instead. Most of it is still recent,
        # because current state is what a scene mostly needs, and the rest is spread evenly
        # across everything older, which guarantees the brief always carries something from the
        # beginning and the middle of its own book.
        #
        # `knows` is deliberately left uncapped and is unaffected; character knowledge was
        # already the one thing that reached back.
        recent_slots = max(1, int(limit * 0.65))
        recent, older = hits[:recent_slots], hits[recent_slots:]
        spread_slots = limit - len(recent)
        if older and spread_slots > 0:
            step = len(older) / spread_slots
            spread = [older[min(len(older) - 1, int(i * step))] for i in range(spread_slots)]
            seen_ids: set[int] = set()
            picked = []
            for f in spread:
                if id(f) not in seen_ids:
                    seen_ids.add(id(f))
                    picked.append(f)
            recent += picked
        return recent

    def latest_state(self, subject: str, predicate: str) -> Fact | None:
        key = (normalise(subject), normalise(predicate))
        matches = [f for f in self.facts if (normalise(f.subject), normalise(f.predicate)) == key]
        return max(matches, key=lambda f: f.scene) if matches else None

    # ---------------------------------------------------------------- conflicts

    def conflict_candidates(
        self, new_facts: list[Fact], similarity: float = 0.34
    ) -> list[tuple[Fact, Fact]]:
        """Pairs of facts that might contradict, for a model to judge.

        Stage 1 of DOME's detection. Two facts are candidates when they share a
        `(subject, predicate)` key but disagree on the object, or when their subject matches
        and their predicates are near-synonymous by token overlap. Events are excluded from
        object-disagreement checks: two different events for the same subject and verb are
        normal ("Mara went to the dock" twice is not a contradiction). States, knowledge and
        details are the kinds where a changed object means something.
        """
        by_key: dict[tuple[str, str], list[Fact]] = defaultdict(list)
        for f in self.facts:
            by_key[f.key()].append(f)

        pairs: list[tuple[Fact, Fact]] = []
        seen: set[tuple[int, int]] = set()

        for nf in new_facts:
            if nf.kind is FactKind.EVENT:
                continue
            # exact key collision with a differing object
            for old in by_key.get(nf.key(), []):
                if old is nf or old.scene == nf.scene:
                    continue
                if (normalise(old.object) == normalise(nf.object) or same_claim(old, nf)
                        or is_moveable_pair(old, nf)
                        or is_possession_pair(old, nf)
                        or is_belief_pair(old, nf)
                        or claim_class(old) != claim_class(nf)):
                    continue
                mark = (id(old), id(nf))
                if mark not in seen:
                    seen.add(mark)
                    pairs.append((old, nf))

            # near-synonymous predicate on the same subject
            nf_pred = content_tokens(nf.predicate)
            for old in self.facts:
                if old is nf or old.scene == nf.scene or old.kind is FactKind.EVENT:
                    continue
                if normalise(old.subject) != normalise(nf.subject):
                    continue
                if old.key() == nf.key():
                    continue
                if jaccard(content_tokens(old.predicate), nf_pred) < similarity:
                    continue
                if (normalise(old.object) == normalise(nf.object) or same_claim(old, nf)
                        or is_moveable_pair(old, nf)
                        or is_possession_pair(old, nf)
                        or is_belief_pair(old, nf)
                        or claim_class(old) != claim_class(nf)):
                    continue
                mark = (id(old), id(nf))
                if mark not in seen:
                    seen.add(mark)
                    pairs.append((old, nf))

        return pairs

    # ---------------------------------------------------------------- rendering

    def render(self, facts: list[Fact]) -> str:
        if not facts:
            return "(nothing established yet)"
        by_kind: dict[str, list[str]] = defaultdict(list)
        for f in facts:
            by_kind[f.kind.value].append(f.as_line())
        out = []
        for kind in ("state", "knowledge", "detail", "event"):
            if kind in by_kind:
                out.append(f"{kind.upper()}:")
                out.extend(f"  {line}" for line in by_kind[kind])
        return "\n".join(out)
