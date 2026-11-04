# PHASE 1 — DATA CONTRACT v1.0 (REVISION 5b — PENDING FINAL FREEZE)

**Status:** REVISED — incorporates signed decisions O-1…O-6, owner-confirmed environment/UTC finalization (§0.2, §5.2), and accepted human policy decisions H-4/H-5 (§11.6); awaiting final human freeze before Stage B authorization
**Version:** 1.0 (revision 5b — in-place amendment of revision 5a; schema version remains 1.0)
**Created:** 2026-11-04
**Project:** `fx_monte_carlo`
**Stage B execution environment (CONFIRMED — owner decision):** WSL development workstation, canonical root `/home/qili/projects/fx_monte_carlo` (§0.2)
**Phase:** 1 of 5 — MC Data Integrity
**Nature:** This is an **implementation contract**, not an architecture review and not code. It defines the exact field semantics that Stage B must implement. It changes no source, config, data, workflow, or schedule.
**Derived from:** `PHASE_1_STAGE_A_DISCOVERY.md` (Stage A evidence) + the Phase 0/Stage A evidence reconciliation + the human reviewer's six corrections, five decisions, and the signed O-1…O-6 determinations.

## Revision Log
| Rev | Date | Change |
|-----|------|--------|
| 1 | 2026-11-04 | Initial draft (O-1 … O-6 proposed). |
| 2 | 2026-11-04 | O-1 revised (`batch_id` run-level uniqueness via `run_nonce`); O-3 decided (keep legacy `=X` key); O-2 / O-4 / O-5 / O-6 signed; count invariants and fingerprint coverage tightened to the signed decisions. |
| 3 | 2026-11-04 | Resolved P0-1…P0-3 and P1-1…P1-5: collision-safe run filenames, explicit count semantics, legacy schema ingestion, lossless pair snapshot, nonce rules, fetch-time and timezone rules, strict interval validation, and API fallback/publication metadata. |
| 4 | 2026-11-04 | Clarified evidence versus target authority; fixed snapshot example; specified no-replace atomic publication, timestamp identity, schema/filename pairing, malformed artifact ordering, downstream compatibility, and the limited meaning of `total_pairs`. |
| 5 | 2026-11-04 | Defined distinct pair/batch generation instants and their ordering; prohibited coercing session-date labels into UTC instants; clarified API builder versus downstream compatibility; recorded empty-config, workspace-root provenance, legacy filename timezone, and target-filesystem boundaries. |
| 5a | 2026-11-04 | **Finalization amendment (in place; no revision 6).** Owner-confirmed the WSL execution target `/home/qili/projects/fx_monte_carlo` and explicitly separated the cloud Ubuntu environment `/home/ubuntu/projects/fx_monte_carlo` (§0.2, §11.4). Added the unified UTC policy for all new system-generated timestamps and time-based operations (§5.2), an evidence-based legacy filename timezone table (§5.3), and a prohibition on fabricated market instants (§5.4). Added Stage B boundary items SB-1…SB-5 (§11.5). Extended §8.3 to all legacy/provenance classes and §12 to WSL acceptance items. No requirement from revisions 1–5 was weakened or removed. |
| 5b | 2026-11-04 | Recorded owner decisions H-4 (accept L-A/L-B only with artifact-specific provenance) and H-5 (accept strict legacy/v1.0 eligibility and transparent fallback); aligned §5.3, §8.3, §11.6, and §12 without granting Contract Freeze or Stage B authorization. |

> This document authorizes no code changes. O-1…O-6 are resolved (§11); H-4/H-5 are **DECIDED — ACCEPTED** (§11.6); H-1/H-2/H-3 remain open. Stage B is not authorized (§12).

---

## 0. AUTHORITY AND EVIDENCE PRECEDENCE

### 0.1 Verified workspace and evidence provenance

- The current WSL workspace was verified with `pwd` and `git rev-parse --show-toplevel` as `/home/qili/projects/fx_monte_carlo`.
- `PHASE_1_STAGE_A_DISCOVERY.md` records its verified root as `/home/ubuntu/projects/fx_monte_carlo` (see §0.2).
- In the current workspace, `mc_results` was checked with `test -L` and `readlink -f` on 2026-11-04 and is an ordinary directory at `/home/qili/projects/fx_monte_carlo/mc_results`, not a symlink (re-confirmed 2026-11-04 during revision 5a: `test -L` false, `readlink -f` returns the path itself, filesystem `ext2/ext3`). The current WSL checkout is ordinary-directory only; no symlink assumption may be introduced into the Stage B implementation (§0.2, §11.5 SB-3).
- The Stage B execution machine/path is **designated** by owner decision (§0.2). Stage B must still record its actual Git root and resolved output path at start.

### 0.2 Execution environments and evidence boundaries (**CONFIRMED — owner decision, revision 5a**)

The following are binding environment facts, not assumptions:

| # | Environment | Status |
|---|-------------|--------|
| E-1 | **WSL development workstation** — canonical project root `/home/qili/projects/fx_monte_carlo` | **DESIGNATED Stage B execution environment.** All Stage B implementation, validation, and batch generation occur here on the actual WSL filesystem. |
| E-2 | **Cloud Ubuntu environment** — `/home/ubuntu/projects/fx_monte_carlo` | **SEPARATE environment. NOT the same checkout as E-1.** MUST NOT be treated as the WSL repository. |
| E-3 | Current WSL `mc_results/` | An ordinary directory, not a symlink. Stage B MUST operate on the actual WSL filesystem; cloud-specific symlink assumptions MUST NOT enter the WSL implementation. |
| E-4 | `PHASE_1_STAGE_A_DISCOVERY.md` and `PHASE_1_STAGE_A_PROMPT.md` | Produced in **E-2**. Their findings are **historical discovery evidence only**, not proof of the current E-1 filesystem state. |

