#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine drift regression tests（§13.5.3 C1 · 方案 B：算术漂移 + GBM 半方差修正）。

验收要求（规格 §13.5.3）：「用**合成数据**独立验证 drift（已知均值方差 →
校验模拟对数收益均值与历史样本一致）」。

本套件用**合成 K 线**（关闭网络）驱动 `run_mc()`，因此既不打网络、
也不覆盖 `mc_results/` 中的 demo live 产物。
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 引擎在 import 期即 `parser.parse_args()`：先用干净的 argv 导入，再还原，
# 避免 pytest 自身参数被 argparse 误读。
_ORIG_ARGV = sys.argv
sys.argv = ["fx_monte_carlo.py"]
try:
    import fx_monte_carlo as mc
finally:
    sys.argv = _ORIG_ARGV


def _synthetic_df(lookback: int, *, mu: float = 0.0008, sigma: float = 0.02, seed: int = 12345):
    """构造已知对数收益均值/方差的合成价格序列（仅 Close 被 run_mc 使用）。"""
    rng = np.random.default_rng(seed)
    log_returns = rng.normal(loc=mu, scale=sigma, size=lookback - 1)
    closes = 1.10 * np.exp(np.concatenate([[0.0], np.cumsum(log_returns)]))
    df = pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes}
    )
    # 用 diff(log) 复现 run_mc 内部的口径，确保断言与实现同源
    realized_log_returns = np.diff(np.log(closes))
    return df, realized_log_returns


@pytest.fixture
def patched_engine(monkeypatch):
    lookback = mc.TF_CFG["lookback"]
    df, log_returns = _synthetic_df(lookback)
    monkeypatch.setattr(mc, "fetch_data", lambda pair: df)
    monkeypatch.setattr(mc, "SIMULATIONS", 4000)
    return df, log_returns


def test_ann_drift_pct_matches_arithmetic_drift_definition(patched_engine):
    """`ann_drift_pct` 必须定义为**年化算术漂移** μ = (m + σ²/2)·periods_year。"""
    _, log_returns = patched_engine
    res, ok = mc.run_mc("TEST=X", "20260101")
    assert ok is True

    m = float(np.mean(log_returns))
    var = float(np.var(log_returns))  # 总体方差（ddof=0）
    expected_ann_drift_pct = (m + 0.5 * var) * mc.TF_CFG["periods_year"] * 100.0

    assert res["ann_drift_pct"] == pytest.approx(expected_ann_drift_pct, abs=0.01)


def test_simulated_step_log_drift_equals_historical_sample_mean(patched_engine):
    """方案 B 的核心不变量：每步模拟对数收益均值 == 历史样本对数收益均值。

    由实现可观测字段反推 step_log_drift = μ/periods_year − 0.5·σ²/periods_year，
    并断言其等于历史样本均值 m（旧实现会系统性偏差 −σ²/2，见下方回归护栏）。
    """
    _, log_returns = patched_engine
    res, ok = mc.run_mc("TEST=X", "20260101")
    assert ok is True

    m = float(np.mean(log_returns))
    periods_year = mc.TF_CFG["periods_year"]

    ann_drift = res["ann_drift_pct"] / 100.0
    ann_vol = res["ann_vol_pct"] / 100.0
    implied_step_log_drift = ann_drift / periods_year - 0.5 * (ann_vol**2) / periods_year

    assert implied_step_log_drift == pytest.approx(m, abs=1e-6)

    # 回归护栏：合成数据的 0.5·σ²/步 远大于容差，
    # 因此该断言足以区分「方案 B」与「旧实现（多出 −σ²/2 系统性下偏）」。
    half_var_step = 0.5 * float(np.var(log_returns))
    assert half_var_step > 1e-4
    assert abs(implied_step_log_drift - (m - half_var_step)) > 1e-6


def test_expected_price_field_retained_with_stable_alternative(patched_engine):
    """C2：`expected_price` 字段名保留（P-1），并随 `distribution` 提供更稳健的位置量。"""
    _, _ = patched_engine
    res, ok = mc.run_mc("TEST=X", "20260101")
    assert ok is True

    assert "expected_price" in res  # 字段名不改
    quantiles = res["distribution"]["quantiles"]
    assert "0.50" in quantiles  # 中位数（稳健位置量）已随 distribution 提供
    assert np.isfinite(quantiles["0.50"])
