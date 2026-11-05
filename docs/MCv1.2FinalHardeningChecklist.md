

要。

而且看完以后，我会把我之前那版 Checklist  **降级成实施层文档** ，而把这份 **MC_FIB v1.2 Action Plan** 作为真正的 v1.2 总设计。

原因很简单：

你这份 Action Plan 已经从「技术优化列表」升级成「风险驱动的发布计划」。

其中有几个点的优先级其实比我前面提的 Metadata 还高。

---

# 我建议的最终优先级

## P0（必须进入 v1.2）

### ① Example Payload Consistency + Invariant Tests

这个我完全同意放第一位。

很多量化项目死于：

文档说的是A

代码算出来是B

而不是死于模型本身。

尤其你已经开始：

schema versioning

external consumers

provider contract

以后：

ratio_pos

range_90_pct

zone_index

这些就是 API。

API 示例错了：

信任直接下降

所以这个优先于 metadata。

---

### ② Fail-Open Gate 修复

这个是我读完后认为最重要的新增点。

之前规格：

range_90_pct < 1.2%

↓

K = 1.0

其实逻辑是：

最低信心

=

最大仓位

确实有点反直觉。

---

我支持：

"multiplier_k": null

而不是：

"multiplier_k": 0.5

原因：

你整个架构正在朝：

Analytics Provider

发展。

那么 Provider 不应该决定：

0.5

0.2

1.0

这些东西。

最中性的表达应该是：

{

  "range_gate": true,

  "risk_model": null

}

然后策略层决定：

skip

half-size

full-size

---

### ③ Stale Data Enforcement

这个应该提升到和 Metadata 同级。

因为这是实盘风险。

例如：

cron死了

generator挂了

Yahoo Finance没更新

但：

latest.json

还在那里。

EA继续下单。

这是典型生产事故。

---

建议：

metadata:

{

   generated_utc: "...",

   expires_utc: "..."

}

不要只给：

fresh:true

因为：

fresh

是时间相关字段。

会过时。

而：

expires_utc

永远能重新计算。

---

### ④ Contract Invariant Tests

这是我觉得最容易被忽略但最值得做的。

建议直接增加：

test_contract_invariants.py

检查：

lower < upper

0 <= ratio_pos <= 1

zone_index in [0..5]

position_in_zone_pct <= 100

range_90_pct >= 0

以及：

zone_index

←

ratio_pos

的一致性。

---

# P1（v1.2主体）

这里我基本同意 Action Plan。

---

## Metadata Expansion

保留。

而且比我之前列得更完整。

建议最终：

metadata:

{

  schema_version

  engine_version

  git_hash

  generated_utc

  as_of_utc

  simulation:

  {

     paths

     lookback

     forecast

     confidence

     distribution

     student_t_df

  }

  provenance:

  {

      data_source

      seed_basis

  }

}

这是很好的审计结构。

---

## Advisory Namespace Cleanup

我现在倾向于：

不要删 risk_model。

改名字。

例如：

advisory:

{

   risk_model:

   {

      multiplier_k:null

   }

}

这样表达非常清楚：

analytics

≠

advisory

---

## Seed Narrative Fix

这一条非常重要。

我发现你们评审里终于有人点到了核心：

当前文档说：

changing seed

captures volatility shifts

严格来说不成立。

真正变化来源：

input data changed

而不是：

seed changed

所以：

### v1.2

修正文档

### v1.3

再考虑：

seed =

hash(

   pair +

   lookback_window

)

---

## Per-Pair Status

我赞成。

增加：

status:

{

   healthy

   narrow_range

   degenerate

   stale

}

比让消费者读五个布尔值简单得多。

---

# P2（不要急）

这一部分我和 Action Plan 100%一致。

---

### Zone 2/3 Concentration

先测。

不要改。

这是典型容易掉进的坑：

发现80%数据在zone 2/3

↓

立刻修改分区

结果：

统计意义变差

---

正确顺序：

先测预测能力

后调模型

---

### Logistic K

不要现在做。

因为：

K已经被降级成 advisory

价值直接下降一档。

---

### ATR Gate

我之前建议过。

现在我也觉得别急。

原因：

当前1.2%阈值

是否真的有问题

还没有数据证明

先收集几个月运行结果。

---

# 我建议的最终 v1.2 Definition of Done

把你的 DoD 再压缩成下面这个版本：

## Blocker（缺一不可）

* [ ] Example payload来源于真实生成数据
* [ ] Invariant tests覆盖所有派生字段
* [ ] Narrow/degenerate不再返回K=1.0
* [ ] Stale-data检测机制落地
* [ ] schema_version升至1.2.0

---

## Required

* [ ] Metadata扩展
* [ ] Provenance扩展
* [ ] Student-t参数暴露
* [ ] seed_basis记录
* [ ] per-pair status
* [ ] git_hash记录

---

## Nice-to-have

* [ ] advisory namespace整理
* [ ] generation_status
* [ ] pair_failures
* [ ] diagnostics

---

**结论：**

如果要定稿，我会以这份 Action Plan 为主，而不是我前面的 Checklist。

最大的变化是优先级重排：

旧排序（偏架构）：

Metadata

→ Freshness

→ Health

→ Quant

新排序（偏生产风险）：

Spec correctness

→ Fail-open removal

→ Stale-data protection

