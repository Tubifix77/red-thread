#!/usr/bin/env bash
# Step 28's re-test: the model-refrain ablation from n=2 to n=4.
#
# The criterion fired at n=2 and is recorded as having fired
# (docs/evidence/step28-model-refrains.md). The deletion is suspended because the miss was 0.34
# phrase occurrences across 121,536 words, and because a design with 4 control runs against 2
# ablated cannot reach p<0.05 on a rank test even with perfect separation — which is what it got.
# Step 6 set the precedent: deleting is cheap later, reversing a published deletion is not.
#
# What n=4 decides was written down before these runs existed. Read it there, not here.
#
# This waits for scripts/phase8.sh to finish rather than competing with it for the GPU. Its
# completion signal is logs/phase8-report.txt, which phase8.sh writes through `tee` as its last
# act. Waiting on an artefact the other script actually produces is deliberate: an earlier
# version of the phase 1 chain polled for a scene count that never arrived and hung for four
# hours after the work had finished.
#
# ~2 GPU-hours. `replicate` resumes, so runs 1 and 2 are skipped and only 3 and 4 are written.
set -u

cd "$(dirname "$0")/.." || exit 1
mkdir -p logs

SIGNAL=logs/phase8-report.txt
WAITED=0
while [ ! -f "$SIGNAL" ]; do
    if [ "$WAITED" -ge 14400 ]; then
        echo "[$(date +%H:%M)] gave up waiting for $SIGNAL after four hours."
        echo "  phase8.sh has not finished. Not starting: two chains on one GPU is slower than"
        echo "  one, and the guard below would be checked at the wrong moment."
        exit 1
    fi
    sleep 60
    WAITED=$((WAITED + 60))
done
echo "[$(date +%H:%M)] phase8.sh finished; starting the step 28 re-test"

# The same guard, re-checked. The first chain verified the writer at launch; this one starts
# hours later, and the whole point of the re-test is that its runs are comparable to the runs
# already on disk. A guard that is checked once at the start of a night is a guard that does not
# cover the end of it.
MARKER=runs/.floor-commit
[ -f "$MARKER" ] || { echo "No $MARKER — nothing to compare against."; exit 1; }
FLOOR_COMMIT=$(cat "$MARKER")
python scripts/same_code.py "$FLOOR_COMMIT" || {
    echo "[$(date +%H:%M)] REFUSING: the writer changed since the floor at $FLOOR_COMMIT."
    echo "  Runs 3 and 4 would differ from runs 1 and 2 by more than the switch, which would"
    echo "  make the n=4 set incomparable with itself."
    exit 1
}

echo "[$(date +%H:%M)] step 28 re-test — model-refrain ablation to n=4"
python -u -m redthread replicate runs/current --runs 4 --label nomodelrefrains \
    --no-model-refrains --local qwen3:8b --quiet >> logs/phase8b-nomodelrefrains.log 2>&1

echo "[$(date +%H:%M)] written. The two pre-registered statistics, in order:"
{
    echo "=== primary: the panel, against its kill criterion ==="
    python -m redthread measures \
        runs/current-floor1 runs/current-floor2 runs/current-floor3 runs/current-floor4 \
        --label "control (list on)" \
        --against runs/current-nomodelrefrains1 runs/current-nomodelrefrains2 \
                  runs/current-nomodelrefrains3 runs/current-nomodelrefrains4 \
        --against-label "model refrains OFF, n=4"
    echo
    echo "=== secondary: the targeted three-phrase rate ==="
    python scripts/model_refrain_rate.py \
        runs/current-floor1 runs/current-floor2 runs/current-floor3 runs/current-floor4 \
        --against runs/current-nomodelrefrains1 runs/current-nomodelrefrains2 \
                  runs/current-nomodelrefrains3 runs/current-nomodelrefrains4
} | tee logs/phase8b-report.txt
echo "Report saved to logs/phase8b-report.txt"