**Rules:**
- No Git state, file state, execution assumption, symlink topology, or filesystem capability may be transferred between E-1 and E-2 in either direction.
- Where an E-2 Stage A finding is used as input to Stage B, it MUST be re-verified against E-1 before it is relied upon (see §12). Until re-verified in E-1, such findings are **NOT VERIFIED for E-1**.
- The historical Stage A report MUST NOT be rewritten. Its `/home/ubuntu` root is correct for its own environment and remains authoritative for that environment only.
- Every place in this contract that speaks of the "current checkout" or "current workspace" means **E-1** unless explicitly stated otherwise.

Authority depends on the question being answered:

| Question | Authoritative evidence |
|----------|------------------------|
| Current behavior / factual state | Current source code, `mc_data.yml`, actual JSON artifacts, scheduler, and API output (inspect the relevant evidence; none alone overrides contradictory direct evidence from another source). |
| Target behavior / implementation requirements | This Phase 1 Data Contract **after it is explicitly frozen**. Before freeze, it remains a proposal and does not authorize implementation. |
| Architecture boundary | Approved Master Blueprint, subject to its approval status and the frozen contract's Phase 1 scope. |
| Historical assumptions | Lowest authority; superseded where contradicted by current evidence or approved target requirements. |

Existing source code establishes current state; it does not override requirements of this frozen contract. Any conflict between existing behavior and the target contract must be reported and resolved through implementation, not silently inherited. Before freeze, no implementation may treat this draft as binding authorization.

**Evidence-status legend used throughout:** **[CONFIRMED]** — owner-confirmed or directly re-verified in E-1 during revision 5a; **[VERIFIED]** — checked with a tool in this session; **NOT VERIFIED** — could not be checked and MUST NOT be assumed.

**Consequence:** Phase 0 facts that Stage A disproved (`29 unique pairs`, `6 duplicates`, `non-atomic write`, `api/daily/latest/`) are **superseded** and MUST NOT be carried into Stage B. Phase 0 architectural *intent* is retained where it does not conflict with the above.

---

## 1. MC BATCH SCHEMA

A batch = one invocation of `fx_monte_carlo.py` for one timeframe. It is written to one file:

```
mc_results/mc_{D|W}_all_pairs_YYYYMMDD_HHMMSS_{nonce8}.json
```

Structure (target state — `metadata` extended, `results` unchanged in shape):

```json
{
  "metadata": {
    "schema_version": "1.0",
    "batch_id": "D-20261103T201555Z-a1b2c3d4e5f6-8c31a72f",
    "timeframe": "D",
    "algorithm_version": "mc-engine-1.0",
    "generated_utc": "2026-11-03T20:15:55.649099+00:00",
    "data_fetched_utc": "2026-11-03T20:15:41.000000+00:00",
    "configuration_snapshot": { "...§4.2..." : 0 },
    "configuration_fingerprint": "sha256:<64 hex chars>",
    "seed": 42,
    "requested_pairs_count": 35,
    "unique_pairs_count": 28,
    "duplicate_pairs_count": 7,
    "executed_pairs_count": 28,
    "successful_pairs_count": 28,
    "failed_pairs_count": 0,
    "not_attempted_pairs_count": 0,
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
| `batch_id` | string | yes | Unique identity **per run**: `{timeframe}-{YYYYMMDDTHHMMSSZ}-{fingerprint[:12]}-{nonce8}`. The final 8 hex characters match the filename nonce (§11 O-1). | **absent** |
| `timeframe` | "D"\|"W" | yes | Timeframe of the batch. | present (`fx_monte_carlo.py:381`) |
| `algorithm_version` | string | yes | Explicit semver of the MC engine (e.g. `mc-engine-1.0`). Bumped **only** on substantive algorithm-behavior change; MUST NOT be a git commit hash or a file hash (§11 O-2). | **absent** |
| `generated_utc` | string (ISO-8601 UTC) | yes | Wall-clock instant when the complete batch payload, including all pair results, finished assembly. Every pair's `generated_utc` MUST be ≤ this value (§5). | present (`:382`) |
| `data_fetched_utc` | string (ISO-8601 UTC) | yes | Wall-clock instant the market data was fetched. | **absent** |
| `configuration_snapshot` | object | yes | Complete effective config (§4.2). | **absent** |
| `configuration_fingerprint` | string | yes | `sha256:` + hex of canonical config incl. unique pair set (§4.3). | **absent** |
| `seed` | integer | yes | RNG seed used. | **absent** (hard-coded 42 at `:237`) |
| `requested_pairs_count` | integer | yes | Raw YAML entry count. | **absent** |
| `unique_pairs_count` | integer | yes | Deduplicated canonical pair count. | **absent** |
| `duplicate_pairs_count` | integer | yes | Raw − unique. | **absent** |
| `successful_pairs_count` | integer | yes | Unique pairs successfully simulated. | **absent** |
| `failed_pairs_count` | integer | yes | Unique pairs whose pair-level attempt began but failed to produce a valid result. | **absent** |
| `executed_pairs_count` | integer | yes | Unique pairs for which a pair-level fetch/simulation attempt began, including attempts that ultimately failed. | **absent** |
| `not_attempted_pairs_count` | integer | yes | Unique pairs not attempted due to a batch/pair precondition or interruption. | **absent** |
| `total_pairs` | integer | yes | **LEGACY-EQUIVALENT.** Sum of raw YAML occurrence counts for successful unique pairs; not the number of attempts in the deduplicating engine (§3.1). | present (`:383`) |
| `simulations` | integer | yes | Simulation count. | present (`:384`) |
| `lookback` | integer | yes | Bars used. | present (`:385`) |
| `forecast` | integer | yes | Steps forecast. | present (`:386`) |
| `confidence` | number | yes | Confidence level used for `range_90`. | **absent** |
| `student_t_df` | integer | yes | Student-t degrees of freedom. | **absent** |
| `batch_status` | enum | yes | §6. | **absent** |
| `failed_pairs` | array | yes | List of `{canonical_pair, provider_ticker, outcome, stage, reason}` (§3.4). Includes attempted failures and pairs not attempted. Empty when none. | **absent** |

**Additive-only rule:** every field above is added; none of the existing fields is renamed or removed.

---

## 2. MC PAIR RESULT SCHEMA

One object per unique pair. The results-map key and the `pair` field **keep the legacy provider form** (`EURUSD=X`) for backward compatibility (§11 O-3). Target state adds provenance fields to the existing 21:

> The example timestamps below assume the source establishes those values as true UTC instants. A session-date label alone does not justify this serialization; such a pair must fail validation under §5.1. Whether the configured source satisfies this is **NOT VERIFIED** in the E-1 WSL environment (§5.1 PV-1, §11.5 SB-1).

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
  "generated_utc": "2026-11-03T20:15:50.075751+00:00"
}
```

