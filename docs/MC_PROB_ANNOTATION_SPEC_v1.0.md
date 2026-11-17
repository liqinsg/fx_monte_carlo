# MC 概率标注体系 · 规格 v1.0（Schema 1.2.0）

**Status:** DRAFT — 待 Owner 审核；审核通过并冻结后方可进入实现
**Version:** 1.0（对应 payload `schema_version = "1.2.0"`）
**Project:** `fx_monte_carlo`
**Created:** 2026-11-17
**Scope:** 只定义标注体系（`distribution` / `prob_bands` / `belief`）的字段语义与契约。**不修改**任何现有字段、`fib` 块、算法与数据。实现授权与本文档审批分离。
**Nature:** 实现契约草案，非架构评审、非代码。
**上位依据:** 既有 payload（现为 schema 1.1.0）、[PHASE_1_DATA_CONTRACT_v1.0.md](PHASE_1_DATA_CONTRACT_v1.0.md) 的契约纪律（additive-only / no historical rewrite / fail-closed / 时间戳语义），与 [FIB_MC_DISCUSSION.md](FIB_MC_DISCUSSION.md) 的"中立分析提供者 → 多消费者"哲学。

> 本文档不授权任何代码改动。所有"PROPOSED PRIOR"参数仅供 Owner 审批，非既定值。

---

## 0. 背景与定位

### 0.1 现状

- `mc_results/` 中存在两类产物：早期**无标注**原始 MC，与近期使用 **Fibonacci 网格**标注（`fib` 块，schema 1.1.0）的产物。
- MC 引擎本身即概率模型：每个 pair 已输出 `p_up` / `p_down` / `percentile_rank` / `range_90` / `var_95` / `cvar_95` / `touch_*` / `expected_price` / `regime`（见 [fx_monte_carlo.py](../fx_monte_carlo.py) `run_mc()`）。
- Fib 标注以 `range_90` 为坐标，按**价格线性**比例 `[0,.236,.382,.5,.618,.786,1.0]` 切成 6 段（见 [fib_mc_segment.py](../fib_mc_segment.py)）。

### 0.2 动机

既然 MC 是概率模型，标注就应以**概率**而非**几何**组织。Fib 的线性网格与概率分布无关，属于"直线"切分。本规格引入**概率（弯曲）**标注：

1. **L1 概率分位带**：以 MC 终值分布的**等概率质量**切带，边界由概率密度决定（真正"弯曲"）。
2. **L2 贝叶斯信念层**：以 MC 的 `p_up` 为**先验锚点**，用 `regime` 与外部指标做证据更新，得到 advisory 的方向信念。

### 0.3 关键定位：静态参考 vs 动态计算

- 写入文件的标注是**静态参考（static reference）**，会随时间过期。
- **消费 MC 数据时，由 Consumer 重新做一轮动态计算**，以当时的实时输入刷新 `belief`。
- 因此 Producer 负责存**原料**（`distribution`）与**参考快照**；Consumer 负责**动态重算**。

---

## 1. 核心原则

| ID | 原则 |
|----|------|
| P-1 | **只增不改**：现有字段与 `fib` 块一律保留，不删除、不改语义；本规格仅新增 `distribution` / `prob_bands` / `belief` 三块，`schema_version` 由 `1.1.0` 升为 `1.2.0`（additive）。 |
| P-2 | **单一真理源**：方向概率的唯一真理源是 `p_up` / `p_down`。`belief` 为 advisory，**永不覆盖** MC 概率。 |
| P-3 | **静态参考 ≠ 当前判断**：静态块必须标注 `mode:"static_reference"` 与 `expires_utc`；Consumer 必须区分静态与动态，过期即失效。 |
| P-4 | **Fail-closed**：退化、窄区间、后验平坦或数据过期时，判定为 `NO_EDGE`，**严禁默认满仓**。 |
| P-5 | **向前生效**：仅对以后新生成的产物追加标注；历史产物不回溯改写（原始数据保留，需要时再另行分析）。 |
| P-6 | **结构一致**：`prob_bands` 由 `distribution` 确定性派生；L1 为 deterministic，L2 为 dynamic。 |

---

## 2. 术语与符号

