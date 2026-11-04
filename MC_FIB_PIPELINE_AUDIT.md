# Fibonacci Segmentation Pipeline — Source-to-Output Audit

**Audit date:** 2026-11-03  
**Scope:** ai_training_cnn/fib_mc_segment.py, the copied script in fx_monte_carlo, fx_monte_carlo.py, mc_data.yml, dated D/W MC and Fib JSON files, and direct consumers/orchestration in fx_monte_carlo.  
**Mode:** Read only. No source, configuration, JSON data, scheduler, or trading logic was changed. This report is the sole deliverable created for this audit.

## 1. Executive Summary

The pipeline is confirmed: fx_monte_carlo.py creates timestamped D/W MC batches; fib_mc_segment.py independently selects the earliest timestamped source file for each timeframe/date, annotates every result, adds Fib metadata, and writes a separate date-only _fib.json file. It does not overwrite the original MC file. In the inspected 2026-11-03 artifacts, all non-Fib fields and metadata match the selected source exactly, and all 29 unique result entries received Fib fields.

The proportional level calculation is mathematically correct for finite, increasing ranges using serialized MC endpoints. The implementation is not safe for invalid or out-of-range data: it maps reversed/zero-width intervals to F5, maps NaN or out-of-range prices to a plausible internal zone, and emits no status to disclose that condition. Shared boundaries are represented as overlapping closed intervals but assigned to the lower-index zone by iteration order. The action label is a heuristic combining zone and p_up; it is not validated predictive or trading evidence.

Pair accounting is inconsistent: config requests 35 entries, with six symbols repeated once, while source and Fib results contain 29 unique keys and metadata still reports 35. Source selection works exactly as documented, but for D it deliberately chooses 04:18 and ignores a later 05:04 run. D and W snapshots are about 47 minutes apart. The Fib script is not found in any direct runtime/scheduler invocation; **execution status: NOT VERIFIED**. The project API builder reads all mc_*.json files, so it can ingest Fib fields on a future API rebuild; current API JSON checked during this audit does not contain Fib fields and is older than the Fib output.

**Final classification: NOT READY — DATA INTEGRITY ISSUES.** Minimum remediation before Shadow Observation: explicit input/range validation and status, documented half-open zone ownership, removal or neutral renaming of action labels, correct unique-pair accounting, and a confirmed controlled invocation/consumer boundary. Keep D and W records separately timestamped and keep Fib out of decision logic.

## 2. Confirmed System Architecture

| Stage | Evidence | Status |
|---|---|---|
| MC generation | fx_monte_carlo.py, run_mc() lines 214–312; main() lines 350–403 | Confirmed by source |
| MC source JSON | mc_results/mc_{D,W}_all_pairs_YYYYMMDD_HHMM.json | Confirmed by source and actual files |
| Fib annotation | ai_training_cnn/fib_mc_segment.py, process() lines 114–145; copied script has matching logic | Confirmed by source; output metadata corroborates past execution |
| Fib output | mc_results/mc_{D,W}_all_pairs_YYYYMMDD_fib.json | Confirmed by source and actual files |
| Potential API ingestion | build_api.py, _load_results() lines 35–62 | Source reads every JSON with a nested results map; actual current API output had no Fib fields |
| Local MC reader | get_mc_data.py, _local_files() lines 64–76 | Filename regex accepts timestamped JSON and excludes date-only _fib.json |
| Trading consumer | No trading-system consumer was audited or established in this scope | Not verified; file presence is not proof |
| Fib invocation/scheduler | Direct-reference search found only Fib script usage text, no shell/cron/systemd invocation | Execution status: NOT VERIFIED |

## 3. Actual Data Flow

