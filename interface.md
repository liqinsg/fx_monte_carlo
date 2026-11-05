
# 🧭 FX-Monte-Carlo Data Access Contract & Example

本模块为外部系统提供标准化的 **Monte Carlo 概率区间 + Fibonacci 空间分割** 纯数据契约。

---

## 1. 核心原则

* **MC提供客观的量化测算结果**（包含模拟概率、统计分位数、Fibonacci 网格区间及当前价格映射）。
* **可自由设计策略绑定**：例如用于仓位控制、网格边界、风控止损或趋势过滤。

---

## 2. API 调用参考

### `get_pair_analytics(pair, day, timeframe="D")`

* **作用**：加载指定日期最新生成的复合 JSON，并返回特定交易对的完整分析数据结构。
* **返回数据结构示例 (JSON Schema)**：

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
      "fib_50": 1.1247,
      "fib_100": 1.13566
    },
    "zones": [...],
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

## 3. 调用者自由消费示例

调用者只需将 `interface.py` 放到本地，即可按需提取任意指标：

```python
from interface import get_pair_analytics

# 获取某交易对的今日数据
data = get_pair_analytics("EURUSD=X", "20261105")

if data:
    current_price = data["current_price"]
    zone_idx = data["fib"]["zone_index"]
    zone_label = data["fib"]["current_zone"]["label"]
  
    print(f"Price: {current_price} | Fib Zone Index: {zone_idx} ({zone_label})")
  
    # 调用者自行实现个性化逻辑（例如：根据 zone_index 自行决定风控、减仓或挂单）
    if zone_idx >= 4:
        # 开发者自己的高位策略...
        pass
```
