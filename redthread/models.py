"""Core data model.

The split between what is immutable and what accumulates follows ConWriter's
static/dynamic memory distinction (docs/RESEARCH.md section 4): `StorySpec` and everything
reachable from it is static memory; `Fact` rows and `Thread.current_state` are dynamic
memory, and dynamic memory is only written after a scene passes its checks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict, fields, is_dataclass
from enum import Enum
from typing import Any


# --------------------------------------------------------------------------------------
# serialisation helpers
# --------------------------------------------------------------------------------------

def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def _from_jsonable(cls: type, data: Any) -> Any:
    """Rebuild a dataclass tree from plain JSON. Tolerates unknown keys."""
    if not (isinstance(cls, type) and is_dataclass(cls)):
        return data
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        kwargs[f.name] = _rebuild_field(f.type, data[f.name])
    return cls(**kwargs)


def _rebuild_field(ftype: Any, value: Any) -> Any:
    name = ftype if isinstance(ftype, str) else getattr(ftype, "__name__", str(ftype))
    if value is None:
        return None
    if "list[Character]" in name:
        return [_from_jsonable(Character, v) for v in value]
    if "list[Thread]" in name:
        return [_from_jsonable(Thread, v) for v in value]
    if "list[Beat]" in name:
        return [_from_jsonable(Beat, v) for v in value]
    if "list[Fact]" in name:
        return [_from_jsonable(Fact, v) for v in value]
    if "dict[str, Transition]" in name:
        return {k: _from_jsonable(Transition, v) for k, v in value.items()}
    if "StyleContract" in name:
        return _from_jsonable(StyleContract, value)
    if "Transition" in name:
        return _from_jsonable(Transition, value)
    if "ThreadKind" in name:
        return ThreadKind(value)
    if "FactKind" in name:
        return FactKind(value)
    if "Severity" in name:
        return Severity(value)
    return value


class JsonMixin:
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(_to_jsonable(self), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str):
        return _from_jsonable(cls, json.loads(text))


# --------------------------------------------------------------------------------------
# static memory
# --------------------------------------------------------------------------------------

@dataclass
class Character:
    id: str
    name: str
    # Immutable attributes. Anything that changes during the story belongs in the ledger
    # as a Fact, not here — that is the whole point of the static/dynamic split.
    description: str = ""
    voice: str = ""
    """How this character speaks. Distinct diction per character is the cheapest defence
    against every character sounding like the narrator."""


@dataclass
class StyleContract:
    """The voice contract injected into every scene brief.

    `samples` matters more than any adjective you could write here: showing the model three
    sentences of the target prose constrains it harder than describing the target prose.
    """
    pov: str = "third limited"
    tense: str = "past"
    samples: list[str] = field(default_factory=list)
    forbidden_phrases: list[str] = field(default_factory=list)
    notes: str = ""


class ThreadKind(str, Enum):
    MAIN = "main"
    SUBPLOT = "subplot"
    RELATIONSHIP = "relationship"
    MYSTERY = "mystery"
    THEMATIC = "thematic"


@dataclass
class Thread:
    """A red thread: a named through-line with an explicit state machine.

    The state machine is the mechanism that makes "did this scene do its job?" a checkable
    question rather than a vibe. ConWriter's formulation (RESEARCH.md section 4).
    """
    id: str
    name: str
    kind: ThreadKind = ThreadKind.SUBPLOT
    states: list[str] = field(default_factory=lambda: ["dormant", "planted", "complicated",
                                                       "escalated", "paid_off"])
    current_state: str = "dormant"

    concealment: str = ""
    """What the reader must NOT yet understand about this thread. Tension is downstream of
    hidden information (RESEARCH.md section 9), so concealment is a first-class field: a thread
    with nothing concealed generates predictable scenes."""

    payoff: str = ""
    """What resolution looks like. An unpaid thread at manuscript end is an error, not a mood."""

    reveal_state: str | None = None
    """The state whose arrival ends the concealment — the semantic half of the reveal. Code
    cannot know that reaching 'discovered' discloses an enclave, but the planner can say so,
    and the scheduler then derives `reveal_scene` from wherever it placed that state. Without
    this, a planner-made thread whose second state was 'discovered' carried a concealment that
    forbade the very disclosure its own schedule ordered two scenes in."""

    reveal_scene: int | None = None
    """First scene allowed to disclose the concealment. Before it, the concealment is enforced
    as a hard prohibition on every scene touching the thread; from it on, it is not. Without
    this, the scene whose job is the reveal gets a brief that simultaneously requires and
    forbids it — a real run deadlocked exactly there, the judge correctly flagging both
    'missed the reveal' and 'violated the concealment'. None means concealed throughout."""

    deadline_scene: int | None = None
    """Latest scene index by which this thread must reach its final state."""

    def state_index(self, state: str) -> int:
        try:
            return self.states.index(state)
        except ValueError:
            return -1

    def is_resolved(self) -> bool:
        return bool(self.states) and self.current_state == self.states[-1]


@dataclass
class StorySpec(JsonMixin):
    """Static memory. Immutable during a run."""
    title: str
    premise: str
    world_rules: list[str] = field(default_factory=list)
    characters: list[Character] = field(default_factory=list)
    threads: list[Thread] = field(default_factory=list)
    style: StyleContract = field(default_factory=StyleContract)

    def character(self, cid: str) -> Character | None:
        return next((c for c in self.characters if c.id == cid), None)

    def thread(self, tid: str) -> Thread | None:
        return next((t for t in self.threads if t.id == tid), None)

    def unresolved_threads(self) -> list[Thread]:
        return [t for t in self.threads if not t.is_resolved()]


# --------------------------------------------------------------------------------------
# the spec tree
# --------------------------------------------------------------------------------------

@dataclass
class Transition:
    """A thread operator: what must hold before, what must hold after, what must not change.

    Lifted directly from ConWriter's (Pre, Post, Forbid) symbolic operators.
    """
    pre: list[str] = field(default_factory=list)
    post: list[str] = field(default_factory=list)
    forbid: list[str] = field(default_factory=list)
    to_state: str | None = None
    """Thread state this scene must leave the thread in. None = no state change required."""


@dataclass
class Beat:
    """A beat is a unit of *intent*, roughly half a page of story.

    Beats are never generated in isolation — the scene is the generation unit. A beat too
    small to carry a turn cannot be written well alone; see RESEARCH.md open question 1.
    """
    summary: str
    concreteness: float = 0.0
    """0 = abstract placeholder, 1 = fully specified. Drives vaguest-first expansion
    (CONCOCT, RESEARCH.md section 8)."""


@dataclass
class SceneSpec(JsonMixin):
    id: str
    index: int
    chapter: int = 1
    summary: str = ""
    setting: str = ""
    time: str = ""
    pov: str = ""
    """Character id whose head we are in."""
    characters: list[str] = field(default_factory=list)
    beats: list[Beat] = field(default_factory=list)
    thread_ops: dict[str, Transition] = field(default_factory=dict)
    """thread id -> the transition this scene must effect."""
    word_target: int = 1100
    concreteness: float = 0.0
    notes: str = ""
    depends_on: list[int] = field(default_factory=list)
    """Earlier scene indices this scene needs the reader to have read.

    Asked for, not inferred. Inference was tried first and failed for a reason worth keeping:
    dependency was derived from subject overlap between a scene and the ledger facts it used,
    and because the cast recurs in every scene, *every* scene came back load-bearing — zero of
    70 contributed facts that were never retrieved again. That measured entity overlap, not
    dependency.

    Asking is cheap and the answer is checkable, which is the whole difference. A declared edge
    can be audited deterministically (does it point backwards, is the graph acyclic, how much of
    the book does the ending actually reach) before a word is written, and separately tested
    against the prose afterwards. An inferred one can only be believed.

    Empty is not "no dependencies" — it is "nobody said", which is what every plan written
    before this field existed will report. `check_dependency_graph` treats absence as unknown
    rather than as a failure.
    """

    def touched_threads(self) -> list[str]:
        return list(self.thread_ops.keys())


# --------------------------------------------------------------------------------------
# dynamic memory
# --------------------------------------------------------------------------------------

class FactKind(str, Enum):
    EVENT = "event"
    """Something that happened."""
    STATE = "state"
    """Something that is now true and stays true until changed."""
    KNOWLEDGE = "knowledge"
    """Character X knows proposition Y. The field that breaks most often."""
    DETAIL = "detail"
    """A concrete physical/sensory particular now fixed by the prose."""


@dataclass
class Fact:
    """A quadruple, per DOME: <subject, predicate, object, scene_index>.

    Prose notes cannot be diffed or conflict-checked. Quadruples can.
    """
    subject: str
    predicate: str
    object: str
    scene: int
    kind: FactKind = FactKind.EVENT

    def key(self) -> tuple[str, str]:
        """Structural grouping key. DOME groups quadruples by structural similarity before
        asking a model to judge conflict; this is that key."""
        return (self.subject.strip().lower(), self.predicate.strip().lower())

    def as_line(self) -> str:
        return f"[s{self.scene}] {self.subject} | {self.predicate} | {self.object}"


class Severity(str, Enum):
    BLOCKER = "blocker"
    """Cannot commit. Contradicts committed state or violates a Forbid."""
    MAJOR = "major"
    """Should repair. Missed a required Post, broke the voice contract."""
    MINOR = "minor"
    """Worth logging. Slop phrase, a repeated image."""


@dataclass
class Violation:
    kind: str
    severity: Severity
    detail: str
    source: str = ""
    """Which check produced this — deterministic check name or 'llm:<probe>'."""
    quote: str = ""
    """The offending span, verbatim, so repair can be localised to it rather than
    regenerating the scene (ConWriter, RESEARCH.md section 4)."""

    def __str__(self) -> str:
        head = f"[{self.severity.value}] {self.kind}: {self.detail}"
        return f"{head}\n    > {self.quote}" if self.quote else head


@dataclass
class ThreadMove:
    """One recorded thread state transition.

    Recording history rather than only current state is what makes the author's second test
    marker checkable without any model call: a thread transitioning *into a state it has already
    occupied* is a story circling its own conflict rather than complicating it
    (docs/TESTING.md marker 2).
    """
    thread_id: str
    from_state: str
    to_state: str
    scene: int

    def is_regression(self, thread: Thread) -> bool:
        return thread.state_index(self.to_state) < thread.state_index(self.from_state)


@dataclass
class Scene(JsonMixin):
    spec_id: str
    index: int
    text: str = ""
    committed: bool = False
    facts: list[Fact] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    attempts: int = 0
    # PLAN2 step 31. `attempts` is candidates + repairs and only the sum was kept, so every run
    # ever written is one subtraction short of saying anything about repair
    # (docs/evidence/repair-backfill.md). These record the terms separately, and the ladder's
    # own events, so the next convergence question is answered from disk instead of re-run.
    candidates_drafted: int = 0
    repairs: int = 0
    repair_log: list[dict] = field(default_factory=list)
    """One dict per repair-ladder event: {"phase", "action", "round", "targets", "outcome"}.
    Phases: "ladder" (deterministic-check repairs, phase A) and "response" (post-verify judge
    responses, phase C). Outcomes: accepted / no-improvement / introduced / unusable /
    exhausted / rejected."""

    def word_count(self) -> int:
        return len(self.text.split())

    def tail(self, words: int = 150) -> str:
        """The chunk-buffer prefix for the next scene's brief (RESEARCH.md section 5)."""
        parts = self.text.split()
        return " ".join(parts[-words:]) if parts else ""