1. fx_monte_carlo.py loads mc_data.yml. It configures 5,000 simulations, confidence 0.90, Student-t df 5, D lookback/forecast 90/5, W 104/5, and 35 raw pair entries.
2. run_mc() fetches closes, simulates terminal prices, calculates lower/upper quantiles from CONFIDENCE, and serializes current_price, range_90, p_up, p_down, expected_price, VaR/CVaR, drift/volatility, timeframe, and generated_utc.
3. main() writes a timestamped root object containing metadata and results through save_batch_mc_safely(). That MC save uses a temporary file followed by replace (fx_monte_carlo.py lines 319–344).
4. Fib process() independently searches for one timestamped source per timeframe/date, reads the JSON, changes each result by adding/replacing its fib member, and adds/replaces metadata.fib_segmentation.
5. Fib writes a separate mc_{TF}_all_pairs_{day}_fib.json with ordinary Path.write_text() (fib_mc_segment.py lines 129–143). It does not write to the source path.

Fib consumes range_90[0:2], current_price, and optionally p_up (default 50) and regime (default empty string). Missing range/current fields raise during segmentation; there is no per-pair recovery.

### Source/output comparison for 2026-11-03

- D output metadata names mc_D_all_pairs_20261103_0418.json; W names mc_W_all_pairs_20261103_0505.json.
- For both timeframes, root keys and result key sets match source; each source has 29 keys, all output records have fib, and every original result field other than fib compares equal. Original metadata is preserved with fib_segmentation added.
- Both outputs preserve metadata.total_pairs: 35 despite 29 unique result entries.
- Source generated_utc values are D 04:18:48 UTC and W 05:05:57 UTC, a 47m09s difference.
- The source_file and date values match the selected source and requested date.

## 4. Source File Selection Analysis

process() builds an exact filename regex for mc_{timeframe}_all_pairs_{day}_{HHMM}.json and separately globs candidates for D then W (fib_mc_segment.py lines 114–126). It extracts HHMM from the filename; pick_earliest() sorts strings ascending and returns the first (lines 109–111). Fixed-width digit ordering is chronological for valid HHMM values. D and W are selected independently. Malformed filenames and date-only Fib outputs are ignored.

On 2026-11-03, D candidates included 0418 and 0504; the script selected 0418. W selected 0505. A later MC run is ignored by design. Earliest-of-day can preserve a stable baseline and avoid mixing later runs, but can also select stale or incomplete data. The script does not validate pair coverage or batch success before choosing. If the selected JSON is malformed or segmentation fails, there is no fallback to a later candidate. If no candidate exists, it prints a notice and continues to the other timeframe.

Selection uses filename HHMM, not generated_utc. File mtimes are shortly after embedded MC generation timestamps. Fib outputs were written at 07:20 UTC, later than both selected source files. These facts corroborate later output creation but do not prove scheduler or invocation.

**Assessment:** Deterministic and consistent with the stated earliest-snapshot policy. Whether earliest is the desired operational snapshot is a policy choice. Add completeness checks if this is to become operational; preserve source age and D/W timestamp differences.

## 5. Fibonacci Mathematics Audit

FIB_RATIOS is exactly [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0] (fib_mc_segment.py line 24). FIB_ZONES maps adjacent ratios to the six expected tags/labels (lines 27–34).

For lo < hi, fib_levels() computes lo + (hi - lo) * ratio (lines 51–53). segment_pair() uses the same values for zone edges (lines 67–70). This math is correct relative to values loaded from MC JSON. It is not using full-precision simulation quantiles because MC serialized rounded endpoints.

position_in_zone_pct is correctly calculated as (price - zone_lower) / zone_width * 100 for the selected zone when width is positive (lines 81–95). For out-of-range prices it can be negative or exceed 100 due to edge-zone assignment.

Fib levels and zone edge prices are rounded to six decimals. MC range_90 is rounded to 3 decimals for JPY symbols and 5 for others (fx_monte_carlo.py lines 288–296). In inspected outputs, max level rounding difference versus recomputation from serialized ranges was about 4.8e-7. Fib assignment uses loaded unrounded floats, but these floats already reflect MC serialization rounding. The extra display decimals do not restore discarded source precision.

## 6. Boundary and Out-of-Range Analysis

locate_zone() checks a <= pos <= b in list order (fib_mc_segment.py lines 56–64). At shared boundaries, the first/lower-index zone wins:

| Position | Runtime assignment |
|---:|---|
| 0.236 | F0 |
| 0.382 | F236 |
| 0.500 | F382 |
| 0.618 | F5 |
| 0.786 | F618 |
| 1.000 | F786 |

The JSON stores each adjacent zone with both endpoints, so the representation looks overlapping and does not disclose the runtime tie-break. A half-open convention would be clearer: lower-inclusive and upper-exclusive, with the last zone including the global upper bound.

For valid positive-width ranges, position below zero maps to zone index 0 and above one maps to index 5 (line 63). Output labels it as F0/F786 without a range status; position may fall below 0% or exceed 100%. In inspected 2026-11-03 D and W files all prices happen to be within range (29/29 each); the code defect remains.

For hi <= lo, locate_zone() returns index 3, F5 (lines 56–58). segment_pair() still calculates levels/edges, and if zone width is zero it reports 50.0% (lines 83–85). Reversed ranges also proceed with descending edges. NaN/infinity are not rejected: NaN comparisons fail, the fallback selects zone 0, and computations may propagate non-finite values. Python json.dumps() defaults to allowing NaN/Infinity tokens, which are not strict JSON. Missing range/current fields or non-numeric values raise and abort processing; no explicit status is emitted.

Recommended classification: BELOW_RANGE, WITHIN_RANGE, ABOVE_RANGE, INVALID_RANGE, MISSING_DATA. Outside or invalid records should not be assigned an internal zone.

## 7. Action Label Assessment

fib_bias_action() marks p_up >= 50 as bullish, otherwise bearish (fib_mc_segment.py lines 37–48), and maps zone/probability as follows:

| Zone index | p_up >= 50 | p_up < 50 |
|---:|---|---|
| 0 or 1 | BUY_ZONE | REVERSAL_WATCH_LONG |
| 2 | BUY_LIMIT | NEUTRAL |
| 3 | NEUTRAL | SELL_LIMIT |
| 4 | REVERSAL_WATCH_SHORT | SELL_ZONE |
| 5 | REVERSAL_WATCH_SHORT | SELL_ZONE |

The 2026-11-03 D artifacts contain 18 SELL_LIMIT, 9 BUY_LIMIT, 2 SELL_ZONE. W contains 16 BUY_LIMIT, 11 SELL_LIMIT, 2 NEUTRAL.

These are heuristic combinations, not statistically validated results. p_up is a simulated terminal-price proportion, not calibrated market probability or trade win rate. Fib position is location within an MC interval, not direction, support, or resistance. BUY_LIMIT/SELL_LIMIT look executable despite the stated experimental/non-trading intent. Exclude action from a shadow schema or replace it with descriptive, non-directional context; any entry bias should remain UNVALIDATED.

## 8. Monte Carlo Input Integrity

mc_data.yml line 3 configures confidence 0.90. run_mc() calculates percentiles at (1-CONFIDENCE)/2 and (1+CONFIDENCE)/2 (fx_monte_carlo.py lines 257–259), so current range_90 is a central 90% terminal-price interval. It is rounded before serialization (line 296), and Fib only receives those rounded values.

The field name remains range_90 even if confidence is later changed; metadata omits confidence. Current naming is accurate for current config, but not self-describing for other settings. Record confidence in metadata or use a schema name that reflects configured coverage.

## 9. JSON Output Integrity

Observed schema is consistent: root metadata/results are retained, with Fib added to each result and fib_segmentation added to metadata. Method, ratios, zones, source_file, and date match code and selected sources.

mc_data.yml lines 14–48 contains 35 entries. EURUSD, GBPUSD, NZDUSD, USDCAD, USDCHF, USDJPY are each repeated once, resulting in 29 unique symbols. MC main() loops raw pairs and writes results into a dict (fx_monte_carlo.py lines 360–370), while total_pairs is len(all_results) (lines 379–388). Thus duplicate simulations can overwrite result keys while inflating metadata. Fib preserves this mismatch. Failed/missing pairs are not listed separately.

