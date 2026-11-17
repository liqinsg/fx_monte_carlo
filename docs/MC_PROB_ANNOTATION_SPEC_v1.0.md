# MC 概率标注体系 · 规格 v1.0（Schema 1.2.0）

**Status:** FROZEN v1.0 — 已由 Owner 批准冻结（§12 冻结清单全部勾选）；Producer 侧实现已获授权
**Version:** 1.0（对应 payload `schema_version = "1.2.0"`）
**Revision:** r5 · 2026-11-17 —— 实施 §13.5.3「代码侧待办」C1 / C2：`run_mc()` drift 改为**方案 B（算术漂移 + GBM 半方差修正）**；`expected_price` **保留字段名 + 语义标注**（§4.5）；并在 §4.5 补录两条既有字段的契约语义。**本规格自身的字段名、冻结参数（§9）、标注算法与 `fib` 均不变**，`schema_version` 仍为 `1.2.0`；改动落在引擎 `run_mc()`（见 §13.5.3 实施记录）。r4 · 2026-11-17 —— 并入第三轮外部评审（ChatGPT，P0/P1/P2）有效意见，见 §13.5；此前 r3 见 §13.4，r2 见 §13.1。正文仍以本文件为唯一真理源。
**Project:** `fx_monte_carlo`
**Created:** 2026-11-17
**Scope:** 只定义标注体系（`distribution` / `prob_bands` / `belief`）的字段语义与契约。**不修改**任何现有字段、`fib` 块、算法与数据。实现授权与本文档审批分离。
**Nature:** 实现契约草案，非架构评审、非代码。
**上位依据:** 既有 payload（现为 schema 1.1.0）、[PHASE_1_DATA_CONTRACT_v1.0.md](PHASE_1_DATA_CONTRACT_v1.0.md) 的契约纪律（additive-only / no historical rewrite / fail-closed / 时间戳语义），与 [FIB_MC_DISCUSSION.md](FIB_MC_DISCUSSION.md) 的"中立分析提供者 → 多消费者"哲学。

> **冻结说明：** 本文档 §9 参数已由 Owner 批准（见 §9 与 §12）。Producer 侧实现（`distribution` / `prob_bands` / `belief`）已获授权。Consumer 侧动态重算（[interface.py](../interface.py)）仍属 Phase 2，**需单独授权**。

---

## 0. 背景与定位

### 0.1 现状

- `mc_results/` 中存在两类产物：早期**无标注**原始 MC，与近期使用 **Fibonacci 网格**标注（`fib` 块，schema 1.1.0）的产物。
- MC 引擎本身即概率模型：每个 pair 已输出 `p_up` / `p_down` / `percentile_rank` / `range_90` / `var_95` / `cvar_95` / `touch_*` / `expected_price` / `regime`（见 [fx_monte_carlo.py](../fx_monte_carlo.py) `run_mc()`）。
- Fib 标注以 `range_90` 为坐标，按**价格线性**比例 `[0,.236,.382,.5,.618,.786,1.0]` 切成 6 段（见 [fib_mc_segment.py](../fib_mc_segment.py)）。

**基准产物（事实核对）**：本规格的 `1.1.0` 基准由其**形态**定义，而非某个具体文件——即任一由 [fib_mc_segment.py](../fib_mc_segment.py) 产出的 `mc_results/mc_{D,W,M}_all_pairs_*.json`：`metadata.schema_version == "1.1.0"` 且含 `fib_segmentation` 块与每 pair 的 `fib` 子块。本地检出所见的 `mc_results/mc_D_all_pairs_20261117_0000.json` 即属此类（`schema_version == "1.1.0"`，含 `fib_segmentation`）。注意 `mc_results/` 为**生成产物**（受 `max_history_files` 上限轮转），故本规格**不依赖**任何具体文件在任一检出中留存。上位契约 [PHASE_1_DATA_CONTRACT_v1.0.md](PHASE_1_DATA_CONTRACT_v1.0.md) 的落地状态以其自身文件为准；本规格只遵循其纪律，不改动它。

### 0.2 动机

既然 MC 是概率模型，标注就应以**概率**而非**几何**组织。Fib 的线性网格与概率分布无关，属于"直线"切分。本规格引入**概率（弯曲）**标注：

1. **L1 概率分位带**：以 MC 终值分布的**等概率质量**切带，边界由概率密度决定（真正"弯曲"）。
2. **L2 贝叶斯信念层**：以 MC 的 `p_up` 为**先验锚点**。Producer 侧无外部指标，似然恒等退化为均匀（`regime` 仅作**上下文**、不作方向证据，§4.4.1）；Phase 2 再由 Consumer 引入外部指标做真实证据更新，得到 advisory 的方向信念。

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
| 概率差 | `spread` | $\lvert p\_up - p\_down \rvert / 100 \in [0,1]$，量化"方向强弱" |
| 窄区间门限口径 | `range_90_pct` | $(q95 - q05) / current\_price \times 100$，单位**百分比（%）**（非比例）；见 §4.3.2 |
| 先验 | `prior` | L2 初始状态分布，由 `p_up` 锚定 |
| 似然 | `likelihood` | $P(E \mid S_i)$；**存储为归一化权重**（§4.4）。 |
| 后验 | `posterior` | $P(S_i \mid E)$，归一化 |
| 置信阈值 | `threshold_tau` | 后验达到即判定的阈值 |
| 状态 | `states` | `{UP, DOWN, RANGE}` |

> 观察：`regime` 与 `spread` 强正相关——盘整 ⇒ `spread≈0`；强动量 ⇒ `spread` 大。故 `regime` 作为 `spread` 的**离散佐证标签**，与 `p_up` **同源**，不引入第二真理源。

> **`p_up` 平价归属（语义告诫）**：既有引擎 `p_up = count(final > current) / N`，`p_down = 100 − p_up`，故 `final == current` 的路径**计入 DOWN**。这是引擎既有事实，本规格**不改动**（P-1）。
> **"锚定"定义**：归一化后的方向先验与 `p_up` / `p_down` **成正比**（非相等），比例由 RANGE 项与 `w_range` 调制；`p_up` 仍是方向概率的唯一真理源（P-2）。

### 2.1 数据分层与压缩程度（防误读）

| 名称 | 实际含义 | 压缩程度 |
|------|----------|----------|
| MC terminal paths | `run_mc()` 的原始模拟终值路径（`simulations` 条） | **原始样本，不落盘** |
| `distribution` | 由原始路径汇总的**压缩摘要**（9 分位 + 4 矩 + 2 形状量 + 生成参数 + `min`/`max`） | **有损**，**无法**精确恢复经验分布或样本计数 |
| `prob_bands` | 由 `distribution` 摘要**插值构造**的**近似**等概率带 | 近似；`prob_mass` 为**构造值**（§4.3.1-3） |
| `belief` | 基于先验与证据的信念状态（advisory，P-2） | 参考快照 |

