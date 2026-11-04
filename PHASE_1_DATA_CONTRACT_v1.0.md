# PHASE 1 — DATA CONTRACT v1.0 (REVISED — PENDING FINAL FREEZE)

**Status:** REVISED — incorporates signed decisions O-1…O-6; awaiting final human freeze before Stage B authorization
**Version:** 1.0 (revision 2)
**Created:** 2026-11-04
**Project:** `fx_monte_carlo` (root: `/home/ubuntu/projects/fx_monte_carlo`)
**Phase:** 1 of 5 — MC Data Integrity
**Nature:** This is an **implementation contract**, not an architecture review and not code. It defines the exact field semantics that Stage B must implement. It changes no source, config, data, workflow, or schedule.
**Derived from:** `PHASE_1_STAGE_A_DISCOVERY.md` (Stage A evidence) + the Phase 0/Stage A evidence reconciliation + the human reviewer's six corrections, five decisions, and the signed O-1…O-6 determinations.

## Revision Log
| Rev | Date | Change |
|-----|------|--------|
| 1 | 2026-11-04 | Initial draft (O-1 … O-6 proposed). |
| 2 | 2026-11-04 | O-1 revised (`batch_id` run-level uniqueness via `run_nonce`); O-3 decided (keep legacy `=X` key); O-2 / O-4 / O-5 / O-6 signed; count invariants and fingerprint coverage tightened to the signed decisions. |

> Nothing in this document authorizes code changes. All previously **[OPEN]** items are now **SIGNED** (§11). Stage B remains unauthorized until the final freeze in §12.

---

## 0. AUTHORITY AND EVIDENCE PRECEDENCE

When this contract and any prior document disagree, the following precedence applies (highest first):

1. Current `fx_monte_carlo` source code.
2. Current `mc_data.yml`.
3. Current actual JSON artifacts in `mc_results/`.
4. Current scheduler and actual API output.
5. Phase 0 architectural intent.
6. Earlier assumptions and human descriptions.

**Consequence:** Phase 0 facts that Stage A disproved (`29 unique pairs`, `6 duplicates`, `non-atomic write`, `api/daily/latest/`) are **superseded** and MUST NOT be carried into Stage B. Phase 0 architectural *intent* is retained where it does not conflict with the above.

---

## 1. MC BATCH SCHEMA

A batch = one invocation of `fx_monte_carlo.py` for one timeframe. It is written to one file:

```
mc_results/mc_{D|W}_all_pairs_YYYYMMDD_HHMM.json
```

Structure (target state — `metadata` extended, `results` unchanged in shape):

```json
{
  "metadata": {
    "schema_version": "1.0",
    "batch_id": "D-20261103T201551Z-a1b2c3d4e5f6-8c31a72f",
    "timeframe": "D",
    "algorithm_version": "mc-engine-1.0",
    "generated_utc": "2026-11-03T20:15:51.649099+00:00",
    "data_fetched_utc": "2026-11-03T20:15:41.000000+00:00",
    "configuration_snapshot": { "...§4.2..." : 0 },
    "configuration_fingerprint": "sha256:<64 hex chars>",
    "seed": 42,
    "requested_pairs_count": 35,
    "unique_pairs_count": 28,
    "duplicate_pairs_count": 7,
    "successful_pairs_count": 28,
    "failed_pairs_count": 0,
    "total_pairs": 35,
    "simulations": 5000,
    "lookback": 90,
    "forecast": 5,
    "confidence": 0.90,
    "student_t_df": 5,
    "batch_status": "ok",
    "failed_pairs": []
  },
  "results": { "EURUSD=X": { "...§2..." : 0 } }
}
```

### 1.1 Metadata field definitions

