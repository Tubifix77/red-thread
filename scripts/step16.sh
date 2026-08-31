#!/usr/bin/env bash
# Step 16 of docs/PLAN.md: does a declared dependency leave any trace in the prose?
#
# Needs a book written from a plan that carries `depends_on`, and no book on disk does — the
# field postdates every finished run. This writes one from `solo-a4`, chosen before it was
# written and for stated reasons: 4% solo, 96% ending reach and 1.5 declared edges per scene,
# which is the densest and most connected of the six generated for step 8. If a declared
# dependency leaves no trace *there*, it leaves none anywhere.
#
# Twenty-four scenes rather than seventy-one. The question is whether an edge shows up between
# two scenes, which does not need a novel's length, and the GPU is already carrying the noise
# floor.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs

PLAN=runs/solo-a4
BOOK=runs/deps-book

echo "[$(date +%H:%M)] waiting for the twelve plans"
while [ "$(ls -d runs/solo-a? runs/solo-b? 2>/dev/null | wc -l)" -lt 12 ]; do sleep 120; done

if [ ! -f "$BOOK/story.json" ]; then
    echo "[$(date +%H:%M)] copying $PLAN to $BOOK"
    python - <<PY
from pathlib import Path
from redthread.project import Project
from redthread.replicate import fresh_copy
fresh_copy(Project.load(Path("$PLAN")), Path("$BOOK"))
print("copied")
PY
fi

echo "[$(date +%H:%M)] writing $BOOK"
python -u -m redthread write "$BOOK" --local qwen3:8b --quiet >> logs/step16.log 2>&1

echo "[$(date +%H:%M)] done. Step 16:"
python -m redthread depends "$BOOK" --prose