> **术语纪律**：`distribution` **不是**完整的终值样本，只是**压缩摘要**；下游**不得**假定可从中恢复原始分布、直方图或样本频数。`prob_bands` 是摘要的**近似**派生，**不是**实测样本分位。`belief` 的 `posterior` 是 advisory 信念分布，**不是**方向概率。

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
    "threshold_tau": 0.55,
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
| `annotation.threshold_tau` | number | 是 | 置信阈值（§9.2，冻结值 `0.55`）。 |
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
| `simulations` / `forecast` / `student_t_df` | int | 是 | 回显生成参数，便于复算与审计。约束：`simulations > 0`（且与样本数一致）、`forecast > 0`、`student_t_df > 2`（否则无有限方差，见 §4.2.1）。 |
| `quantiles` | object | 是 | 键为小数概率字符串（`"0.05"`）；键**恰为固定键集**且数值**随概率非递减**，值均为**有限正数**（"键顺序正确" ≠ "值顺序正确"，详见 §6 V-1）。 |
| `mean` / `std` / `min` / `max` | number | 是 | 终值分布统计量；定义见 §4.2.1。`min`/`max` 为有限正数且 `min ≤ max`、`std ≥ 0`。 |
| `skew` / `kurtosis` | number | 是 | 形状描述子；定义见 §4.2.1。 |
| `degenerate` | bool | 是 | 分布退化（如 `std == 0` 或全同值）标志。 |

#### 4.2.1 统计量计算定义（固定口径，防"同 Schema 异数值"）

各实现必须采用**同一口径**，否则会出现同样的 Schema、不同的数值：

| 字段 | 定义 |
|------|------|
| `std` | **总体**标准差（`ddof = 0`，即 $\sqrt{\frac{1}{n}\sum (x_i-\bar{x})^2}$），**非**样本标准差。 |
| `skew` | **总体标准化三阶矩**（Fisher–Pearson，无偏性修正**不做**）：$\frac{1}{n}\sum \left(\frac{x_i-\bar{x}}{\sigma}\right)^3$。 |
| `kurtosis` | **超额（Fisher）峰度**：$\frac{1}{n}\sum \left(\frac{x_i-\bar{x}}{\sigma}\right)^4 - 3$。**正态分布 = 0**（**非** Pearson 定义的 3）。 |
| `quantiles` | 采用 **numpy 默认 `linear`** 插值分位数（`np.percentile(..., method="linear")`）于小数概率 $\times 100$ 处。 |
| `mean` / `min` / `max` | 样本算术均值 / 最小值 / 最大值。 |

> 上表为**已实现口径的事实固定**（P-1：不改算法），目的仅是消除歧义、供 Consumer 复算对齐。`student_t_df ≤ 2` 时拒绝产出（无有限方差，继续运行会静默产生无意义扰动）。

### 4.3 `prob_bands`（L1 · 等概率带）

由 `distribution` **确定性近似**派生（分位线性插值 + 经验众数；规则见 §4.3.1）。

> **近似语义（必读）**：本方法产出的是**近似等概率分位带**——边界由已存 9 个分位点**线性插值**得到，**不是**对原始模拟样本重新计数得到的精确等概率带。因此 `prob_mass` 是**构造值**，**不代表**实际样本命中比例恰为 `1/N`（§4.3.1-3）。
> **命名保留**：字段 `method` 的值**保留** `"equal_probability_mass"`（P-1：改名即破坏已冻结契约）；其"近似"性质由本段与 §2.1 明确，**不通过改名表达**。

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

#### 4.3.1 派生规则（确定性近似 · 实现细则）

由 `distribution.quantiles`（9 个键）确定性地派生，**不重跑模拟**：

1. **分位函数** $Q(p)$：以已存分位点为锚，两端锚定 `distribution.min`（$p{=}0$）与 `distribution.max`（$p{=}1$），中间对相邻已存分位做**线性插值**。
2. **带边界**：$b_k = Q(k/N)$，$k = 0 \dots N$（$N$ = `band_count`）。相邻带**共享端点**，故 `bands[i].price_hi == bands[i+1].price_lo`；首带下界 = `min`，末带上界 = `max`。
3. **`prob_mass`**：按构造恒为 `target_mass = 1/N`（**构造值，非实测**），故 $\sum = 1$，**不受分位四舍五入影响**。Consumer **不得**将其当作实际命中概率。
4. **`band_index`**：唯一真理源是 `percentile_rank`（$P(\text{final} \le \text{current})$）。`band_index = clamp(⌊percentile_rank / (100/N)⌋, 0, N−1)`；`percentile_rank` 须 ∈ `[0,100]`。
5. **`current.position_in_band_pct`**：$(\text{current} - lo)/(hi - lo) \times 100$，clamp 到 `[0,100]`；零宽带取 `50.0`（§4.3.1-11）。
6. **`shape.mode`**：由分位点无原始样本可算真众数，采用 **Pearson 经验式** $\text{mode} \approx 3 \cdot \text{median} - 2 \cdot \text{mean}$。**字段名 `mode` 保留**（P-1：不改名），但其语义为**经验估计值**，**不是**真实样本众数，**不得**用于直接推断"最高概率价格"。
7. **`shape.prob_below` / `prob_above`**：分别取 `percentile_rank` 与 $100 - \text{percentile_rank}$。
8. **`degenerate`**：继承 `distribution.degenerate`；若派生边界不可分辨（非严格递增）则亦置 `true`（退化输出结构见 §4.3.1-11）。
9. **端点归属**：各带定义为半开区间 $[price\_lo,\ price\_hi)$，仅**末带**取闭区间 $[price\_lo,\ price\_hi]$。
10. **`current` 定带与自洽**：一律由 `percentile_rank` clamp 定带（**不依赖几何查找**）；若几何位置与 `percentile_rank` 冲突，**以 `percentile_rank` 为准**。但 `current` 与所定带必须**结构自洽**：`current.index == band_index`、`current.price_lo == bands[band_index].price_lo`、`current.price_hi == bands[band_index].price_hi`。`position_in_band_pct` **仅**描述价格在带内的**几何位置**，**不具**重新确定概率带归属的权力。
    - **一致性 fail-closed**：`percentile_rank` 与 `current_price` 的几何落点必须**相容**（允许 ±1 带容差，以吸收分位线性插值 + 取整误差）。超出容差即视为**输入自相矛盾**并**拒绝**，**不得**用 `clamp` 将矛盾隐藏成 `position_in_band_pct = 0/100`。
11. **退化输出结构（完整定义）**：当 `degenerate == true` 时：
    - `bands[]` **仍保持 N 个元素**（结构不变，仅几何不可分辨：`price_lo == price_hi`）；此时 **V-3 的 `price_lo < price_hi` 豁免**；
    - `current.position_in_band_pct` 取 `50.0`；
    - `belief.verdict` 必为 `NO_EDGE`（§7）；
    - 该退化标志**必须**并入 `belief` 的退化判定输入：`effective_degenerate = distribution.degenerate OR prob_bands.degenerate`。**任一为真即 fail-closed**——不得因 `distribution.degenerate == false` 而漏判（例如仅因输出取整使相邻边界相等）。

#### 4.3.2 窄区间门限口径 `range_90_pct`

Fail-closed 的"窄区间"判据使用 `range_90_pct`，其定义**唯一**为：

```
range_90_pct = (q95 - q05) / current_price * 100     # 单位：百分比（%）
```