Fib output overwrites a same-date output on rerun (fib_mc_segment.py line 141) and writes directly, not atomically (line 142). Interruption can leave truncated JSON. No completion marker or post-write validation exists. A D output may be refreshed even if W processing later fails. If an error occurs before writing, an older date-matched output can remain.

**Potential API ingestion:** build_api.py _load_results() scans every *.json and loads nested results (lines 35–62), without excluding _fib.json; a future API build can ingest Fib fields. Fib and source preserve the same generated_utc, so tie behavior and filename sort order can affect which record wins in _group_latest() (lines 65–83). This is not evidence of a trading consumer. Current api/latest/EURUSD.json contains no fib and has an mtime of 05:04 UTC, earlier than the 07:20 Fib output. get_mc_data.py excludes date-only Fib names because its regex requires YYYYMMDD_HHMM.json (lines 64–76).

## 10. D1/W1 Separation

D and W are processed independently in a fixed loop (fib_mc_segment.py line 116), each with its own source and MC range. No D/W values are combined. Their source timestamps differ by 47m09s, so snapshots are not synchronized. Future observations should retain timeframe and source timestamp separately. D1 can be the entry-location observation and W1 longer-term context, but neither Fib zone is directional evidence; W1 should not independently create or veto a trade. No such decision logic was demonstrated here.

## 11. Runtime and Scheduling Findings

Direct-reference searches in the scoped project found only Fib usage examples. No shell, cron, systemd, or orchestration file directly invokes fib_mc_segment.py. Output artifacts prove that files were written after their MC inputs, not whether execution was manual or scheduled.

**Execution status: NOT VERIFIED.** Automatic execution, ordering after MC generation, race possibility, repetition policy, and failure reporting are unknown.

## 12. Shadow Observation Readiness

Fib output provides pair/timeframe, MC generated_utc, current_price, range_90, p_up/p_down, levels, current zone, and source filename in metadata. It lacks a separate observation ID/time, explicit range status, per-record source lineage, invalid/incomplete status, outcomes at 1/3/5 periods, zone transitions, and subsequent range coverage. It does not resolve future observations.

The current script is a segmentation annotator, not a complete shadow observation system. Before shadow use, define an idempotent observation record and resolution process using only prices available after each horizon. Remove the action label and make invalid/outside data explicit. No logger or resolver was added in this audit.

## 13. Risk Classification

### Confirmed Defects

| ID | Severity | Evidence | Behavior / consequence | Recommendation |
|---|---|---|---|---|
| F-01 | HIGH | fib_mc_segment.py lines 56–64, 81–102 | Outside prices map to F0/F786; hi <= lo maps to F5; no state indicates invalid/outside location. | Validate finite values and hi > lo; represent explicit status and no internal zone outside range. |
| F-02 | MEDIUM | fib_mc_segment.py lines 27–34, 60–62, 73–78 | Output zone boundaries overlap while runtime silently assigns shared boundary to lower-index zone. | Document and serialize half-open ownership; final zone includes global upper bound. |
| F-03 | HIGH | fx_monte_carlo.py lines 360–370, 379–388; mc_data.yml lines 14–48; actual artifacts | Duplicate symbols simulated more than once and overwritten in results, while metadata says 35 for 29 keys. | Deduplicate preserving order; report requested/unique/successful/failed counts and pair errors. |
| F-04 | MEDIUM | fib_mc_segment.py lines 141–142 | Same-date outputs overwrite non-atomically; interruption can leave truncated output. | Validate and atomically replace completed output. |
| F-05 | MEDIUM | fib_mc_segment.py lines 37–48, 98–102; outputs | Order-like labels derive from zone and p_up threshold without validation. | Exclude or rename to non-directional, explicitly unvalidated description. |

### Design Trade-offs