| Field | Type | Req | Semantics | Current state (Stage A) |
|-------|------|-----|-----------|--------------------------|
| `schema_version` | string | yes | Version of this contract that the file conforms to. | **absent** |
| `batch_id` | string | yes | Unique identity **per run**: `{timeframe}-{YYYYMMDDTHHMMSSZ}-{fingerprint[:12]}-{run_nonce}`. Two runs of the same config MUST yield different `batch_id`s (§11 O-1). | **absent** |
| `timeframe` | "D"\|"W" | yes | Timeframe of the batch. | present (`fx_monte_carlo.py:381`) |
| `algorithm_version` | string | yes | Explicit semver of the MC engine (e.g. `mc-engine-1.0`). Bumped **only** on substantive algorithm-behavior change; MUST NOT be a git commit hash or a file hash (§11 O-2). | **absent** |
| `generated_utc` | string (ISO-8601 UTC) | yes | Wall-clock instant the batch payload was assembled. | present (`:382`) |
| `data_fetched_utc` | string (ISO-8601 UTC) | yes | Wall-clock instant the market data was fetched. | **absent** |
| `configuration_snapshot` | object | yes | Complete effective config (§4.2). | **absent** |
| `configuration_fingerprint` | string | yes | `sha256:` + hex of canonical config incl. unique pair set (§4.3). | **absent** |
| `seed` | integer | yes | RNG seed used. | **absent** (hard-coded 42 at `:237`) |
| `requested_pairs_count` | integer | yes | Raw YAML entry count. | **absent** |
| `unique_pairs_count` | integer | yes | Deduplicated canonical pair count. | **absent** |
| `duplicate_pairs_count` | integer | yes | Raw − unique. | **absent** |
| `successful_pairs_count` | integer | yes | Unique pairs successfully simulated. | **absent** |
| `failed_pairs_count` | integer | yes | Unique pairs that failed/skipped. | **absent** |
| `total_pairs` | integer | yes | **LEGACY.** Retains current meaning: raw successful attempts. Do NOT redefine. | present (`:383`) |
| `simulations` | integer | yes | Simulation count. | present (`:384`) |
| `lookback` | integer | yes | Bars used. | present (`:385`) |
| `forecast` | integer | yes | Steps forecast. | present (`:386`) |
| `confidence` | number | yes | Confidence level used for `range_90`. | **absent** |
| `student_t_df` | integer | yes | Student-t degrees of freedom. | **absent** |
| `batch_status` | enum | yes | §6. | **absent** |
| `failed_pairs` | array | yes | List of `{canonical_pair, provider_ticker, stage, reason}` (§3.4). Empty when none. | **absent** |

**Additive-only rule:** every field above is added; none of the existing fields is renamed or removed.

---

## 2. MC PAIR RESULT SCHEMA

One object per unique pair. The results-map key and the `pair` field **keep the legacy provider form** (`EURUSD=X`) for backward compatibility (§11 O-3). Target state adds provenance fields to the existing 21:

```json
{
  "timeframe": "D",
  "pair": "EURUSD=X",
  "canonical_pair": "EURUSD",
  "provider_ticker": "EURUSD=X",
  "current_price": 1.11932,
  "ann_drift_pct": -5.51,
  "ann_vol_pct": 4.32,
  "range_90": [1.10707, 1.12888],
  "confidence": 0.90,
  "percentile_rank": 57.9,
  "p_up": 42.1,
  "p_down": 57.9,
  "p_up_pct": 42.1,
  "p_down_pct": 57.9,
  "touch_upper_pct": 6.7,
  "touch_lower_pct": 6.3,
  "var_95": -0.0109,
  "cvar_95": -0.0137,
  "expected_price": 1.11797,
  "regime": "🔹 D NEUTRAL",
  "lookback": 90,
  "forecast": 5,
  "simulations": 5000,
  "last_bar_timestamp": "2026-11-03T00:00:00+00:00",
  "data_window_start": "2026-06-16T00:00:00+00:00",
  "data_window_end": "2026-11-03T00:00:00+00:00",
  "generated_utc": "2026-11-03T20:15:53.075751+00:00"
}
```

### 2.1 New per-pair fields