| 术语 | 符号 | 说明 |
|------|------|------|
| 终值分布 | $F$ | MC 模拟终点价格的分布（`forecast` 步后） |
| 等概率带 | — | 使每带概率质量相等（$1/N$）的分割 |
| 概率质量 | `prob_mass` | 某带内的概率占比，$\sum = 1$ |
| 方向概率 | `p_up` / `p_down` | 终点高于/低于当前价的模拟比例（既有真理源） |
| 概率差 | `spread` | $|p\_up - p\_down| / 100 \in [0,1]$，量化"方向强弱" |
| 先验 | `prior` | L2 初始状态分布，由 `p_up` 锚定 |
| 似然 | `likelihood` | $P(E \mid S_i)$ |
| 后验 | `posterior` | $P(S_i \mid E)$，归一化 |
| 置信阈值 | `threshold_tau` | 后验达到即判定的阈值 |
| 状态 | `states` | `{UP, DOWN, RANGE}` |

> 观察：`regime` 与 `spread` 强正相关——盘整 ⇒ `spread≈0`；强动量 ⇒ `spread` 大。故 `regime` 作为 `spread` 的**离散佐证标签**，与 `p_up` **同源**，不引入第二真理源。

---

## 3. 系统架构

```
Producer (fx_monte_carlo.py, additive)
  run_mc() ──▶ 每 pair 增 distribution（终值分位+矩）
             ──▶ 标注模块增 prob_bands（L1）+ belief（L2 参考快照）
             ──▶ 写入 mc_D/W_*.json（原字段 & fib 不变，schema 1.2.0）
        │
        ▼
Consumer (interface.py, Phase 2)
  读 distribution + p_up + regime（原料与锚点）
  + 消费时实时行情/指标（RSI/MA/成交量/当前 regime）
        ──▶ 动态重算 belief（mode:"dynamic"）
        ──▶ 供 forex_oanda_v7 消费
```

- **Producer**：确定性；`distribution` 为不可变原料；`prob_bands` / `belief` 为参考快照。
- **Consumer**：非确定性；以实时输入重算 `belief`，并把静态快照标记为过期参考。

---

## 4. Producer Schema v1.2.0

### 4.1 metadata（新增/变更部分）

```json
"metadata": {
  "...既有字段保持不变...": 0,
  "schema_version": "1.2.0",
  "annotation": {
    "method": "prob_bands+belief",
    "band_count": 5,
    "states": ["UP", "DOWN", "RANGE"],
    "threshold_tau": "<pending>",
    "mode": "static_reference"
  }
}
```

| 字段 | 类型 | 必填 | 语义 |
|------|------|------|------|
| `schema_version` | string | 是 | 由 `1.1.0` 升为 `"1.2.0"`。 |
| `annotation.method` | string | 是 | 标注方法标识。 |
| `annotation.band_count` | int | 是 | L1 分带数（默认 5）。 |
| `annotation.states` | array | 是 | L2 状态集。 |
| `annotation.threshold_tau` | number | 是 | 置信阈值（§9 待审批）。 |
| `annotation.mode` | string | 是 | 恒为 `"static_reference"`。 |

### 4.2 `distribution`（每 pair 新增 · 原料）

由 `run_mc()` 在计算 `final = paths[:, -1]` 后直接产出，写入该 pair 记录。

```json
"distribution": {
  "source": "mc_terminal_paths",
  "simulations": 5000,
  "forecast": 5,
  "student_t_df": 5,
  "quantiles": {
    "0.01": "<q01>", "0.05": "<q05>", "0.10": "<q10>",
    "0.25": "<q25>", "0.50": "<q50>", "0.75": "<q75>",
    "0.90": "<q90>", "0.95": "<q95>", "0.99": "<q99>"
  },
  "mean": "<float>", "std": "<float>", "min": "<float>", "max": "<float>",
  "skew": "<float>", "kurtosis": "<float>",
  "degenerate": false
}
```

| 字段 | 类型 | 必填 | 语义 |
|------|------|------|------|
| `source` | string | 是 | 分布来源标识。 |
| `simulations` / `forecast` / `student_t_df` | int | 是 | 回显生成参数，便于复算与审计。 |
| `quantiles` | object | 是 | 键为小数概率字符串（`"0.05"`），值为对应价格。键**严格递增**。 |
| `mean` / `std` / `min` / `max` | number | 是 | 终值分布矩。 |
| `skew` / `kurtosis` | number | 是 | 形状描述子（用于"弯曲"刻画）。 |
| `degenerate` | bool | 是 | 分布退化（如 `std==0` 或全同值）标志。 |

### 4.3 `prob_bands`（L1 · 等概率带）

由 `distribution` 确定性派生。

