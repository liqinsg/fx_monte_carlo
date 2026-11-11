# MC_FIB v1.2 Action Plan

## Purpose

This document is the master design for `fx_monte_carlo` v1.2 hardening.

It consolidates the recent review cycle into a release plan driven by production risk rather than architectural neatness.

Core philosophy remains unchanged:

- One analytics producer
- Many independent consumers
- One shared neutral market-state language

Non-goals remain unchanged:

- no model redesign
- no portfolio engine
- no strategy coupling

## Executive Decision

v1.2 should be treated as a contract hardening release.

The release order is intentionally:

1. Spec correctness
2. Fail-open removal
3. Stale-data protection
4. Contract regression protection
5. Auditability expansion
6. Consumer ergonomics cleanup

This ordering is deliberate. For an analytics provider approaching production use, correctness and operational safety matter before metadata elegance.

## Final Priority

### P0: Release blockers

1. Example payload consistency
2. Invariant tests for derived fields
3. Eliminate fail-open behavior
4. Stale-data enforcement
5. Contract regression protection

### P1: Core v1.2 value

1. Metadata expansion
2. Provenance expansion
3. Student-t transparency
4. Seed narrative correction
5. Per-pair status
6. `git_hash` recording

### P2: Research only

1. Zone concentration study
2. Dynamic range gate study
3. Logistic K-factor study

## P0 Release Blockers

### 1. Example Payload Consistency

Problem:

- The published example payload must be treated as part of the API.
- If the example says one thing and the generator emits another, consumer trust drops immediately.

Required changes:

- Replace the example payload in `MC_FIB_ARCHITECTURE_AND_STRATEGY_SPEC.md` with a real generated snapshot.
- Ensure the example is copied from actual output rather than stitched manually.

Derived fields that must stay consistent with raw fields:

- `range_90_pct`
- `ratio_pos`
- `zone_index`
- `current_zone.position_in_zone_pct`
- derived zone labels

Success criteria:

- Documentation always matches the implementation.

### 2. Contract Invariant Tests

Problem:

- Derived fields are now effectively API fields.
- Silent drift between formula and payload is unacceptable once consumers depend on the contract.

Required changes:

- Add automated invariant tests, preferably in `tests/test_contract_invariants.py`.
- Update existing v1.1-specific tests so that the future v1.2 transition is intentional rather than blocked by stale version assertions.

Required invariants:

- `range_90[0] < range_90[1]`
- `0 <= ratio_pos <= 1`
- `zone_index in [0..5]`
- `0 <= position_in_zone_pct <= 100`
- `range_90_pct >= 0`
- `zone_index` must be consistent with `ratio_pos`

Success criteria:

- Future changes cannot silently break derived-field correctness.

### 3. Eliminate Fail-Open Behavior

Problem:

- Lowest-confidence states must not imply the largest exposure.
- This applies not only to narrow-range or degenerate outputs, but to any missing or invalid advisory state.

Current anti-pattern to remove:

- narrow range -> `multiplier_k = 1.0`
- degenerate range -> `multiplier_k = 1.0`
- missing analytics -> implied full-size fallback

Preferred v1.2 contract direction:

```json
{
  "range_gate": true,
  "multiplier_k": null,
  "reason": "range_too_narrow_or_degenerate"
}
```

Design intent:

- Provider expresses advisory state explicitly.
- Consumer must make an explicit decision.
- Full-size exposure is never the default for low-confidence states.

Success criteria:

- Narrow or degenerate states never return `K = 1.0`.
- Missing or invalid advisory state never implies full-size exposure.

### 4. Stale-Data Enforcement

Problem:

- Stale analytics are a production risk, not a documentation issue.
- Filename ordering alone is not a sufficient freshness contract.

Required metadata fields:

```json
{
  "generated_utc": "...",
  "expires_utc": "..."
}
```

Why `expires_utc` is preferred over `fresh: true`:

- `fresh` becomes stale as soon as time passes.
- `expires_utc` can always be re-evaluated by any consumer.

Required consumer support:

- `is_snapshot_fresh()`
- stale-data detection examples
- explicit fail-closed rule when data is stale

Success criteria:

- Consumers can deterministically reject stale analytics.
- Freshness no longer depends on filename ordering.

### 5. Contract Regression Protection

Problem:

- Existing contract tests already lock parts of v1.1 behavior.
- v1.2 must expand protection, not accidentally inherit brittle version locks.

Required changes:

- Keep regression tests for schema presence and field ranges.
- Add checks for:
  - freshness fields
  - quality fields
  - advisory fields
