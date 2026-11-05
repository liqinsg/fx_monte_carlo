#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module: fx_monte_carlo.interface
Description: 
    标准化对外接口层。负责解耦底层的 Monte Carlo 概率计算与 Fibonacci 空间分割结果，
    为外部交易 Bot（或其他策略模块）提供统一、类型安全、带降级保护的风控查询 Spec。

Usage in external projects:
    from interface import query_pair_risk_factor
    risk_info = query_pair_risk_factor("XAU_USD", "20261104")
    multiplier = risk_info["multiplier_k"]
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "mc_results"

def get_latest_fib_segment_data(
    day: str, 
    timeframe: str = "D", 
    results_dir: Path = DEFAULT_RESULTS_DIR
) -> Optional[Dict[str, Any]]:
    """
    加载指定日期与时间框架下已完成 Fibonacci 分割的底层 JSON 数据。

    Args:
        day (str): 查询日期，格式 'YYYYMMDD' (例如 '20261104')
        timeframe (str): 时间周期，支持 'D' (日线) 或 'W' (周线)
        results_dir (Path): 结果文件所在的目录路径

    Returns:
        Optional[Dict[str, Any]]: 原始 JSON 字典数据，若文件不存在或解析失败则返回 None。
    """
    day = day.replace("-", "")
    # Fibonacci data now lives in the original timestamped MC file.
    candidates = sorted(results_dir.glob(f"mc_{timeframe}_all_pairs_{day}_????.json"))
    if candidates:
        fib_file = candidates[-1]
    else:
        # Read older snapshots produced before in-place segmentation was added.
        fib_file = results_dir / f"mc_{timeframe}_all_pairs_{day}_fib.json"
    if not fib_file.is_file():
        return None
    try:
        return json.loads(fib_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] Interface Error reading fib json: {e}")
        return None

def query_pair_risk_factor(
    pair: str, 
    day: str, 
    timeframe: str = "D", 
    results_dir: Path = DEFAULT_RESULTS_DIR
) -> Dict[str, Any]:
    """
    🌟 对外核心 Spec 接口：
    查询特定交易对在指定日期的概率-空间偏离度、区位标签及动态仓位缩放系数（K）。

    Args:
        pair (str): 交易对代号，例如 'XAU_USD', 'EUR_USD'
        day (str): 日期字符串，格式 'YYYYMMDD'
        timeframe (str): 时间框架 'D' 或 'W'
        results_dir (Path): 结果目录路径

    Returns:
        Dict[str, Any]: 结构化风控参数字典，包含：
            - status (str): 'SUCCESS' 或 'FALLBACK'
            - pair (str): 交易对名称
            - zone_index (int): 当前所处的 Fib 区间索引 (0~5)
            - zone_label (str): 区域中文/英文描述
            - action (str): 交易倾向建议 (如 'BUY_LIMIT', 'SELL_LIMIT', 'NEUTRAL')
            - multiplier_k (float): 仓位缩放系数 K (1.0 / 0.5 / 0.2)
            - combined_label (str): 组合标记
    """
    data = get_latest_fib_segment_data(day, timeframe, results_dir)
    
    # 容错降级：数据未就绪时返回安全默认态（K=1.0，不阻断交易主逻辑）
    if not data or "results" not in data or pair not in data["results"]:
        return {
            "status": "FALLBACK",
            "pair": pair,
            "error": "Data not found or pipeline not run for today",
            "multiplier_k": 1.0,
            "zone_index": 3
        }

    rec = data["results"][pair]
    fib_info = rec.get("fib", {})
    zone_idx = fib_info.get("zone_index", 3)

    # 🌟 核心映射规则：根据 Fib 空间偏离度映射动态风控系数 K
    # 均衡中心区 (Index 2, 3): 满额仓位 K = 1.0
    # 次核心区 (Index 1, 4): 降至半仓 K = 0.5
    # 极端边缘区 (Index 0, 5): 防守轻仓 K = 0.2
    if zone_idx in [2, 3]:
        k_factor = 1.0
    elif zone_idx in [1, 4]:
        k_factor = 0.5
    else:
        k_factor = 0.2

    return {
        "status": "SUCCESS",
        "pair": pair,
        "current_price": rec.get("current_price"),
        "p_up": rec.get("p_up"),
        "regime": rec.get("regime"),
        "zone_index": zone_idx,
        "zone_tag": fib_info.get("current_zone", {}).get("tag"),
        "zone_label": fib_info.get("current_zone", {}).get("label"),
        "action": fib_info.get("labels", {}).get("action"),
        "multiplier_k": k_factor,
        "combined_label": fib_info.get("fib_regime_label")
    }

if __name__ == "__main__":
    import datetime
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    print(f"=== Interface Self-Test for XAU_USD ({today_str}) ===")
    res = query_pair_risk_factor("XAU_USD", today_str)
    print(json.dumps(res, indent=2, ensure_ascii=False))