其中 `q05` / `q95` = `distribution.quantiles["0.05"]` / `["0.95"]`，`current_price` = 当前价。

- **与既有 fib 口径一致**：既有 fib 的 `range_90_pct`（schema 1.1.0）为 `(range_90.upper − range_90.lower) / current_price × 100`；因 `range_90 = [q05, q95]`（`confidence = 0.90`），二者**数值相同**。本规格沿用同一口径，**不引入第二套宽度定义**。
- **单位是百分比，不是比例**：门限 `1.2` 即 **`1.2%`**。
- **分母是 `current_price`**（**非** `mean`、**非** 价差绝对值）。
- **无效输入 fail-closed**：当 `current_price ≤ 0`、`q05`/`q95` 缺失或非有限、或无法计算（`None`）时，**不得**判为"不窄"——一律视为**不可判定** → `verdict = NO_EDGE`（§7）。**"不知道区间宽度" ≠ "区间不窄"。**

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
| `likelihood` | object | 是 | 合成似然，以**归一化权重**存储（用于贝叶斯相乘）；Producer 侧恒等退化为均匀 `1/3`（§4.4.1），**不作方向证据**。 |
| `posterior` | object | 是 | 后验（归一化）。 |
| `edge` | object | 是 | `argmax` / `value` / `spread`。不变量：`argmax == argmax(posterior)`、`value == max(posterior)`、`spread == max(posterior) − 次大(posterior)`（见 §6 V-7）。 |
| `threshold_tau` | number | 是 | 判定阈值（§9.2，冻结值 `0.55`）；须有限且 ∈ `[0,1]`。 |
| `verdict` | enum | 是 | `UP` / `DOWN` / `RANGE` / `NO_EDGE`；**必须**与 §7 判定优先级规则一致（由 `degenerate` / 窄区间 / 后验平坦 / `argmax` 推出，不得残留旧结果）。 |
| `advisory` | bool | 是 | 恒 `true`，标记非真理源。 |
| `decay_half_life_h` | number | 是 | 时效衰减半衰期（§9.3，冻结值 `24`）；须有限且 `> 0`。 |
| `generated_utc` / `expires_utc` | string | 是 | ISO-8601 UTC（`+00:00`）。 |
| `mode` | string | 是 | `"static_reference"`（Producer）或 `"dynamic"`（Consumer）。 |

#### 4.4.1 派生规则（Producer 侧 · 无外部指标）

方向与动量强弱是**两个概念**：`regime` 只表征动量强弱，**不含方向信息**。因此在 Producer 侧（尚无外部指标）似然退化：

1. **先验 `prior`**：按 §9.1 由 `p_up` / `p_down` / `spread` / `w_range(regime)` 推导并归一化（`prior_source = "mc_p_up"`）。
2. **似然 `likelihood`**：**恒等退化为均匀** `{UP: 1/3, DOWN: 1/3, RANGE: 1/3}`——即 `regime` 不作为方向的证据；其"强弱"信息已前置进入先验的 `w_range`。`evidence` 仍列出 `regime` 以留痕，但其 `likelihood` 为均匀值。
3. **后验 `posterior`**：$P(S_i) \propto \text{prior}_i \cdot \text{likelihood}_i$，归一化。均匀似然下 $\text{posterior} = \text{prior}$（L2 不引入第二真理源）。
4. **`edge`**：`argmax = argmax(posterior)`；`value = max(posterior)`；`spread = max(posterior) − 次大(posterior)`（非负置信边际）。
5. **`verdict`**（§7 Fail-closed）：`degenerate` / 窄区间（`range_90_pct < 1.2`）/ `max(posterior) < threshold_tau` 任一成立 → `NO_EDGE`；否则取 `argmax`。
6. **时效**：`expires_utc = generated_utc + decay_half_life_h` 小时。

> Phase 2（Consumer）在具备外部指标（RSI / MA / 成交量）后，用真实标定的似然替换均匀退化，并按 §9.3 做时效衰减。

### 4.5 冻结部分（原样保留）

- 既有 **21 个** pair 字段语义不变。
- `fib` 块（schema `1.1.0`）**保留不动**，本规格不引用、不修改、不删除它。
- `regime` 字段保留；L2 将其作为**上下文**记录（在 `evidence` 中留痕），其"强弱"信息仅进入先验的 RANGE 权重 `w_range`（§9.1），**不作为方向的证据**——Producer 侧似然恒等退化为均匀（§4.4.1），故 `regime` 不改变后验的方向。
- **打标顺序（顺序要求）**：`fib` 打标（1.1.0）**先于**概率打标（1.2.0）。两个阶段都**只补不降**：仅当既有 `schema_version` **更低**时才写入本阶段版本，**绝不**下调更高版本（见 §10）。
- `ann_drift_pct`（既有字段）语义 = **年化算术漂移** μ。由历史对数收益均值 $m$ 与每步方差 $\sigma^2$ 换算：$\mu = (m + \tfrac{1}{2}\sigma^2)\cdot\text{periods\_year}$（**方案 B**，§13.5.3 C1）。模拟所用的每步对数漂移为 $\mu/\text{periods\_year} - \tfrac{1}{2}\sigma^2 = m$，即**模拟对数收益均值与历史样本一致**；字段名保留（P-1）。注意：这是**定义修正**，其**数值**会由此变化（原实现误将 $m$ 当作算术漂移并再减 $\tfrac{1}{2}\sigma^2$，导致系统性下偏）。
- `expected_price`（既有字段）语义 = MC 终值的**有限样本经验均值**，**不是**可靠的理论期望：Student-t 厚尾下 $E[e^{X}]$ 理论不存在，样本均值随重抽样不稳定（§13.5.3 C2）。字段名保留（P-1）；需稳健位置量时应改取 `distribution.quantiles["0.50"]`（中位数）。

### 4.6 目标结构示意（真实字段锚定）

> ⚠️ 依据项目硬约束"示例须来自真实快照"：下例**既有字段取自真实快照** `mc_D_all_pairs_20261117_0000.json` 的 `EURUSD=X`（生成产物快照；若该文件已随轮转移除，可改用任一 `schema_version=="1.1.0"` 产物核对同一形态）；**新增字段为结构占位符**（`<...>`），其真实数值以首次生成产物为准，**此处不伪造**。

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

### 5.4 消费语义约束（L1 与 L2 不得混用）

- **L1 是概率分布的解释层，L2 是证据融合层**，二者**不可互相替代**：
  - L1（`prob_bands`）只说明当前价在终值分布中的**分位位置**；
  - L0 的 `p_up` / `p_down` 才是方向概率的**唯一真理源**（P-2）；
  - L2（`belief`）只说明**证据是否达到判定阈值**。
- 三者**可以并存而不矛盾**：价格处于高分位 ≠ 方向信念达到阈值 ≠ 未来上涨概率。例如「L1 显示当前价位于 `Q80–100`、L0 显示 `p_up = 65%`、L2 显示 `verdict = NO_EDGE`」并不矛盾。
- **禁止**把 `belief.verdict == "UP"` 解释为"未来上涨概率 = `posterior.UP`"；`posterior` 是 advisory 信念分布，**不是**方向概率。
- **禁止**把 `prob_bands.bands[i].prob_mass` 当作实测命中概率（其为构造值，§4.3.1-3）。
- **禁止**把 `shape.mode` 当作真实样本众数或"最高概率价格"（§4.3.1-6）。

