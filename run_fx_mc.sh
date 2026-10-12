#!/bin/bash
set -euo pipefail

# 完全复刻你手动操作的流程
cd "$HOME/projects/fx_monte_carlo" || exit 1

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate ai-sprint

# 每日固定执行
python fx_monte_carlo.py D

# 周一额外执行 W (1=周一)
if [ "$(date +%u)" -eq 1 ]; then
    python fx_monte_carlo.py W
fi