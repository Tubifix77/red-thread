"""Project state on disk.

Plain files, one concern per file, all human-readable and diffable. The manuscript is not the
source of truth — the spec plus the ledger is — so prose lives in its own directory and can be
regenerated from state.

Layout:

    <run>/
      story.json          static memory: premise, world rules, characters, threads, style
      plan.json           the spec tree: list of SceneSpec
      ledger.json         dynamic memory: facts + thread move history
      scenes/0001.txt     committed prose, one file per scene
      scenes/0001.json    per-scene record: violations, attempts, extracted facts
      manuscript.md       assembled output, regenerated on demand

Keeping prose in numbered text files rather than one blob means `git diff` on a repaired scene
shows the repair, not a whole-manuscript reflow.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .ledger import Ledger
from .models import (Fact, FactKind, Scene, SceneSpec, StorySpec, ThreadMove,
                     Violation, _from_jsonable, _to_jsonable)


class Project:
    def __init__(self, root: Path, story: StorySpec,
                 plan: list[SceneSpec] | None = None,
                 ledger: Ledger | None = None,
                 history: list[ThreadMove] | None = None) -> None:
        self.root = Path(root)
        self.story = story
        self.plan: list[SceneSpec] = plan or []
        self.ledger = ledger or Ledger()
        self.history: list[ThreadMove] = history or []
        self._scenes: dict[str, Scene] = {}

    # ------------------------------------------------------------------ paths

    @property
    def scenes_dir(self) -> Path:
        return self.root / "scenes"

    def _scene_stem(self, spec: SceneSpec) -> Path:
        return self.scenes_dir / f"{spec.index:04d}"

    # ------------------------------------------------------------------ io

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.scenes_dir.mkdir(exist_ok=True)

        (self.root / "story.json").write_text(self.story.to_json(), encoding="utf-8")
        (self.root / "plan.json").write_text(
            json.dumps([_to_jsonable(s) for s in self.plan], indent=2, ensure_ascii=False),
            encoding="utf-8")
        (self.root / "ledger.json").write_text(
            json.dumps({
                "facts": [_to_jsonable(f) for f in self.ledger.facts],
                "history": [asdict(m) for m in self.history],
            }, indent=2, ensure_ascii=False),
            encoding="utf-8")

        for scene in self._scenes.values():
            spec = self.spec(scene.spec_id)
            if spec is None:
                continue
            stem = self._scene_stem(spec)
            stem.with_suffix(".txt").write_text(scene.text, encoding="utf-8")
            stem.with_suffix(".json").write_text(json.dumps({
                "spec_id": scene.spec_id,
                "index": scene.index,
                "committed": scene.committed,
                "attempts": scene.attempts,
                "candidates_drafted": scene.candidates_drafted,
                "repairs": scene.repairs,
                "repair_log": scene.repair_log,
                "word_count": scene.word_count(),
                "facts": [_to_jsonable(f) for f in scene.facts],
                "violations": [_to_jsonable(v) for v in scene.violations],
            }, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, root: Path) -> "Project":
        root = Path(root)
        story = StorySpec.from_json((root / "story.json").read_text(encoding="utf-8"))

        plan: list[SceneSpec] = []
        plan_file = root / "plan.json"
        if plan_file.exists():
            plan = [_from_jsonable(SceneSpec, d)
                    for d in json.loads(plan_file.read_text(encoding="utf-8"))]

        facts: list[Fact] = []
        history: list[ThreadMove] = []
        ledger_file = root / "ledger.json"
        if ledger_file.exists():
            raw = json.loads(ledger_file.read_text(encoding="utf-8"))
            facts = [_from_jsonable(Fact, d) for d in raw.get("facts", [])]
            history = [ThreadMove(**d) for d in raw.get("history", [])]

        project = cls(root, story, plan, Ledger(facts), history)

        for spec in plan:
            stem = project._scene_stem(spec)
            txt, meta = stem.with_suffix(".txt"), stem.with_suffix(".json")
            if not txt.exists():
                continue
            scene = Scene(spec_id=spec.id, index=spec.index,
                          text=txt.read_text(encoding="utf-8"))
            if meta.exists():
                m = json.loads(meta.read_text(encoding="utf-8"))
                scene.committed = m.get("committed", False)
                scene.attempts = m.get("attempts", 0)
                # Absent in every record written before step 31 (2 September 2026); the defaults
                # mean "not recorded", never "zero repairs" — 1,631 records predate these fields
                # and the backfill treats them by era, not by default value.
                scene.candidates_drafted = m.get("candidates_drafted", 0)
                scene.repairs = m.get("repairs", 0)
                scene.repair_log = m.get("repair_log", [])
                scene.facts = [_from_jsonable(Fact, d) for d in m.get("facts", [])]
                scene.violations = [_from_jsonable(Violation, d)
                                    for d in m.get("violations", [])]
            project._scenes[spec.id] = scene

        return project

    # ------------------------------------------------------------------ access

    def spec(self, spec_id: str) -> SceneSpec | None:
        return next((s for s in self.plan if s.id == spec_id), None)

    def spec_at(self, index: int) -> SceneSpec | None:
        return next((s for s in self.plan if s.index == index), None)

    def scene(self, spec_id: str) -> Scene | None:
        return self._scenes.get(spec_id)

    def put_scene(self, scene: Scene) -> None:
        self._scenes[scene.spec_id] = scene

    def committed_scenes(self) -> list[Scene]:
        out = [s for s in self._scenes.values() if s.committed]
        out.sort(key=lambda s: s.index)
        return out

    def committed_texts(self, before: int | None = None) -> list[str]:
        return [s.text for s in self.committed_scenes()
                if before is None or s.index < before]

    def previous_committed(self, index: int) -> Scene | None:
        earlier = [s for s in self.committed_scenes() if s.index < index]
        return earlier[-1] if earlier else None

    # ------------------------------------------------------------------ commit gate

    def commit(self, scene: Scene) -> None:
        """Write a passing scene into dynamic memory.

        ConWriter updates dynamic memory only after a scene passes its consistency checks
        (docs/RESEARCH.md section 4). This method is the only path by which facts and thread
        state may change, which is what makes that guarantee enforceable rather than aspirational.
        """
        spec = self.spec(scene.spec_id)
        if spec is None:
            raise KeyError(f"no spec for scene {scene.spec_id}")

        self.ledger.drop_scene(scene.index)
        self.ledger.extend(scene.facts)

        for tid, op in spec.thread_ops.items():
            if not op.to_state:
                continue
            thread = self.story.thread(tid)
            if thread is None or thread.current_state == op.to_state:
                continue
            self.history.append(ThreadMove(tid, thread.current_state, op.to_state, scene.index))
            thread.current_state = op.to_state

        scene.committed = True
        self.put_scene(scene)

    def rollback(self, scene: Scene) -> None:
        self.ledger.drop_scene(scene.index)
        scene.committed = False
        scene.facts = []

    # ------------------------------------------------------------------ output

    def manuscript(self) -> str:
        chunks: list[str] = [f"# {self.story.title}\n"]
        chapter = None
        for scene in self.committed_scenes():
            spec = self.spec(scene.spec_id)
            if spec and spec.chapter != chapter:
                chapter = spec.chapter
                chunks.append(f"\n## {chapter}\n")
            chunks.append(scene.text.strip())
            chunks.append("\n* * *\n")
        if chunks and chunks[-1].strip() == "* * *":
            chunks.pop()
        return "\n".join(chunks)

    def write_manuscript(self) -> Path:
        path = self.root / "manuscript.md"
        path.write_text(self.manuscript(), encoding="utf-8")
        return path

    # ------------------------------------------------------------------ stats

    def status(self) -> dict:
        written = self.committed_scenes()
        return {
            "title": self.story.title,
            "scenes_planned": len(self.plan),
            "scenes_committed": len(written),
            "words": sum(s.word_count() for s in written),
            "facts": len(self.ledger.facts),
            "threads_resolved": sum(1 for t in self.story.threads if t.is_resolved()),
            "threads_total": len(self.story.threads),
            "knowledge_facts": sum(1 for f in self.ledger.facts
                                   if f.kind is FactKind.KNOWLEDGE),
        }
