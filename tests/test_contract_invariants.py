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

from interface import (
    example_calculate_position_multiplier,
    get_latest_fib_mc_data,
    get_pair_advisory,
    is_pair_advisory_fresh,
    is_snapshot_fresh,
)


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


# ==============================================================================
# interface.py 消费侧契约：时效（硬 TTL 闭左）与 fail-closed 标注状态
# 对应 docs/MC_PROB_ANNOTATION_SPEC_v1.0.md §5 / §7 / §9.3 与
# docs/MC_FIB_V1_2_ACTION_PLAN.md P0-3 / P0-4。
# 全部为离线单元测试（合成 dict，无网络、无文件 IO）。
# ==============================================================================
GEN_UTC = "2026-11-17T00:00:00+00:00"
EXP_UTC = "2099-01-01T00:00:00+00:00"  # 远期，避免用例随时间自然失效
NOW_UTC = datetime.datetime(2026, 11, 17, 12, 0, 0, tzinfo=datetime.timezone.utc)
EXPIRED_UTC = "2026-11-16T00:00:00+00:00"


def _rec(**overrides):
    """构造一个 healthy 的 pair 记录，再按需覆盖。"""
    rec = {
        "current_price": 1.10,
        "range_90": [1.08, 1.13],  # 宽度 ≈ 4.5% > 1.2 门限
        "distribution": {"degenerate": False},
        "prob_bands": {"degenerate": False},
        "belief": {
            "verdict": "UP",
            "generated_utc": GEN_UTC,
            "expires_utc": EXP_UTC,
            "advisory": True,
        },
        "fib": {"zone_index": 2},
    }
    rec.update(overrides)
    return rec


def test_is_pair_advisory_fresh_happy_path():
    assert is_pair_advisory_fresh(_rec(), NOW_UTC) is True


def test_is_pair_advisory_fresh_closed_left_boundary():
    """硬 TTL **闭左**：now == expires 即失效（§9.3 / V-9）。"""
    at_expiry = datetime.datetime(2026, 11, 18, 0, 0, 0, tzinfo=datetime.timezone.utc)
    boundary_rec = _rec(belief={"expires_utc": "2026-11-18T00:00:00+00:00"})
    assert is_pair_advisory_fresh(boundary_rec, at_expiry - datetime.timedelta(seconds=1)) is True
    assert is_pair_advisory_fresh(boundary_rec, at_expiry) is False


def test_is_pair_advisory_fresh_fail_closed_on_bad_inputs():
    assert is_pair_advisory_fresh(None, NOW_UTC) is False
    assert is_pair_advisory_fresh({}, NOW_UTC) is False  # 无 belief（1.1.0 及更早产物）
    assert is_pair_advisory_fresh(_rec(belief={}), NOW_UTC) is False  # 缺 expires_utc
    assert is_pair_advisory_fresh(
        _rec(belief={"expires_utc": "2026-11-18T00:00:00"}), NOW_UTC  # 裸时间戳
    ) is False
    assert is_pair_advisory_fresh(
        _rec(belief={"expires_utc": "not-a-timestamp"}), NOW_UTC
    ) is False


def test_naive_now_utc_is_rejected():
    with pytest.raises(ValueError):
        is_pair_advisory_fresh(_rec(), datetime.datetime(2026, 11, 17, 12, 0, 0))


def test_is_snapshot_fresh_requires_all_pairs():
    fresh = _rec()
    stale = _rec(belief={"expires_utc": EXPIRED_UTC, "verdict": "UP"})
    assert is_snapshot_fresh({"results": {"A": fresh, "B": fresh}}, NOW_UTC) is True
    assert is_snapshot_fresh({"results": {"A": fresh, "B": stale}}, NOW_UTC) is False
    assert is_snapshot_fresh({"results": {}}, NOW_UTC) is False
    assert is_snapshot_fresh(None, NOW_UTC) is False


def test_get_pair_advisory_states():
    assert get_pair_advisory(None)["state"] == "invalid"
    assert get_pair_advisory({})["state"] == "invalid"  # 老产物无新增块
    assert get_pair_advisory(_rec())["state"] == "healthy"
    assert get_pair_advisory(_rec(fib={}))["state"] == "healthy"  # 不依赖 fib

    assert get_pair_advisory(_rec(prob_bands={"degenerate": True}))["state"] == "degenerate"
    assert get_pair_advisory(_rec(distribution={"degenerate": True}))["state"] == "degenerate"

    narrow = get_pair_advisory(_rec(range_90=[1.10, 1.1005]))  # 宽度 ≈ 0.045% < 1.2
    assert narrow["state"] == "narrow_range"
    assert narrow["narrow_range"] is True
    assert get_pair_advisory(_rec(range_90=None))["state"] == "narrow_range"  # 宽度不可用 ≠ 不窄


def test_get_pair_advisory_stale_downgrades_verdict():
    """过期后不得透传旧 verdict（P0-4 fail-closed）。"""
    adv = get_pair_advisory(
        _rec(belief={"expires_utc": EXPIRED_UTC, "verdict": "UP"}), NOW_UTC
    )
    assert adv["state"] == "stale"
    assert adv["stale"] is True
    assert adv["verdict"] == "NO_EDGE"


def test_example_multiplier_is_fail_closed(monkeypatch):
    """P0-3：数据缺失或非 healthy 时，绝不返回 K = 1.0。"""
    monkeypatch.setattr("interface.get_pair_analytics", lambda *a, **k: None)
    res = example_calculate_position_multiplier("EURUSD=X", "20261117")
    assert res["multiplier_k"] is None
    assert res["status"] == "NO_ADVISORY"

    monkeypatch.setattr("interface.get_pair_analytics", lambda *a, **k: _rec(range_90=None))
    res = example_calculate_position_multiplier("EURUSD=X", "20261117")
    assert res["multiplier_k"] is None
    assert res["advisory_state"] == "narrow_range"

    monkeypatch.setattr("interface.get_pair_analytics", lambda *a, **k: _rec(fib={"zone_index": 3}))
    res = example_calculate_position_multiplier("EURUSD=X", "20261117")
    assert res["multiplier_k"] == 1.0
    assert res["advisory_state"] == "healthy"