```json
"prob_bands": {
  "schema_version": "1.2.0",
  "method": "equal_probability_mass",
  "band_count": 5,
  "target_mass": 0.20,
  "bands": [
    {"index": 0, "tag": "Q0-20",  "price_lo": "<float>", "price_hi": "<float>", "prob_mass": 0.20},
    {"index": 1, "tag": "Q20-40", "price_lo": "<float>", "price_hi": "<float>", "prob_mass": 0.20}
  ],
  "current": {
    "index": 2, "tag": "Q40-60",
    "price_lo": "<float>", "price_hi": "<float>",
    "position_in_band_pct": "<float>"
  },
  "band_index": 2,
  "shape": {
    "mean": "<float>", "median": "<float>", "mode": "<float>",
    "quantiles": {"0.05": "<q05>", "0.25": "<q25>", "0.50": "<q50>", "0.75": "<q75>", "0.95": "<q95>"},
    "skew": "<float>", "kurtosis": "<float>",
    "prob_below": "<float>", "prob_above": "<float>"
  },
  "degenerate": false,
  "mode": "static_reference"
}
```

| 字段 | 类型 | 必填 | 语义 |
|------|------|------|------|
| `method` | string | 是 | `"equal_probability_mass"`。 |
| `band_count` / `target_mass` | int / number | 是 | 带数与其目标概率（`target_mass = 1/band_count`）。 |
| `bands[]` | array | 是 | 按 `index` 升序；`price_lo < price_hi`；相邻带**端点相接**（`bands[i].price_hi == bands[i+1].price_lo`）。 |
| `current` | object | 是 | 当前价落入的带。 |
| `band_index` | int | 是 | `∈ [0, band_count-1]`，冗余便捷字段。 |
| `shape` | object | 是 | 分布形状摘要（"弯曲"程度）。 |
| `degenerate` | bool | 是 | 继承 `distribution.degenerate`。 |
| `mode` | string | 是 | 恒 `"static_reference"`。 |

**与 fib 的本质区别**：fib 边界按**价格**线性均分；`prob_bands` 边界按**概率质量**均分。二者并行存在、互不覆盖。

### 4.4 `belief`（L2 · 贝叶斯信念 · 参考快照）

Producer 侧写入的是**参考快照**；Consumer 侧重算为 `mode:"dynamic"`。

```json
"belief": {
  "schema_version": "1.2.0",
  "states": ["UP", "DOWN", "RANGE"],
  "prior": {"UP": "<float>", "DOWN": "<float>", "RANGE": "<float>"},
  "prior_source": "mc_p_up",
  "evidence": [
    {"name": "regime", "value": "<regime>", "spread": "<float>",
     "likelihood": {"UP": "<float>", "DOWN": "<float>", "RANGE": "<float>"}}
  ],
  "likelihood": {"UP": "<float>", "DOWN": "<float>", "RANGE": "<float>"},
  "posterior": {"UP": "<float>", "DOWN": "<float>", "RANGE": "<float>"},
  "edge": {"argmax": "UP", "value": "<float>", "spread": "<float>"},
  "threshold_tau": "<number>",
  "verdict": "NO_EDGE",
  "advisory": true,
  "decay_half_life_h": "<number>",
  "generated_utc": "<iso-utc>",
  "expires_utc": "<iso-utc>",
  "mode": "static_reference"
}
```

| 字段 | 类型 | 必填 | 语义 |
|------|------|------|------|
| `states` | array | 是 | 固定 `["UP","DOWN","RANGE"]`。 |
| `prior` | object | 是 | 归一化先验，**锚定** `p_up`（§9.1）。 |
| `prior_source` | string | 是 | 先验来源标识（`"mc_p_up"`）。 |
| `evidence[]` | array | 是 | 证据列表；每条含 `name` / `value` / `likelihood`。 |
| `likelihood` | object | 是 | 合成似然（归一化）。 |
| `posterior` | object | 是 | 后验（归一化）。 |
| `edge` | object | 是 | `argmax` 与置信度、`spread`。 |
| `threshold_tau` | number | 是 | 判定阈值（§9 待审批）。 |
| `verdict` | enum | 是 | `UP` / `DOWN` / `RANGE` / `NO_EDGE`。 |
| `advisory` | bool | 是 | 恒 `true`，标记非真理源。 |
| `decay_half_life_h` | number | 是 | 时效衰减半衰期（§9 待审批）。 |
| `generated_utc` / `expires_utc` | string | 是 | ISO-8601 UTC（`+00:00`）。 |
| `mode` | string | 是 | `"static_reference"`（Producer）或 `"dynamic"`（Consumer）。 |

### 4.5 冻结部分（原样保留）