| ID | Severity | Evidence | Assessment | Recommendation |
|---|---|---|---|---|
| D-01 | INFORMATIONAL | fib_mc_segment.py lines 114–126; D candidates 0418/0504 | Earliest selection is deterministic and may preserve a baseline, but ignores later data and may choose incomplete output. | Keep only as explicit policy; add coverage/completeness checks and source age. |
| D-02 | LOW | fib_mc_segment.py lines 51–53, 67–78; fx_monte_carlo.py lines 288–296 | Fib uses serialized rounded ranges, then rounds displayed levels independently. Math is correct for serialized values, not full-precision quantiles. | Preserve source precision if materially required; disclose basis. |
| D-03 | LOW | build_api.py lines 35–62, 65–83 | API builder can ingest Fib JSON on a later rebuild; current API file predates Fib and has none. | Decide explicitly whether Fib should be exposed; filter intended input files if not. |

### Potential Risks

| ID | Severity | Evidence | Potential consequence | Recommendation |
|---|---|---|---|---|
| P-01 | HIGH | fib_mc_segment.py lines 127–130 | Malformed/missing/non-finite data can abort processing; no per-pair status or fallback source. | Validate before writing and report invalid records explicitly. |
| P-02 | MEDIUM | fib_mc_segment.py lines 126–142 | D may update before W fails; date-only outputs can represent different snapshots or stale counterpart. | Expose per-timeframe run status and output freshness. |
| P-03 | MEDIUM | fx_monte_carlo.py lines 258–296; mc_data.yml line 3 | range_90 name is fixed if confidence changes, and metadata omits confidence. | Record configured confidence in metadata/schema. |

### Unverified Items

| ID | Severity | Evidence | Unknown | Recommendation |
|---|---|---|---|---|
| U-01 | INFORMATIONAL | Direct invocation search found only usage text | Whether/when script runs automatically and how failures are reported | Verify host-level runtime before relying on output. |
| U-02 | INFORMATIONAL | No trading consumer in scope; API code can ingest fields | Whether external service consumes Fib output/API fields | Trace consumers separately; do not infer from file presence. |
| U-03 | INFORMATIONAL | Output and source timestamps | Who/what generated inspected Fib files | Preserve execution logs/run metadata in future. |

## 14. Recommended Remediation

Minimum before Shadow Observation:

1. Validate required fields, numeric types, finiteness, and strictly positive interval width; classify missing/invalid/outside states explicitly.
2. Apply and document half-open zone ownership; do not assign outside prices to internal zones.
3. Remove action labels from shadow schema or use only non-directional context marked unvalidated.
4. Fix pair deduplication/accounting; expose failures and reasons; validate pair coverage before annotating.
5. Publish atomically and verify output against source keys/metadata.
6. Record confidence and source lineage; keep D/W independent and expose their distinct snapshot ages.
7. Establish actual invocation schedule and failure reporting; confirm Fib is excluded from trading decisions.
8. Design outcome resolution at 1/3/5 periods and range coverage before making any statistical or performance claim.

No changes were made.

## 15. Final Verdict

1. **Mathematics for valid inputs:** Yes, relative to serialized finite endpoints where hi > lo.
2. **Boundary handling:** Runtime is deterministic, but the serialized representation overlaps boundaries and does not document ownership.
3. **Outside-range identification:** No; outside prices are assigned to an edge zone.
4. **Invalid input safety:** No; invalid ranges and non-finite/missing data are not explicitly classified or safely rejected.
5. **Source selection:** Deterministic and consistent with the documented earliest policy, but may ignore later/better data and does not check completeness.
6. **Output JSON reliability:** Original fields are preserved in inspected outputs, but pair counts are inconsistent and writes are non-atomic.
7. **D/W separation:** Preserved; snapshots are not synchronized.
8. **Shadow suitability:** Not ready; validity/range status and outcome resolution are missing, and order-like labels remain.
9. **Minimum remediation:** Input/status validation, boundary policy, remove/neutralize action labels, correct pair counts, atomic validated writes, establish runtime/consumer boundary, and define future-only resolution.
10. **Evidence of trading impact:** None found in this scoped audit. API ingestion is possible on future rebuild, but no trading consumer or decision effect is established.

**Final classification: NOT READY — DATA INTEGRITY ISSUES.**

