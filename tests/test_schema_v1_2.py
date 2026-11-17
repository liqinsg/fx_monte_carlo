#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pytest Suite: tests/test_schema_v1_2.py
Description:
    校验 MC 概率标注体系（payload schema 1.2.0）：
      L1 prob_bands（等概率带）与 L2 belief（贝叶斯信念）的契约与不变量
      （docs/MC_PROB_ANNOTATION_SPEC_v1.0.md §4 / §6）。

    绝大多数用例为离线单元测试（合成分布，确定性、无网络）。
    末尾附一条「若已生成 v1.2 产物则校验、否则 skip」的集成用例。
"""

import datetime
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from prob_mc_segment import (  # noqa: E402
    BAND_COUNT,
    DIST_QUANTILE_KEYS,
    SCHEMA_VERSION,
    STATES,
    TARGET_MASS,
    THRESHOLD_TAU,
    annotate_pair,
    build_distribution,
    derive_belief,
    derive_prob_bands,
    segment_prob_data,
)

TOL = 0.01


# ── fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture
def synthetic_final():
    """确定性的 Student-t 终值样本，锚定 EURUSD 量级。"""
    rng = np.random.default_rng(20261117)
    return 1.10 * np.exp(rng.standard_t(5, 5000) * 0.006 * np.sqrt(5))


@pytest.fixture
def synthetic_distribution(synthetic_final):
    return build_distribution(
        synthetic_final, simulations=5000, forecast=5, student_t_df=5, decimals=5
    )


@pytest.fixture
def synthetic_record(synthetic_distribution):
    return {
        "timeframe": "D",
        "pair": "EURUSD=X",
        "current_price": 1.10249,
        "percentile_rank": 61.4,
        "p_up": 38.6,
        "p_down": 61.4,
        "regime": "⚡ D STRONG MOMENTUM",
        "range_90": [1.08869, 1.11227],
        "generated_utc": "2026-11-17T00:00:04.275891+00:00",
        "distribution": synthetic_distribution,
    }


# ── L0 distribution ─────────────────────────────────────────────────────────
def test_distribution_shape_and_quantile_monotonicity(synthetic_distribution):
    dist = synthetic_distribution
    assert set(dist["quantiles"]) == set(DIST_QUANTILE_KEYS)
    assert dist["degenerate"] is False

    values = [dist["quantiles"][k] for k in DIST_QUANTILE_KEYS]
    assert all(v > 0 for v in values), "V-1: 分位值必须 > 0"
    assert all(values[i] < values[i + 1] for i in range(len(values) - 1)), "V-1: 分位严格递增"

    for key in ("mean", "std", "min", "max", "skew", "kurtosis"):
        assert np.isfinite(dist[key]), f"V-2: {key} 必须有限"


def test_distribution_degenerate_flag_on_constant_input():
    dist = build_distribution(np.full(100, 1.2345), simulations=100, forecast=5, student_t_df=5)
    assert dist["degenerate"] is True


# ── L1 prob_bands ───────────────────────────────────────────────────────────
def test_prob_bands_invariants(synthetic_distribution):
    bands = derive_prob_bands(synthetic_distribution, 1.10249, 61.4, decimals=5)

    assert bands["schema_version"] == SCHEMA_VERSION
    assert bands["method"] == "equal_probability_mass"
    assert bands["band_count"] == BAND_COUNT
    assert bands["mode"] == "static_reference"

    items = bands["bands"]
    assert len(items) == BAND_COUNT
    assert [b["index"] for b in items] == list(range(BAND_COUNT)), "V-3: 索引升序"

    for i, band in enumerate(items):
        assert band["price_lo"] < band["price_hi"], "V-3: 每带下界严格小于上界"
        if i < BAND_COUNT - 1:
            assert band["price_hi"] == items[i + 1]["price_lo"], "V-3: 相邻带端点相接"

    assert items[0]["price_lo"] == synthetic_distribution["min"], "V-3: 首带下界 = min"
    assert items[-1]["price_hi"] == synthetic_distribution["max"], "V-3: 末带上界 = max"

    total_mass = sum(b["prob_mass"] for b in items)
    assert total_mass == pytest.approx(1.0, abs=TOL), "V-4: Σ prob_mass ≈ 1"
    for band in items:
        assert abs(band["prob_mass"] - TARGET_MASS) <= TOL, "V-4: 各带 = target_mass"


def test_prob_bands_current_band_consistency(synthetic_distribution):
    bands = derive_prob_bands(synthetic_distribution, 1.10249, 61.4, decimals=5)

    # percentile_rank=61.4 ⇒ 落在第 4 带（index 3）
    assert bands["band_index"] == 3
    assert bands["current"]["index"] == 3
    assert bands["current"]["tag"] == "Q60-80"

    pos = bands["current"]["position_in_band_pct"]
    assert 0.0 <= pos <= 100.0, "V-5: position_in_band_pct 越界"

    shape = bands["shape"]
    assert shape["prob_below"] == 61.4
    assert shape["prob_above"] == pytest.approx(38.6, abs=0.05)
    assert set(shape["quantiles"]) == {"0.05", "0.25", "0.50", "0.75", "0.95"}


def test_prob_bands_degenerate_derivation():
    degenerate_dist = build_distribution(np.full(50, 1.10), simulations=50, forecast=5, student_t_df=5)
    bands = derive_prob_bands(degenerate_dist, 1.10, 50.0, decimals=5)
    assert bands["degenerate"] is True


# ── L2 belief ───────────────────────────────────────────────────────────────
def test_belief_invariants():
    belief = derive_belief(38.6, 61.4, "⚡ D STRONG MOMENTUM")

    assert belief["schema_version"] == SCHEMA_VERSION
    assert belief["states"] == STATES
    assert belief["prior_source"] == "mc_p_up"
    assert belief["advisory"] is True, "V-8: advisory 恒为 true"

    for key in ("prior", "likelihood", "posterior"):
        weights = belief[key]
        assert set(weights) == set(STATES)
        assert sum(weights.values()) == pytest.approx(1.0, abs=TOL), f"V-6: {key} 需归一化"
        assert all(0.0 <= v <= 1.0 for v in weights.values()), "V-6: 分量 ∈ [0,1]"

    post = belief["posterior"]
    argmax = max(STATES, key=lambda s: post[s])
    assert belief["edge"]["argmax"] == argmax, "V-7: edge.argmax == argmax(posterior)"

    assert belief["expires_utc"] > belief["generated_utc"], "V-9: expires > generated"
    assert belief["verdict"] in set(STATES) | {"NO_EDGE"}
    assert belief["threshold_tau"] == THRESHOLD_TAU
    assert belief["mode"] == "static_reference"


def test_belief_prior_anchor_values():
    # EURUSD=X 锚定样例：p_up=38.6 / p_down=61.4 / STRONG MOMENTUM(w=0.5, gamma=2)
    belief = derive_belief(38.6, 61.4, "⚡ D STRONG MOMENTUM")
    assert belief["prior"]["UP"] == pytest.approx(0.2974, abs=0.001)
    assert belief["prior"]["DOWN"] == pytest.approx(0.4730, abs=0.001)
    assert belief["prior"]["RANGE"] == pytest.approx(0.2296, abs=0.001)


def test_belief_uniform_likelihood_makes_posterior_equal_prior():
    """Producer 侧无外部指标：似然均匀 ⇒ 后验 == 先验（不引入方向）。"""
    belief = derive_belief(38.6, 61.4, "⚡ D STRONG MOMENTUM")
    assert all(belief["likelihood"][s] == pytest.approx(1.0 / 3, abs=0.001) for s in STATES)
    for s in STATES:
        assert belief["posterior"][s] == pytest.approx(belief["prior"][s], abs=0.001)


def test_belief_consolidation_verdict_is_range():
    # 盘整：spread≈0 ⇒ RANGE 先验高 ⇒ verdict = RANGE
    belief = derive_belief(50.5, 49.5, "⏳ D CONSOLIDATION RANGE")
    assert belief["verdict"] == "RANGE"


def test_belief_fail_closed_on_degenerate():
    belief = derive_belief(70.0, 30.0, "⚡ D STRONG MOMENTUM", degenerate=True)
    assert belief["verdict"] == "NO_EDGE"


def test_belief_fail_closed_on_narrow_range():
    belief = derive_belief(70.0, 30.0, "⚡ D STRONG MOMENTUM", range_90_pct=0.5)
    assert belief["verdict"] == "NO_EDGE"


def test_belief_fail_closed_on_flat_posterior():
    # 动量很弱的方向先验：max(posterior) < tau ⇒ NO_EDGE
    belief = derive_belief(70.0, 30.0, "🔹 D NEUTRAL")
    assert belief["posterior"]["UP"] < THRESHOLD_TAU
    assert belief["verdict"] == "NO_EDGE"


# ── 组装 ────────────────────────────────────────────────────────────────────
def test_segment_prob_data_is_additive_and_metadata(synthetic_record):
    payload = {
        "metadata": {"timeframe": "D", "schema_version": "1.1.0", "fib_segmentation": {"x": 1}},
        "results": {"EURUSD=X": json.loads(json.dumps(synthetic_record))},
    }
    before = json.loads(json.dumps(payload))

    out = segment_prob_data(payload)

    # 输入不变（deepcopy）
    assert payload == before, "segment_prob_data 不得修改输入"

    assert out["metadata"]["schema_version"] == SCHEMA_VERSION
    assert out["metadata"]["annotation"]["band_count"] == BAND_COUNT
    assert out["metadata"]["annotation"]["threshold_tau"] == THRESHOLD_TAU
    # 既有 fib 元数据保留
    assert out["metadata"]["fib_segmentation"] == {"x": 1}

    rec = out["results"]["EURUSD=X"]
    assert "prob_bands" in rec and "belief" in rec
    # V-10: 既有字段未被改动
    for key, value in synthetic_record.items():
        assert rec[key] == value, f"既有字段 {key} 被改动"


def test_annotate_pair_without_distribution_is_rejected():
    """评审 #2：缺料必须 fail-closed 拒绝，而不是静默 no-op。"""
    rec = {"pair": "EURUSD=X", "current_price": 1.1, "p_up": 50.0, "p_down": 50.0,
           "percentile_rank": 50.0, "regime": "🔹 D NEUTRAL"}
    with pytest.raises(ValueError):
        annotate_pair(dict(rec))


