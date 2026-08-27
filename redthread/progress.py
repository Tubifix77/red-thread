"""Orchestrator progress reporting.

A real run is long — minutes per scene, hours per manuscript — so the display is line-based
rather than a live-redrawn dashboard. Scrollback is the point: when scene 34 is held back you
want to read what happened at scene 31, and a spinner that overwrote itself has thrown that away.
Output stays useful piped to a file.

Every stage transition is timestamped and costed, because the two questions you actually have
during a run are "where is it" and "what is this costing me".

On glyphs: this module went through one real bug worth recording. `UnicodeEncodeError` subclasses
`ValueError`, so a broad `except ValueError` around the write silently *dropped* every line
containing a block or tick character on a Windows cp1252 console — the progress bars and the
commit ticks vanished with no error. Hence `_Glyphs`: probe the stream's encoding once and fall
back to ASCII rather than emitting bytes the terminal cannot take.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field

from .models import SceneSpec, Severity, StorySpec, Thread


@dataclass(frozen=True)
class _Glyphs:
    full: str
    empty: str
    scene: str
    stage: str
    ok: str
    bad: str

    @classmethod
    def for_stream(cls, stream) -> "_Glyphs":
        unicode_set = cls(full="█", empty="░", scene="▸", stage="·", ok="✓", bad="✗")
        encoding = getattr(stream, "encoding", None) or "ascii"
        try:
            "".join((unicode_set.full, unicode_set.empty, unicode_set.scene,
                     unicode_set.stage, unicode_set.ok, unicode_set.bad)).encode(encoding)
            return unicode_set
        except (LookupError, UnicodeEncodeError):
            return cls(full="#", empty="-", scene=">", stage="*", ok="OK", bad="XX")


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


@dataclass
class Progress:
    """Stage-by-stage reporter. Silent when `quiet`, so tests and scripts stay clean."""

    total_scenes: int = 0
    total_target_words: int = 0
    quiet: bool = False
    stream: object = None

    started: float = field(default_factory=time.monotonic)
    scenes_done: int = 0
    words_done: int = 0
    scenes_held: int = 0
    scene_started: float = 0.0
    _current: SceneSpec | None = None
    _stage_started: float = 0.0
    _glyphs: _Glyphs | None = None

    def __post_init__(self) -> None:
        # Start the stage clock now. It used to be initialised only by `scene_start`, so any
        # caller that reports stages without scenes — the planner does exactly that — measured
        # its first stage against the epoch and printed durations like "359h30m".
        self._stage_started = self.started
        if self.stream is None:
            self.stream = sys.stdout
        # Best effort: prefer UTF-8 so the unicode set survives. If the stream refuses, the
        # glyph probe below picks ASCII instead of writing bytes the terminal cannot take.
        try:
            self.stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
        self._glyphs = _Glyphs.for_stream(self.stream)

    @property
    def g(self) -> _Glyphs:
        return self._glyphs or _Glyphs.for_stream(self.stream)

    # ------------------------------------------------------------------ plumbing

    def _write(self, line: str = "") -> None:
        if self.quiet:
            return
        try:
            self.stream.write(line + "\n")
            self.stream.flush()
        except UnicodeEncodeError:
            # Should not happen after the probe, but never lose a progress line to encoding.
            self.stream.write(line.encode("ascii", "replace").decode("ascii") + "\n")
            self.stream.flush()
        except (ValueError, OSError):
            pass

    def bar(self, fraction: float, width: int = 26) -> str:
        fraction = max(0.0, min(1.0, fraction))
        filled = int(fraction * width)
        return self.g.full * filled + self.g.empty * (width - filled)

    def thread_bar(self, thread: Thread) -> str:
        """A thread's arc as a row of blocks, filled to its current state."""
        total = max(1, len(thread.states) - 1)
        reached = max(0, thread.state_index(thread.current_state))
        return "".join(self.g.full if i <= reached else self.g.empty
                       for i in range(total + 1))

    @classmethod
    def for_project(cls, project, quiet: bool = False) -> "Progress":
        done = project.committed_scenes()
        return cls(
            total_scenes=len(project.plan),
            total_target_words=sum(s.word_target for s in project.plan),
            quiet=quiet,
            scenes_done=len(done),
            words_done=sum(s.word_count() for s in done),
        )

    # ------------------------------------------------------------------ run level

    def run_header(self, story: StorySpec, writer: str, critic: str) -> None:
        self._write()
        self._write(f"  {story.title}")
        self._write(f"  {self.total_scenes} scenes, {self.total_target_words:,} target words")
        self._write(f"  writer: {writer}    critic: {critic}")
        if self.scenes_done:
            self._write(f"  resuming - {self.scenes_done} scene(s) already committed")
        self._write("  " + "-" * 74)

    def overall(self) -> str:
        fraction = self.scenes_done / self.total_scenes if self.total_scenes else 0.0
        return (f"{self.bar(fraction)} {fraction * 100:5.1f}%  "
                f"{self.scenes_done}/{self.total_scenes} scenes, {self.words_done:,} words, "
                f"{_fmt_duration(time.monotonic() - self.started)}")

    # ------------------------------------------------------------------ scene level

    def scene_start(self, spec: SceneSpec, story: StorySpec) -> None:
        self._current = spec
        self.scene_started = time.monotonic()
        self._stage_started = self.scene_started
        pov = story.character(spec.pov)
        self._write()
        self._write(f"  {self.overall()}")
        self._write(f"  {self.g.scene} scene {spec.index:>3}  ch{spec.chapter}  "
                    f"{spec.word_target}w  pov:{pov.name if pov else spec.pov or '?'}  "
                    f"threads:{','.join(spec.thread_ops) or 'none'}")
        if spec.summary:
            self._write(f"      {spec.summary[:72]}")

    def stage(self, name: str, detail: str = "") -> None:
        """One line per stage transition, with how long the previous stage took."""
        now = time.monotonic()
        elapsed = now - self._stage_started
        self._stage_started = now
        tail = f"  {detail}" if detail else ""
        self._write(f"      {self.g.stage} {name:<16} {_fmt_duration(elapsed):>7}{tail}")

    def scene_done(self, result) -> None:
        elapsed = time.monotonic() - self.scene_started
        if result.committed:
            self.scenes_done += 1
            self.words_done += result.scene.word_count()
            mark, verdict = self.g.ok, "committed"
        else:
            self.scenes_held += 1
            mark, verdict = self.g.bad, "HELD BACK"

        self._write(f"      {mark} {verdict} - {result.scene.word_count()} words in "
                    f"{_fmt_duration(elapsed)}, {result.candidates_drafted} draft(s), "
                    f"{result.repairs} repair(s)")

        for note in result.notes:
            self._write(f"          {note}")
        for v in result.violations:
            if v.severity is not Severity.MINOR:
                self._write(f"          [{v.severity.value}] {v.kind}: {v.detail[:88]}")
        minors = sum(1 for v in result.violations if v.severity is Severity.MINOR)
        if minors:
            self._write(f"          ({minors} minor, see scenes/{result.scene.index:04d}.json)")

    # ------------------------------------------------------------------ summary

    def summary(self, story: StorySpec) -> None:
        self._write()
        self._write("  " + "-" * 74)
        self._write(f"  {self.overall()}")
        if self.scenes_held:
            self._write(f"  {self.scenes_held} scene(s) held back - "
                        f"the run halted at the first one")
        self._write()
        self._write("  threads")
        for t in story.threads:
            mark = self.g.ok if t.is_resolved() else " " * len(self.g.ok)
            self._write(f"    [{mark}] {self.thread_bar(t)}  {t.id:<10} "
                        f"{t.current_state:<16} {t.name[:34]}")
        self._write()
