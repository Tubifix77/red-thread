#!/usr/bin/env bash
# Step 6, second half: two more gesture-feedback ablations, taking that side from n=2 to n=4.
#
# The first pair failed the kill criterion the plan named — a whole-book mean gesture rate inside
# the floor — and then turned out to have an effect that statistic cannot see. The mechanism only
# names a movement after it has recurred across four scenes, so its effect grows across a book:
# gesture rate falls 32% from first quarter to last across six feedback-on runs and is flat across
# the two without it.
#
# That is suggestive, post-hoc and n=2. This is its test. If the trajectory difference does not
# survive at n=4, the mechanism goes on the original criterion.
#
# Read out with scripts/phase1-report.sh, which compares against the same four-run floor.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs

MARKER=runs/.floor-commit
[ -f "$MARKER" ] || { echo "No $MARKER — the floor's revision is unknown, so this cannot be
compared against it. Run scripts/phase1.sh first."; exit 1; }
FLOOR_COMMIT=$(cat "$MARKER")

# Same guard as phase1.sh, plus the scene-check surface the git diff cannot see.
python scripts/same_code.py "$FLOOR_COMMIT" || {
    echo "REFUSING: these runs would not be comparable with the floor or the first pair."
    exit 1
}

# `--runs 4` resumes the two that exist rather than rewriting them, which is deliberate and has
# a consequence worth stating: both halted, at 66 and 48 of 71, and resuming retries the scene
# each stopped on. If those now commit, the runs become complete and **the numbers already
# published for them change** — which is an improvement, because it removes the length confound
# that weakened the first comparison, but it does mean the write-up has to be re-read against the
# new figures rather than assumed still true.
echo "[$(date +%H:%M)] step 6 re-test — gesture ablations to n=4, resuming the two that halted"
python -u -m redthread replicate runs/current --runs 4 --label nogesture \
    --no-gesture-feedback --local qwen3:8b --quiet >> logs/phase1-nogesture.log 2>&1

echo "[$(date +%H:%M)] done. Read it with:  bash scripts/phase1-report.sh"
