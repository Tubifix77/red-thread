#!/usr/bin/env bash
# Everything left that needs the GPU, in order, unattended:
#
#     step 25   the panel on a premise never written    (waits for the run already in flight)
#     step 6    two more gesture ablations, n=2 -> n=4
#
# Sequential rather than parallel: two writers on one card halve each other's rate and neither
# finishes sooner.
set -u
cd "$(dirname "$0")/.." || exit 1

echo "[$(date +%H:%M)] waiting for step 25"
while ! grep -q "the panel, with the floor" logs/step25-chain.log 2>/dev/null; do sleep 120; done
echo "[$(date +%H:%M)] step 25 done"

bash scripts/step6-retest.sh
echo "[$(date +%H:%M)] overnight queue empty"
