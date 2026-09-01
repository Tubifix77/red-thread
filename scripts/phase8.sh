#!/usr/bin/env bash
# Phase 8 of docs/PLAN2.md, end to end and unattended:
#
#     step 28  model-refrain list ablated (2 runs, 71 scenes each)
#     step 30  premise-B floor extended to n=4 (+2 runs, 24 scenes each)
#
# ~4 GPU-hours. Step 29's prose stage is deliberately NOT here: it is gated on its deterministic
# stage-1 count, which costs nothing and runs off-GPU first.
#
# THE ORDERING THIS SCRIPT EXISTS TO PROTECT (PLAN2, "the one hard ordering"): every run below is
# compared against runs written at the floor commit, so the write path must still be at that
# revision. The guard refuses rather than warns — phase 1's guard refused three times and was
# right each time. After this chain finishes, the write path is free for step 31's
# instrumentation, and these comparisons close forever.
#
# Every `replicate` call resumes rather than restarts: an interruption costs the current scene,
# and re-running this script picks up where it stopped.
set -u

cd "$(dirname "$0")/.." || exit 1
mkdir -p logs

MARKER=runs/.floor-commit
if [ ! -f "$MARKER" ]; then
    echo "No $MARKER — the floor's revision is unknown, so nothing can be compared to it."
    exit 1
fi
FLOOR_COMMIT=$(cat "$MARKER")

# Belt and braces, same as phase 1: the diff catches write-path commits, the AST check catches
# scene-check drift in checks.py (which the diff deliberately ignores).
WRITE_PATH="redthread/pipeline.py redthread/brief.py redthread/verify.py redthread/llm.py redthread/schedule.py"
if ! git diff --quiet "$FLOOR_COMMIT..HEAD" -- $WRITE_PATH; then
    echo "[$(date +%H:%M)] REFUSING TO CONTINUE."
    echo "  The write path changed since the floor at $FLOOR_COMMIT:"
    git diff --stat "$FLOOR_COMMIT..HEAD" -- $WRITE_PATH | sed 's/^/    /'
    echo "  These runs would differ from their controls by more than the switch."
    exit 1
fi
python scripts/same_code.py "$FLOOR_COMMIT" || exit 1
echo "[$(date +%H:%M)] writer unchanged since $FLOOR_COMMIT — the switch is the only variable"

# ---------------------------------------------------------------- step 28: model-refrain list
# Kill criterion (pre-registered in PLAN2): duplication_manuscript AND repetition_concentration
# both inside their floors -> the list is prompt weight and comes out of the brief.
echo "[$(date +%H:%M)] step 28 — model-refrain list ablated"
python -u -m redthread replicate runs/current --runs 2 --label nomodelrefrains \
    --no-model-refrains --local qwen3:8b --quiet >> logs/phase8-nomodelrefrains.log 2>&1

# ---------------------------------------------------------------- step 30: premise-B floor n=4
# --runs 4 resumes past the two step-25 panels and writes panel3, panel4.
echo "[$(date +%H:%M)] step 30 — premise-B floor to n=4"
python -u -m redthread replicate runs/solo-b2 --runs 4 --label panel \
    --local qwen3:8b --quiet >> logs/phase8-panel.log 2>&1

# ---------------------------------------------------------------- read-out
echo "[$(date +%H:%M)] all conditions written."
{
    echo "=== step 28 — model-refrain list, against its kill criterion ==="
    python -m redthread measures \
        runs/current-floor1 runs/current-floor2 runs/current-floor3 runs/current-floor4 \
        --label "control (list on)" \
        --against runs/current-nomodelrefrains1 runs/current-nomodelrefrains2 \
        --against-label "model refrains off"
    echo
    echo "=== step 30 — the premise-B floor at n=4 (paste nothing; re-run step 26 with it) ==="
    python -m redthread measures runs/solo-b2-panel1 runs/solo-b2-panel2 \
        runs/solo-b2-panel3 runs/solo-b2-panel4 --label "Ink of the Drowned, n=4" --emit-floor
} | tee logs/phase8-report.txt
echo "Report saved to logs/phase8-report.txt"
