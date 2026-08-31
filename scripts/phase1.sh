#!/usr/bin/env bash
# Phase 0 step 2 and phase 1 of docs/PLAN.md, end to end and unattended:
#
#     the four-run noise floor  ->  refrain feedback ablated  ->  gesture feedback ablated
#
# Each condition is the same plan and the same code with exactly one switch flipped, which is the
# only design that can separate a mechanism from the sampling — and the reason the switches were
# built before any of the mechanisms were evaluated.
#
# **The floor now runs inside this script rather than being waited for.** The first version polled
# for 4 x 71 scenes and hung for four hours after the set had finished, because two runs halted at
# 44 and 22 and the count it wanted never arrived. A halt is a normal outcome — `write_all` stops
# on a scene it cannot commit rather than writing later scenes against an incomplete ledger — and
# `replicate` now measures the common prefix, so a short run still yields a usable floor.
#
# Running both stages here also makes the shared-code property structural instead of checked. The
# guard below is kept as a belt-and-braces test that nothing was committed to the write path
# mid-run; it is no longer the thing the design rests on.
#
# About ten GPU-hours. Every `replicate` call resumes rather than restarts, so an interruption
# costs the current scene and re-running this script picks up where it stopped.
set -u

cd "$(dirname "$0")/.." || exit 1
mkdir -p logs

START_COMMIT=$(git rev-parse --short HEAD)
WRITE_PATH="redthread/pipeline.py redthread/brief.py redthread/verify.py redthread/llm.py redthread/schedule.py"

echo "[$(date +%H:%M)] phase 1 starting at $START_COMMIT"

# ---------------------------------------------------------------- step 2: the floor
echo "[$(date +%H:%M)] step 2 — four replicates, nothing ablated"
python -u -m redthread replicate runs/current --runs 4 --label floor \
    --local qwen3:8b --quiet >> logs/floor-n4.log 2>&1

for i in 1 2 3 4; do
    printf '  floor%s: %s scenes\n' "$i" "$(ls runs/current-floor$i/scenes/*.txt 2>/dev/null | wc -l)"
done

# ---------------------------------------------------------------- the guard
# A control and an ablation written hours apart must differ by the switch and nothing else. This
# refused twice on 31 August and the floor was regenerated both times rather than the guard
# waived — the same defect each time, a model's number used to address a list without checking it
# addresses anything. A guard waived the first time it is inconvenient is decoration.
#
# `checks.py` is deliberately not in WRITE_PATH: it changes constantly for reporting reasons, and
# the scene-level half of it was verified separately by AST-diffing every function.
if ! git diff --quiet "$START_COMMIT..HEAD" -- $WRITE_PATH; then
    echo "[$(date +%H:%M)] REFUSING TO CONTINUE."
    echo "  The write path changed while the floor was being written:"
    git diff --stat "$START_COMMIT..HEAD" -- $WRITE_PATH | sed 's/^/    /'
    echo "  The ablations would differ from their control by more than the switch."
    exit 1
fi
echo "[$(date +%H:%M)] write path unchanged since $START_COMMIT — the switch is the only variable"

# ---------------------------------------------------------------- step 5: refrain feedback
# Kill criterion: repetition concentration inside the floor means the feedback is prompt weight
# with no return, and it comes out.
echo "[$(date +%H:%M)] step 5 — refrain feedback ablated"
python -u -m redthread replicate runs/current --runs 2 --label norefrain \
    --no-refrain-feedback --local qwen3:8b --quiet >> logs/phase1-norefrain.log 2>&1

# ---------------------------------------------------------------- step 6: gesture feedback
# Kill criterion: mean gesture rate inside the floor. Mean across runs, never the first-fire
# scene, which is a maximum in disguise.
echo "[$(date +%H:%M)] step 6 — gesture feedback ablated"
python -u -m redthread replicate runs/current --runs 2 --label nogesture \
    --no-gesture-feedback --local qwen3:8b --quiet >> logs/phase1-nogesture.log 2>&1

echo "[$(date +%H:%M)] all conditions written. Read them out with:"
echo "    bash scripts/phase1-report.sh"