---

## 6. 不变量与校验规则

实现须在写出前校验；任一失败即按 Fail-closed 处理。

| ID | 不变量 |
|----|--------|
| V-1 | `distribution.quantiles` 键**恰为固定键集**且数值**随概率非递减**；每题值均为**有限正数**。（**键顺序正确 ≠ 值顺序正确**：值逆序会使插值产生错误带边界，必须拒绝。） |
| V-2 | `distribution` 各统计量有限（无 `NaN` / `Inf`）；`min` / `max` 为**有限正数**且 `min ≤ max`；`std ≥ 0`；且 **`min ≤ q01 ≤ q05 ≤ … ≤ q99 ≤ max`**（分位值须被 `min`/`max` 括住并自身非递减）。 |
| V-3 | `prob_bands.bands` 按 `index` 升序；每条 `price_lo < price_hi`（`degenerate == true` 时**豁免**，见 §4.3.1-11）；相邻端点相接；首尾覆盖 `distribution` 支撑区间。 |
| V-4 | `Σ bands[i].prob_mass ≈ 1`（容差 ≤ 0.01）；$\lvert prob\_mass - target\_mass \rvert \le$ 容差。 |
| V-5 | `band_index ∈ [0, band_count-1]`；`current.position_in_band_pct ∈ [0,100]`；`current.index == band_index`；`current.price_lo/hi` 与 `bands[band_index]` 一致；`percentile_rank ∈ [0,100]` 且与 `current_price` 的几何落点**相容**（超过 ±1 带容差即**拒绝**，不得用 `clamp` 掩盖矛盾）。 |
| V-6 | `belief.prior` / `likelihood` / `posterior` 各自 `Σ ≈ 1`（容差 ≤ 0.01），各分量 `∈ [0,1]`，且**全部为有限数值**。 |
| V-7 | `edge.argmax == argmax(posterior)`；`edge.value == max(posterior)`；`edge.spread == max(posterior) − 次大(posterior)`（非负）。 |
| V-8 | `advisory == true`。 |
| V-9 | `expires_utc > generated_utc`；硬 TTL 边界为**闭左**：`now_utc ≥ expires_utc` 即视为**过期**（§7 / §9.3）。 |
| V-10 | 新增键集在所有 pair 间一致；既有字段与 `fib` 未被改动。 |
| V-11 | `verdict` **必须**与 §7 判定优先级规则一致：`degenerate` → 窄区间 → 后验平坦 → 否则 `argmax`。不得出现"`posterior` 已更新但 `verdict` 仍是旧结果"的不一致。 |
| V-12 | `threshold_tau` / `decay_half_life_h` / `edge.value` / `edge.spread` / `range_90_pct` 均为有限数值；参数边界 `0 ≤ tau ≤ 1`、`gamma > 0`、`half_life_h > 0`、`range_90_pct ≥ 0`、`range_90_pct` 为 `None` 时按**不可判定**处理（§4.3.2）。 |
| V-13 | `distribution` 参数有效：`simulations` 为正整数且与样本数一致；`forecast` 为正整数；`student_t_df > 2`。 |
| V-14 | 退化输出结构：`degenerate == true` 时 `bands[]` **仍为 N 个元素**、`current.position_in_band_pct == 50.0`、`verdict == NO_EDGE`；且 `belief` 的退化输入为 `distribution.degenerate OR prob_bands.degenerate`（任一为真即 fail-closed）。 |

---

## 7. Fail-closed 映射

| 触发条件 | `verdict` | 约束 |
|----------|-----------|------|
| `distribution.degenerate == true` 或 `prob_bands.degenerate == true` | `NO_EDGE` | 不得产生方向信念；不得默认满仓。 |
| `max(posterior) < threshold_tau`（后验平坦） | `NO_EDGE` | 保持中性。 |
| 窄区间（`range_90_pct < 1.2`）**或宽度不可用**（`None` / 非有限） | `NO_EDGE` | 与既有 fib 的 fail-open 教训一致（见 [interface.md](../interface.md) §4.1）。**"不知道宽度" ≠ "不窄"**。 |
| `now_utc ≥ expires_utc`（过期） | 消费端拒绝 | 标记过期，**不得**当作当前判断。 |
| 原料缺失 / 校验失败 | `NO_EDGE` | 保守降级。 |

> **判定优先级（自上而下，任一命中即 `NO_EDGE`）**：`effective_degenerate` → 窄区间（`range_90_pct < 1.2`，含宽度不可用）→ 后验平坦（`max(posterior) < threshold_tau`）→ 否则取 `argmax`。

#### 7.1 `verdict` 推导（与 §6 V-11 一致）

| 条件（自上而下，任一命中即 `NO_EDGE`） | `verdict` |
|----------------------------------------|-----------|
| `effective_degenerate == true`（`distribution` 或 `prob_bands` 任一退化） | `NO_EDGE` |
| 窄区间：`range_90_pct < 1.2`，或 `range_90_pct` 不可用（`None` / 非有限） | `NO_EDGE` |
| 后验平坦：`max(posterior) < threshold_tau` | `NO_EDGE` |
| 以上均不成立 | `argmax(posterior)` |

> `verdict` 必须由**当前** `posterior` 与上述输入即时推出，**不得**残留旧结果（§6 V-11）。

---

## 8. 时间与时效语义

| 字段 | 语义 | 约束 |
|------|------|------|
| `generated_utc` | 该块生成时刻 | ISO-8601 UTC，`+00:00`；**必须显式存在**，缺失即拒绝（见下）。 |
| `expires_utc` | 该块失效时刻 | `= generated_utc + decay_half_life_h`；`> generated_utc`；过期边界为**闭左**：`now_utc ≥ expires_utc` 即弃用。 |
| `decay_half_life_h` | 后验随时间回落的半衰期 | 见 §9.3 |

- 静态块与动态块各自携带时间戳，**不得混用**。
- **时间戳校验（fail-closed）**：`generated_utc` 必须是带**显式偏移量**的 ISO-8601；缺失 / 非法 / 裸（naive）时间戳一律**报错**，**不得**静默替换为当前时间或臆断时区。
- **不得补当前时间**：`generated_utc` 缺失时**拒绝**生成该块，**绝不**用 `now()` 兜底——否则无时间戳的旧数据会被伪装成"刚生成"，获得虚假新鲜度。
- **过期边界统一（r4）**：`expires_utc` 是**硬 TTL** 的到期**瞬间**，该瞬间即**失效**（`now_utc ≥ expires_utc`）；因此有效区间为 `Δt < half_life`，软衰减 $\lambda \in (0.5, 1]$。原文"`>` / `Δt ≥ half_life`"并存的边界冲突（恰为 `24:00:00` 时）由此消除。

---

## 9. 标定参数（FROZEN v1.0）

