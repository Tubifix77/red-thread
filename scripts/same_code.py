"""Did two revisions write prose the same way?

`scripts/phase1.sh` guards the write path by git-diffing five files. That leaves a hole:
`checks.py` is deliberately excluded, because it changes constantly for reporting reasons — and
it also contains every scene-level check, which drives candidate selection and every repair. A
change there moves the writer without tripping the guard.

Closing it by diffing the whole file would make the guard fire on every measurement tweak, which
is how guards get switched off. So this compares the *scene-check surface* instead: `run_all` and
every function it calls, by AST, ignoring docstrings and comments.

Used after the fact by `scripts/phase1-report.sh`, so a comparison states whether its conditions
actually shared a writer rather than assuming it. Exit 0 if they did.

    python scripts/same_code.py <revision>
"""

from __future__ import annotations

import ast
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
        diff = subprocess.run(["git", "diff", "--quiet", f"{revision}..HEAD", "--", path])
        if diff.returncode != 0:
            problems.append(f"{path} changed")

    old, new = (_source_at(revision, "redthread/checks.py"),
                _source_at("HEAD", "redthread/checks.py"))
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

    print(f"The writer is unchanged since {revision}: write path identical, and every function "
          f"reachable from checks.run_all is identical by AST.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
