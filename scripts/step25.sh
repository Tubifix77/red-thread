#!/usr/bin/env bash
# Step 25 of docs/PLAN.md — the last one: re-run the whole panel on a fresh premise and publish
# the numbers. Two runs, every measure with its floor.
#
# "Whatever it says then is the state of the project — and the first time that sentence will be
# true." The point is that every figure comes from the same panel, at one code revision, with an
# error bar attached, on a book nobody has tuned against.
#
# The premise is fresh to the *prose*: `solo-b2` is a plan of the night-nurse premise generated
# for step 8 and never written into a book. It was chosen on its audit rather than after the fact
# — 0% solo scenes, 91% ending reach — and picking the plan before seeing the prose is the whole
# difference between a report and a selection.
#
# Run this after scripts/phase1.sh, not beside it. Two 20k-word books, about three GPU-hours.
set -u

cd "$(dirname "$0")/.." || exit 1
mkdir -p logs

SOURCE=runs/solo-b2

if [ ! -f "$SOURCE/plan.json" ]; then
    echo "No plan at $SOURCE. Run scripts/phase1-plans.sh first."
    exit 1
fi

echo "[$(date +%H:%M)] step 25 — two runs of a premise never written before"
python -u -m redthread audit "$SOURCE" 2>&1 | head -20

python -u -m redthread replicate "$SOURCE" --runs 2 --label panel \
    --local qwen3:8b --quiet >> logs/step25.log 2>&1

echo
echo "[$(date +%H:%M)] the panel, with the floor phase 1 measured:"
python -m redthread measures runs/solo-b2-panel1 runs/solo-b2-panel2 \
    --label "fresh premise" \
    --against runs/current-floor1 runs/current-floor2 \
              runs/current-floor3 runs/current-floor4 \
    --against-label "The Debt of Years, four replicates"

echo
echo "Read the comparison as two premises, not as an effect: nothing was ablated between them."
echo "What it answers is whether the measures hold their values on a book they were not tuned on."