> 以下参数已由 Owner 批准并冻结，为 Producer 侧既定实现值。Phase 2 引入外部指标标定后若需调整，须另行修订本表并重新冻结。

### 9.1 先验锚定（由 `p_up` + `spread` + `regime` 推导）

```
spread     = |p_up - p_down| / 100                 # ∈ [0,1]
raw_UP     = p_up / 100
raw_DOWN   = p_down / 100
raw_RANGE  = (1 - spread)^gamma * w_range(regime)  # 单调递减地随 spread 收缩
prior_i    = raw_i / Σ_j raw_j                     # 归一化
```

`w_range(regime)` 冻结值：

| regime 倾向 | `w_range` |
|-------------|-----------|
| CONSOLIDATION RANGE | 1.3 |
| NEUTRAL | 1.0 |
| OVERBOUGHT / OVERSOLD | 0.7 |
| STRONG MOMENTUM | 0.5 |

`gamma` 冻结值：`2`。

`w_range(regime)` 匹配规则：对 `regime` 字符串**先大写、再子串匹配**；命中顺序即上表顺序（CONSOLIDATION RANGE → NEUTRAL → OVERBOUGHT → OVERSOLD → STRONG MOMENTUM）。带时间框架前缀的标签（如 `"⚡ D STRONG MOMENTUM"`）不影响匹配；未命中回退 `NEUTRAL = 1.0`。

> 该式即体现你的观察：盘整 ⇒ `spread≈0` ⇒ RANGE 先验高；强动量 ⇒ `spread` 大 ⇒ RANGE 先验收缩、方向先验突出。

> **`w_range` 的定位（r4 · 防重复计权）**：`w_range(regime)` 是**启发式先验修饰项（heuristic prior modifier）**，**不是**一份独立的统计证据。因 `regime` 与 `spread` **同源强正相关**（§2），`spread` 已决定 RANGE 的基础权重，`regime` 只是对同一类市场状态信息做**启发式再调制**——同一组 `p_up` 仅因 `regime` 标签不同，RANGE 原始权重即可相差约 2.6 倍（如 `STRONG MOMENTUM 0.5` vs `CONSOLIDATION RANGE 1.3`）。这**是**有意的先验调整，**不是**两份独立证据的叠加。
> **由此产生的约束**：Phase 2 引入外部指标时，**不得**把 `regime` 再当作一份**独立似然**重复加入；其"强弱"信息已在先验的 `w_range` 中体现（§4.4.1）。

### 9.2 似然与阈值

- **Producer 侧（冻结）**：无外部指标，似然**恒等退化为均匀** `{UP: 1/3, DOWN: 1/3, RANGE: 1/3}`，后验 == 先验（§4.4.1）。
- **Phase 2**：似然来源为外部指标（RSI / MA / 成交量）+ `regime`；具体数值表与标定方法留待 Phase 2 单独授权标定。
- `threshold_tau` 冻结值：`0.55`（三态均匀基线为 `0.333`）。

### 9.3 时效衰减

- `decay_half_life_h` 冻结值：`24`（Daily）。
- **衰减（软性回落）**：令 $\lambda = 2^{-\Delta t / \text{half\_life}} \in (0,1]$（$\Delta t$ = 自 `generated_utc` 起的小时数），则
  $posterior_t \propto \lambda \cdot posterior_0 + (1-\lambda) \cdot prior$，再归一化。
  即证据带来的相对增益随时间**退回到 MC 锚定先验** `prior`。
  **注（r2 修正）**：旧式 `posterior_0 · 2^(−Δt/half_life)` 对所有状态同乘同一系数，归一化后**完全抵消、不会回落**；必须引入基线项 `prior` 才有效。
- **硬性过期 vs 软性衰减（r4 边界统一）**：`expires_utc` 是**硬 TTL**（`generated_utc + half_life` 小时），过期边界为**闭左**：`now_utc ≥ expires_utc` 即弃用（§7）。衰减是 TTL 内的**软性**权重调节：
  - $\Delta t = 0 \Rightarrow \lambda = 1$（无回落）；
  - $0 < \Delta t < \text{half\_life} \Rightarrow \lambda \in (0.5, 1)$（向 `prior` 回落）；
  - $\Delta t \ge \text{half\_life}$（等价于 `now_utc ≥ expires_utc`）→ **直接拒绝**，不再计算回落。
  因此软衰减在有效区间内 $\lambda \in (0.5, 1]$，**不会**触及 $\lambda = 0.5$——原文"$\Delta t = \text{half\_life} \Rightarrow \lambda = 1/2$"与"$\Delta t \ge \text{half\_life}$ 即过期"并存的边界冲突（恰为 `24:00:00` 时）由此消除。
- Producer 侧 `expires_utc = generated_utc + 24h`；Consumer 超时即弃用（§7）。

---

## 10. 向后兼容与边界

- **Additive only**：`schema_version` 升 `1.2.0`；既有字段与 `fib` 保留，`range_90` 语义不变。
- **打标顺序**：Producer 内 `fib`（1.1.0）在前、概率（1.2.0）在后；两模块单独运行（`process()` / `segment_prob_data()`）。**版本只升不降**：任一模块都不得把已存在的更高 `schema_version` 改写为更低值（[fib_mc_segment.py](../fib_mc_segment.py) r2 已修；[prob_mc_segment.py](../prob_mc_segment.py) r3 已修）。
- **版本三分法与高版本整体拒绝（r4 定论）**：读入既有 `schema_version`（metadata 及块级）后，按下列规则处理，**无第四种分支**：
  - **缺失** → 补写为 `1.2.0`；
  - **低于** `1.2.0`（如 `1.1.0`）→ 升级为 `1.2.0`（additive）；
  - **等于** `1.2.0` → 幂等，不改写；
  - **高于** `1.2.0`（如 `1.3.0`）→ **整体拒绝**：抛错终止，**既不降写、也不在未知结构上执行任何 additive 修改**。理由：`schema_version` 更高意味着存在本规格**未知的字段与语义**，"不降级"并不等于"可以安全修改"。
  - **不可解析**（非 `X.Y.Z` 全数字段，如 `"2.0.x"` / `"v1"`）→ **拒绝**，**严禁**按"最小版本"处理（否则 `2.0.x` 会被误判为旧版并被降写）。

  > 一致性要求：同一 payload 内 metadata 与块级（`prob_bands` / `belief`）的版本声明**必须一致**，不得出现"metadata 保留高版本、块级强标 `1.2.0`"的分裂声明。
- **缺原料 fail-closed 拒绝**：概率打标要求每个 pair 均带 `distribution` 原料；任一 pair 缺料即**整体拒绝**（抛错），**绝不**产出「被误标为 1.2.0、但结构不全」的 payload（r3 已实施，见 §13.4）。
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