### 2.1 New per-pair fields

| Field | Type | Req | Semantics |
|-------|------|-----|-----------|
| `canonical_pair` | string | yes | Clean symbol (`EURUSD`). |
| `provider_ticker` | string | yes | Provider symbol with suffix (`EURUSD=X`). |
| `confidence` | number | yes | Confidence level for `range_90`. |
| `last_bar_timestamp` | string (ISO-8601 UTC instant) | yes | UTC instant of the **last market bar actually used**, only when source semantics establish an instant. |
| `data_window_start` | string (ISO-8601 UTC instant) | yes | UTC instant of the **first market bar actually used**, only when source semantics establish an instant. |
| `data_window_end` | string (ISO-8601 UTC instant) | yes | UTC instant of the **last market bar actually used** (== `last_bar_timestamp`), only when source semantics establish an instant. |

### 2.2 Preserved fields
All existing 21 fields keep their names and meanings. `range_90` and its computation are **unchanged** (§10). The results-map key and `pair` are **retained unchanged in the legacy provider form (`EURUSD=X`)**; `canonical_pair` (`EURUSD`) and `provider_ticker` (`EURUSD=X`) are added alongside for internal dedup and clarity (§11 O-3). Existing downstream consumers remain compatible through preservation of the legacy results-map keys and fields. The API builder itself is a Phase 1 implementation target and MUST be updated as specified in §8.

---

## 3. PAIR COUNTING SEMANTICS

### 3.1 Definitions (all counts are explicit; none inferred)

| Term | Definition |
|------|------------|
| Requested | Number of raw entries in `mc_data.yml` `pairs:`. |
| Unique | Number of distinct canonical pairs after dedup. |
| Duplicate | Requested − Unique (extra occurrences beyond the first for each repeated canonical pair). |
| Successful | Unique pairs that produced a valid result. |
| Failed | Unique pairs whose fetch/simulation attempt began but did not produce a valid result. |
| Not attempted | Unique pairs for which no pair-level attempt began. |

**Invariants:**
- `requested_pairs_count = unique_pairs_count + duplicate_pairs_count`
- `successful_pairs_count + failed_pairs_count + not_attempted_pairs_count = unique_pairs_count`
- `executed_pairs_count = successful_pairs_count + failed_pairs_count`
- `len(results) == successful_pairs_count`
- `len(failed_pairs) == failed_pairs_count + not_attempted_pairs_count` (entries distinguish `failed` vs `not_attempted` outcome)
- `total_pairs = sum(raw YAML occurrence_count(pair) for each successful unique pair)`
- `total_pairs` follows the raw-success-equivalent formula below; it is not an attempt count. §9.

**Worked example** — YAML: `EURUSD, GBPUSD, EURUSD, USDJPY`
```json
{
  "requested_pairs_count": 4,
  "unique_pairs_count": 3,
  "duplicate_pairs_count": 1,
  "successful_pairs_count": 3,
  "failed_pairs_count": 0,
  "not_attempted_pairs_count": 0,
  "executed_pairs_count": 3,
  "total_pairs": 4
}
```
`EURUSD` is executed **once**; its duplicate YAML entry is counted, not executed. If `USDJPY` fails, the successful unique pairs are `EURUSD` and `GBPUSD`, so `total_pairs` is 3 (EURUSD's two raw occurrences plus GBPUSD's one); `executed_pairs_count` is 3 and `failed_pairs_count` is 1.

> **Critical:** a duplicate pair is **NOT** a failed pair. `failed_pairs_count` counts only **unique** pairs that could not be produced; duplicates never inflate it, and they never mask a real failure.

### 3.2 Unique execution
Each **unique** pair is fetched and simulated **exactly once** per batch, regardless of duplicate YAML entries. Duplicates are recorded in the counts, not executed twice.

### 3.3 Duplicate handling
Duplicate YAML entries are **preserved as-is** in `mc_data.yml` (no auto-removal, no normalization to "make numbers match"). Duplicates are additionally itemized in the snapshot (§4.2).

### 3.4 Failure recording
Each failed or not-attempted unique pair produces one entry (canonical identity plus provider ticker); `outcome` distinguishes the two:
```json
{ "canonical_pair": "EURUSD", "provider_ticker": "EURUSD=X", "outcome": "failed|not_attempted", "stage": "fetch|insufficient_data|validation|precondition", "reason": "free-text" }
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
  "configured_pairs_raw": ["EURUSD", "GBPUSD", "EURUSD", "USDJPY", "EURUSD"],
  "unique_pairs": ["EURUSD", "GBPUSD", "USDJPY"],
  "duplicate_pair_counts": {"EURUSD": 2}
}
```
The raw pair sequence is retained in original order and spelling. `duplicate_pair_counts` records extra occurrences beyond the first (not total occurrences). The **full effective snapshot and raw pair evidence are stored** (not only a hash), so the batch is explainable without reversing a digest.

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

