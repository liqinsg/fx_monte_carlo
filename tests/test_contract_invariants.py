#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Contract invariant tests for the generated MC + Fib payload.

These checks focus on derived-field correctness rather than only key presence.
"""

import datetime
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from interface import get_latest_fib_mc_data


FIB_ZONES = [
    (0.0, 0.236, "F0", "Deep Discount"),
    (0.236, 0.382, "F236", "Discount"),
    (0.382, 0.5, "F382", "Below Equilibrium"),
    (0.5, 0.618, "F5", "Above Equilibrium"),
    (0.618, 0.786, "F618", "Premium"),
    (0.786, 1.0, "F786", "Deep Premium"),
]


@pytest.fixture
def latest_contract_data():
    """Load today's latest generated contract payload."""
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    raw_data = get_latest_fib_mc_data(today_str, timeframe="D")
    if not raw_data:
        pytest.skip(f"今日 ({today_str}) 尚未生成 MC 数据文件，跳过 contract invariant 校验。")
    return raw_data


def _matching_zones(ratio_pos: float):
    clipped_pos = max(0.0, min(1.0, ratio_pos))
    matches = []
    for index, zone in enumerate(FIB_ZONES):
        low, high, _tag, _label = zone
        if low <= clipped_pos <= high:
            matches.append((index, zone))
    if not matches:
        raise AssertionError(f"无法根据 ratio_pos={ratio_pos} 计算 zone_index")
    return matches, clipped_pos


def test_contract_invariants_for_all_pairs(latest_contract_data):
    results = latest_contract_data.get("results", {})
    assert results, "Results 结果集为空"

    for pair, rec in results.items():
        fib = rec.get("fib")
        assert fib is not None, f"标的 {pair} 缺少 fib 块"

        lower, upper = map(float, rec["range_90"])
        current_price = float(rec["current_price"])
        assert lower < upper, f"标的 {pair} 的 range_90 非递增: {rec['range_90']}"

        ratio_pos = float(fib["ratio_pos"])
        range_90_pct = float(fib["range_90_pct"])
        zone_index = int(fib["zone_index"])
        current_zone = fib["current_zone"]

        expected_range_pct = round(((upper - lower) / current_price) * 100, 3)
        expected_ratio_pos = round((current_price - lower) / (upper - lower), 4)

        assert range_90_pct >= 0, f"标的 {pair} 的 range_90_pct 为负数: {range_90_pct}"
        assert range_90_pct == pytest.approx(expected_range_pct, abs=1e-3), (
            f"标的 {pair} 的 range_90_pct 与原始字段不一致: "
            f"expected={expected_range_pct}, actual={range_90_pct}"
        )

        assert 0 <= ratio_pos <= 1, f"标的 {pair} 的 ratio_pos 越界: {ratio_pos}"
        assert ratio_pos == pytest.approx(expected_ratio_pos, abs=1e-4), (
            f"标的 {pair} 的 ratio_pos 与原始字段不一致: "
            f"expected={expected_ratio_pos}, actual={ratio_pos}"
        )

        matches, clipped_pos = _matching_zones(ratio_pos)
        matching_indices = [index for index, _zone in matches]

        assert 0 <= zone_index <= 5, f"标的 {pair} 的 zone_index 越界: {zone_index}"
        assert zone_index in matching_indices, (
            f"标的 {pair} 的 zone_index 与 ratio_pos 不一致: "
            f"allowed={matching_indices}, actual={zone_index}"
        )

        low_ratio, high_ratio, expected_tag, expected_label = FIB_ZONES[zone_index]
        expected_zone_pos = round(((clipped_pos - low_ratio) / (high_ratio - low_ratio)) * 100, 1)

        actual_zone_pos = float(current_zone["position_in_zone_pct"])
        assert 0 <= actual_zone_pos <= 100, (
            f"标的 {pair} 的 position_in_zone_pct 越界: {actual_zone_pos}"
        )
        assert actual_zone_pos == pytest.approx(expected_zone_pos, abs=0.2), (
            f"标的 {pair} 的 position_in_zone_pct 与 zone 区间不一致: "
            f"expected={expected_zone_pos}, actual={actual_zone_pos}"
        )

        assert current_zone["tag"] == expected_tag, (
            f"标的 {pair} 的 current_zone.tag 不一致: "
            f"expected={expected_tag}, actual={current_zone['tag']}"
        )
        assert current_zone["label"] == expected_label, (
            f"标的 {pair} 的 current_zone.label 不一致: "
            f"expected={expected_label}, actual={current_zone['label']}"
        )

        labels = fib.get("labels", {})
        assert labels.get("fib_zone") == f"FIB {expected_tag} | {expected_label}", (
            f"标的 {pair} 的 labels.fib_zone 不一致: {labels.get('fib_zone')}"
        )
        assert labels.get("fib_position") == (
            f"FIB {zone_index + 1}/6 {round(expected_zone_pos)}% in {expected_tag}"
        ), f"标的 {pair} 的 labels.fib_position 不一致: {labels.get('fib_position')}"
