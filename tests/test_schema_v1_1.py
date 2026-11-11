#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pytest Suite: tests/test_schema_v1_1.py
Description:
    自动化校验生成的 MC + Fib 复合 JSON 文件。
    确保所有标的均严格符合 Schema v1.1.0 契约及扩展风控字段的要求。
"""

import sys
import datetime
from pathlib import Path
import pytest

# 确保能正确导入项目根目录下的模块
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from interface import get_latest_fib_mc_data, DEFAULT_RESULTS_DIR
from fib_mc_segment import apply_fib_segmentation

@pytest.fixture
def latest_processed_data():
    """Pytest 夹具：加载今日最新数据并运行内存级打标"""
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    raw_data = get_latest_fib_mc_data(today_str, timeframe="D")
    
    if not raw_data:
        pytest.skip(f"今日 ({today_str}) 尚未生成 MC 数据文件，跳过契约校验。")
        
    # 应用打标与风控注入
    processed = apply_fib_segmentation(raw_data, min_width_pct_gate=1.2)
    return processed

def test_metadata_schema_version(latest_processed_data):
    """验证顶层 metadata 是否包含 v1.1.0 版本声明"""
    metadata = latest_processed_data.get("metadata", {})
    assert metadata.get("schema_version") == "1.1.0", "Metadata 缺少或未正确声明 schema_version '1.1.0'"

def test_all_pairs_contain_v1_1_extensions(latest_processed_data):
    """验证所有标的 (Results) 内部的 fib 块是否包含所有 v1.1.0 扩展字段与 risk_model Gate"""
    results = latest_processed_data.get("results", {})
    assert len(results) > 0, "Results 结果集为空"

    required_fib_keys = {
        "schema_version",
        "range_90_pct",
        "ratio_pos",
        "breakout",
        "degenerate",
        "zone_index",
        "current_zone",
        "risk_model"
    }

    required_risk_keys = {
        "multiplier_k",
        "reason",
        "min_width_gate_pct"
    }

    for pair, rec in results.items():
        fib = rec.get("fib")
        assert fib is not None, f"标的 {pair} 缺少 'fib' 字典块"
        
        # 1. 检查 fib 块内的基础契约字段
        missing_fib_keys = required_fib_keys - set(fib.keys())
        assert not missing_fib_keys, f"标的 {pair} 的 fib 块缺少必需字段: {missing_fib_keys}"
        assert fib["schema_version"] == "1.1.0", f"标的 {pair} 的 fib.schema_version 不匹配"

        # 2. 检查数据类型与合理性
        assert isinstance(fib["range_90_pct"], (int, float)), f"标的 {pair} 的 range_90_pct 类型错误"
        assert isinstance(fib["ratio_pos"], (int, float)), f"标的 {pair} 的 ratio_pos 类型错误"
        assert isinstance(fib["breakout"], bool), f"标的 {pair} 的 breakout 必须是布尔值"
        assert isinstance(fib["degenerate"], bool), f"标的 {pair} 的 degenerate 必须是布尔值"
        assert 0 <= fib["zone_index"] <= 5, f"标的 {pair} 的 zone_index 越界 (0~5)"

        # 3. 检查 risk_model 风险风控 Gate 结构
        risk_model = fib.get("risk_model")
        missing_risk_keys = required_risk_keys - set(risk_model.keys())
        assert not missing_risk_keys, f"标的 {pair} 的 risk_model 缺少必需字段: {missing_risk_keys}"
        
        assert risk_model["multiplier_k"] in [0.2, 0.5, 1.0], f"标的 {pair} 的 K 系数值不合法: {risk_model['multiplier_k']}"
        assert isinstance(risk_model["reason"], str) and len(risk_model["reason"]) > 0, f"标的 {pair} 缺少有效的风险原因说明"