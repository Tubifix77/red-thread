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
        return hits[:limit]

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
                if normalise(old.object) == normalise(nf.object):
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
                if normalise(old.object) == normalise(nf.object):
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
