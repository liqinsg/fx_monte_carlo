本报告的目的是为**第三方 LLM 参与审核（Review & Advise）**以及**外部调用者**准备的技术总结与架构契约。

---

# 🧭 Technical Specification: Monte Carlo Spatial Segmentation & Risk Integration

> **Target Audience**: Third-party LLMs (for code review & architecture advice) & External System Developers.
> **Project Scope**: `fx_monte_carlo` (Branch: `fib26`)
> **Core Philosophy**: Clean separation of concerns—this underlying service produces objective probabilistic metrics and spatial grids; consumer systems retain full autonomy over strategy execution.

---

## 1. Core Architecture: MC Data & Logical Fib Segmentation

The system generates daily and weekly Monte Carlo simulations (e.g., 5,000 paths over a 90-day lookback) for 35 currency pairs and assets, producing an in-memory unified JSON payload.

* **No Physical Splitting**: The term "Fibonacci segmentation" refers strictly to **logical spatial partitioning** rather than data slicing.
* **Methodology**:

1. The simulation yields a 90% probability range (`range_90: [lower, upper]`).
2. The system maps standard Fibonacci ratios ($0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0$) across this statistical band to establish non-linear price thresholds.
3. Each asset's `current_price` is evaluated against these thresholds and tagged with a spatial zone, tag (`F0` through `F786`), and a discrete `zone_index` ($0$ to $5$).

---

## 2. Risk & Position Sizing Strategy (Reference Implementation)

While the underlying service remains strictly agnostic, a reference quantitative risk model is provided via `interface.py` to demonstrate how downstream trading bots can consume the spatial tags for **dynamic position sizing ($K$-factor scaling)**.

### The $K$-Factor Scaling Model

By leveraging the statistical breadth of wide Monte Carlo boundaries, price movements are filtered into three distinct spatial tiers:

| Zone Index (`zone_index`) | Fibonacci Zone Name                      | Market State                  | Position Multiplier ($K$) | Strategy Implication (Reference)                                      |
| --------------------------- | ---------------------------------------- | ----------------------------- | --------------------------- | --------------------------------------------------------------------- |
| **2 or 3**            | `F382 / F5` (Equilibrium Zones)        | **Core Equilibrium**    | **`1.0`**           | Normal execution at full standard tier size (e.g., 10k Units).        |
| **1 or 4**            | `F236 / F618` (Discount / Premium)     | **Secondary / Warning** | **`0.5`**           | Proactive risk reduction, half-position sizing (e.g., 5k Units).      |
| **0 or 5**            | `F0 / F786+` (Deep Discount / Premium) | **Extreme Tail / Edge** | **`0.2`**           | Defensive light positioning awaiting mean reversion (e.g., 2k Units). |

* **Fallback Resilience**: If data is missing or out-of-date, the interface defaults to $K = 1.0$ (with `status: "FALLBACK"`), ensuring downstream execution never halts due to data pipeline interruptions.

---

## 3. Integration & Consumption Contract

External systems consume this data via a standardized access layer (`interface.py`), which safely locates and parses the latest timestamped output files under `mc_results/` (e.g., `mc_D_all_pairs_YYYYMMDD_HHMM.json`).

### Data Schema Overview (Sample JSON Structure)

```json
{
  "timeframe": "D",
  "pair": "EURUSD=X",
  "current_price": 1.12575,
  "range_90": [1.11374, 1.13566],
  "percentile_rank": 56.0,
  "p_up": 44.0,
  "fib": {
    "levels": {
      "fib_0": 1.11374,
      "fib_50": 1.247,
      "fib_100": 1.13566
    },
    "current_zone": {
      "tag": "F5",
      "label": "Above Equilibrium",
      "position_in_zone_pct": 40.6
    },
    "zone_index": 3
  }
}

```

---
