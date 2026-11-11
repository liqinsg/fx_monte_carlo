# MC Probabilistic Fibonacci Grid — Audit Report

**Scope:** Read-only audit of `fx_monte_carlo.py`, `mc_data.yml`, the available D/W batch outputs and Fib-annotated outputs in `mc_results/`.

**Mode:** Audit only. No engine, configuration, output or trading-system files were changed. This report is the only file created.

## Executive finding

The Monte Carlo generator is D/W-based and currently has no Fib generation/configuration code. Fib is present in dated JSON artifacts, but the generator that produced those Fib fields is not present in this project checkout. Therefore the integration path, its statistical non-interference, and its shadow logger cannot be established from source here. The artifacts do establish several correctness and data-accounting problems in the existing Fib output: it emits order-like actions, clamps out-of-range prices into internal zones, assigns exact internal boundaries to the lower zone, and reports 35 pairs while containing 29 unique result keys.

The task's requested implementation should not begin until the missing Fib source/generation step is located or explicitly treated as an absent component. This report does not implement a correction.

## Existing Monte Carlo path

| Responsibility | Current location | Audit notes |
|---|---|---|
| Range calculation | `run_mc()` in `fx_monte_carlo.py` | Simulates terminal prices and computes lower/upper quantiles using `CONFIDENCE` (default 0.90). The result is serialized under the fixed name `range_90`, even if confidence is changed. Endpoints are rounded to pair precision before serialization. |
| Simulation | `run_mc()` | Student-t shocks are scaled when df > 2; `np.random.seed(42)` is reset for each pair. Statistical calculations do not currently call Fib code. |
| Fib generation | Not found in this project | `fx_monte_carlo.py` has no Fib functions or Fib config. Dated `*_fib.json` artifacts exist, but the generating script is absent from this checkout. |
| Current-zone assignment | Not found in this project | Can only infer behavior from output artifacts; see mathematical findings below. |
| JSON writing | `save_batch_mc_safely()` called by `main()` | Writes a temporary file and atomically replaces the timestamped target. It prunes old history files after saving. |
| Metadata | `main()` | Writes timeframe, timestamp, total successful result-list length, simulations, lookback and forecast. No requested/unique/successful/failed breakdown or Fib metadata from the generator. |
| Pair iteration/errors | `main()` | Iterates `PAIRS` as-is. Failed `run_mc()` results are skipped. Duplicate pairs are simulated repeatedly; the results dictionary overwrites duplicate keys while `all_results` still counts them. An uncaught pair exception aborts the batch. |
| Observation logging | Optional import at module load and hooks in `main()` | ImportError silently disables both hooks. Other errors from `log_mc_observation()` are uncaught and can abort generation. Hook implementation is unavailable in this checkout. |

## Configuration and pair accounting

`mc_data.yml` contains the simulation settings and 35 declared pair entries. It has no `fib` section. The dated Fib artifacts' metadata says `total_pairs: 35`, while each artifact has 29 keys in `results`. This matches duplicate-symbol overwrite behavior: the output map has one entry per unique symbol, but total count reflects the raw list. The batch generator does not log duplicate symbols or deduplicate before simulation.

The engine does avoid writing a batch when every pair returns `ok=False`, which protects prior history files from an empty run. A partial-success batch is still saved without listing the failed pairs or their reasons. `total_pairs` is `len(all_results)`, not the actual number of unique result keys.

## Fib behavior evidenced by the output artifacts

The D1 Fib artifact `mc_D_all_pairs_20261103_fib.json` stores the six requested zones, seven levels, `current_zone`, labels, and a `fib_regime_label`. Its metadata identifies the method as “Fibonacci grid on range_90” and gives the source file. The W1 artifact has the same schema. This confirms an offline or separate annotation step existed, but not which source code produced it.

Observed EURUSD D1 values:

- `range_90`: `[1.10707, 1.12888]`
- Current price: `1.11932`
- Zone: `F5 / Above Equilibrium`, position `52.3%`
- Fib label action: `SELL_LIMIT`