def test_segment_prob_data_rejects_payload_without_distribution():
    """评审 #2：任一 pair 缺 distribution ⇒ 整包拒绝，绝不产出假标 1.2.0 的 payload。"""
    payload = {
        "metadata": {"schema_version": "1.1.0", "fib_segmentation": {"x": 1}},
        "results": {"EURUSD=X": {"pair": "EURUSD=X", "current_price": 1.1,
                                 "p_up": 50.0, "p_down": 50.0, "regime": "🔹 D NEUTRAL"}},
    }
    with pytest.raises(ValueError):
        segment_prob_data(payload)


def test_segment_prob_data_does_not_downgrade_schema(synthetic_record):
    """评审 #1：不得把已存在的更高 schema_version 写回 1.2.0。"""
    payload = {
        "metadata": {"schema_version": "1.3.0", "annotation": {"band_count": 5}},
        "results": {"EURUSD=X": json.loads(json.dumps(synthetic_record))},
    }
    out = segment_prob_data(payload)

    assert out["metadata"]["schema_version"] == "1.3.0", "不得向下覆盖更高版本"
    assert out["metadata"]["annotation"]["band_count"] == 5
    rec = out["results"]["EURUSD=X"]
    assert "prob_bands" in rec and "belief" in rec


def test_belief_rejects_naive_and_invalid_timestamps():
    """评审 #6：裸/非法时间戳必须报错，不得静默造时间或臆断时区。"""
    with pytest.raises(ValueError):
        derive_belief(38.6, 61.4, "🔹 D NEUTRAL", generated_utc="2026-11-17T00:00:04")
    with pytest.raises(ValueError):
        derive_belief(38.6, 61.4, "🔹 D NEUTRAL", generated_utc="not-a-timestamp")
    with pytest.raises(ValueError):
        derive_belief(38.6, 61.4, "🔹 D NEUTRAL", generated_utc="")