Three distinct temporal concepts across five fields; they MUST never be conflated. §5.1 gives the field rules, §5.2 the unified UTC policy for new records, §5.3 legacy filename interpretation, and §5.4 the market-timestamp rule.

| Field | Scope | Meaning | MUST NOT be used as |
|-------|-------|---------|----------------------|
| `generated_utc` | batch + pair | Batch: when the complete payload finished assembly. Pair: when that pair's MC result finished computation. Pair time MUST be ≤ batch time. | market time |
| `data_fetched_utc` | batch | When the data was fetched (wall clock). | market time |
| `last_bar_timestamp` | per-pair | The last **market bar** actually used. | generation time |
| `data_window_start` | per-pair | First market bar actually used. | — |
| `data_window_end` | per-pair | Last market bar actually used (== `last_bar_timestamp`). | — |

### 5.1 Rules
- `data_fetched_utc` is the UTC wall-clock timestamp immediately after all pair-level market-data fetch operations for the batch have completed, including failed fetches. `last_bar_timestamp`, `data_window_*` are market-bar facts. Pair-level `generated_utc` is captured when that pair's MC calculation completes; batch-level `generated_utc` is captured when the complete payload, including all pair results, finishes assembly.
- Every pair-level `generated_utc` MUST be ≤ batch-level `generated_utc`.
- `data_window_start` < `data_window_end`.
- `last_bar_timestamp` ≤ `data_fetched_utc`; `data_fetched_utc` ≤ `generated_utc`.
- Per-pair values are captured **per pair** (different pairs may be unsynchronized; especially Weekly).
- DatetimeIndex values MUST be interpreted using their actual timezone/type and classified as an instant or an exchange/session date label. Only values whose source semantics establish a UTC instant may be written to `last_bar_timestamp` and `data_window_*`; timezone-aware instants are converted to UTC before serialization.
- A naive value MUST NOT be relabeled as UTC by merely appending an offset. A session date label MUST NOT be converted to `00:00:00+00:00` or any other instant unless source semantics establish that exact instant. If the source provides only a session date label, or its timezone/instant semantics cannot be established, the pair MUST fail validation. Do not substitute `generated_utc` for a market timestamp.
- **PV-1 (NOT VERIFIED — Stage B preflight required):** the plausibility of the configured market-data source supplying market timestamps that satisfy the above has **not** been verified in E-1: the WSL checkout has no virtual environment with the project dependencies installed (`pandas`, `yfinance` absent on 2026-11-04), so the live index timezone could not be inspected. This is an unresolved technical question. Stage B MUST determine it from actual source output before relying on `last_bar_timestamp` / `data_window_*` (see §11.5 SB-1). No assumption is recorded here.
- Format convention (**SIGNED — §11 O-4**): ISO-8601 with explicit offset, `+00:00` (e.g. `2026-11-04T01:02:03+00:00`); `Z` only where `build_api` already emits it.
- The five fields MUST retain their distinct semantics: `generated_utc` (process time), `data_fetched_utc` (fetch time), `last_bar_timestamp` / `data_window_start` / `data_window_end` (market-data time). `generated_utc` MUST NOT stand in for market-data time.
- Downstream (API) MUST derive any "date" from a **market** timestamp when available; `generated_utc` may be used only as an explicit fallback.

### 5.2 Unified UTC policy for new system-generated time (**CONFIRMED — revision 5a**)

UTC is the mandatory time standard for **all new** system-generated timestamps and time-based operations.

| Area | Rule |
|------|------|
| New batch filenames | `YYYYMMDD_HHMMSS` component is UTC (`generated_utc` truncated to seconds), §11 O-1. |
| Batch IDs | `{timeframe}-{YYYYMMDDTHHMMSSZ}-{fingerprint[:12]}-{nonce8}`, UTC, with literal `Z` |
| Pair-level timestamps | `generated_utc` (UTC instant, `+00:00`) |
| Batch-level timestamps | `generated_utc` (UTC instant, `+00:00`) |
| Data-fetch timestamps | `data_fetched_utc` (UTC instant, `+00:00`) |
| Internal time comparisons | Timezone-aware UTC only; never compare naive to aware values |
| Batch ordering | By UTC `generated_utc`, then nonce (§8.3) |
| Audit timestamps | UTC, `+00:00`, in newly generated metadata and logs |
| Logs / newly generated metadata | UTC with explicit offset; state the zone explicitly |

**Rules:**
- All new timestamps MUST be **timezone-aware UTC**.
- ISO 8601 serialization MUST explicitly carry `+00:00` (e.g. `2026-11-04T01:02:03+00:00`). Bare `Z` is permitted only where an existing API builder already emits it (§5.1 O-4, §8.3).
- **Naive local timestamps MUST NEVER be used** for new system-generated records. `datetime.now()`, `datetime.today()`, `date.today()`, or any host-local clock reading without an explicit UTC timezone is prohibited for new records.
- Internal comparisons MUST normalize to UTC before comparison.
- This policy governs **new** records only. Historical artifacts are governed by §5.3 and are never rewritten (§9.4).

### 5.3 Legacy filename timezone interpretation — evidence-based (**H-4 ACCEPTED — revision 5b; evidence baseline revision 5a**)