- 既有 **21 个** pair 字段语义不变。
- `fib` 块（schema `1.1.0`）**保留不动**，本规格不引用、不修改、不删除它。
- `regime` 字段保留；L2 将其作为证据之一。

### 4.6 目标结构示意（真实字段锚定）

> ⚠️ 依据项目硬约束"示例须来自真实快照"：下例**既有字段取自真实快照** `mc_D_all_pairs_20261117_0000.json` 的 `EURUSD=X`；**新增字段为结构占位符**（`<...>`），其真实数值以首次生成产物为准，**此处不伪造**。

```json
{
  "EURUSD=X": {
    "current_price": 1.10249,
    "p_up": 38.6, "p_down": 61.4,
    "percentile_rank": 61.4,
    "range_90": [1.08869, 1.11227],
    "regime": "⚡ D STRONG MOMENTUM",

    "distribution": { "...": "<待首次生成>", "degenerate": false },
    "prob_bands":   { "...": "<待首次生成>", "band_count": 5, "mode": "static_reference" },
    "belief":       { "...": "<待首次生成>", "states": ["UP","DOWN","RANGE"],
                      "prior_source": "mc_p_up", "advisory": true,
                      "verdict": "<待首次生成>", "mode": "static_reference" },

    "fib": { "...原 fib 块保持不变...": 0 }
  }
}
```

---

## 5. Consumer 契约（Phase 2 · interface.py）

> 本节定义接口契约；实现属第二阶段，需独立授权。

### 5.1 输入

- 静态原料：`distribution`、`p_up` / `p_down`、`regime`、`fib`（只读）。
- 动态输入（由 Consumer 提供）：当前时刻的 `regime`、外部指标（RSI / MA / 成交量等）、`now_utc`。

### 5.2 输出

- **动态 `belief`**：以静态 `p_up` 为锚点，融合实时证据重算；`mode:"dynamic"`，携带本次 `generated_utc` / `expires_utc`。
- **可复用 L1**：`prob_bands` 为 `distribution` 的确定性函数；若 `band_count` 配置未变可复用，否则按新配置重算。
- **失效标记**：静态快照若 `now_utc > expires_utc`，必须标记为过期，**不得**作为当前判断使用。

### 5.3 规则

- C-1：Consumer **只读** `p_up` / `distribution` / `fib`，绝不回写。
- C-2：动态 `belief` 必须携带 `mode:"dynamic"` 与本次时间戳。
- C-3：数据缺失 / 过期 / 退化时，按 §7 输出 `NO_EDGE`。
- C-4：一次调用只加载一个文件并复用结果，避免 N 次 IO（与 [interface.md](../interface.md) §4.2 一致）。

---

## 6. 不变量与校验规则

实现须在写出前校验；任一失败即按 Fail-closed 处理。

| ID | 不变量 |
|----|--------|
| V-1 | `distribution.quantiles` 键严格递增，值有限且 `> 0`。 |
| V-2 | `distribution` 各矩有限（无 `NaN` / `Inf`）。 |
| V-3 | `prob_bands.bands` 按 `index` 升序；每条 `price_lo < price_hi`；相邻端点相接；首尾覆盖 `distribution` 支撑区间。 |
| V-4 | `Σ bands[i].prob_mass ≈ 1`（容差 ≤ 0.01）；`|prob_mass − target_mass| ≤ 容差`。 |
| V-5 | `band_index ∈ [0, band_count-1]`；`current.position_in_band_pct ∈ [0,100]`；`band_index` 与 `percentile_rank` 自洽。 |
| V-6 | `belief.prior` / `likelihood` / `posterior` 各自 `Σ ≈ 1`（容差 ≤ 0.01），各分量 `∈ [0,1]`。 |
| V-7 | `edge.argmax == argmax(posterior)`。 |
| V-8 | `advisory == true`。 |
| V-9 | `expires_utc > generated_utc`。 |
| V-10 | 新增键集在所有 pair 间一致；既有字段与 `fib` 未被改动。 |

---

## 7. Fail-closed 映射

| 触发条件 | `verdict` | 约束 |
|----------|-----------|------|
| `distribution.degenerate == true` 或 `prob_bands.degenerate == true` | `NO_EDGE` | 不得产生方向信念；不得默认满仓。 |
| `max(posterior) < threshold_tau`（后验平坦） | `NO_EDGE` | 保持中性。 |
| 窄区间 / `range_90` 退化 | `NO_EDGE` | 与既有 fib 的 fail-open 教训一致（见 [interface.md](../interface.md) §4.1）。 |
| `now_utc > expires_utc`（过期） | 消费端拒绝 | 标记过期，**不得**当作当前判断。 |
| 原料缺失 / 校验失败 | `NO_EDGE` | 保守降级。 |