def test_belief_normalizes_offset_to_utc():
    """带偏移量的合法时间戳被归一化到 UTC，expires 严格晚于 generated。"""
    belief = derive_belief(
        38.6, 61.4, "🔹 D NEUTRAL", generated_utc="2026-11-17T08:00:00+08:00"
    )
    assert belief["generated_utc"] == "2026-11-17T00:00:00+00:00"
    assert belief["expires_utc"] == "2026-11-18T00:00:00+00:00"


def test_fib_then_prob_pipeline_keeps_fib_and_bumps_schema(synthetic_record):
    """模拟 main() 顺序：先 fib 打标，再概率打标 → schema 1.2.0 且 fib 块保留。"""
    from fib_mc_segment import segment_mc_data

    payload = {
        "metadata": {"timeframe": "D"},
        "results": {"EURUSD=X": json.loads(json.dumps(synthetic_record))},
    }
    payload = segment_mc_data(payload, date="20261117")
    assert payload["metadata"]["schema_version"] == "1.1.0"
    fib_before = json.loads(json.dumps(payload["results"]["EURUSD=X"]["fib"]))

    payload = segment_prob_data(payload)

    assert payload["metadata"]["schema_version"] == SCHEMA_VERSION
    assert payload["metadata"]["fib_segmentation"]["date"] == "20261117"
    rec = payload["results"]["EURUSD=X"]
    assert rec["fib"] == fib_before, "V-10: prob 打标不得改动 fib 块"
    assert "prob_bands" in rec and "belief" in rec


