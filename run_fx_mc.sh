#!/bin/bash
set -euo pipefail

# 进入项目目录
CD_PATH="$HOME/projects/fx_monte_carlo"
cd "$CD_PATH" || exit 1

# 激活 conda 环境
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate ai-sprint

# 每日执行：脚本内部完成 Monte Carlo、Fib 分割，并写回同一个结果文件。
python fx_monte_carlo.py D

# 周一额外执行周线 (W) (1=周一)
if [ "$(date +%u)" -eq 1 ]; then
    python fx_monte_carlo.py W
fi