---

## 8. 时间与时效语义

| 字段 | 语义 | 约束 |
|------|------|------|
| `generated_utc` | 该块生成时刻 | ISO-8601 UTC，`+00:00`；沿用既有 UTC 纪律 |
| `expires_utc` | 该块失效时刻 | `> generated_utc`；Consumer 超时即弃用 |
| `decay_half_life_h` | 后验随时间回落的半衰期 | 见 §9.3 |

- 静态块与动态块各自携带时间戳，**不得混用**。

---

## 9. 标定参数（PROPOSED PRIOR — 待 Owner 审批）

> 以下均为先验建议值，**非既定**。请 Owner 审批或修订。Project 原则：参数应尽量由数据/Demo 验证，不凭直觉死定。

### 9.1 先验锚定（由 `p_up` + `spread` + `regime` 推导）

```
spread     = |p_up - p_down| / 100                 # ∈ [0,1]
raw_UP     = p_up / 100
raw_DOWN   = p_down / 100
raw_RANGE  = (1 - spread)^gamma * w_range(regime)  # 单调递减地随 spread 收缩
prior_i    = raw_i / Σ_j raw_j                     # 归一化
```

`w_range(regime)` 建议初值（待审批）：

| regime 倾向 | `w_range` |
|-------------|-----------|
| CONSOLIDATION RANGE | 1.3 |
| NEUTRAL | 1.0 |
| OVERBOUGHT / OVERSOLD | 0.7 |
| STRONG MOMENTUM | 0.5 |

`gamma` 建议初值：`2`。

> 该式即体现你的观察：盘整 ⇒ `spread≈0` ⇒ RANGE 先验高；强动量 ⇒ `spread` 大 ⇒ RANGE 先验收缩、方向先验突出。

### 9.2 似然与阈值

- 似然来源：外部指标（RSI / MA / 成交量）+ `regime`；具体数值需标定，**待审批**。
- `threshold_tau` 建议初值：`0.55`（三态均匀基线为 `0.333`）。**待审批**。

### 9.3 时效衰减

- `decay_half_life_h` 建议初值：`24`（Daily）。**待审批**。
- 衰减公式建议：`posterior_t ∝ posterior_0 · 2^(−Δt / half_life)` 后重新归一化；矛盾证据到达时同样触发回落，避免判断固化。

---

## 10. 向后兼容与边界

- **Additive only**：`schema_version` 升 `1.2.0`；既有字段与 `fib` 保留，`range_90` 语义不变。
- **向前生效**：仅新产物带新增块；历史产物不改写（P-5）。
- **消费兼容**：消费者必须容忍 `distribution` / `prob_bands` / `belief` 缺失（早期产物）——按 §7 降级，不报错。
- **不依赖 Phase 1 冻结**：本规格独立于 [PHASE_1_DATA_CONTRACT_v1.0.md](PHASE_1_DATA_CONTRACT_v1.0.md)，但遵循其 additive / no-rewrite / UTC / fail-closed 纪律。

---

## 11. 明确不在范围

- 删除或修改 `fib` 块与任何既有字段。
- 回溯改写历史 `mc_results/*`。
- 修改 `range_90` / Student-t 算法 / 引擎既有行为。
- `interface.py` 第二阶段动态实现（单独授权）。
- 外部指标数据管线的具体实现。
- 任何实盘下单/执行路径改动。

---

## 12. 开放项与冻结清单

### 12.1 开放项（需 Owner 决定）

- [ ] `band_count` 最终取值（建议 5）。
- [ ] `threshold_tau` 终值（建议 0.55）。
- [ ] `gamma` 与 `w_range` 终值（§9.1）。
- [ ] 似然数值表与其标定方法（§9.2）。
- [ ] `decay_half_life_h` 终值（建议 24h）。
- [ ] 外部指标清单（RSI / MA / 成交量 …）与各自数据来源。
- [ ] Consumer 接口函数签名（Phase 2）。

### 12.2 冻结清单

本文档成为 **FROZEN v1.0** 需满足：

- [ ] §9 全部 PROPOSED PRIOR 经 Owner 审批或修订。
- [ ] §12.1 开放项关闭。
- [ ] Owner 确认 §4 Schema 与 §6 不变量可实施。
- [ ] 明确实现授权范围（Producer 侧 / Consumer 侧分开授权）。

**在以上勾选完成前，不进入实现。**