> **r4 修订边界（本轮）**：本轮**只补契约文本**（公式 / 语义 / 不变量 / 边界 / 命名保留说明 / 消费语义约束）。据此**明确不做**：
> - 不重新设计 Student-t MC 算法、贝叶斯公式或 `w_range` 权重数值；
> - 不改任何冻结参数（§9）、不改任何字段名（含 `shape.mode`、`method`、`prob_mass`，见 §4.3）；
> - 不改 [fx_monte_carlo.py](../fx_monte_carlo.py) 与 [prob_mc_segment.py](../prob_mc_segment.py) 的算法行为；
> - 不为本轮修订新建平行规格文件（同一份回填，避免双真理源）；
> - 不进入 Consumer Phase 2（RSI / MA / 成交量等外部证据的接入与标定）。
>
> 引擎侧代码修订（drift 定义、`expected_price` 语义、YAML 参数校验、数据质量校验等）单独排期，见 §13.5「代码侧待办」。

---

## 12. 开放项与冻结清单

### 12.1 开放项（已关闭）

- [x] `band_count` 最终取值 → `5`（冻结）。
- [x] `threshold_tau` 终值 → `0.55`（冻结）。
- [x] `gamma` 与 `w_range` 终值 → `gamma = 2`；`w_range` 见 §9.1（冻结）。
- [x] 似然数值表与其标定方法 → Producer 侧**恒等退化为均匀 `1/3`**；真实外部指标标定**推迟至 Phase 2**（冻结）。
- [x] `decay_half_life_h` 终值 → `24h`（冻结）。
- [x] 外部指标清单（RSI / MA / 成交量 …）与各自数据来源 → **推迟至 Phase 2**（本规格不实现）。
- [x] Consumer 接口函数签名 → **Phase 2 单独授权时定义**。

### 12.2 冻结清单

本文档成为 **FROZEN v1.0** 需满足（全部完成）：

- [x] §9 全部参数经 Owner 审批（§9 已改标 FROZEN）。
- [x] §12.1 开放项关闭。
- [x] Owner 确认 §4 Schema 与 §6 不变量可实施。
- [x] 明确实现授权范围：**Producer 侧已授权**；Consumer 侧（[interface.py](../interface.py)）待 Phase 2 单独授权。

**冻结签署：** Owner（仅 Owner 可签署；Agent / 第三方模型不得代签）。
**冻结日期：** 2026-11-17

---

## 13. 修订记录与外部评审处置（r2 · 2026-11-17）

### 13.1 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| r1 | 2026-11-17 | 初版冻结（§9 参数固化、§12 勾选、Owner 签署）。 |
| r2 | 2026-11-17 | 并入外部评审（Codex `v1.0.1`）有效意见；修正 §9.3 衰减公式；补 §4.3.1-9/10/11、§7 判定优先级、§9.1 匹配规则、§10 版本单调性；修 §2/V-4 表格转义。**正文以本文件为唯一真理源。** |
| r3 | 2026-11-17 | 并入第二轮外部评审（Codex P1–P3，见 §13.4）：§0.1 基准产物改由**形态**定义；§4.4/§2 `likelihood` 措辞统一；§4.5 `regime` 表述澄清；§10 版本单调性与缺料 fail-closed。代码侧 [prob_mc_segment.py](../prob_mc_segment.py) 修版本单调性 / 缺料拒绝 / 时间戳严格校验。 |
| r4 | 2026-11-17 | 并入第三轮外部评审（ChatGPT，P0/P1/P2，见 §13.5）：补 `range_90_pct` 公式与单位（§2 / §4.3.2）、L1 近似等概率语义（§4.3）、`distribution` 压缩摘要定位（§2.1）、统计量计算口径（§4.2.1）、分位数单调性 / 有效性不变量（§6 V-1/V-2）、`shape.mode` 语义保留（§4.3.1）、`current` 与带索引自洽（§4.3.1）、`verdict`↔`posterior` 推导（§7.1）、TTL 边界闭左统一（§8 / §9.3）、`w_range` 启发式定位（§9.1）、退化输出结构完整定义（§4.3.1）、高版本整体拒绝（§10）、消费语义约束（§5.4）。**不改冻结参数、字段名、算法与 `fib`**；代码侧待办见 §13.5。 |
| r5 | 2026-11-17 | 实施 §13.5.3 C1 / C2 并补录契约语义：`run_mc()` drift 改为**方案 B**（算术漂移 + GBM 半方差修正，使模拟对数收益均值 = 历史样本均值）；`expected_price` 保留字段名并标注"有限样本经验均值、非可靠理论期望"（§4.5）。**字段名 / 冻结参数 / 标注算法 / `fib` 均不变**；`ann_drift_pct` 为**定义修正**（数值随之变化）。实施记录见 §13.5.3。 |

### 13.2 外部评审处置

来源：`docs/MC_PROB_ANNOTATION_SPEC_v1.0.1.md`（Codex 生成）。注意：该文件正文实为**冻结前草稿的回滚**（回退了 r1 的冻结），其净增量为 10 条评审意见；经评审后该平行文件**已废弃并删除**，以消除双真理源。逐条处置：

| # | 评审意见 | 处置 |
|---|----------|------|
| 1 | 需澄清 `1.1.0` 基准与 Phase 1 契约落地状态 | 采纳 → §0.1「基准产物（事实核对）」 |
| 2 | 9 分位无法唯一确定带边界/众数；四舍五入对 `prob_mass` 容差的影响 | 部分采纳 → §4.3 改称「确定性近似」；§4.3.1-3 声明 `prob_mass` 为**构造值**，不受取整影响 |
| 3 | 退化零宽带违反 `price_lo < price_hi`；端点归属；`current` 落在支撑区间外 | 采纳 → §4.3.1-9/10/11 + V-3 豁免 |
| 4 | `w_range` 匹配规则；`final == current` 的归属 | 采纳 → §9.1 匹配规则 + §2 平价归属告诫（**不改引擎**，P-1） |
| 5 | `regime` 与 `p_up` 同源 ⇒ 重复计权 | **不成立 / 已解决** → §4.4.1 已定 Producer 侧似然恒等退化均匀，`regime` 不作方向证据 |
| 6 | 多样证据聚合/独立性假设；「归一化似然」术语 | 部分采纳 → §4.4 `likelihood` 语义澄清；聚合规则属 Phase 2 |
| 7 | 旧衰减式经归一化后恒等、**不会回落** | **采纳（数学修正）** → §9.3 引入基线项 `prior`，并调和硬 TTL 与软衰减 |
| 8 | 「窄区间」缺阈值定义 | 已解决 → §4.4.1-5 冻结 `range_90_pct < 1.2` |
| 9 | 占位符 `"<pending>"` 与「number 必填」自相矛盾 | 已解决 → §4.1 示例已为 `0.55` |
| 10 | `fib_mc_segment.py` 会把 metadata `schema_version` 写回 `1.1.0` | 采纳（含**代码修复**）→ §4.5 顺序要求 + §10；[fib_mc_segment.py](../fib_mc_segment.py) 已改为**不向下覆盖**既有更高版本 |

### 13.3 一并修复的文档缺陷

- §2 `spread` 行与 §6 V-4 行的裸 `|` 破坏表格渲染（V-4 后半句曾被截断）→ 已转义为 `\lvert … \rvert`。
- 删除平行文件 `docs/MC_PROB_ANNOTATION_SPEC_v1.0.1.md`，消除双真理源。

### 13.4 第二轮外部评审处置（r3 · 2026-11-17）

来源：Codex 第二轮评审（P1–P3，经对话转发，非文件）。逐条处置：

