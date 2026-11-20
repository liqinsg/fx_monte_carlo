#!/bin/bash
set -euo pipefail

# Resolve the project directory from this script's location.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Schedule this script at 00:00, 00:05, and 00:10 Europe/London. Cron gives
# up to three attempts; output-file checks below make later invocations skip
# timeframes that already succeeded. For cron implementations supporting CRON_TZ:
#   CRON_TZ=Europe/London
#   0,5,10 0 * * * <repo-directory>/run_fx_mc_new.sh

LONDON_NOW="$(TZ=Europe/London date '+%Y-%m-%d %H:%M:%S %Z')"
LONDON_DAY="$(TZ=Europe/London date +%d)"
LONDON_DOW="$(TZ=Europe/London date +%u)"  # 1=Monday ... 7=Sunday
# fx_monte_carlo.py timestamps output filenames in UTC, so use UTC date for
# the existence check (London midnight falls on the previous UTC date in BST).
UTC_DAY="$(date -u +%Y%m%d)"
echo "[$LONDON_NOW] FX Monte Carlo schedule check"

# 激活 conda 环境
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate ai-sprint

# Retry cron entries may overlap if a Monte Carlo run takes over five
# minutes. Serialize invocations so later ticks check results after the
# previous run completes instead of starting duplicate work.
LOCK_FILE="${TMPDIR:-/tmp}/fx_monte_carlo_${UID}.lock"
exec 9>"$LOCK_FILE"
flock 9

shopt -s nullglob
overall_status=0

run_if_missing() {
    local timeframe="$1"
    local files=("mc_results/mc_${timeframe}_all_pairs_${UTC_DAY}_"*.json)

    if (( ${#files[@]} > 0 )); then
        echo "[$LONDON_NOW] ${timeframe}: result already exists (${files[0]}); skipping."
        return 0
    fi

    echo "[$LONDON_NOW] ${timeframe}: no result for UTC date ${UTC_DAY}; running."
    if python fx_monte_carlo.py "$timeframe"; then
        local generated=("mc_results/mc_${timeframe}_all_pairs_${UTC_DAY}_"*.json)
        if (( ${#generated[@]} > 0 )); then
            echo "[$LONDON_NOW] ${timeframe}: result saved."
            return 0
        fi
        echo "[$LONDON_NOW] ERROR: ${timeframe} exited successfully but produced no result file."
    else
        local rc=$?
        echo "[$LONDON_NOW] ERROR: ${timeframe} run failed with exit code ${rc}."
    fi
    return 1
}

# Daily: run on weekdays.
if (( LONDON_DOW <= 5 )); then
    run_if_missing D || overall_status=1
fi

# Weekly: run every Monday.
if (( LONDON_DOW == 1 )); then
    run_if_missing W || overall_status=1
fi

# Monthly: run on the first calendar day, including when it falls on a weekend.
if [[ "$LONDON_DAY" == "01" ]]; then
    run_if_missing M || overall_status=1
fi

exit "$overall_status"
