# 🧭 FX-Monte-Carlo & Fibonacci Interface Specification

本文档面向所有需要对接 `fx_monte_carlo` 模块的外部系统（如交易 Bot、自动化风控脚本等），提供统一的接口契约说明。

---

## 1. 模块概述

本项目将 **Monte Carlo 概率区间模拟** 与 **Fibonacci 非线性空间分割** 深度结合。外部交易 Bot 无需关心复杂的统计模拟过程，只需通过标准接口查询当前价格的**空间偏离度**与**动态仓位缩放系数 ($K$)**。

---

## 2. 核心调用方法

### `query_pair_risk_factor(pair, day, timeframe="D")`

* **作用**：查询指定交易对在特定日期的最新风控状态。
* **参数说明**：

  * `pair` (str): 交易对代号，例如 `"XAU_USD"`, `"EUR_USD"`。
  * `day` (str): 目标日期，格式为 `YYYYMMDD`（如 `"20261104"`）。
  * `timeframe` (str): 时间框架，支持 `"D"`（日线，默认）或 `"W"`（周线）。

* **返回值格式 (JSON Schema)**：

```json
{
  "status": "SUCCESS",
  "pair": "XAU_USD",
  "current_price": 2745.50,
  "p_up": 56.2,
  "regime": "BULLISH_TREND",
  "zone_index": 3,
  "zone_tag": "F382",
  "zone_label": "Below Equilibrium",
  "action": "NEUTRAL",
  "multiplier_k": 1.0,
  "combined_label": "🧭 FIB F382 Below Equilibrium | BULLISH_TREND"
}
```

---

## 3. 仓位缩放系数 (K 系数) 映射规则

根据价格在 Fibonacci 划分区间的 `zone_index`（0 到 5），系统自动输出对应的动态风控系数 **K**，用于与你的梯级仓位（如 10k → 5k → 2k Units）相乘：

| 区域索引 (zone_index) | Fibonacci 区间名 | 市场空间状态 | 仓位缩放系数 (K) | 策略含义 |
|---|---|---|---|---|
| 2 或 3 | F382 / F5 (Below/Above Equilibrium) | 均衡核心区 | 1.0 | 正常执行当前阶梯标准仓位（如 10,000 Units） |
| 1 或 4 | F236 / F618 (Discount / Premium) | 次核心/预警区 | 0.5 | 结构偏离中心，主动降半仓（如 5,000 Units） |
| 0 或 5 | F0 / F786+ (Deep Discount/Premium) | 极端边缘/尾部区 | 0.2 | 极度偏离，随时面临均值回归，挂防守轻仓（如 2,000 Units） |

> **注**：若底层数据未生成或文件缺失，接口将自动触发降级保护，返回 `status: "FALLBACK"` 且 `multiplier_k: 1.0`，确保交易 Bot 不会因外部数据故障而崩溃。

---

## 4. 外部交易 Bot 调用示例 (Python)

```python
import sys
from pathlib import Path

# 1. 导入 fx_monte_carlo 接口
sys.path.append(str(Path.home() / "projects" / "fx_monte_carlo"))
from interface import query_pair_risk_factor

# 2. 获取当前交易对风险系数
today_str = "20261104"  # 或动态获取日期
risk_info = query_pair_risk_factor("XAU_USD", today_str)

k_factor = risk_info["multiplier_k"]
print(f"当前 Fib 区间: {risk_info['zone_label']} | 推荐 K 系数: {k_factor}")

# 3. 结合你的阶梯仓位计算最终下单 Units
base_tier_units = 10000  # 假设当前处于第一梯级
final_units = int(base_tier_units * k_factor)

print(f"最终下发到 OANDA 的 Units: {final_units}")
```