| Field | Type | Req | Semantics |
|-------|------|-----|-----------|
| `canonical_pair` | string | yes | Clean symbol (`EURUSD`). |
| `provider_ticker` | string | yes | Provider symbol with suffix (`EURUSD=X`). |
| `confidence` | number | yes | Confidence level for `range_90`. |
| `last_bar_timestamp` | string (ISO-8601 UTC) | yes | Timestamp of the **last market bar actually used**. |
| `data_window_start` | string (ISO-8601 UTC) | yes | Timestamp of the **first market bar actually used**. |
| `data_window_end` | string (ISO-8601 UTC) | yes | Timestamp of the **last market bar actually used** (== `last_bar_timestamp`). |

### 2.2 Preserved fields
All existing 21 fields keep their names and meanings. `range_90` and its computation are **unchanged** (§10). The results-map key and `pair` are **retained unchanged in the legacy provider form (`EURUSD=X`)**; `canonical_pair` (`EURUSD`) and `provider_ticker` (`EURUSD=X`) are added alongside for internal dedup and clarity (§11 O-3). Consumers that already strip the `=X` suffix (e.g. `get_mc_data.py`, `build_api.py`) remain compatible; **no consumer is required to change**.

---

## 3. PAIR COUNTING SEMANTICS

### 3.1 Definitions (all counts are explicit; none inferred)

| Term | Definition |
|------|------------|
| Requested | Number of raw entries in `mc_data.yml` `pairs:`. |
| Unique | Number of distinct canonical pairs after dedup. |
| Duplicate | Requested − Unique (occurrence count of duplicated entries). |
| Successful | Unique pairs that produced a valid result. |
| Failed | Unique pairs that did not (fetch failure, insufficient data, invalid result). |

**Invariants:**
- `requested_pairs_count = unique_pairs_count + duplicate_pairs_count`
- `successful_pairs_count + failed_pairs_count = unique_pairs_count`
- `len(results) == successful_pairs_count`
- `len(failed_pairs) == failed_pairs_count`
- `total_pairs` is **exempt** from these invariants (legacy raw-attempt semantics). §9.

**Worked example** — YAML: `EURUSD, GBPUSD, EURUSD, USDJPY`
```json
{
  "requested_pairs_count": 4,
  "unique_pairs_count": 3,
  "duplicate_pairs_count": 1,
  "successful_pairs_count": 3,
  "failed_pairs_count": 0
}
```
`EURUSD` is executed **once**; its duplicate YAML entry is counted, not executed.

> **Critical:** a duplicate pair is **NOT** a failed pair. `failed_pairs_count` counts only **unique** pairs that could not be produced; duplicates never inflate it, and they never mask a real failure.

### 3.2 Unique execution
Each **unique** pair is fetched and simulated **exactly once** per batch, regardless of duplicate YAML entries. Duplicates are recorded in the counts, not executed twice.

### 3.3 Duplicate handling
Duplicate YAML entries are **preserved as-is** in `mc_data.yml` (no auto-removal, no normalization to "make numbers match"). Duplicates are additionally itemized in the snapshot (§4.2).

### 3.4 Failure recording
Each failed unique pair produces one entry (canonical identity plus provider ticker):
```json
{ "canonical_pair": "EURUSD", "provider_ticker": "EURUSD=X", "stage": "fetch|insufficient_data|validation", "reason": "free-text" }
```

### 3.5 Pair identity
- YAML keeps the clean symbol (`EURUSD`).
- `canonical_pair` = uppercase clean symbol (`EURUSD`); used for **internal dedup**.
- `provider_ticker` = canonical + provider suffix (`EURUSD=X` for yfinance).
- Results-map key = **legacy provider form (`EURUSD=X`) — unchanged** (§11 O-3).
- `pair` field = **legacy provider form (`EURUSD=X`) — unchanged**.
- Deduplication runs on `canonical_pair`; the output key/`pair` are **not** normalized, to avoid breaking un-audited consumers.

---

## 4. CONFIGURATION SNAPSHOT AND FINGERPRINT

### 4.1 Source of truth
Only values that **actually affect the computed result** are included. Current effective config keys read by the engine: `pairs, simulations, confidence, student_t_df, daily_lookback, daily_forecast, weekly_lookback, weekly_forecast` (plus `max_history_files`, which is **excluded** from the fingerprint — it affects retention, not results). The fingerprint **additionally covers `timeframe` and `seed`** (§4.3).

