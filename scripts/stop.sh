#!/usr/bin/env bash
# Stop the generation chain cleanly. Nothing is lost but the scene in progress.
#
#     bash scripts/stop.sh            show what would be stopped
#     bash scripts/stop.sh --yes      stop it
#
# Resume afterwards with `bash scripts/phase1.sh`, which reads runs/.floor-commit and picks up the
# part-written run where it stopped.
#
# Two processes have to go, not one: the `redthread replicate` writer *and* the `phase1.sh` chain
# that launched it. Killing only the writer leaves the chain to start the next condition
# immediately, which is the opposite of stopping.
#
# Written as a script rather than a one-liner because the PowerShell equivalent needs nested
# quoting that does not survive being copied into a prompt, and because a careless selector
# matches the shell running it — including this session's own tooling.
set -u
cd "$(dirname "$0")/.." || exit 1

LIST='Get-CimInstance Win32_Process |
  Where-Object { ($_.CommandLine -match "redthread replicate" -or
                 $_.CommandLine -match "phase1\.sh$") -and
                 $_.CommandLine -notmatch "CimInstance" } |
  Select-Object ProcessId, Name'

if [ "${1:-}" = "--yes" ]; then
    powershell -NoProfile -Command "$LIST | ForEach-Object {
        Write-Output ('stopped ' + \$_.Name + ' ' + \$_.ProcessId)
        Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }"
    echo
    for i in 1 2 3 4; do
        printf '  floor%s: %s of 71 scenes kept\n' "$i" \
            "$(ls runs/current-floor$i/scenes/*.txt 2>/dev/null | wc -l)"
    done
    echo
    echo "Resume with:  bash scripts/phase1.sh"
else
    echo "Would stop:"
    powershell -NoProfile -Command "$LIST | Format-Table -AutoSize"
    echo "Nothing stopped. Pass --yes to do it."
fi
