"""red-thread — orchestrated long-form fiction.

The artifact this package produces is not prose. It is a spec tree plus a fact ledger; the prose
is a rendering of them. That inversion is the whole design: coherence across a manuscript is a
property of what each small session is handed and what a verifier refuses to accept back, not a
property of the model's context window.

Every architectural decision here traces to a cited source in `docs/RESEARCH.md`.
"""

from .models import (Beat, Character, Fact, FactKind, Scene, SceneSpec, Severity,
                     StorySpec, StyleContract, Thread, ThreadKind, ThreadMove,
                     Transition, Violation)
from .ledger import Ledger
from .project import Project

__version__ = "0.1.0"

__all__ = [
    "Beat", "Character", "Fact", "FactKind", "Ledger", "Project", "Scene", "SceneSpec",
    "Severity", "StorySpec", "StyleContract", "Thread", "ThreadKind", "ThreadMove",
    "Transition", "Violation", "__version__",
]
