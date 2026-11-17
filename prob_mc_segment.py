#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Probability annotation (distribution / prob_bands / belief) for FX Monte-Carlo results.

与 fib_mc_segment.py 并列的「只增不改」标注模块，契约见
docs/MC_PROB_ANNOTATION_SPEC_v1.0.md（FROZEN v1.0, payload schema 1.2.0）。

分层：
  L0 原始层      : 冻结不动。
  L1 概率分位带  : prob_bands —— 按「等概率质量」切带（真正"弯曲"），
                   由 distribution 的终值分位确定性派生。
  L2 贝叶斯信念层: belief —— 以 MC 的 p_up / p_down 为先验锚点；Producer 侧
                   无外部指标，似然恒等退化为均匀（1/3），后验 == 先验。

关键纪律：
  * distribution 是原料，由 fx_monte_carlo.run_mc() 直接产出；本模块只消费它。
  * 方向概率的唯一真理源始终是 p_up / p_down；belief 恒为 advisory。
  * 退化 / 窄区间 / 后验平坦 → fail-closed，verdict = "NO_EDGE"。
  * 只增不改：既有字段与 fib 块原样保留。
"""

import copy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import numpy as np

# ── 冻结参数（docs/MC_PROB_ANNOTATION_SPEC_v1.0.md §9, FROZEN v1.0）──────────
SCHEMA_VERSION = "1.2.0"
STATES = ["UP", "DOWN", "RANGE"]

BAND_COUNT = 5
TARGET_MASS = round(1.0 / BAND_COUNT, 4)  # 0.2

THRESHOLD_TAU = 0.55
PRIOR_GAMMA = 2.0
DECAY_HALF_LIFE_H = 24.0
MIN_WIDTH_PCT_GATE = 1.2

# regime 倾向 → RANGE 先验权重（方向无关，仅调制"盘整 / 动量强弱"）
W_RANGE_MAP = (
    ("CONSOLIDATION RANGE", 1.3),
    ("NEUTRAL", 1.0),
    ("OVERBOUGHT", 0.7),
    ("OVERSOLD", 0.7),
    ("STRONG MOMENTUM", 0.5),
)
DEFAULT_W_RANGE = 1.0

# distribution.quantiles 的固定键集（§4.2）
DIST_QUANTILE_KEYS = ["0.01", "0.05", "0.10", "0.25", "0.50", "0.75", "0.90", "0.95", "0.99"]
# prob_bands.shape 暴露的分位子集（§4.3）
SHAPE_QUANTILE_KEYS = ["0.05", "0.25", "0.50", "0.75", "0.95"]


def w_range_for(regime: Any) -> float:
    """regime 字符串 → RANGE 先验权重；未知一律回退 NEUTRAL 权重 1.0。"""
    if not regime:
        return DEFAULT_W_RANGE
    upper = str(regime).upper()
    for token, weight in W_RANGE_MAP:
        if token in upper:
            return weight
    return DEFAULT_W_RANGE


# ==============================================================================
# L0 → 原料：distribution（由 run_mc 的终值路径直接产出）
# ==============================================================================
def build_distribution(
    final,
    *,
    simulations: int,
    forecast: int,
    student_t_df: int,
    decimals: int = 5,
) -> Dict[str, Any]:
    """把 MC 终值路径的样本汇总为不可变原料 distribution。

    仅做确定性汇总（分位 + 矩），不重跑模拟、不引入任何外部输入。
    """
    arr = np.asarray(final, dtype=float)

    if arr.size == 0:
        quantiles = {k: 0.0 for k in DIST_QUANTILE_KEYS}
        return {
            "source": "mc_terminal_paths",
            "simulations": int(simulations),
            "forecast": int(forecast),
            "student_t_df": int(student_t_df),
            "quantiles": quantiles,
            "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0,
            "skew": 0.0, "kurtosis": 0.0,
            "degenerate": True,
        }

    mean = float(np.mean(arr))
    std = float(np.std(arr))
    vmin = float(np.min(arr))
    vmax = float(np.max(arr))

    degenerate = bool(not np.isfinite(std) or std <= 0.0 or vmin == vmax)

    quantiles = {
        key: round(float(np.percentile(arr, float(key) * 100.0)), decimals)
        for key in DIST_QUANTILE_KEYS
    }

    if not degenerate and np.isfinite(std):
        z = (arr - mean) / std
        skew = float(np.mean(z ** 3))
        kurtosis = float(np.mean(z ** 4) - 3.0)  # excess kurtosis (Fisher)
    else:
        skew = 0.0
        kurtosis = 0.0

    return {
        "source": "mc_terminal_paths",
        "simulations": int(simulations),
        "forecast": int(forecast),
        "student_t_df": int(student_t_df),
        "quantiles": quantiles,
        "mean": round(mean, decimals),
        "std": round(std, decimals),
        "min": round(vmin, decimals),
        "max": round(vmax, decimals),
        "skew": round(skew, 4),
        "kurtosis": round(kurtosis, 4),
        "degenerate": degenerate,
    }


# ==============================================================================
# L1：prob_bands（等概率带，由 distribution 确定性派生）
# ==============================================================================
def _sorted_quantile_points(distribution: Dict[str, Any]) -> List[Tuple[float, float]]:
    quantiles = distribution.get("quantiles") or {}
    points: List[Tuple[float, float]] = []
    for key, value in quantiles.items():
        try:
            points.append((float(key), float(value)))
        except (TypeError, ValueError):
            continue
    points.sort(key=lambda kv: kv[0])
    return points


def derive_prob_bands(
    distribution: Dict[str, Any],
    current_price: float,
    percentile_rank: float,
    *,
    band_count: int = BAND_COUNT,
    decimals: int = 5,
) -> Dict[str, Any]:
    """由 distribution 派生等概率带（§4.3.1 派生规则）。"""
    points = _sorted_quantile_points(distribution)
    vmin = float(distribution.get("min", points[0][1] if points else 0.0))
    vmax = float(distribution.get("max", points[-1][1] if points else 0.0))
    degenerate = bool(distribution.get("degenerate", False))

    # 单调分位函数：两端锚定 min / max，中间对已存分位线性插值
    xs = [0.0] + [p for p, _ in points] + [1.0]
    ys = [vmin] + [v for _, v in points] + [vmax]

    def quantile_at(p: float) -> float:
        return float(np.interp(p, xs, ys))

    target_mass = round(1.0 / band_count, 4)
    boundaries = [round(quantile_at(k / band_count), decimals) for k in range(band_count + 1)]

    # 边界不可分辨（非严格递增）视为退化
    if any(boundaries[i] >= boundaries[i + 1] for i in range(band_count)):
        degenerate = True

    bands: List[Dict[str, Any]] = []
    for i in range(band_count):
        bands.append({
            "index": i,
            "tag": f"Q{int(i * 100 / band_count)}-{int((i + 1) * 100 / band_count)}",
            "price_lo": boundaries[i],
            "price_hi": boundaries[i + 1],
            "prob_mass": target_mass,
        })

    # 位置：唯一真理源是 percentile_rank（P(终值 <= 当前价)）
    rank = float(percentile_rank)
    band_index = int(min(max(rank, 0.0) // (100.0 / band_count), band_count - 1))
    band = bands[band_index]
    lo, hi = band["price_lo"], band["price_hi"]
    if hi > lo:
        position = (float(current_price) - lo) / (hi - lo) * 100.0
    else:
        position = 50.0
    position = round(max(0.0, min(100.0, position)), 1)

    quantiles = distribution.get("quantiles") or {}
    median = float(quantiles.get("0.50", vmin))
    mean = float(distribution.get("mean", median))

    shape = {
        "mean": round(mean, decimals),
        "median": round(median, decimals),
        # Pearson 经验式：无原始样本时的众数估计
        "mode": round(3.0 * median - 2.0 * mean, decimals),
        "quantiles": {
            k: round(float(quantiles[k]), decimals)
            for k in SHAPE_QUANTILE_KEYS
            if k in quantiles
        },
        "skew": distribution.get("skew"),
        "kurtosis": distribution.get("kurtosis"),
        "prob_below": round(rank, 1),
        "prob_above": round(100.0 - rank, 1),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "method": "equal_probability_mass",
        "band_count": band_count,
        "target_mass": target_mass,
        "bands": bands,
        "current": {
            "index": band_index,
            "tag": band["tag"],
            "price_lo": lo,
            "price_hi": hi,
            "position_in_band_pct": position,
        },
        "band_index": band_index,
        "shape": shape,
        "degenerate": degenerate,
        "mode": "static_reference",
    }


# ==============================================================================
# L2：belief（贝叶斯信念参考快照）
# ==============================================================================
def _normalize(raw: Dict[str, float], decimals: int = 4) -> Dict[str, float]:
    total = sum(raw.values())
    if total <= 0:
        uniform = round(1.0 / len(raw), decimals)
        return {k: uniform for k in raw}
    return {k: round(v / total, decimals) for k, v in raw.items()}


def _expires_utc(generated_utc: str, half_life_h: float) -> str:
    try:
        dt = datetime.fromisoformat(generated_utc)
    except (TypeError, ValueError):
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(hours=float(half_life_h))).isoformat()


def derive_belief(
    p_up: float,
    p_down: float,
    regime: Any,
    *,
    generated_utc: str = None,
    tau: float = THRESHOLD_TAU,
    gamma: float = PRIOR_GAMMA,
    half_life_h: float = DECAY_HALF_LIFE_H,
    range_90_pct: float = None,
    degenerate: bool = False,
) -> Dict[str, Any]:
    """以 p_up / p_down 锚定先验；Producer 侧似然均匀 → posterior == prior。"""
    p_up = float(p_up)
    p_down = float(p_down)
    spread = abs(p_up - p_down) / 100.0

    w_range = w_range_for(regime)
    prior = _normalize({
        "UP": p_up / 100.0,
        "DOWN": p_down / 100.0,
        "RANGE": ((1.0 - spread) ** gamma) * w_range,
    })

    # Producer 侧无外部指标：似然恒等退化为均匀，regime 不代表方向
    uniform = round(1.0 / len(STATES), 4)
    likelihood = {s: uniform for s in STATES}
    evidence = [{
        "name": "regime",
        "value": regime,
        "spread": round(spread, 4),
        "likelihood": dict(likelihood),
    }]

    posterior = _normalize({s: prior[s] * likelihood[s] for s in STATES})

    order = sorted(STATES, key=lambda s: posterior[s], reverse=True)
    edge = {
        "argmax": order[0],
        "value": round(posterior[order[0]], 4),
        "spread": round(posterior[order[0]] - posterior[order[1]], 4),
    }

    narrow = range_90_pct is not None and float(range_90_pct) < MIN_WIDTH_PCT_GATE
    if degenerate or narrow or posterior[order[0]] < tau:
        verdict = "NO_EDGE"
    else:
        verdict = order[0]

    generated = generated_utc or datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": SCHEMA_VERSION,
        "states": list(STATES),
        "prior": {s: prior[s] for s in STATES},
        "prior_source": "mc_p_up",
        "evidence": evidence,
        "likelihood": {s: likelihood[s] for s in STATES},
        "posterior": {s: posterior[s] for s in STATES},
        "edge": edge,
        "threshold_tau": tau,
        "verdict": verdict,
        "advisory": True,
        "decay_half_life_h": half_life_h,
        "generated_utc": generated,
        "expires_utc": _expires_utc(generated, half_life_h),
        "mode": "static_reference",
    }


# ==============================================================================
# 组装：把 L1 / L2 注入 MC payload（纯内存，无文件 I/O）
# ==============================================================================
def annotate_pair(rec: Dict[str, Any], *, band_count: int = BAND_COUNT) -> Dict[str, Any]:
    distribution = rec.get("distribution")
    if not isinstance(distribution, dict):
        # 无原料（早期 / 手工产物）→ 不产出 L1/L2，保持 fail-closed
        return rec

    decimals = 3 if "JPY" in str(rec.get("pair", "")) else 5
    current_price = float(rec["current_price"])

    rec["prob_bands"] = derive_prob_bands(
        distribution,
        current_price,
        float(rec.get("percentile_rank", 50.0)),
        band_count=band_count,
        decimals=decimals,
    )

    range_90_pct = None
    quantiles = distribution.get("quantiles") or {}
    if current_price > 0 and "0.05" in quantiles and "0.95" in quantiles:
        range_90_pct = (
            float(quantiles["0.95"]) - float(quantiles["0.05"])
        ) / current_price * 100.0

    rec["belief"] = derive_belief(
        rec.get("p_up", 50.0),
        rec.get("p_down", 50.0),
        rec.get("regime", ""),
        generated_utc=rec.get("generated_utc"),
        range_90_pct=range_90_pct,
        degenerate=bool(distribution.get("degenerate", False)),
    )
    return rec


def segment_prob_data(mc_data: Dict[str, Any], *, band_count: int = BAND_COUNT) -> Dict[str, Any]:
    """返回追加了概率标注的 MC payload；输入保持不变（deepcopy）。

    输入形状与 fib_mc_segment.segment_mc_data 相同：``metadata`` + ``results``。
    """
    if not isinstance(mc_data, dict) or not isinstance(mc_data.get("results"), dict):
        raise ValueError("MC data must be a dict containing a 'results' mapping")

    segmented = copy.deepcopy(mc_data)
    for pair, rec in segmented["results"].items():
        if not isinstance(rec, dict):
            raise ValueError(f"MC result for {pair!r} must be a dictionary")
        segmented["results"][pair] = annotate_pair(rec, band_count=band_count)

    metadata = segmented.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("MC data 'metadata' must be a dictionary")
    metadata["schema_version"] = SCHEMA_VERSION
    metadata["annotation"] = {
        "method": "prob_bands+belief",
        "band_count": band_count,
        "states": list(STATES),
        "threshold_tau": THRESHOLD_TAU,
        "mode": "static_reference",
    }
    return segmented


apply_prob_segmentation = segment_prob_data


if __name__ == "__main__":
    # 最小自检：用合成分布验证 L1 / L2 的输出形状与不变量
    import json

    rng = np.random.default_rng(20261117)
    final = 1.10 * np.exp(rng.standard_t(5, 5000) * 0.006 * np.sqrt(5))
    dist = build_distribution(final, simulations=5000, forecast=5, student_t_df=5, decimals=5)
    bands = derive_prob_bands(dist, 1.10249, 61.4, decimals=5)
    belief = derive_belief(38.6, 61.4, "⚡ D STRONG MOMENTUM")
    print(json.dumps({"distribution": dist, "prob_bands": bands, "belief": belief},
                     indent=2, ensure_ascii=False))
