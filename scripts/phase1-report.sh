#!/usr/bin/env bash
# Steps 5 and 6 of docs/PLAN.md, read out against their own kill criteria.
#
# Run this once scripts/phase1.sh has finished. It compares each ablation pair against the
# four-run control and prints the verdicts, so the conclusion does not depend on whoever is
# reading the tables remembering what the criteria were.
#
#   step 5  refrain feedback.  Kill if concentration sits inside the floor: the feedback is
#           prompt weight with no return, and it comes out.
#   step 6  gesture feedback.  Kill if the mean gesture rate sits inside the floor. Mean across
#           runs, never the first-fire scene, which is a maximum in disguise.
#
# Neither verdict may be read off `worst_refrain`. It swings 45% between identical runs and was,
# before anyone measured that, the statistic this project quoted most.
set -u
cd "$(dirname "$0")/.." || exit 1

CONTROL="runs/current-floor1 runs/current-floor2 runs/current-floor3 runs/current-floor4"

have() { [ -d "$1" ] && [ "$(ls "$1/scenes"/*.txt 2>/dev/null | wc -l)" -gt 0 ]; }

present=""
for d in $CONTROL; do have "$d" && present="$present $d"; done
if [ -z "$present" ]; then
    echo "No control runs yet. Run scripts/phase1.sh first."
    exit 1
fi
echo "Control: $present"

for pair in "norefrain:refrain feedback off:step 5" "nogesture:gesture feedback off:step 6"; do
    label="${pair%%:*}"; rest="${pair#*:}"; name="${rest%%:*}"; step="${rest##*:}"
    runs=""
    for i in 1 2; do have "runs/current-$label$i" && runs="$runs runs/current-$label$i"; done
    if [ -z "$runs" ]; then
        echo
        echo "=== $step — not run yet ($label) ==="
        continue
    fi
    echo
    echo "=================================================================="
    echo "  $step — $name"
    echo "=================================================================="
    python -m redthread measures $present --label "control (feedback on)" \
        --against $runs --against-label "$name"
done

echo
echo "Reading these: a measure that clears the floor is evidence the mechanism does something."
echo "A measure inside it is not evidence that the mechanism does nothing — it is evidence this"
echo "instrument cannot tell. The kill criteria are written against the first reading, so a"
echo "mechanism whose measures all sit inside the floor comes out for lack of a reason to stay,"
echo "not because it was shown to be useless."
