#!/bin/bash
set -euo pipefail

# Resolve the project directory from this script's location.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Schedule this script for 00:00 Europe/London on day 1 of each month.
# For cron implementations that support CRON_TZ, use:
#   CRON_TZ=Europe/London
#   0 0 1 * * <repo-directory>/run_fx_mc.sh
# Keep this guard so accidental/manual invocations on other London dates
# don't launch the monthly pipeline.
LONDON_DAY="$(TZ=Europe/London date +%d)"
if [[ "$LONDON_DAY" != "01" ]]; then
    echo "[$(TZ=Europe/London date '+%Y-%m-%d %H:%M:%S %Z')] Not the first day of the month in London; skipping."
    exit 0
fi

# 激活 conda 环境
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate ai-sprint

# Run daily Monte Carlo; the main program segments and saves the same MC file.
python fx_monte_carlo.py D

# Run weekly Monte Carlo too when the London date is Monday.
if [ "$(TZ=Europe/London date +%u)" -eq 1 ]; then
    python fx_monte_carlo.py W
fi