Findings from schema and stored results:

1. **Executable-looking action label:** The output contains `BUY_LIMIT`/`SELL_LIMIT`-style actions (the representative record has `SELL_LIMIT`). That conflicts with shadow-only observation and risks downstream interpretation as an instruction.
2. **Out-of-range status is not represented:** The schema has no `BELOW_RANGE`/`INSIDE_RANGE`/`ABOVE_RANGE` status. The current-zone field always looks like an internal zone.
3. **Clamping can misclassify:** The artifact behavior is consistent with out-of-range prices being mapped to the first or last zone. Without source this cannot be confirmed line-by-line, but no explicit out-of-range state is present in the JSON.
4. **Boundary ownership is ambiguous and likely lower-zone inclusive at both ends:** Zone ratio ranges are stored as closed ranges, e.g. `[0.0, 0.236]` and `[0.236, 0.382]`. Thus an exact shared boundary is represented as belonging to both. A deterministic half-open rule is not declared.
5. **Invalid ranges lack an observable error state:** The JSON schema has no invalid-range status. The actual behavior for NaN, infinity, zero-width, or reversed boundaries cannot be established because the implementation source is missing.
6. **Precision:** The MC result rounds `range_90` to 3 decimals for JPY pairs and 5 for others before the Fib step. The original unrounded quantile endpoints are therefore unavailable to a downstream annotator. Fib output rounds display levels to six decimals. Zone assignment should use unrounded interval values, but current source is unavailable to verify this.
7. **Terminology:** The artifact method string does not yet use the requested `MC_PROBABILISTIC_GRID` identifier. These are proportional divisions of the simulated terminal interval, not historical swing retracements or proven support/resistance.

## Statistical-integrity assessment

The current `run_mc()` function does not reference Fib, and the checked-in generator does not attach Fib fields. That is evidence that the present generator's statistical calculations are structurally separate from Fib. It is **not** proof that enabling the separate artifact step leaves every original statistical field exactly unchanged: there is no enable/disable switch or available Fib integration source to compare. The existing Fib artifacts retain original fields alongside `fib`, but that alone does not establish exact before/after equality for corresponding simulation runs.

The requested exact comparison is therefore **not demonstrated** by this audit. It needs paired deterministic inputs or a shared baseline payload once the actual Fib source is available.

## Shadow observation readiness

There is an optional observation API hook in the engine, imported from `utils.mc_loader_local`, but that module is not present in this project checkout. The import fallback silently sets the hooks to `None`; consequently, observation logging and resolution may be disabled without a visible warning. The hook signatures/data contract, idempotency, timestamp behavior, resolution horizon, and failure isolation cannot be audited. In addition, the current observation call is not isolated: a runtime exception from the logger would interrupt the batch.

No source evidence in this checkout establishes duplicate-observation prevention or that future data is only used after each forecast horizon elapses.

## Risks to resolve before implementation

1. Locate and review the source that creates the `*_fib.json` artifacts; it is absent from this repository's file list.
2. Add explicit Fib config validation with disabled-by-default behavior and `shadow` as the only accepted mode.
3. Preserve the existing MC calculation path; calculate Fib only after each MC result is complete.
4. Define finite, positive-width interval validation, half-open zone boundaries, and explicit outside-range status. Never clamp outside prices into an internal zone.
5. Remove action/order labels and keep any entry context explicitly unvalidated.
6. Deduplicate pair symbols before simulation while preserving order; separately count requested, unique, successful and failed pairs, and retain visible per-pair errors.
7. Audit the observation logger implementation and make logger failures visible without blocking MC generation.
8. Verify no downstream consumer treats Fib fields as trading inputs. This audit did not inspect the separate `forex_oanda_v7` project, consistent with the task boundary.

## Audit disposition

**Audit complete; implementation not performed.** The main blockers are missing Fib generation source and missing observation-hook implementation. The current artifacts are not safe to describe as fully shadow-only because they expose order-like action names and do not encode out-of-range state.