### 4.2 `configuration_snapshot` (stored in full, per batch)
```json
{
  "timeframe": "D",
  "simulations": 5000,
  "confidence": 0.90,
  "student_t_df": 5,
  "daily_lookback": 90,
  "daily_forecast": 5,
  "weekly_lookback": 104,
  "weekly_forecast": 5,
  "seed": 42,
  "unique_pairs": ["AUDCAD", "AUDCHF", "..."],
  "duplicate_pairs": ["EURUSD", "GBPUSD", "NZDCHF", "NZDUSD", "USDCAD", "USDCHF", "USDJPY"]
}
```
The **full snapshot is stored** (not only a hash), so the batch is explainable without reversing a digest.

### 4.3 `configuration_fingerprint`
```
configuration_fingerprint = "sha256:" + SHA256(canonical_json(effective_config))
```
`effective_config` MUST cover **every input that affects the computed result**:
- `timeframe`
- `simulations`
- `lookback` / `forecast` for that timeframe
- `confidence`
- `student_t_df` (Student-t parameters)
- `seed`
- the **de-duplicated, sorted canonical pair set**
- any other effective parameter that changes results

Canonicalization rules:
- keys sorted lexicographically;
- pair arrays sorted and de-duplicated (unique set);
- numeric values normalized (no float formatting drift);
- UTF-8, no insignificant whitespace.

**Determinism guarantees (required):**
- **Same effective config ⇒ same `configuration_fingerprint`.**
- **Different effective config ⇒ different `configuration_fingerprint`** (SHA-256 collision risk assumed negligible).

**Correction of Phase 0 §6.1:** the pair set **IS included**. Rationale: the pair population changed between 2026-10-26 and 2026-10-27 (see §3.1 of the reconciliation); two configs with identical simulation parameters could otherwise be indistinguishable.

---

## 5. TIMESTAMP SEMANTICS

Three distinct temporal concepts across five fields; they MUST never be conflated.

| Field | Scope | Meaning | MUST NOT be used as |
|-------|-------|---------|----------------------|
| `generated_utc` | batch + pair | When the MC result was produced (wall clock). | market time |
| `data_fetched_utc` | batch | When the data was fetched (wall clock). | market time |
| `last_bar_timestamp` | per-pair | The last **market bar** actually used. | generation time |
| `data_window_start` | per-pair | First market bar actually used. | — |
| `data_window_end` | per-pair | Last market bar actually used (== `last_bar_timestamp`). | — |

### 5.1 Rules
- `data_fetched_utc`, `last_bar_timestamp`, `data_window_*` are **market/fetch** facts; `generated_utc` is a **process** fact.
- `data_window_start` < `data_window_end`.
- `last_bar_timestamp` ≤ `data_fetched_utc`; `data_fetched_utc` ≤ `generated_utc`.
- Per-pair values are captured **per pair** (different pairs may be unsynchronized; especially Weekly).
- Format convention (**SIGNED — §11 O-4**): ISO-8601 with explicit offset, `+00:00` (e.g. `2026-11-04T01:02:03+00:00`); `Z` only where `build_api` already emits it.
- The five fields MUST retain their distinct semantics: `generated_utc` (process time), `data_fetched_utc` (fetch time), `last_bar_timestamp` / `data_window_start` / `data_window_end` (market-data time). `generated_utc` MUST NOT stand in for market-data time.
- Downstream (API) MUST derive any "date" from a **market** timestamp when available; `generated_utc` may be used only as an explicit fallback.

---

## 6. BATCH STATUS

`batch_status` enum:

| Value | Condition |
|-------|-----------|
| `ok` | `failed_pairs_count == 0` and `successful_pairs_count == unique_pairs_count`. |
| `partial` | `0 < successful_pairs_count < unique_pairs_count`. |
| `failed` | `successful_pairs_count == 0` (no valid results). |

