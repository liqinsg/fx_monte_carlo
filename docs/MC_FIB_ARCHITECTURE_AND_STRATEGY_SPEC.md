
---

# 🧭 Technical Specification & Architecture Review: Monte Carlo Spatial Segmentation & Risk Integration

> **Target Audience**: Third-Party LLMs (for Code Review, Architecture Validation & Strategic Advice) & External Consumer Systems.
> **Project Scope**: `fx_monte_carlo` (Branch: `fib26`)
> **Contract Version**: `v1.1.0`
> **Core Philosophy**: Absolute separation of concerns—this underlying service produces objective, schema-versioned probabilistic metrics and spatial grids; downstream execution algorithms retain 100% autonomy over trading decisions.

---

## 1. Executive Summary & Purpose

The `fx_monte_carlo` core engine serves strictly as a **Data & Analytics Provider**. It computes 5,000-path Monte Carlo simulations over a 90-day lookback for 28 unique asset pairs (deduplicated from config).

### Core Purpose & Value Proposition

* **Decoupled Architecture**: Eliminates hardcoded trading rules, buy/sell flags, or position sizes within the core calculation routines.
* **Spatial Normalization**: Translates raw price fluctuations into normalized, non-linear Fibonacci spatial grids based on dynamic statistical probability bands (`range_90`).
* **Schema-Enforced Reliability**: Guarantees atomic file operations and strict regular-expression interface matching to prevent race conditions and downstream silent failures.

---

## 2. Core Concepts & Technical Architecture

### 2.1 Dynamic Seeding & Path Generation

To prevent statistical degradation (where paths degenerate into deterministic cones), random paths are driven by **per-pair, per-date dynamic seeding**:


$$\text{Seed} = \text{MD5}(\text{pair} + \text{date\_str}) \pmod{2^{32}}$$


This guarantees that while daily paths remain 100% reproducible for audit purposes, cross-day variance properly captures real volatility shifts.

### 2.2 In-Memory Logical Fibonacci Partitioning

"Fibonacci Segmentation" is purely **logical tagging** (in-memory) rather than physical data slicing:

1. **Range Definition**: The simulation yields a 90% confidence interval: $\text{range\_90} = [\text{lower}, \text{upper}]$.
2. **Non-Linear Grid Mapping**: Standard ratios ($0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0$) map non-linearly across $\text{range\_90}$ to establish discrete price tiers ($F0$ through $F786$).
3. **Discrete Indexing**: Assigns a discrete `zone_index` ($0$ to $5$) and normalized coordinates to current prices.

---

## 3. Known Issues Identified & Production Fixes (P0 ~ P2 Audit)

During real-data verification across 1,390 historical pair-day snapshots, several critical vulnerabilities were diagnosed and repaired:

### 3.1 [P0 Fixed] Deterministic Seed & Statistical Degeneration

* **Diagnosis**: Legacy code used a static `np.random.seed(42)`, causing `range_90` to degenerate into a deterministic function of price $\pm k \cdot \sigma$. Over 97.6% of historical snapshots fell into `zone_index` 2 or 3, rendering extreme zones inactive.
* **Fix**: Replaced static seeding with `np.random.default_rng(MD5(pair + day_str))` and Student-$t$ distribution sampling.

### 3.2 [P0 Fixed] Non-Atomic Writes & Concurrent Read Corruptions

* **Diagnosis**: In-place `Path.write_text()` operations allowed downstream consumers to read truncated JSON payloads during execution runs.
* **Fix**: Implemented `save_json_safely()` using POSIX-compliant `tempfile.mkstemp` + `os.replace` atomic substitution.

### 3.3 [P0 Fixed] Interface Pattern Ambiguity

* **Diagnosis**: Unrestricted `sorted(glob(...))[-1]` logic accidentally selected legacy `_fib.json` files over timestamped snapshots due to lexicographical ordering (`"f" > "0"`).
* **Fix**: Enforced strict regex parsing: `^mc_{tf}_all_pairs_{day}_(\d{4})\.json$`.

### 3.4 [P1/P2 Fixed] Low-Volatility Jitter & The Range Gate

* **Diagnosis**: In narrow-range markets ($\text{range\_90\_pct} < 1.2\%$), bid-ask spreads caused `zone_index` and position scaling to jump erratically between $0.5$ and $1.0$.
* **Fix**: Introduced the **Range Gate**: when $\text{range\_90\_pct} < 1.2\%$, position sizing is forced to $K = 1.0$ with `reason: "range_too_narrow_or_degenerate"`.

---

## 4. Downstream Risk Model Reference Implementation ($K$-Factor)

While the data provider remains agnostic, `interface.py` provides a reference quantitative model mapping spatial zones to position sizing multipliers ($K$):

| Zone Index (`zone_index`) | Spatial Tag | Market State | Position Multiplier ($K$) | Risk Gate Condition |
| --- | --- | --- | --- | --- |
| **N/A** | `Gate` | **Low Volatility / Narrow Range** | **`1.0`** | Triggered when $\text{range\_90\_pct} < 1.2\%$ |
| **2 or 3** | `F382 / F5` | **Core Equilibrium** | **`1.0`** | Standard position size |
| **1 or 4** | `F236 / F618` | **Discount / Premium Warning** | **`0.5`** | Proactive 50% position reduction |
| **0 or 5** | `F0 / F786` | **Extreme Tail / Breakout Watch** | **`0.2`** | Defensive 80% position reduction |

---

## 5. Formal Interface Contract (Schema `v1.1.0`)

External systems access data strictly through `interface.get_pair_analytics()` or `get_latest_fib_mc_data()`.

The example below is an excerpt copied from a real generated snapshot (`2026-11-05T04:50:42Z`, pair `EURUSD=X`), not a hand-assembled illustration.

```json
{
  "metadata": {
    "schema_version": "1.1.0",
    "timeframe": "D",
    "generated_utc": "2026-11-05T04:50:42.553610+00:00",
    "total_pairs": 28,
    "simulations": 5000,
    "lookback": 90,
    "forecast": 5
  },
  "results": {
    "EURUSD=X": {
      "timeframe": "D",
      "pair": "EURUSD=X",
      "current_price": 1.12651,
      "range_90": [1.11447, 1.13679],
      "percentile_rank": 55.1,
      "p_up": 44.9,
      "fib": {
        "schema_version": "1.1.0",
        "range_90_pct": 1.981,
        "ratio_pos": 0.5394,
        "breakout": false,
        "degenerate": false,
        "zone_index": 3,
        "current_zone": {
          "tag": "F5",
          "label": "Above Equilibrium",
          "position_in_zone_pct": 33.4
        },
        "risk_model": {
          "multiplier_k": 1.0,
          "reason": "equilibrium_zone",
          "min_width_gate_pct": 1.2
        }
      }
    }
  }
}

```

---

## 6. Known Limitations & Future Roadmap

1. **Step-Function Jump Discontinuity**: Current $K$-factor scaling drops discretely ($1.0 \to 0.5 \to 0.2$). Future versions should evaluate continuous logistic function scaling: $K = f(\text{ratio\_pos})$.
2. **Strategy Layer Decoupling**: Legacy fields (`labels.action`, `fib_regime_label`) remain present for backwards compatibility but are deprecated. Consumers should rely exclusively on raw metrics (`zone_index`, `ratio_pos`, `risk_model`).
3. **Database Migration Threshold**: If asset pairs exceed 100 or concurrent consumer bots exceed 5, storage should transition from single-file JSON snapshots to **SQLite WAL mode** for $O(1)$ single-pair query performance.

---