The project owner has confirmed that inspectable historical versions of `fx_monte_carlo.py` generated the legacy `YYYYMMDD_HHMM` filename component with `datetime.now(timezone.utc)`. Revision 5a re-confirmed this directly from Git history in E-1: every committed version of `fx_monte_carlo.py` (`d255a44`, `7f36d4f`, `8205688`, `5868a7e`, `13b16f3`, `653b807`, `49e86cd`, `706ce69`, `6f6dab3`) computes the filename stamp from `datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")`; no committed version uses a local-time generator.

| Provenance class | Evidence | Filename timestamp may be interpreted as UTC? | Ordering use | Chronology claim |
|------------------|----------|-----------------------------------------------|--------------|------------------|
| L-A — attributable to a committed generator version | Artifact demonstrably produced by one of the versions above | **YES** | Verified UTC ordering key | May be compared on a UTC basis with v1.0 instants |
| L-B — unknown provenance (e.g. damaged, hand-edited, or non-attributable artifact) | No evidence tying the file to a UTC-generating version | **NO** | Deterministic ordering key **only** | MUST NOT be claimed as a verified UTC instant; MUST NOT be claimed globally chronological against v1.0 artifacts |

**Rules:**
- UTC interpretation is permitted **only** when reliable evidence ties the **specific artifact** to an exact generator version and establishes that version's timezone behavior. The fact that a compatible UTC-generating code version existed is not, by itself, artifact-to-code provenance. Attribution and its evidence basis MUST be recorded when a file is classified L-A (for example, in the builder log/metadata).
- For L-B files the filename timestamp is used **only** as a deterministic ordering key. The contract makes **no claim** that it represents a verified UTC instant.
- Where a file cannot be classified, it is treated as **L-B**.
- Legacy artifacts are never rewritten to "fix" their timestamps (§9.4).
- This section constrains interpretation only; it does not weaken §8.3.

### 5.4 Market timestamps — no fabricated instants (**CONFIRMED — revision 5a**)

