#!/usr/bin/env bash
# Steps 7, 8 and 16 of docs/PLAN.md — the plan-level half, which is far cheaper than the
# book-level half and answers three questions at once.
#
# Six plans of one premise and six of another, all with `--no-repeople` so what is measured is
# the planner's *raw* solo rate rather than the rate after the pass that exists to fix it.
# Six plans of one premise already gave 5, 5, 22, 24, 10 and 28 solo scenes; if the split
# persists on a second premise it is the planner, and if one premise clusters low and the other
# high it is the story asking for solitude.
#
# Every plan generated here also carries `depends_on`, which no plan on disk has, so this is
# also what unblocks step 16.
set -u

cd "$(dirname "$0")/.." || exit 1
mkdir -p logs runs

PREMISE_A="A harbour inspector finds the printed tide tables have been altered, and the only press that could have set them is two days away."
PREMISE_B="A night nurse on a geriatric ward keeps finding a dead patient's handwriting on the new charts, and the ward's records were destroyed in a flood nobody will discuss."

run_plan() {
    local out="$1" premise="$2" seed="$3"
    if [ -f "$out/plan.json" ]; then
        echo "[$(date +%H:%M)] $out exists, skipping"
        return
    fi
    echo "[$(date +%H:%M)] $out"
    python -u -m redthread plan "$premise" --out "$out" --words 20000 --seed "$seed" \
        --no-repeople --local qwen3:8b --quiet >> "logs/plans.log" 2>&1
}

for i in 1 2 3 4 5 6; do run_plan "runs/solo-a$i" "$PREMISE_A" "$i"; done
for i in 1 2 3 4 5 6; do run_plan "runs/solo-b$i" "$PREMISE_B" "$i"; done

echo "[$(date +%H:%M)] done. Solo share and declared dependencies:"
python -u - <<'PY'
import json
import pathlib
import sys

sys.path.insert(0, ".")
from redthread import checks
from redthread.models import SceneSpec, _from_jsonable

print(f"  {'plan':<12}{'scenes':>7}{'solo':>6}{'solo %':>8}{'edges':>7}{'ending reach':>14}")
for group in ("a", "b"):
    for i in range(1, 7):
        path = pathlib.Path(f"runs/solo-{group}{i}/plan.json")
        if not path.exists():
            continue
        plan = [_from_jsonable(SceneSpec, d)
                for d in json.loads(path.read_text(encoding="utf-8"))]
        solo = sum(1 for s in plan if len(s.characters) < 2)
        edges = sum(len(s.depends_on) for s in plan)
        print(f"  solo-{group}{i:<7}{len(plan):>7}{solo:>6}{solo / max(1, len(plan)):>8.0%}"
              f"{edges:>7}{checks.ending_reach(plan):>13.0%}")
PY