| # | 级别 | 评审意见 | 处置 |
|---|------|----------|------|
| 1 | P1 | `segment_prob_data()` 无条件写 `"1.2.0"`，可降级更新的更高版本 | **采纳（含代码修复）** → [prob_mc_segment.py](../prob_mc_segment.py) 增 `_version_tuple`，仅当既有版本**更低**时才写 `1.2.0`；单测 `test_segment_prob_data_does_not_downgrade_schema` |
| 2 | P1 | 缺 `distribution` 时 `annotate_pair()` 静默 no-op，整包仍标 1.2.0（假标） | **采纳（fail-closed 拒绝）** → `annotate_pair()` 缺料即抛 `ValueError`，`segment_prob_data()` 随之**整体拒绝**，绝不产出假标 payload；单测 `test_annotate_pair_without_distribution_is_rejected` / `test_segment_prob_data_rejects_payload_without_distribution` |
| 3 | P1 | 规格 §0.1 引用的基准文件「不存在」，契约测试因此 skip | **部分采纳** → 评审基于**异机检出**（`/Users/liqin/...`）给出；本机该文件**存在**，且 v1.1 / contract 套件**未** skip（仅 1 例 1.2 集成 skip）。已把 §0.1 基准改为**由形态定义**，不再依赖具体文件留存 |
| 4 | P2 | `MC_PROB_DOLA_DISCUSSION.md` 公式截断、模板缺后验、未指向冻结规格 | **采纳** → 补全 `P(E)` 公式、修正 `P(S₃\|E)` 模板、转义坏表格行、加指向冻结规格与阈值差异的说明 |
| 5 | P2 | §4.4.1 与 §4.5 对 `regime` 自相矛盾 | **采纳** → §4.5 改为「上下文记录；仅影响先验 `w_range`，不作方向证据」 |
| 6 | P2 | `_expires_utc()` 静默接受无效 / 裸时间戳 | **采纳** → 改为 `_utc_datetime()` 严格校验（缺失 / 非法 / naive 一律报错，不造时间、不臆断时区），并归一化到 UTC；单测 `test_belief_rejects_naive_and_invalid_timestamps` / `test_belief_normalizes_offset_to_utc` |
| 7 | P3 | `likelihood` 字段「非线性意义上」措辞易混 / 疑似笔误 | **采纳** → §4.4 / §2 统一为「归一化权重（Producer 侧恒等退化为均匀，不作方向证据）」 |

### 13.5 第三轮外部评审处置（r4 · 2026-11-17）

来源：ChatGPT 第三轮评审（P0/P1/P2，经对话转发，非文件；同时覆盖本规格与 `fx_monte_carlo.py` / `prob_mc_segment.py`）。**本轮只处置规格契约文本部分；代码侧意见单列于本节末「代码侧待办」。**

#### 13.5.1 规格契约缺口（逐条处置）

| # | 级别 | 评审意见 | 处置 |
|---|------|----------|------|
| 1 | P0 | `range_90_pct < 1.2` 缺少计算定义（分母 / 单位 / 边界未定） | **采纳（补定义）** → §2 术语表新增口径行；§4.3.2 明确 `range_90_pct = (q95 − q05) / current_price × 100`，单位**百分比（%）**（`1.2` 即 1.2%，非比例），与既有 `fib` 口径一致；并规定 `current_price <= 0` / 缺失 / 非有限时该宽度**不可用**，按 §7 走 `NO_EDGE`。**不改冻结阈值 `1.2`。** |
| 2 | P0 | L1 所谓「等概率带」实为插值近似，非样本实测等概率 | **采纳（补语义，保留命名）** → §4.3 引言新增「近似语义（必读）」：`prob_mass=0.20` 是**构造值**而非实测命中概率；`method` 字段**保留** `"equal_probability_mass"`（改名会破坏已冻结 1.2.0 字段值，违反 P-1），改以文本明确其为**基于插值分位函数的近似**；Consumer **不得**把 `prob_mass` 当作实际命中概率使用。 |
| 3 | P0 | `distribution` 有效性校验不完整（缺分位值单调性等关系约束） | **采纳** → §6 V-1 / V-2 扩写：追加 `min ≤ q01 ≤ q05 ≤ … ≤ q99 ≤ max`、`min/max` 有限正数且 `min ≤ max`、`std ≥ 0`、`simulations > 0`、`forecast > 0`、`student_t_df > 0`、全部分位值有限为正且随概率**非递减**。特别注明：**分位键顺序正确 ≠ 分位值顺序正确**。 |
| 4 | P1 | `shape.mode` 易被误读为真实众数（实为 Pearson 经验估计） | **采纳（补语义，保留命名）** → §4.3.1 明确 `mode ≈ 3·median − 2·mean` 是 **Pearson 经验众数估计**，非样本频数众数 / 直方图 / KDE 结果，**不得**用于直接推断"最高概率价格"；字段名按 P-1 保留。 |
| 5 | P1 | `percentile_rank` 与价格几何位置可能冲突，`position_in_band_pct` 可能被 clamp 掩盖矛盾 | **采纳** → §4.3.1-10 补一致性约束：`current.index == band_index` 且 `current.price_lo/hi == bands[band_index].price_lo/hi`；`position_in_band_pct` 仅描述价格几何位置，**无**重新确定概率带归属之权；实质性不一致（rank 与价格不相容）**fail-closed 拒绝**，不用 clamp 隐藏。 |
| 6 | P1 | `verdict` 缺少完整一致性校验（仅验 `argmax`） | **采纳** → 新增 §7.1「verdict 推导」：按 Degenerate / 窄区间 / `max(posterior) < tau` / 否则 `argmax` 的优先级显式给出 `verdict` 判定表，并追加 V-7 扩展：`edge.value == max(posterior)`、`edge.spread == max(posterior) − 第二大的 posterior`；防止「posterior 已更新、verdict 仍旧」的不一致。 |
| 7 | P1 | 硬 TTL 与软衰减边界不一致（`>` vs `>=`） | **采纳（统一）** → §8 / §9.3 定为**闭左**：`now_utc ≥ expires_utc` 即失效；有效区间内 $\lambda \in (0.5, 1]$，**不会**触及 $\lambda = 0.5$；`Δt ≥ half_life` 等价于硬过期，直接拒绝、不再计算回落。 |
| 8 | P1 | `w_range(regime)` 与 `spread` 同源，可能重复计权 | **采纳（补定位，不改数值）** → §9.1 新增「`w_range` 的定位（r4 · 防重复计权）」：明确 `w_range` 是**启发式先验调节项（heuristic prior modifier）**，**不是**独立统计证据；`regime` 与 `spread` 同源，故 Phase 2 **不得**再把 `regime` 作为一份独立证据重复加入似然。冻结数值不变。 |
| 9 | P1 | `distribution` 被称作"原料"，但其为压缩摘要而非完整分布 | **采纳（补术语分层）** → 新增 §2.1「数据分层与压缩程度（防误读）」：区分 `MC terminal paths`（原始路径）→ `distribution`（**压缩摘要**，无法恢复经验分布）→ `prob_bands`（基于摘要的近似分位带）→ `belief`（信念状态）；并加术语纪律，防止 Consumer 误以为拿到完整模拟分布。 |
| 10 | P2 | 统计量（`std`/`skew`/`kurtosis`/`quantiles`/`mode`）未规定计算口径 | **采纳** → 新增 §4.2.1「统计量计算定义」：`std` 用**总体**标准差（`ddof=0`）；`skew` 用总体标准化三阶矩；`kurtosis` 用 **Fisher 超额峰度**（正态 = 0，非 Pearson 的 3）；`quantiles` 用 numpy 默认 **`linear`** 插值；`mode` 用 Pearson 经验估计。 |
| 11 | P2 | `belief` 数值校验缺有限性检查（不能只靠概率求和判有效） | **采纳** → §4.4 字段表 + §6 V-6 扩写：`prior` / `likelihood` / `posterior` 各分量必须 `math.isfinite`；`edge.value` / `edge.spread` / `threshold_tau` / `decay_half_life_h` 亦须有限且满足各自不变量。 |
| 12 | P2 | 分位带退化的输出结构未完整规定 | **采纳** → §4.3.1 补完整退化定义：相邻边界相等（含四舍五入致相等）→ 该组 `prob_bands.degenerate = true`；`bands[]` **仍恒为 5 个元素**；零宽带处 `position_in_band_pct` 按 §4.3.1-11 处理；并定义 `effective_degenerate = distribution.degenerate OR prob_bands.degenerate`，作为 `belief` 的唯一退化输入（阻塞 §4.3.1 与 belief 之间的退化传递缺口）。 |
| 13 | P2 | 版本兼容性需明确"高版本"边界（不降级 ≠ 可安全改动） | **采纳** → §10 增加「版本三分法与高版本整体拒绝（r4 定论）」：缺失→补写；低→升级；等→幂等；**高→整体拒绝**（不降写、不在未知结构上做 additive 修改）；**不可解析→拒绝**（严禁按最小版本处理）；并要求 metadata 与块级版本声明一致。 |

