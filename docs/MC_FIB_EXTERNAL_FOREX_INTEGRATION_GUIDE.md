# MC_FIB External Forex Integration Guide

## Purpose

This guide describes how to use `fx_monte_carlo` outputs inside other forex trading systems without tightly coupling them to the internal implementation.

The key idea is simple:

- `fx_monte_carlo` provides analytical state.
- The external trading system keeps control over direction, entry, exit, portfolio limits, and execution.

## Recommended Integration Principle

Use MC/Fib outputs as an overlay, not as a full strategy replacement.

The safest reusable fields are:

- `range_90`
- `range_90_pct`
- `ratio_pos`
- `zone_index`
- `breakout`
- `degenerate`
- `percentile_rank`
- `p_up`
- `generated_utc`

Treat any shipped `risk_model` as advisory only.

## Integration Patterns

### 1. Trend-following systems

Examples:

- moving-average trend systems
- breakout continuation systems
- momentum EAs

Recommended use:

- Let the native strategy decide direction.
- Use MC/Fib only to modulate confidence and sizing.

Typical policy:

- If `zone_index` is 2 or 3, allow normal sizing.
- If `zone_index` is 1 or 4, reduce size or require stronger confirmation.
- If `zone_index` is 0 or 5, require a breakout-confirmation rule or skip entry.
- If `degenerate` is true, do not open new positions.

Why this works:

- Trend systems usually already know the trade side.
- What they often lack is a normalized cross-pair spatial context.

### 2. Mean-reversion systems

Examples:

- Bollinger reversion
- RSI reversion
- channel fade systems

Recommended use:

- Use zone extremes as context, not as a naked trade trigger.
- Combine `zone_index`, `ratio_pos`, and local confirmation from the native strategy.

Typical policy:

- Long reversion candidates: prefer `zone_index` 0 or 1.
- Short reversion candidates: prefer `zone_index` 4 or 5.
- Reject trades when `range_90_pct` is too narrow or the payload is stale.

Why this works:

- The MC layer helps answer whether price is near the lower or upper probabilistic edge.
- The native reversion logic still decides whether reversal evidence is present.

### 3. Breakout systems

Examples:

- Donchian breakout
- volatility expansion
- session range breakout

Recommended use:

- Use MC/Fib as a "should we trust this breakout?" filter.

Typical policy:

- If the breakout occurs from zone 5 upward or zone 0 downward, label it as higher expansion risk.
- If the signal fires from the middle zones, require stronger volatility confirmation.
- If `range_90_pct` is abnormally narrow, treat breakout signals as lower quality until real expansion appears.

Why this works:

- Many false breakouts happen when the underlying probabilistic range is too compressed or stale.

### 4. Multi-strategy portfolio layer

Examples:

- one account running several EAs
- one allocator routing to multiple execution bots
- a supervisor process above MT4/MT5 or cTrader agents

Recommended use:

- Standardize MC/Fib as a shared risk language across strategies.

Typical policy:

- Strategy alpha decides whether it wants to trade.
- Portfolio overlay decides how much risk is permitted based on:
  - `zone_index`
  - `range_90_pct`
  - freshness
  - pair overlap rules

Why this works:

- Different systems can stay independent while sharing one common market-state overlay.

## Best Reuse Pattern by Architecture

### A. MT4 / MT5 Expert Advisors

Recommended flow:

1. External Python service generates the latest JSON snapshot.
2. EA reads a reduced local export or bridge file.
3. EA only consumes a few canonical fields.
4. EA applies its own trade logic and risk rules.

Notes:

- Do not push raw internal calculation logic into MQL unless necessary.
- Prefer a stable bridge schema over re-implementing the engine inside the terminal.

### B. Python execution bots

Recommended flow:

1. Load snapshot via `interface.py` or a thin wrapper.
2. Check freshness first.
3. Extract analytics fields.
4. Convert those fields into strategy-specific features or gates.

Notes:

- This is the cleanest integration path.
- It is also the easiest place to add audit logging.

### C. OANDA / REST-driven execution services

Recommended flow:

1. Analytics job writes a snapshot.
2. Execution service reads only the latest valid snapshot.
3. Order logic rejects stale or missing analytics.
4. Trade decisions are logged with both native signal reason and MC/Fib context.

Notes:

- This pattern is ideal for fail-closed controls.
- It also scales well to supervisor or watchdog processes.

### D. Cross-platform signal bus

Recommended flow:

1. Generate one canonical analytics payload.
2. Publish only normalized fields into Redis, SQLite, Kafka, or another lightweight bus.
3. Let each consumer map the same fields into its own internal policy.

Notes:

- This is the best option when you have multiple systems in different languages.

## Contract Rules for External Consumers

Every external forex system should follow these rules:

1. Check `schema_version` and reject incompatible major versions.
2. Check `generated_utc` and fail closed on stale data.
3. Treat `risk_model` as advisory, not mandatory.
4. Use `zone_index` and `ratio_pos` as state descriptors, not trade directions.
5. Handle missing or invalid pairs explicitly.
6. Log the payload timestamp used for every trade decision.

## What Not to Do

Avoid these integration mistakes:

- Do not map `zone_index` directly to BUY or SELL without local context.
- Do not trust latest-by-filename alone without freshness checks.
- Do not let narrow-range or degenerate outputs silently pass as normal-confidence inputs.
- Do not treat the MC layer as a portfolio risk engine yet.
- Do not assume pair-level analytics already handle triangular FX exposure.

## Highest-Value Use Cases Outside This Repo

If this system is reused elsewhere, the best early wins are:

### 1. Position-sizing overlay

Use the analytics only to scale or cap risk on an existing profitable strategy.

This is the lowest-friction adoption path.

### 2. No-trade filter

Reject entries when:

- data is stale
- range is degenerate
- range is too narrow
- the pair is in a low-information middle state and the native edge is weak

This often improves systems faster than adding new entries.

### 3. Cross-pair normalization layer

Use `range_90_pct` and `ratio_pos` to compare setups across different forex pairs.

This is useful for:

- basket selection
- top-N opportunity ranking
- supervisor bots that choose one trade among many candidates

### 4. Shared analytics service for multiple bots

One analytics producer can serve:

- mean-reversion bots
- breakout bots
- trend bots
- discretionary dashboards

This preserves one source of truth and reduces duplicated model code.

## Next Recommended Evolution

For broader external adoption, the best next improvements are:

1. Add richer metadata and provenance.
2. Publish explicit freshness helpers.
3. Provide a minimal consumer contract with only neutral analytics fields.
4. Add per-pair status reporting.
5. Later, add correlation-aware portfolio overlays above the pair level.

## Bottom Line

The strongest way to use this work in other forex systems is not to copy its internal logic everywhere.

Instead:

- keep one analytics producer,
- keep many independent consumers,
- and let each consumer convert neutral probabilistic state into its own execution policy.

That is the part of the current design most worth preserving.