- Review and update any test that hard-codes `1.1.0` or the old contract shape.

Success criteria:

- Contract evolution is deliberate.
- Version bumps and advisory changes break tests only when intended.

## P1 Core v1.2 Features

### 6. Metadata Expansion

Target structure:

```json
{
  "metadata": {
    "schema_version": "1.2.0",
    "engine_version": "...",
    "git_hash": "...",
    "generated_utc": "...",
    "as_of_utc": "...",
    "simulation": {
      "paths": 5000,
      "lookback_days": 90,
      "forecast_days": 5,
      "confidence": 0.90,
      "distribution": "student_t",
      "student_t_df": 5
    },
    "provenance": {
      "data_source": "...",
      "seed_basis": "pair + trading_day"
    }
  }
}
```

Success criteria:

- Payload is auditable without reading local code or config.

### 7. Per-Pair Status Object

Goal:

- Let consumers do one explicit health check instead of reading multiple booleans ad hoc.

Target structure:

```json
{
  "status": {
    "state": "healthy",
    "stale": false,
    "degenerate": false,
    "narrow_range": false
  }
}
```

Allowed states:

- `healthy`
- `narrow_range`
- `degenerate`
- `stale`
- `invalid`

Success criteria:

- Consumers can perform a single status check before using the payload.

### 8. Advisory Namespace Cleanup

Goal:

- Align payload structure with provider-only philosophy while preserving the analytical contract.

Preferred structure:

```json
{
  "advisory": {
    "risk_model": {
      "multiplier_k": null,
      "reason": "...",
      "advisory": true
    }
  }
}
```

Canonical analytics should remain:

- `range_90`
- `range_90_pct`
- `ratio_pos`
- `zone_index`
- `breakout`
- `degenerate`
- `percentile_rank`
- `p_up`

Important note:

- This cleanup improves clarity, but it is less urgent than safety and auditability.

### 9. Correct Seeding Documentation

Problem:

- Current wording overstates the role of seed changes.

Correct v1.2 statement:

- Seed controls reproducibility.
- Market-state change comes from changed input data.

Required provenance record:

```json
{
  "provenance": {
    "seed_basis": "pair + trading_day"
  }
}
```

Deferred to later research:

- possible data-derived seed basis such as `pair + lookback_window_hash`

### 10. Student-t Transparency

Problem:

- The generator already depends on Student-t assumptions.
- Consumers need those assumptions exposed in the payload.

Required exposure:

- `distribution`
- `student_t_df`
- simulation path count
- lookback and forecast settings

Success criteria:

- Contract users can audit distribution assumptions directly from the payload.

## P2 Research Only

### 11. Zone Concentration Study

Measure:

- zone occupancy by pair
- zone occupancy by timeframe
- historical stability
- forward predictive value

Do not change yet:

- Fibonacci geometry
- zone boundaries
- occupancy balancing

### 12. Dynamic Range Gate Study

Research only:

- compare `range_90_pct` against ATR-normalized thresholds

Do not change production logic until evidence exists.

### 13. Logistic K-Factor Study

Current form:

- `1.0 -> 0.5 -> 0.2`

Possible future form:

- `K = f(ratio_pos)`

Do not implement in v1.2.

## Definition of Done

### Blocker: all required for v1.2

- Example payload comes from real generated output
- Invariant tests cover all derived fields
- Narrow or degenerate states no longer return `K = 1.0`
- Stale-data detection mechanism is implemented
- `schema_version` is bumped to `1.2.0`

### Required: defines the actual value of v1.2

- Metadata expanded
- Provenance expanded
- Student-t parameters exposed
- `seed_basis` recorded
- Per-pair status implemented
- `git_hash` recorded

### Nice-to-have

- advisory namespace cleanup
- generation status reporting
- pair failure reporting
- diagnostics block

## Recommended Delivery Order

### Phase 1: Safety

1. Spec correction
2. Invariant tests
3. Fail-open removal
4. Stale-data protection

### Phase 2: Auditability

1. Metadata expansion
2. Provenance expansion
3. Student-t transparency
4. Seed documentation

### Phase 3: Consumer Experience

1. Status object
2. Advisory cleanup
3. Diagnostics

## Explicitly Out of Scope for v1.2

- SQLite migration
- correlation-aware portfolio sizing
- cross-pair allocation engine
- GARCH or stochastic volatility models
- learned K calibration
- Kafka or Redis architecture changes
- replacing JSON snapshot delivery

## Release Guidance

Do not ship v1.2 until all P0 items are complete.

P1 items define the real value of the release.

P2 items should produce evidence first and become candidates for v1.3.