#### 13.5.2 复核确认（评审中判定"设计合理、建议保留"的部分）

| 设计 | 处置 |
|------|------|
| `copy.deepcopy()` 不污染原始 MC payload | 保留（实现行为，不改）。 |
| Producer 侧 likelihood 恒等均匀、`posterior == prior` | 保留（§4.4.1 已定；评审确认"非计算错误，但不得当作独立确认信号"，已入 §5.4 消费语义约束）。 |
| `p_up`/`p_down` 为方向概率唯一真理源 | 保留（P-2）。 |
| UTC 显式偏移检查（删除缺失时补当前时间的 fallback） | 保留（§8；代码侧 r3 已实施）。 |
| 五条概率带 `band_count=5` | 保留（冻结参数，不改）。 |
| Pearson 经验式 mode / Fisher 超额峰度 / `static_reference` | 保留（补语义与口径定义，不改算法）。 |

#### 13.5.3 代码侧待办（本轮不改代码 · 单独排期）

以下评审意见针对 [fx_monte_carlo.py](../fx_monte_carlo.py)：**已受理，但按本轮边界（§11）暂不修改**，留待代码修订步骤统一实施，避免未经审议即改动冻结 Schema 语义。

| # | 级别 | 位置 | 待办（已受理） |
|---|------|------|------|
| C1 | P0 | `run_mc()` drift | **Owner 已裁定采用「方案 B：算术漂移 + 半方差修正」**：先将历史对数收益率转换为算术收益率漂移，再套用 GBM 半方差修正，使模拟对数收益均值与历史样本一致；`ann_drift_pct` 定义须与之一致。须以合成数据验证（已知均值方差 → 校验模拟对数收益均值与累计漂移）。 |
| C2 | P0 | `expected_price` 厚尾 | **Owner 已裁定「保留字段名 + 加语义说明」**：Student-t 厚尾下 $E[e^X]$ 理论不存在，样本均值非稳定理论期望；字段名保留（P-1），但须在契约中标注其"有限样本经验均值、非可靠理论期望"语义，并考虑更稳定统计量。 |
| C3 | P1 | YAML 校验 | 补参数有效性校验：`pairs` 非空且不重复、`simulations` 正整数、`confidence ∈ (0,1)`、`student_t_df > 2`、各 `lookback` 足以计算有效收益率、`forecast` 正整数、`max_history_files` 非负整数；禁止 `int(2.5) → 2` 式静默截断。 |
| C4 | P1 | `fetch_data()` 数据质量 | 清 `inf`/`-inf`、校验全序列为正、索引递增、无重复时间戳、明确是否使用未完成 K 线（D/W/M 须有统一规则）。 |
| C5 | P1 | `range_90` 命名 | 使字段名与真实置信水平一致，或在校验中强制 `CONFIDENCE == 0.90`。 |
| C6 | P1 | 概率字段语义 | 在契约中写明 `percentile_rank`（价格位置）与 `p_down`（`P(final ≤ current)`）实为同一事件的两种表述，`p_up` 用严格 `>`，不得作为两份独立证据重复使用。 |
| C7 | P1/P2 | `save_batch_mc_safely()` 等 | `max_files=0` 语义、观察日志与批次提交的成功关系、单 pair 失败隔离、文件名同分钟覆盖、随机种子加 timeframe、记录实际行情时间范围、区分批次 vs 单项 `generated_utc`、CLI 互斥参数。 |

> **验收要求（与评审一致）**：不能只看 `pytest passed`，还须验证**实际生成的 JSON**；用**合成数据**独立验证 drift、`expected_price`、先验 / 后验、分位带及边界；覆盖 1.1.0 / 1.2.0 / 更高版本三种处理路径；确认既有 `fib` 与字段**无变化**。

**实施记录（r5 · 2026-11-17）**：

| # | 状态 | 落地 |
|---|------|------|
| C1 | **已实施** | [fx_monte_carlo.py](../fx_monte_carlo.py) `run_mc()`：`drift = (mean(log_returns) + 0.5·var(log_returns))·periods_year`（年化**算术**漂移；`var` 取总体方差 `ddof=0`），故 `step_drift = drift/periods_year − 0.5·σ²/periods_year == mean(log_returns)`——每步模拟对数收益均值与历史样本一致。合成数据回归测试见 [tests/test_engine_drift.py](../tests/test_engine_drift.py)（已知均值方差 → 反推 `step_drift` 与历史样本均值一致，并设回归护栏区分旧实现的 $-\sigma^2/2$ 系统性下偏）。语义录入 §4.5。 |
| C2 | **已实施（契约侧）** | `expected_price` **字段名保留**（P-1）；语义录入 §4.5（"有限样本经验均值、非可靠理论期望"）；[fx_monte_carlo.py](../fx_monte_carlo.py) 内注释标注同一语义，稳健位置量指向 `distribution.quantiles["0.50"]`（中位数）。 |
| C3–C7 | **待办** | 仍按本表单独排期，本轮（r5）未动。 |

> r5 只实施 C1 / C2。**C3–C7 未实施**；本规格本轮未改动冻结参数（§9）、字段名、标注算法与 `fib`，`schema_version` 仍为 `1.2.0`。