Rules:
- `failed` batches MUST still be written to disk (so absence of a file is never ambiguous).
- `batch_status != "ok"` MUST surface the `failed_pairs` list.
- API ingestion MUST reject `failed` batches (§8.3) while retaining the artifact on disk for audit (**SIGNED — §11 O-6**).

---

## 7. VALIDATION RULES

Validation runs **before** the atomic write. A pair failing validation is moved to `failed_pairs` with `stage="validation"`.

| Rule | Target |
|------|--------|
| V-1 | All numeric outputs are finite (no `NaN`, `Inf`, `null`). |
| V-2 | `current_price > 0`. |
| V-3 | `0 ≤ p_up ≤ 100` and `0 ≤ p_down ≤ 100`. |
| V-4 | `p_up + p_down == 100` (tolerance ≤ 0.1). |
| V-5 | `range_90` has exactly 2 finite elements and `range_90[0] ≤ range_90[1]`. |
| V-6 | `data_window_start < data_window_end`. |
| V-7 | `last_bar_timestamp ≤ data_fetched_utc ≤ generated_utc`. |
| V-8 | Required keys present (batch §1.1; pair §2.1/§2.2). |
| V-9 | Per-pair key set is uniform across all pairs in the batch. |
| V-10 | Count invariants of §3.1 hold. |

Notes:
- Existing artifacts were scanned and are currently clean (no non-finite, no reversed/zero-width `range_90`, uniform 21-key schema) — validation is introduced to **guarantee** this, not because defects were observed.
- Validation is **non-destructive**: it never rewrites historical JSON (§9.4).

---

## 8. API INGESTION RULES

### 8.1 Accepted filenames (strict)
```
^mc_(D|W)_all_pairs_\d{8}_\d{4}\.json$
```
- The current prefix-only filter (`build_api.py:47`, `startswith("mc_D_")`) is **insufficient** and MUST be replaced by the strict pattern.
- Any filename containing `_fib` is **explicitly excluded**, independent of the pattern.

### 8.2 Source directory restriction
- Only `mc_results/` is scanned.
- Fib output (future `mc_results_fib/`, Phase 2) is never scanned by the MC API builder.

### 8.3 Record selection and batch-status gate (**SIGNED — §11 O-6**)
- "Latest" is chosen by `generated_utc` (unchanged from current behavior).
- The builder MUST read `batch_status` and, for `batch_status == "failed"`:
  1. **skip** the batch (do not publish it);
  2. write an **explicit log entry** (batch file, `batch_id`, reason);
  3. **retain** the skipped artifact on disk for audit.
- A batch whose `schema_version` is unsupported is **skipped with a logged error**, not silently ingested.

### 8.4 Current API defects — REPORT ONLY, NO DELETION (**SIGNED — §11 O-5**)
- `api/latest/` retains legacy pairs `CADNZD`, `CHFNZD` and lacks `NZDCAD`.
- `api/latest/all.json` lags the newest `mc_results` artifacts because recent files are uncommitted.
- Phase 1 MUST NOT delete any historical API data. The builder MAY **report**: stale pair, stale date directory, missing pair, outdated API artifact.
- Any pruning is a separate, separately-approved change (out of Phase 1 scope).

---

## 9. BACKWARD COMPATIBILITY

9.1 **Additive only.** New fields are added; existing field names and `range_90` semantics are unchanged.
9.2 **`total_pairs` is frozen in its legacy meaning** (raw successful attempts). It is not redefined; the new explicit counts are provided alongside.
9.3 **Existing consumers** (`get_mc_data.py`, `build_api.py`) continue to function because they rely on `pair`, `generated_utc`, `results`, and the strict/known filename forms.
9.4 **No historical rewrite.** `mc_results/*` and `api/*` are not migrated or rewritten. Only newly generated batches adopt v1.0 fields.
9.5 **`range_90` unchanged**; `confidence` is added additively. No `range_0.90` alias (§10).
9.6 **Legacy `=X` keys preserved** (**SIGNED — §11 O-3**): results-map keys and `pair` remain `EURUSD=X`; `canonical_pair` / `provider_ticker` are added. No consumer is forced to change; a full consumer audit is not required for Phase 1.
9.7 **`total_pairs` is legacy/deprecated** but retained verbatim; new consumers SHOULD use the explicit counts (§3.1) instead.

