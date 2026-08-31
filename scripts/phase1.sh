#!/usr/bin/env bash
# Phase 1 of docs/PLAN.md: confirm or delete the mechanisms that have machinery and no evidence.
#
# Runs unattended, in order, after the noise-floor set finishes. Each condition is the same plan
# and the same code with exactly one switch flipped, which is the only design that can separate
# a mechanism from the sampling — and the reason the switches were built first.
#
# About twelve GPU-hours end to end. Every `replicate` invocation resumes rather than restarts,
# so an interruption costs the current scene and nothing else; re-running this script after a
# reboot picks up where it stopped.
set -u

cd "$(dirname "$0")/.." || exit 1
mkdir -p logs

# Wait for the floor set. Polling a directory rather than a PID so this survives the floor run
# being restarted by hand, which is the likely way it gets interrupted.
echo "[$(date +%H:%M)] waiting for the noise-floor set to finish"
while true; do
    done_runs=0
    for i in 1 2 3 4; do
        n=$(ls "runs/current-floor$i/scenes"/*.txt 2>/dev/null | wc -l)
        [ "$n" -ge 71 ] && done_runs=$((done_runs + 1))
    done
    [ "$done_runs" -ge 4 ] && break
    sleep 300
done
echo "[$(date +%H:%M)] floor set complete"

# The control and the ablations must differ by the switch and nothing else, and they are written
# hours apart by two different processes — so the code the floor set ran has to still be the code
# the ablations will run. A long session that improves the writer between them silently turns a
# one-variable experiment into a two-variable one, and the arithmetic cannot tell.
#
# FLOOR_COMMIT is the revision the floor set was generated at. It moved twice on 31 August, both
# times because this guard refused and the floor was regenerated rather than the guard waived.
# Both were the same defect — a model's number used to address a list without checking it
# addresses anything — first in `judge_conflicts` and then, found by grepping for the shape,
# twice more in `check_threads`. The first cost about two GPU-hours; the second cost minutes,
# because the restart had barely begun.
#
# A guard waived the first time it is inconvenient is decoration. The paths below are the write path:
# everything a scene passes through between its brief and its commit. `checks.py` is deliberately
# not in the list because it changes constantly for reporting reasons; it was verified separately
# by AST-diffing every function, which found only manuscript_measures, describe_difference and
# audit_plan changed, none of them a scene-level check.
FLOOR_COMMIT=d5058fa
WRITE_PATH="redthread/pipeline.py redthread/brief.py redthread/verify.py redthread/llm.py redthread/schedule.py"
if ! git diff --quiet "$FLOOR_COMMIT..HEAD" -- $WRITE_PATH; then
    echo "[$(date +%H:%M)] REFUSING TO RUN."
    echo "  The write path has changed since the floor set was generated at $FLOOR_COMMIT:"
    git diff --stat "$FLOOR_COMMIT..HEAD" -- $WRITE_PATH | sed 's/^/    /'
    echo "  The ablations would differ from their control by more than the switch."
    echo "  Regenerate the floor set at HEAD, or check out $FLOOR_COMMIT to run these."
    exit 1
fi
echo "[$(date +%H:%M)] write path unchanged since $FLOOR_COMMIT — the switch is the only variable"

# Step 5. Kill criterion: repetition concentration inside the floor means the refrain feedback is
# prompt weight with no return, and it comes out.
echo "[$(date +%H:%M)] step 5 — refrain feedback ablated"
python -m redthread replicate runs/current --runs 2 --label norefrain \
    --no-refrain-feedback --local qwen3:8b --quiet >> logs/phase1-norefrain.log 2>&1

# Step 6. Kill criterion: mean gesture rate inside the 31% floor. Mean across runs, never the
# first-fire scene, which is a maximum in disguise.
echo "[$(date +%H:%M)] step 6 — gesture feedback ablated"
python -m redthread replicate runs/current --runs 2 --label nogesture \
    --no-gesture-feedback --local qwen3:8b --quiet >> logs/phase1-nogesture.log 2>&1

echo "[$(date +%H:%M)] both ablations written. Compare with:"
echo "  python -m redthread measures runs/current-floor1 runs/current-floor2 \\"
echo "      runs/current-floor3 runs/current-floor4 --label control \\"
echo "      --against runs/current-norefrain1 runs/current-norefrain2 \\"
echo "      --against-label 'refrain feedback off'"