def test_fib_segmentation_does_not_downgrade_schema(synthetic_record):
    """r2 / 评审 #10：fib 打标不得把已升到 1.2.0 的 metadata 写回 1.1.0。"""
    from fib_mc_segment import segment_mc_data

    payload = {
        "metadata": {"schema_version": "1.2.0", "annotation": {"band_count": 5}},
        "results": {"EURUSD=X": json.loads(json.dumps(synthetic_record))},
    }
    out = segment_mc_data(payload, date="20261117")

    assert out["metadata"]["schema_version"] == "1.2.0", "不得向下覆盖 schema_version"
    assert out["metadata"]["annotation"] == {"band_count": 5}, "既有 metadata 应保留"
    assert out["metadata"]["fib_segmentation"]["date"] == "20261117"


# ── 集成：若今日已生成 v1.2 产物则校验 ───────────────────────────────────────
def test_live_v1_2_payload_if_present():
    results_dir = ROOT_DIR / "mc_results"
    if not results_dir.exists():
        pytest.skip("mc_results 目录不存在")
    today = datetime.datetime.now().strftime("%Y%m%d")
    candidates = sorted(results_dir.glob(f"mc_D_all_pairs_{today}_*.json"))
    if not candidates:
        pytest.skip(f"今日 ({today}) 尚未生成 MC 数据文件")

    data = json.loads(candidates[-1].read_text(encoding="utf-8"))
    if data.get("metadata", {}).get("schema_version") != SCHEMA_VERSION:
        pytest.skip("最新产物尚未升级到 schema 1.2.0（仅向前生效）")

    for pair, rec in data["results"].items():
        assert "distribution" in rec and "prob_bands" in rec and "belief" in rec, pair
        bands = rec["prob_bands"]["bands"]
        assert sum(b["prob_mass"] for b in bands) == pytest.approx(1.0, abs=TOL)
        for i in range(len(bands) - 1):
            assert bands[i]["price_hi"] == bands[i + 1]["price_lo"], pair
        weights = rec["belief"]["posterior"]
        assert sum(weights.values()) == pytest.approx(1.0, abs=TOL), pair
        assert rec["belief"]["advisory"] is True, pair