---

## 10. EXPLICIT OUT-OF-SCOPE (Phase 1 MUST NOT DO)

- Fib algorithm fixes; Fib zone/`locate_zone` logic.
- Fib output-directory migration (`mc_results_fib/`) — deferred to Phase 2.
- Shadow Observation; Outcome Resolver; Statistical Validation.
- D1/W1 probability blending; unify the two MC engines.
- Scheduler time changes (Weekly stays Monday; no timing change in Phase 1).
- `ai_training_cnn` changes; `blend_metric()` changes.
- Student-t algorithm changes; adding a Normal engine.
- Rewriting/migrating historical JSON.
- Changing the `range_90` computation or adding `range_0.90`.
- Auto-removing duplicate YAML pairs, or editing `mc_data.yml` to force count consistency.
- OANDA trading-execution code or any order-placement path.
- Deleting, cleaning, or re-adding the pre-existing untracked data files (the original 43) or this phase's documents.
- Pruning historical `api/` entries or dated directories (§8.4).

---

## 11. SIGNED DECISIONS (O-1 … O-6)

All previously open items are **RESOLVED**. No `[OPEN]` items remain.

| ID | Decision | Determination |
|----|----------|---------------|
| O-1 | `batch_id` format | **MODIFIED-ACCEPT.** `{timeframe}-{YYYYMMDDTHHMMSSZ}-{fingerprint[:12]}-{run_nonce}`. The `run_nonce` guarantees run-level uniqueness: **two runs of the same config MUST have different `batch_id`s** (a same-minute re-run must not collide). Example: `D-20261104T010203Z-a1b2c3d4e5f6-8c31a72f`. |
| O-2 | `algorithm_version` | **ACCEPT.** Explicit semver string (e.g. `mc-engine-1.0`). MUST be bumped on any substantive algorithm-behavior change; log/comment/formatting-only changes need not bump it. MUST NOT be a git commit hash or a file hash. |
| O-3 | Results-map key | **DO NOT CHANGE THE LEGACY KEY.** Results-map key and `pair` stay `EURUSD=X`; add `canonical_pair` (`EURUSD`) and `provider_ticker` (`EURUSD=X`); dedup internally on `canonical_pair`; do NOT delete duplicate YAML entries. Rationale: only `get_mc_data.py` / `build_api.py` are known `=X`-tolerant; a complete consumer audit has not been performed, so preserving keys is the safer engineering choice. |
| O-4 | Timestamp serialization | **ACCEPT.** ISO-8601 with explicit UTC offset, `+00:00` (e.g. `2026-11-04T01:02:03+00:00`). |
| O-5 | Historical API cleanup | **ACCEPT.** Phase 1 deletes nothing; the builder **reports** stale pair / stale date directory / missing pair / outdated API artifact only. |
| O-6 | `failed` batches | **ACCEPT.** `batch_status = "failed"` MUST be written to disk, but the API MUST NOT ingest it: check `batch_status` → skip → log the reason → retain the artifact for audit. |

---

## 12. FREEZE CHECKLIST

This contract becomes **FROZEN v1.0** when all are true:

- [x] §11 decisions O-1 … O-6 resolved (O-1 modified; O-2 … O-6 accepted).
- [x] Phase 0 / Stage A evidence precedence (§0) acknowledged.
- [ ] Final human confirmation that: (a) §1–§10 contain no field-definition conflicts or contradictions; (b) every required field is obtainable from real code (no schema-driven fabrication); (c) old/new artifacts and API consumers remain genuinely compatible.
- [ ] Explicit Stage B authorization issued **after** this file is frozen.

**Until the final confirmation above, Stage B MUST NOT begin.** No code, config, data, workflow, or schedule has been modified by Stage A or by any revision of this document. The pre-existing untracked data files and this phase's documents are to be left in place.
