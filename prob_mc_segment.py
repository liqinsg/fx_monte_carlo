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


def _version_tuple(version: Any) -> tuple:
    """严格解析 ``"1.2.0"`` → ``(1, 2, 0)``。

    Fail-closed（§10 版本单调性）：**不可解析**的版本一律报错，绝不当作最低版本 ——
    否则会把更高版本静默降级。缺失（``None``）由调用方按"无版本"处理，不在此吞掉。
    """
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"schema_version must be a non-empty string, got {version!r}")
    try:
        return tuple(int(part) for part in version.strip().split("."))
    except ValueError as exc:
        raise ValueError(f"unparseable schema_version: {version!r}") from exc


def _finite_float(value: Any, field: str) -> float:
    """转 float 并校验有限性（拒绝 NaN / Infinity）。"""
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric, got {value!r}") from exc
    if not np.isfinite(number):
        raise ValueError(f"{field} must be finite, got {value!r}")
    return number


def _finite_percent(value: Any, field: str) -> float:
    """校验一个落在 [0,100] 的有限百分比数值。"""
    number = _finite_float(value, field)
    if not (0.0 <= number <= 100.0):
        raise ValueError(f"{field} must be within [0,100], got {number}")
    return number


def _require_positive_int(value: Any, field: str) -> int:
    """校验正整数（拒绝 bool，拒绝 ``2.5 → 2`` 这类静默截断）。"""
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer, got {value!r}")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{field} must be an integer, got {value!r}")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer, got {value!r}") from exc
    if number <= 0:
        raise ValueError(f"{field} must be a positive integer, got {value!r}")
    return number


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
    simulations = _require_positive_int(simulations, "simulations")
    forecast = _require_positive_int(forecast, "forecast")
    student_t_df = _require_positive_int(student_t_df, "student_t_df")
    if student_t_df <= 2:
        raise ValueError(f"student_t_df must be > 2 (finite variance), got {student_t_df}")

    arr = np.asarray(final, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"final must be a 1-D terminal-price sample, got ndim={arr.ndim}")
    if arr.size == 0:
        raise ValueError("final is empty; refusing to fabricate an all-zero distribution")
    if not np.all(np.isfinite(arr)):
        raise ValueError("final contains non-finite values (NaN/Inf); refusing to build distribution")
    if np.any(arr <= 0.0):
        raise ValueError("final contains non-positive prices; refusing to build distribution")
    if arr.size != simulations:
        raise ValueError(
            f"sample count {arr.size} != simulations {simulations}; refusing to build distribution"
        )

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
    """严格解析 ``distribution.quantiles``（§4.2 / V-1）。

    要求：键集**完整且恰为** ``DIST_QUANTILE_KEYS``；值有限、为正；随概率**非递减**。
    任一不满足即拒绝 —— 而不是静默跳过坏点，再用残缺分位插值出错误的带边界。
    """
    quantiles = distribution.get("quantiles")
    if not isinstance(quantiles, dict):
        raise ValueError("distribution.quantiles must be an object")

    missing = [k for k in DIST_QUANTILE_KEYS if k not in quantiles]
    if missing:
        raise ValueError(f"distribution.quantiles missing required keys: {missing}")
    extra = [k for k in quantiles if k not in DIST_QUANTILE_KEYS]
    if extra:
        raise ValueError(f"distribution.quantiles has unexpected keys: {extra}")

    points: List[Tuple[float, float]] = []
    for key in DIST_QUANTILE_KEYS:
        value = quantiles[key]
        try:
            probability = float(key)
            price = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"quantile {key!r} has non-numeric value {value!r}") from exc
        if not np.isfinite(probability) or not (0.0 <= probability <= 1.0):
            raise ValueError(f"quantile probability out of range: {key!r}")
        if not np.isfinite(price) or price <= 0.0:
            raise ValueError(f"quantile {key!r} must be a finite positive price, got {value!r}")
        if points and price < points[-1][1]:
            raise ValueError(
                f"quantiles must be non-decreasing with probability: "
                f"{key!r}={price} < {points[-1][1]}"
            )
        points.append((probability, price))
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
    try:
        vmin = _finite_float(distribution["min"], "distribution.min")
        vmax = _finite_float(distribution["max"], "distribution.max")
    except KeyError:
        vmin, vmax = points[0][1], points[-1][1]
    if vmin <= 0.0 or vmax <= 0.0:
        raise ValueError("distribution.min/max must be positive prices")
    if vmin > vmax:
        raise ValueError(f"distribution.min ({vmin}) must be <= distribution.max ({vmax})")
    if not (vmin <= points[0][1] and points[-1][1] <= vmax):
        raise ValueError(
            f"distribution.min/max [{vmin}, {vmax}] must bracket the stored quantiles "
            f"[{points[0][1]}, {points[-1][1]}]"
        )
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
    rank = _finite_percent(percentile_rank, "percentile_rank")
    price = _finite_float(current_price, "current_price")
    if price <= 0.0:
        raise ValueError(f"current_price must be positive, got {current_price!r}")

    band_index = int(min(rank // (100.0 / band_count), band_count - 1))
    band = bands[band_index]
    lo, hi = band["price_lo"], band["price_hi"]

    # 一致性（fail-closed）：rank 定带与 current_price 的几何落点必须相容。
    # 容许 ±1 带，以吸收分位线性插值 + 取整的边界误差；超出即视为输入自相矛盾并**拒绝**，
    # 而不是靠 clamp 把矛盾隐藏成 "position_in_band_pct = 0/100"（§4.3.1-10）。
    if not degenerate:
        geo_index = None
        for i, candidate in enumerate(bands):
            if candidate["price_lo"] <= price <= candidate["price_hi"]:
                geo_index = i
                break
        if geo_index is None or abs(geo_index - band_index) > 1:
            raise ValueError(
                "percentile_rank and current_price are inconsistent: "
                f"rank={rank} -> band {band_index}, price {price} -> geometric band {geo_index}"
            )

    if hi > lo:
        position = (price - lo) / (hi - lo) * 100.0
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


def _utc_datetime(value: Any, *, field: str) -> datetime:
    """解析必须带显式偏移量的 ISO-8601 时间戳，并归一化到 UTC。

    Fail-closed（§8 UTC 时间戳契约）：缺失 / 非法 / 裸（naive）时间戳一律报错，
    **不得**静默替换为当前时间或臆断时区。
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 string")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid ISO-8601 timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise ValueError(
            f"{field} must carry an explicit UTC offset "
            f"(naive timestamp rejected): {value!r}"
        )
    return dt.astimezone(timezone.utc)


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
    # 方向概率是唯一真理源：必须有限、落在 [0,100]，且两者构成完整概率（和 = 100）。
    # 非法输入一律拒绝，绝不带着 NaN / 越界概率进入贝叶斯计算（评审 P0-3）。
    p_up = _finite_percent(p_up, "p_up")
    p_down = _finite_percent(p_down, "p_down")
    if abs((p_up + p_down) - 100.0) > 1e-6:
        raise ValueError(
            f"p_up + p_down must equal 100, got {p_up} + {p_down} = {p_up + p_down}"
        )

    # 先验调制参数边界：防止无效 tau / gamma / half_life 产生非法先验或失效时间（评审 P1-belief）。
    tau = _finite_float(tau, "tau")
    if not (0.0 <= tau <= 1.0):
        raise ValueError(f"tau must be within [0,1], got {tau}")
    gamma = _finite_float(gamma, "gamma")
    if gamma <= 0.0:
        raise ValueError(f"gamma must be > 0, got {gamma}")
    half_life_h = _finite_float(half_life_h, "half_life_h")
    if half_life_h <= 0.0:
        raise ValueError(f"half_life_h must be > 0, got {half_life_h}")
    if range_90_pct is not None:
        range_90_pct = _finite_float(range_90_pct, "range_90_pct")
        if range_90_pct < 0.0:
            raise ValueError(f"range_90_pct must be >= 0, got {range_90_pct}")

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

    # 窄区间保护（fail-closed）：宽度缺失 / 无法计算同样判为不可判定 → NO_EDGE。
    # "不知道区间宽度" ≠ "区间不窄"，因此 None 绝不 fail-open（评审 P1-range_90_pct）。
    narrow = range_90_pct is None or range_90_pct < MIN_WIDTH_PCT_GATE
    if degenerate or narrow or posterior[order[0]] < tau:
        verdict = "NO_EDGE"
    else:
        verdict = order[0]

    # 时间戳契约（§8 / 评审 P0-1）：缺失即拒绝，绝不静默补当前时间 ——
    # 否则无 generated_utc 的历史数据会被伪装成"刚生成"，获得虚假新鲜度。
    if generated_utc is None:
        raise ValueError(
            "generated_utc is required; refusing to silently stamp the current time"
        )
    generated_dt = _utc_datetime(generated_utc, field="generated_utc")
    generated = generated_dt.isoformat()
    expires = (generated_dt + timedelta(hours=half_life_h)).isoformat()

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
        "expires_utc": expires,
        "mode": "static_reference",
    }


# ==============================================================================
# 组装：把 L1 / L2 注入 MC payload（纯内存，无文件 I/O）
# ==============================================================================
def annotate_pair(rec: Dict[str, Any], *, band_count: int = BAND_COUNT) -> Dict[str, Any]:
    distribution = rec.get("distribution")
    if not isinstance(distribution, dict):
        # 无原料（早期 / 手工产物）→ 拒绝，而非静默 no-op。
        # 若此处放过，调用方仍会把整包标成 1.2.0，产生「假标 1.2.0」的非法 payload（评审 #2）。
        raise ValueError(
            f"pair {rec.get('pair')!r} has no 'distribution' raw material; "
            "refusing to annotate (fail-closed). Reject the payload instead of "
            "producing a falsely-labeled 1.2.0 record."
        )

    decimals = 3 if "JPY" in str(rec.get("pair", "")) else 5
    current_price = float(rec["current_price"])

    # 方向概率唯一真理源：必须显式存在；缺失不得静默填 50/50 造出一个假先验（评审 P0-3）。
    if "p_up" not in rec or "p_down" not in rec:
        raise ValueError(
            f"pair {rec.get('pair')!r} is missing p_up/p_down; "
            "refusing to default to a 50/50 prior (fail-closed)"
        )

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

    # 退化状态必须合并 L1 的退化（prob_bands.degenerate）：分位带因取整退化为零宽时，
    # belief 不得仍凭 distribution.degenerate=False 给出方向 verdict（评审 P0-2）。
    effective_degenerate = (
        bool(distribution.get("degenerate", False))
        or bool(rec["prob_bands"].get("degenerate", False))
    )

    rec["belief"] = derive_belief(
        rec["p_up"],
        rec["p_down"],
        rec.get("regime", ""),
        generated_utc=rec.get("generated_utc"),
        range_90_pct=range_90_pct,
        degenerate=effective_degenerate,
    )
    return rec


def segment_prob_data(mc_data: Dict[str, Any], *, band_count: int = BAND_COUNT) -> Dict[str, Any]:
    """返回追加了概率标注的 MC payload；输入保持不变（deepcopy）。

    输入形状与 fib_mc_segment.segment_mc_data 相同：``metadata`` + ``results``。
    任一 pair 缺少 ``distribution`` 原料即整体拒绝（fail-closed），避免产生
    「被误标为 1.2.0」的 payload。
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
    # 版本单调（§10 / 评审 #4）：缺失 → 视为最低版本并补写；低于 → 升级；
    # 高于当前版本 → 结构未知，整体拒绝（fail-closed），绝不静默降级或改写未知结构；
    # 不可解析 → _version_tuple 抛错，同样拒绝。
    existing_version = metadata.get("schema_version")
    if existing_version is None:
        metadata["schema_version"] = SCHEMA_VERSION
    else:
        current = _version_tuple(existing_version)
        target = _version_tuple(SCHEMA_VERSION)
        if current > target:
            raise ValueError(
                f"refusing to annotate higher schema_version {existing_version!r} "
                f"(current {SCHEMA_VERSION}): unknown structure, fail-closed"
            )
        if current < target:
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
    belief = derive_belief(
        38.6,
        61.4,
        "⚡ D STRONG MOMENTUM",
        generated_utc="2026-11-17T00:00:00+00:00",
        range_90_pct=bands["bands"][-1]["price_hi"] / 1.10 * 100.0 - 100.0,
    )
    print(json.dumps({"distribution": dist, "prob_bands": bands, "belief": belief},
                     indent=2, ensure_ascii=False))