→ Contract tests

→ Metadata

→ Advisory cleanup

对于一个准备进入实盘的 analytics provider，后者明显更符合工程现实。

fx_monte_carlo v1.2 Final Hardening Checklist
Objective

Harden the contract for production use while preserving the core philosophy:

One Analytics Producer → Many Independent Consumers → Shared Neutral Market-State Language

No model redesign. No portfolio engine. No strategy coupling.

P0 (Release Blockers)

1. Fix Spec Example & Add Invariant Tests
   Deliverables
   Replace documentation payload with a real generated snapshot
   Add automated validation for:
   range_90_pct
   ratio_pos
   zone_index
   position_in_zone_pct
   derived zone labels
   Contract Invariants
   range_90[0] < range_90[1]
   0 <= ratio_pos <= 1
   zone_index ∈ [0..5]
   0 <= position_in_zone_pct <= 100
   range_90_pct >= 0
   Success Criteria

Documentation always matches actual implementation.

2. Eliminate Fail-Open Narrow-Range Behavior
   Current Problem
   range too narrow
   → K = 1.0
   → full position size

Lowest confidence should not imply largest exposure.

Deliverables
 Remove automatic K = 1.0
 Return explicit advisory state instead

Preferred output:

{
  "range_gate": true,
  "multiplier_k": null,
  "reason": "range_too_narrow_or_degenerate"
}

Success Criteria
 Narrow-range states never default to full-size exposure
 Consumer must make an explicit decision
3. Stale Data Protection
Deliverables

Add:

{
  "generated_utc": "...",
  "expires_utc": "..."
}

Interface Helpers
 is_snapshot_fresh()
 stale-data detection examples
Contract Rule
Fail closed when data is stale.

Success Criteria
 Consumers can deterministically reject stale analytics
 No dependency on filename ordering
4. Contract Regression Tests
Deliverables

Create:

tests/test_contract_invariants.py

Verify:

 schema structure
 field ranges
 freshness fields
 quality fields
 advisory fields
Success Criteria

Future changes cannot silently break the contract.

P1 (Core v1.2 Features)
5. Metadata Expansion
Add
metadata:
{
  schema_version,
  engine_version,
  git_hash,

  generated_utc,
  as_of_utc,

  simulation:
  {
    paths,
    lookback_days,
    forecast_days,
    confidence,
    distribution,
    student_t_df
  },

  provenance:
  {
    data_source,
    seed_basis
  }
}

Success Criteria

Payload is fully auditable without reading local code.

6. Per-Pair Status Object
   Add
   status:
   {
   state: "healthy",
   stale: false,
   degenerate: false,
   narrow_range: false
   }

Allowed States
healthy
narrow_range
degenerate
stale
invalid

Success Criteria

Consumers can perform a single status check.

7. Risk Model Advisory Cleanup
   Goal

Align payload structure with provider-only philosophy.

Preferred Structure
advisory:
{
  risk_model:
  {
    multiplier_k: null,
    reason: "...",
    advisory: true
  }
}

Contract Rule

Canonical analytics remain:

 range_90
 range_90_pct
 ratio_pos
 zone_index
 breakout
 degenerate
 percentile_rank
 p_up
Success Criteria

Analytics and execution guidance are clearly separated.

8. Correct Seeding Documentation
   Clarify

Current wording should state:

Seed controls reproducibility.
Market-state change comes from changed input data.

Record
provenance:
{
  seed_basis: "pair + trading_day"
}

Success Criteria

No misleading explanation of volatility behavior.

P2 (Research Only)
9. Zone Concentration Study
Measure
 Zone occupancy by pair
 Zone occupancy by timeframe
 Historical stability
 Forward predictive value
Do Not Change Yet
 Fibonacci geometry
 Zone boundaries
 Occupancy balancing
10. Dynamic Range Gate Study

Research only:

range_90_pct
vs
ATR-normalized thresholds

Do not modify production logic until evidence exists.

11. Logistic K-Factor Study

Current:

1.0 → 0.5 → 0.2

Potential future:

K = f(ratio_pos)

Research only.

Explicitly Out of Scope for v1.2
 SQLite migration
 Correlation-aware portfolio sizing
 Cross-pair allocation engine
 GARCH / stochastic volatility models
 Learned K calibration
 Kafka / Redis architecture changes
 Replacing JSON snapshot delivery
Definition of Done (v1.2)
Mandatory
 Spec example generated from real output
 Invariant tests implemented
 Fail-open gate removed
 Stale-data enforcement implemented
 Metadata expanded
 Student-t parameters exposed
 Provenance fields exposed
 Seed basis documented
 Per-pair status implemented
 Schema version bumped to 1.2.0
Optional (if time permits)
 Advisory namespace cleanup
 Generation status reporting
 Pair failure reporting
 Diagnostics block
Recommended Delivery Order
Phase 1 (Safety)
Spec correction
Invariant tests
Fail-open removal
Stale-data protection
Phase 2 (Auditability)
Metadata expansion
Provenance expansion
Student-t transparency
Seed documentation
Phase 3 (Consumer Experience)
Status object
Advisory cleanup
Diagnostics

Release Recommendation: Do not ship v1.2 until all P0 items are complete. P1 items define the actual value of the release. P2 items should generate evidence first and become candidates for v1.3.