- Market session-date labels are **NOT** converted into artificial UTC instants.
- A market timestamp may be represented as a UTC instant **only** when the data source semantics establish that it is a real instant.
- If a source supplies only a date label (a session date, not an instant), the correct target representation is a validation failure for that pair (§5.1, §7) — not a synthesized midnight instant and not a substituted `generated_utc`.
- Verification status of the configured source's instant semantics in E-1: **NOT VERIFIED** (§5.1 PV-1).

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
| V-5 | `range_90` has exactly 2 finite elements and `range_90[0] < range_90[1]`; zero-width intervals are validation failures. |
| V-6 | `data_window_start < data_window_end`. |
| V-7 | `last_bar_timestamp ≤ data_fetched_utc ≤ batch generated_utc`, and each pair-level `generated_utc` ≤ batch-level `generated_utc`. |
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
Legacy: ^mc_(D|W)_all_pairs_\d{8}_\d{4}\.json$
v1.0:  ^mc_(D|W)_all_pairs_\d{8}_\d{6}_[0-9a-f]{8}\.json$
```
- The six-digit UTC timestamp plus nonce form is required for v1.0 files. The four-digit legacy form remains accepted only for schema-less historical artifacts; it MUST NOT be used for new writes. Filename form and schema MUST match exactly as specified in §8.3. The current prefix-only filter (`build_api.py:47`, `startswith("mc_D_")`) is **insufficient** and MUST be replaced by these schema-aware strict forms.
- Any filename containing `_fib` is **explicitly excluded**, independent of the pattern.

### 8.2 Source directory restriction
- Only `mc_results/` is scanned.
- Fib output (future `mc_results_fib/`, Phase 2) is never scanned by the MC API builder.

### 8.3 Schema compatibility, selection, and batch-status gate (**SIGNED — §11 O-6; H-5 ACCEPTED — §11.6**)
- Schema classification and filename pairing: missing `metadata.schema_version` with a legacy four-digit filename means **legacy schema**; `"1.0"` with a v1.0 six-digit-plus-nonce filename means Contract v1.0. Missing schema with a v1 filename, or schema `"1.0"` with a legacy filename, MUST be rejected and logged. Any unsupported explicit version is rejected and logged with either filename form. Legacy files MUST NOT be assigned an invented `batch_status` or treated as v1.0 validated.
- Legacy eligibility uses only legacy rules: strict legacy filename, parseable JSON, matching `metadata.timeframe`, and usable `results` structure; preserve legacy payload handling and original `=X` keys. Since legacy files may have no `schema_version` or `batch_status`, do not fabricate either or claim v1.0 validation. Log the eligibility class and any rejection reason. Legacy filename provenance and timestamp classification follow §5.3 (H-4).
- For v1.0, validate the declared schema and status. `failed` batches MUST be skipped and logged (filename, `batch_id`, reason), while retained on disk. `partial` batches are eligible for publication; preserve `batch_status`, `failed_pairs_count`, and `failed_pairs` in API metadata.
- Legacy filename timestamps have no inherent timezone semantics. The tracked historical `fx_monte_carlo.py` implementations in this repository construct the `YYYYMMDD_HHMM` filename component with `datetime.now(timezone.utc)`, so artifacts attributable to those implementations use UTC independent of host-local timezone. For a legacy artifact that cannot be tied to that generator history, its filename timestamp may be used only as a deterministic legacy ordering key, not as a verified UTC instant. The provenance classes and the exact rules derived from this are defined in **§5.3** (L-A / L-B); that section governs, and the builder MUST classify every legacy candidate into L-A or L-B before applying the ordering rules below.
- For parseable artifacts, order by validated metadata `generated_utc`. For unparseable/malformed artifacts without usable metadata time, use the filename timestamp only as the deterministic ordering key described in §5.3 and mark them malformed. For v1.0, filename timestamp MUST equal `generated_utc` converted to UTC and truncated to seconds; mismatch means reject and log. If `generated_utc` ties, order by filename nonce lexicographically as a stable secondary key; for legacy files without a nonce, use the full filename lexicographically. Never depend on directory iteration order. Do not claim globally chronological ordering between legacy artifacts whose time base is unverified (L-B) and v1.0 artifacts unless their time bases can be reliably normalized. L-A legacy artifacts (§5.3) and v1.0 artifacts share a UTC time basis and may be compared on it. Where time bases are incomparable, `latest_seen_batch` MUST expose `ordering_status: "incomparable"` and the newest candidate within each comparable time-base group; it MUST NOT present one as the global chronological winner, and it MUST label any L-B candidate as having an unverified time basis. `latest_seen_batch` otherwise identifies the newest candidate under these ordering rules (including malformed/unsupported/failed candidates); `latest_eligible_batch` is the newest parseable, schema/filename-matched, status-eligible candidate; `latest_published_batch` is the batch actually written to API output. A malformed, unsupported, or failed artifact MUST NOT silently become eligible. A valid older eligible artifact may remain published when a newer candidate is rejected, but the required `latest_seen_batch`, `latest_eligible_batch`, and published identity plus rejection/fallback reason MUST remain distinguishable and visible under the existing API metadata/logging contract. Do not present fallback data as the newest generated artifact. Do not add response fields or runtime behavior beyond this contract. If an ambiguity remains, report it as open rather than infer a policy.

### 8.4 Current API defects — REPORT ONLY, NO DELETION (**SIGNED — §11 O-5**)
- `api/latest/` retains legacy pairs `CADNZD`, `CHFNZD` and lacks `NZDCAD`.
- `api/latest/all.json` lags the newest `mc_results` artifacts because recent files are uncommitted.
- Phase 1 MUST NOT delete any historical API data. The builder MAY **report**: stale pair, stale date directory, missing pair, outdated API artifact.
- Any pruning is a separate, separately-approved change (out of Phase 1 scope).

---

## 9. BACKWARD COMPATIBILITY

9.1 **Additive only.** New fields are added; existing field names and `range_90` semantics are unchanged.
9.2 **`total_pairs` is the legacy-equivalent success count under the new deduplicated execution model**: sum the original YAML occurrence counts for successful unique pairs. It is not the historical actual execution count and cannot reconstruct whether separate executions of the same duplicate entry would each have succeeded. `executed_pairs_count` provides actual unique pair attempts, including failures; new consumers SHOULD use the explicit counts.
9.3 **Downstream consumers** of the published API retain compatibility through preserved legacy fields. The API builder itself is explicitly in scope for Phase 1 changes and MUST implement the ingestion contract in §8, including strict filename filtering, `_fib` exclusion, schema classification, status gating, partial publication, and deterministic fallback selection.
9.4 **No historical rewrite.** `mc_results/*` and `api/*` are not migrated or rewritten. Only newly generated batches adopt v1.0 fields.
9.5 **`range_90` unchanged**; `confidence` is added additively. No `range_0.90` alias (§10).
9.6 **Legacy `=X` keys preserved** (**SIGNED — §11 O-3**): results-map keys and `pair` remain `EURUSD=X`; `canonical_pair` / `provider_ticker` are added. No downstream consumer is forced to change solely because of the results-map key or pair identity rules; the API builder changes described in §9.3 remain required. A full consumer audit is not required for Phase 1.
9.7 **`total_pairs` is legacy/deprecated** but retained as a legacy-equivalent statistic; new consumers SHOULD use the explicit counts (§3.1) instead.

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
| O-1 | Run identity, artifact name, and publication | **MODIFIED-ACCEPT.** Capture one UTC batch timestamp and one 8 lowercase hex nonce. `filename_timestamp = batch_id_timestamp = batch generated_utc converted to UTC and truncated to seconds`; filename is `mc_{timeframe}_all_pairs_YYYYMMDD_HHMMSS_{nonce8}.json`; `batch_id` is `{timeframe}-{YYYYMMDDTHHMMSSZ}-{fingerprint[:12]}-{nonce8}`. The nonce matches the filename and batch ID. Generate nonce from a cryptographically secure random source (UUID-derived or equivalent; never PID/time alone). Prepare the complete JSON in a temporary file that is not a matching batch filename. Publish using a filesystem operation with exclusive-create/no-replace atomic semantics so consumers cannot observe partial JSON and existing artifacts cannot be overwritten. A check-then-`os.replace()` is not sufficient; do not reserve the final path as an empty visible batch file. On destination collision, discard the unpublished temporary file, generate a new nonce, update the ID/filename, and retry. Validate this mechanism on the actual Stage B target filesystem (E-1, §0.2 E-3), not only in the project directory. The E-1 `mc_results` is an ordinary directory; a symlink-shape assumption MUST NOT be applied to it (§11.5 SB-3). API recency uses batch `generated_utc`.
| O-2 | `algorithm_version` | **ACCEPT.** Explicit semver string (e.g. `mc-engine-1.0`). MUST be bumped on any substantive algorithm-behavior change; log/comment/formatting-only changes need not bump it. MUST NOT be a git commit hash or a file hash. |
| O-3 | Results-map key | **DO NOT CHANGE THE LEGACY KEY.** Results-map key and `pair` stay `EURUSD=X`; add `canonical_pair` (`EURUSD`) and `provider_ticker` (`EURUSD=X`); dedup internally on `canonical_pair`; do NOT delete duplicate YAML entries. Rationale: only `get_mc_data.py` / `build_api.py` are known `=X`-tolerant; a complete consumer audit has not been performed, so preserving keys is the safer engineering choice. |
| O-4 | Timestamp serialization | **ACCEPT.** ISO-8601 with explicit UTC offset, `+00:00` (e.g. `2026-11-04T01:02:03+00:00`). |
| O-5 | Historical API cleanup | **ACCEPT.** Phase 1 deletes nothing; the builder **reports** stale pair / stale date directory / missing pair / outdated API artifact only. |
| O-6 | `failed` batches | **ACCEPT.** `batch_status = "failed"` MUST be written to disk, but the API MUST NOT ingest it: check `batch_status` → skip → log the reason → retain the artifact for audit. |

## 11.1 Resolved review findings (P0/P1)

| ID | Contract rule |
|----|---------------|
| P0-1 | Unique UTC-second filename plus nonce; no-overwrite atomic creation; filename nonce matches `batch_id`; API recency is by `generated_utc`. |
| P0-2 | `total_pairs` is successful raw-equivalent count; `executed_pairs_count` counts attempts, and `not_attempted_pairs_count` closes the count model. |
| P0-3 | Missing schema is legacy, explicit 1.0 is v1, other explicit versions are skipped/logged. Legacy has no fabricated status. |
| P1-1 | Snapshot stores ordered `configured_pairs_raw`, sorted unique canonical `unique_pairs`, and extra occurrence counts in `duplicate_pair_counts`. Fingerprint uses the sorted unique set and effective calculation settings. |
| P1-2 | Secure random nonce, not PID/time alone; destination collision check and retry; atomic no-overwrite write. |
| P1-3 | Batch fetch timestamp is immediately after all pair fetch operations finish. Index timezone is interpreted and converted based on actual type/source semantics; never attach UTC to an unverified naive value. |
| P1-4 | V-5 requires strictly increasing range bounds; zero-width is invalid. Data windows use first/last bars in the cleaned valid bars actually supplied to the calculation. |
| P1-5 | Failed/unsupported newest batches are logged and skipped in favor of newest eligible older batch. Partial is publishable with failure metadata. API metadata/logs expose latest seen/eligible/published and fallback reason. |
| R4-1 | Current evidence establishes current behavior; only the explicitly frozen contract establishes target behavior. |
| R4-2 | Snapshot JSON has a single sorted `unique_pairs` list; raw entries and extra duplicate counts are preserved separately. |
| R4-3 | Temporary complete artifact plus atomic exclusive no-replace publication; no check-then-replace and no visible empty reservation file. |
| R4-4 | `total_pairs` is only the deduplicated model's legacy-equivalent success statistic, not historical execution truth. |
| R4-5 | Filename timestamp, batch ID timestamp, and truncated UTC `generated_utc` align; nonce is identical across filename and ID. |
| R4-6 | Legacy/v1 filename form must match missing/1.0 schema exactly; mismatch is rejected and logged. |
| R4-7 | Builder changes are in Phase 1 scope; compatibility claim applies to downstream API consumers through preserved fields. |
| R4-8 | Malformed artifacts use filename timestamp for deterministic seen ordering; v1 time mismatch is rejected; ties use filename nonce. |
| R5-1 | Pair completion time is no later than batch payload completion time; the fields have distinct documented capture points. |
| R5-2 | Market-bar timestamps require source semantics establishing an instant; session date labels are never coerced to UTC instants. |
| R5-3 | Compatibility claims concern downstream consumers; the builder is a Phase 1 implementation target. |
| R5a-1 | Stage B executes in the WSL workstation `/home/qili/projects/fx_monte_carlo`; the cloud Ubuntu root is a separate environment with no transferred state (§0.2, §11.4). |
| R5a-2 | UTC is mandatory for all new timestamps and time-based operations; new records are timezone-aware and serialize `+00:00` (§5.2). |
| R5a-3 | Legacy filename UTC interpretation requires evidence (L-A); unknown-provenance (L-B) files are ordering keys only and carry no UTC or global-chronology claim (§5.3, §8.3). |
| R5a-4 | Market session-date labels are never fabricated into UTC instants; source instant semantics must be established or the pair fails validation (§5.4, SB-1). |
| R5a-5 | Requirements inherited from revisions 1–5 (counts, fingerprint, schema/filename pairing, no-replace publication, API eligibility, legacy compatibility, preservation, failed-batch handling, zero-pair preflight) are unchanged and unweakened. |

**Stage B boundary notes:** An effective configuration with `unique_pairs_count == 0` is invalid and MUST be rejected before a batch is instantiated; it must not produce an `ok` empty-results batch. Log the configuration error. Because no batch is instantiated, this preflight rejection is distinct from a `failed` batch, which §6 requires to be written. No-replace publication MUST be validated on the actual target filesystem (E-1, §11.5 SB-3). The E-1 `mc_results` path is an ordinary directory (§0.2); symlink handling MUST NOT be introduced into the E-1 implementation.

**Count edge rule:** Every configured unique pair is classified exactly once as successful, failed, or not attempted. `failed_pairs` records failed and not-attempted identities with `outcome` distinguishing them. `failed_pairs_count` counts attempted failures; `not_attempted_pairs_count` counts unattempted pairs. Therefore `successful_pairs_count + failed_pairs_count + not_attempted_pairs_count = unique_pairs_count`, `executed_pairs_count = successful_pairs_count + failed_pairs_count`, and `len(failed_pairs) = failed_pairs_count + not_attempted_pairs_count`. `batch_status` is `ok` only when failures and not-attempted counts are zero; `partial` when at least one pair succeeds and some pair fails/is not attempted; `failed` when no pair succeeds.

## 11.6 Human policy decisions H-4 and H-5 (**DECIDED — ACCEPTED; no Freeze implied**)

| ID | Decision | Determination |
|----|----------|---------------|
| H-4 | Historical legacy artifact timestamp classification | **ACCEPT L-A/L-B dual classification.** L-A requires reliable provenance tying the specific artifact to an exact generator version whose UTC filename behavior is established. Code history alone is insufficient. L-B covers unknown or insufficient provenance and permits deterministic ordering only, with no UTC-instant or unsupported cross-class chronology claims. Rationale: preserve useful history without asserting more temporal certainty than artifact-specific evidence supports. Operational consequence: Stage B must classify each legacy candidate and record the provenance basis before making recency claims (§5.3, §8.3, SB-4). |
| H-5 | Legacy artifact eligibility and API fallback | **ACCEPT strict Legacy/v1.0 separation and transparent fallback.** Legacy and v1.0 filename/schema pairs remain distinct; eligibility follows the class-specific rules in §8.3. Rejections are logged with reasons; a prior eligible artifact may remain published, with `latest_seen`, `latest_eligible`, and published identity plus fallback reason distinguishable. No v1.0 metadata is fabricated for legacy artifacts, and no new API fields/runtime behavior or historical migration is authorized by this decision. Rationale: preserve backward compatibility while making rejection and fallback auditable. |

These decisions settle H-4 and H-5 only. They do **not** approve H-1 (human Contract Freeze), H-2 (Stage B Authorization), or H-3 (PV-1 acceptance); those remain open (§12 and the finalization audit).

---

## 11.4 Environment finalization (**CONFIRMED — revision 5a**)

| ID | Decision | Determination |
|----|----------|---------------|
| ENV-1 | Stage B execution target | **WSL development workstation**, canonical root `/home/qili/projects/fx_monte_carlo` (§0.2 E-1). |
| ENV-2 | Cloud Ubuntu environment | `/home/ubuntu/projects/fx_monte_carlo` is a **separate** environment (§0.2 E-2); no state, Git, or execution assumption transfers in either direction. |
| ENV-3 | Stage A evidence status | Stage A findings are **historical discovery evidence** from E-2, not proof of E-1 state (§0.2 E-4). |
| ENV-4 | Filesystem | E-1 `mc_results` is an ordinary directory, not a symlink; Stage B operates on the actual WSL filesystem (§0.2 E-3). |
| ENV-5 | UTC policy | UTC mandatory for all new system-generated timestamps and time operations; timezone-aware, `+00:00` (§5.2). |
| ENV-6 | Legacy filename UTC | UTC interpretation only for L-A (evidence-attributable) legacy files; L-B is an ordering key only (§5.3). |
| ENV-7 | Market timestamps | No fabricated instants; UTC instant only where source semantics establish a real instant (§5.4). |

## 11.5 Stage B boundary (**NOT AUTHORIZED**)

| ID | Boundary rule |
|----|---------------|
| SB-1 | Stage B MUST first establish, in E-1, whether the configured market-data source yields index values whose semantics establish a real UTC instant (§5.1 PV-1). **Status: NOT VERIFIED.** If the answer is no, affected pairs fail validation under §5.1/§7; this contract does not authorize inventing an instant. |
| SB-2 | Stage B MUST re-verify in E-1 any E-2 Stage A finding it depends on (artifact inventory, counts, API state, source versions, scheduler configuration) before relying on it. |
| SB-3 | No-replace atomic publication (§11 O-1) MUST be validated on the actual E-1 `mc_results` filesystem, without symlink assumptions. |
| SB-4 | Stage B MUST classify every legacy artifact as L-A or L-B per §5.3 before any recency claim, and MUST NOT present an unverified time basis as a UTC instant or as a global chronological winner. |
| SB-5 | Stage B MUST NOT begin from this revision. `PHASE_1_CONTRACT_FINALIZATION_AUDIT.md` records the finalization audit only; it is not authorization. |

---

## 12. FREEZE CHECKLIST

This contract becomes **FROZEN v1.0** when all are true:

- [x] §11 decisions O-1 … O-6 resolved (O-1 modified; O-2 … O-6 accepted).
- [x] Phase 0 / Stage A evidence precedence (§0) acknowledged.
- [x] Final Contract Audit of Revision 5: pair and batch generation instants have distinct capture points and valid ordering; market timestamp provenance rules reject coercion; API builder and downstream compatibility roles are distinct; zero-pair preflight rejection is distinct from a failed batch; and legacy malformed ordering is not falsely represented as UTC.
- [x] Revision 5a environment finalization (§0.2, §11.4): E-1 WSL target designated; E-2 cloud Ubuntu environment explicitly separated; E-1 `mc_results` confirmed as an ordinary directory.
- [x] Revision 5a UTC policy (§5.2): UTC mandatory for all new timestamps and time-based operations; evidence-based legacy interpretation (§5.3) with L-B files not assigned fabricated UTC chronology; market session-date labels not fabricated into UTC instants (§5.4).
- [x] H-4/H-5 policy decisions recorded as **DECIDED — ACCEPTED** (§11.6); this decision recording does not grant Contract Freeze, Stage B authorization, or PV-1 acceptance.
- [ ] **HUMAN FREEZE — UNCHECKED.** Final human confirmation that §1–§12 contain no remaining contract conflicts, that the documented WSL/cloud environment split and the documented legacy compatibility/API fallback behavior are accepted, and that outstanding items marked **NOT VERIFIED** (PV-1 / SB-1) are acceptable to carry into Stage B as preflight checks.
- [ ] Explicit Stage B authorization issued **after** this file is frozen.

**Until the two unchecked boxes above are signed by a human, Stage B MUST NOT begin.** No code, config, data, workflow, or schedule has been modified by Stage A or by any revision of this document. No Git commit has been made and no freeze has been applied. The pre-existing untracked data files and this phase's documents are to be left in place.
