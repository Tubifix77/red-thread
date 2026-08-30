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
