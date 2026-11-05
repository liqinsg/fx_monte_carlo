#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example Interface Module: fx_monte_carlo.interface
Description:
    数据访问层参考示例。供调用者拷贝到本地项目中使用。
    1. 纯粹的数据契约：按日期和时间框架安全加载、解析 fx_monte_carlo 生成的复合 JSON 数据。
    2. 业务使用样例：附带展示如何利用返回的 Fib 区间与 zone_index 实现动态仓位缩放（K系数）策略。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

# 默认指向标准输出目录（可由调用者按需修改）
DEFAULT_RESULTS_DIR = Path.home() / "projects" / "fx_monte_carlo" / "mc_results"


def get_latest_fib_mc_data(
    day: str, timeframe: str = "D", results_dir: Path = DEFAULT_RESULTS_DIR
) -> Optional[Dict[str, Any]]:
    """
    根据日期前缀（如 '20261105'）和时间框架（'D'/'W'）自动通配匹配并加载最新的 MC+Fib 复合 JSON 数据。
    """
    if not results_dir.exists():
        return None

    pattern = f"mc_{timeframe}_all_pairs_{day}_*.json"
    matched_files = sorted(results_dir.glob(pattern))

    if not matched_files:
        return None

    latest_file = matched_files[-1]
    try:
        return json.loads(latest_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] Interface Error reading json {latest_file.name}: {e}")
        return None


def get_pair_analytics(
    pair: str, day: str, timeframe: str = "D", results_dir: Path = DEFAULT_RESULTS_DIR
) -> Optional[Dict[str, Any]]:
    """
    基础检索函数：获取指定交易对在特定日期的所有 MC 统计指标与 Fibonacci 空间分割详情。
    """
    data = get_latest_fib_mc_data(day, timeframe, results_dir)
    if not data or "results" not in data or pair not in data["results"]:
        return None

    return data["results"][pair]


# ==============================================================================
# 🌟 经典业务使用样例（Example Strategy: 动态仓位缩放 K 系数）
# 说明：这只是本系统提供的一种推荐参考用法，调用者完全可以根据需要编写自己的策略。
# ==============================================================================
def example_calculate_position_multiplier(
    pair: str, day: str, timeframe: str = "D"
) -> Dict[str, Any]:
    """
    [示例方法] 演示如何消费底层数据：
    根据 Fib 空间区域的 zone_index 计算仓位缩放系数 K：
      - 均衡核心区 (zone_index 2, 3): K = 1.0 (标准仓位)
      - 次核心区 (zone_index 1, 4): K = 0.5 (降半仓)
      - 极端边缘区 (zone_index 0, 5): K = 0.2 (防守轻仓)
    """
    res = get_pair_analytics(pair, day, timeframe)
    if not res:
        return {"status": "FALLBACK", "multiplier_k": 1.0, "reason": "Data not found"}

    fib_info = res.get("fib", {})
    zone_idx = fib_info.get("zone_index", 3)

    if zone_idx in [2, 3]:
        k_factor = 1.0
    elif zone_idx in [1, 4]:
        k_factor = 0.5
    else:
        k_factor = 0.2

    return {
        "status": "SUCCESS",
        "pair": pair,
        "current_price": res.get("current_price"),
        "zone_index": zone_idx,
        "zone_label": fib_info.get("current_zone", {}).get("label"),
        "action": fib_info.get("labels", {}).get("action"),
        "multiplier_k": k_factor,
    }


if __name__ == "__main__":
    import datetime

    today_str = datetime.datetime.now().strftime("%Y%m%d")
    print(f"=== Interface Example Test for EURUSD=X ({today_str}) ===")

    # 测试基础数据获取
    raw_data = get_pair_analytics("EURUSD=X", today_str)
    print("Raw Analytics Retrieved:", bool(raw_data))

    # 测试样例策略计算
    strategy_res = example_calculate_position_multiplier("EURUSD=X", today_str)
    print(json.dumps(strategy_res, indent=2, ensure_ascii=False))
