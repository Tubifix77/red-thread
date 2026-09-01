"""Did two revisions write prose the same way?

`scripts/phase1.sh` guards the write path by git-diffing five files. That leaves a hole:
`checks.py` is deliberately excluded, because it changes constantly for reporting reasons — and
it also contains every scene-level check, which drives candidate selection and every repair. A
change there moves the writer without tripping the guard.

Closing it by diffing the whole file would make the guard fire on every measurement tweak, which
is how guards get switched off. So this compares the *scene-check surface* instead: `run_all` and
every function it calls, by AST, ignoring docstrings and comments.

It also compares **what is on disk**, not only what is in git. `git diff revision..HEAD` and
`git show HEAD:path` both describe committed history; the writer imports the working tree. An
uncommitted edit to `pipeline.py` therefore used to pass every guard this project had while
changing every scene it wrote — verified by probe, 1 September 2026, before it cost anything.

Used before a chain by `scripts/phase8.sh` and after the fact by `scripts/phase1-report.sh`, so
a comparison states whether its conditions actually shared a writer rather than assuming it.
Exit 0 if they did.

    python scripts/same_code.py <revision>
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

WRITE_PATH = ["redthread/pipeline.py", "redthread/brief.py", "redthread/verify.py",
              "redthread/llm.py", "redthread/schedule.py"]


def _source_at(revision: str, path: str) -> str:
    """The file as of a revision, decoded as UTF-8.

    The encoding is explicit because the default on Windows is cp1252, and this project's source
    is full of em-dashes. Without it `git show` raised inside subprocess's reader thread and the
    checker reported "the writer is NOT the same" — a decode failure presented as a code change.
    A guard that cries wolf is a guard that gets switched off, so a read failure is now
    distinguished from a difference.
    """
    result = subprocess.run(["git", "show", f"{revision}:{path}"],
                            capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    return result.stdout if result.returncode == 0 else ""


def _source_on_disk(path: str) -> str:
    """The file as the interpreter will actually import it.

    **This is the fix for a hole that existed for the whole of phase 1.** Every comparison here
    used to be `git show revision:path` against `git show HEAD:path` — two versions out of git,
    neither of them the one that runs. An uncommitted edit to `pipeline.py` is executed by the
    writer and is invisible to both that diff and the commit-range diff in the chain scripts, so
    the guard printed "the writer is unchanged" over a modified writer. Verified by probe on
    1 September 2026 before it cost anything.

    A guard that reads a different artefact than the one under test is the same defect as a
    check over a scheduler-guaranteed field (rule IV): it confirms something, just not the thing
    its name claims.
    """
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _working_tree_is_dirty(paths: list[str]) -> list[str]:
    """Which of `paths` differ from HEAD on disk right now."""
    result = subprocess.run(["git", "status", "--porcelain", "--"] + paths,
                            capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    return [line[3:].strip() for line in result.stdout.splitlines() if line.strip()]


def _functions(source: str) -> dict[str, str]:
    """Every top-level function, normalised: docstrings and comments dropped.

    Comparing `ast.unparse` output rather than text is what lets a comment be rewritten — which
    happens constantly in this project — without reading as a behaviour change.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    out: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        clone = ast.parse(ast.unparse(node)).body[0]
        body = clone.body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            clone.body = body[1:] or [ast.Pass()]
        out[node.name] = ast.dump(clone)
    return out


def _scene_check_surface(source: str) -> set[str]:
    """`run_all` plus every function it calls, transitively within the module."""
    functions = _functions(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    calls: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            calls[node.name] = {
                n.func.id for n in ast.walk(node)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    surface, stack = set(), ["run_all"]
    while stack:
        name = stack.pop()
        if name in surface or name not in functions:
            continue
        surface.add(name)
        stack.extend(calls.get(name, ()))
    return surface


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    revision = argv[1]

    problems: list[str] = []
    for path in WRITE_PATH:
        # `git diff revision..HEAD` compares two commits and cannot see the working tree, so the
        # committed comparison and the on-disk one are both required. Only the second describes
        # the code that will actually run.
        diff = subprocess.run(["git", "diff", "--quiet", f"{revision}..HEAD", "--", path])
        if diff.returncode != 0:
            problems.append(f"{path} changed (committed)")
        if _source_at(revision, path) != _source_on_disk(path):
            problems.append(f"{path} differs ON DISK from {revision} — this is what would run")

    for path in _working_tree_is_dirty(WRITE_PATH + ["redthread/checks.py"]):
        problems.append(f"{path} has uncommitted changes")

    old, new = (_source_at(revision, "redthread/checks.py"),
                _source_on_disk("redthread/checks.py"))
    if not old or not new:
        problems.append("could not read checks.py at one of the revisions")
    else:
        surface = _scene_check_surface(old) | _scene_check_surface(new)
        old_fns, new_fns = _functions(old), _functions(new)
        for name in sorted(surface):
            if old_fns.get(name) != new_fns.get(name):
                problems.append(f"checks.{name} changed (scene-check surface)")

    if problems:
        print(f"The writer is NOT the same as at {revision}:")
        for problem in problems:
            print(f"  {problem}")
        print("\nAny comparison spanning these revisions differs by more than its switch.")
        return 1

    print(f"The writer is unchanged since {revision}: write path identical on disk and in git, "
          f"no uncommitted changes, and every function reachable from checks.run_all is "
          f"identical by AST.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
