#!/bin/bash
set -euo pipefail

# 进入项目目录
CD_PATH="$HOME/projects/fx_monte_carlo"
cd "$CD_PATH" || exit 1

# 激活 conda 环境
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate ai-sprint

# 获取当前日期 (YYYYMMDD 格式，供 fib_mc_segment.py 使用)
TODAY=$(date +"%Y%m%d")

# 1. 每日固定执行日线 (D) Monte Carlo
python fx_monte_carlo.py D

# 2. 紧接着对生成的数据运行 Fibonacci 空间分割与偏离度计算
if [ -f "fib_mc_segment.py" ]; then
    python fib_mc_segment.py "$TODAY"
fi

# 3. 周一额外执行周线 (W) (1=周一) 
if [ "$(date +%u)" -eq 1 ]; then
    python fx_monte_carlo.py W
    # 如果周一也需要对周线数据跑一遍 Fib 分割，可以加上这行：
    python fib_mc_segment.py "$TODAY"
fi
