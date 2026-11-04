# PHASE 1 — STAGE A DISCOVERY REPORT (READ-ONLY)

**Project under audit:** `fx_monte_carlo`
**Project root (verified):** `/home/ubuntu/projects/fx_monte_carlo`
**Phase:** 1 of 5 — MC Data Integrity
**Stage:** A — Read-Only Discovery ONLY
**Report created:** 2026-11-04
**Authorization:** strictly read-only. No source, config, data, workflow, or scheduler file was modified. The only file created is this report.
**Reference inputs requested by prompt:** `PHASE_0_ARCHITECTURE_REVIEW.md`, `MC_FIB_SHADOW_SYSTEM_BLUEPRINT.md` (Master Blueprint v1.0) — **neither is present in this repository** (see Evidence Gap EG-1).

> All `path:line` references below are relative to the project root.
> Markings used: **CONFIRMED / DIFFERS / NOT FOUND / NOT VERIFIED**.

---

## 1. PROJECT ROOT, FILE INVENTORY, GIT WORKING-TREE STATE

### 1.1 Project root
- Verified: `/home/ubuntu/projects/fx_monte_carlo` (`git rev-parse --show-toplevel` returns the same path). **CONFIRMED**

### 1.2 Top-level inventory (excluding `.git/`)
```
.github/            (workflows/mc_daily.yml, workflows/mc_weekly.yml)
.vscode/            (launch.json, settings.json)
__pycache__/        (.pyc for 3.12 and 3.13)
api/                (public API tree)
mc_results/         (MC JSON artifacts)
API.md
PHASE_1_STAGE_A_PROMPT.md
build_api.py
config.py           (EMPTY)
copula.py           (EMPTY)
copula_mc.py
four_d_mc.py
fx_monte_carlo.py
get_mc_data.py
index.html
mc_cron.log
mc_data.yml
requirements.txt
run_fx_mc.sh
test_api_pipeline.py
test_trigger_missing_mc.sh
trigger_missing_mc.sh
FX_DAILY_MONTE_CARLO_UPDATE   (directory — empty, 0 files)
```

### 1.3 Git working-tree state (read-only inspection)
- Command: `git status`, `git branch -vv`, `git log -n 5 --oneline`.
- Branch: `main`. **Dirty.** Ahead of `origin/main` by 1 commit.
- Last commits:
  - `bfa211d mc data updated`
  - `074a29b MC: weekly forecast 2026-10-26 [skip ci]`
  - `67cb59d MC: daily forecast 2026-10-26 [skip ci]`
  - `14f564f MC: daily forecast 2026-10-23 [skip ci]`
  - `28c08ee MC: daily forecast 2026-10-22 [skip ci]`
- Staged changes: 0.
- **Untracked files: 43 total** (= 1 prompt + 38 Daily MC JSON + 4 Weekly MC JSON).
  - ⚠️ **DIFFERS from the pre-Stage-A baseline provided by the human reviewer**, which stated 41 untracked (1 + 36 Daily + 4 Weekly). Actual verified count is **43** (1 + **38** Daily + 4 Weekly). See Difference D-1.
- `mc_results/` contains **71 files total = 29 tracked + 42 untracked** (`git ls-files mc_results | wc -l` = 29; `ls mc_results | wc -l` = 71).
- No files were cleaned, overwritten, reset, stashed, or reverted. **CONFIRMED (record only)**

### 1.4 Reference documents
- `find` for `*PHASE_0*`, `*BLUEPRINT*`, `*MASTER*`, `*FIB*` → **NONE FOUND**. Only two `.md` files exist in the repo: `PHASE_1_STAGE_A_PROMPT.md` and `API.md`.

---

## 2. DISCOVERY CHECKLIST RESULTS

### A. Repository reality

**A1. Project root + top-level listing — CONFIRMED**
- Root = `/home/ubuntu/projects/fx_monte_carlo`; inventory as §1.2.

**A2. Git state — CONFIRMED (dirty); baseline count DIFFERS**
- Branch `main`, working tree dirty, 0 staged, 43 untracked, ahead of `origin/main` by 1. Recorded, unmodified.
- Baseline discrepancy: reviewer's baseline said 41 untracked (36 Daily). Actual = 43 (38 Daily).

**A3. Python modules and apparent roles — CONFIRMED**
| File | Apparent role |
|------|---------------|
| `fx_monte_carlo.py` | Core MC engine for Daily/Weekly; reads `mc_data.yml`, fetches via yfinance, writes `mc_results/mc_{D,W}_all_pairs_*.json`. |
| `build_api.py` | Builds the public `api/` tree from `mc_results/`. |
| `get_mc_data.py` | CLI client: reads remote GitHub API by default, or local `mc_results/` via `--local`. |
| `test_api_pipeline.py` | Remote integration/dispatch script (needs a GitHub PAT); **not** an assertion test. |
| `test_trigger_missing_mc.sh` | Shell test harness for `trigger_missing_mc.sh` (mocks `date`/`python`/`gh`). |
| `trigger_missing_mc.sh` | Dispatches missing D/W workflow runs via `gh`. |
| `run_fx_mc.sh` | Local manual runner (D always, W on Monday). |
| `config.py` | **Empty file (0 bytes).** |
| `copula.py` | **Empty file (0 bytes).** |
| `copula_mc.py` | Standalone JPY 4-pair t-copula research script; not imported by the pipeline. |
| `four_d_mc.py` | Standalone JPY 4-pair Cholesky MC research script; not imported by the pipeline. |

**A4. Existence of specific paths — CONFIRMED (as absent/present)**
- `fib_mc_segment.py` → **NOT FOUND**.
- `utils/mc_loader_local.py` → **NOT FOUND**. The import is attempted at `fx_monte_carlo.py:40-46`; because `utils/` does not exist, `ImportError` is caught and `log_mc_observation` / `resolve_pending_mc_observations` are set to `None` (i.e., those hooks are silently disabled).
- `tests/` directory → **NOT FOUND**.
- `mc_results/` → **FOUND** (71 files).
- `api/` → **FOUND**.

**A5. Scheduler, invocation times, D/W cadence — CONFIRMED**
- Daily: `.github/workflows/mc_daily.yml:5` → `cron: '0 0 * * 1-5'` (Mon–Fri 00:00 UTC) → runs `python fx_monte_carlo.py D` (`:31`) then `python build_api.py` (`:34`).
- Weekly: `.github/workflows/mc_weekly.yml:7` → `cron: '17 0 * * 1'` (Mon 00:17 UTC) and `:11` → `cron: '30 6 * * 1'` (Mon 06:30 UTC backup). Runs `python fx_monte_carlo.py W` (`:48`).
- Local: `run_fx_mc.sh:11` runs `D` unconditionally; `:14-15` runs `W` only when `date +%u == 1` (Monday). The script itself contains no cron time.
- Dispatch helper: `trigger_missing_mc.sh` (guards on existing dates and running workflows, then `gh workflow run`).
- Runtime evidence: `mc_cron.log:1` shows an actual D run header `... — 20261013_0000 UTC | Pairs: 35` and `:37-38` shows the saved batch + `Run complete — 35 pairs processed`.

**A6. Filename patterns in `mc_results/` — CONFIRMED**
- Patterns present: `mc_D_all_pairs_YYYYMMDD_HHMM.json` and `mc_W_all_pairs_YYYYMMDD_HHMM.json`.
- `*_fib*.json` → **NONE** (`ls mc_results/*fib*` → no match). **No Fib JSON artifact exists.**

### B. Data Provenance

**B7. Metadata dict written to output — CONFIRMED**
- `fx_monte_carlo.py:379-389` writes exactly:
  `{"metadata": {timeframe, generated_utc, total_pairs, simulations, lookback, forecast}, "results": {...}}`.
- Observed in artifact `mc_results/mc_D_all_pairs_20261103_2015.json:2-9`:
  `timeframe=D, generated_utc=2026-11-03T20:15:51.649099+00:00, total_pairs=35, simulations=5000, lookback=90, forecast=5`.

**B8. Configuration actually read from `mc_data.yml` — CONFIRMED**
- `fx_monte_carlo.py:69-77` reads: `pairs`, `simulations`, `confidence`, `student_t_df`, `daily_lookback`, `daily_forecast`, `weekly_lookback`, `weekly_forecast`.
- `fx_monte_carlo.py:85` reads (optional): `max_history_files` (default 100).
- `mc_data.yml` actually defines: `simulations: 5000`, `confidence: 0.90`, `student_t_df: 5`, `daily_lookback: 90`, `daily_forecast: 5`, `weekly_lookback: 104`, `weekly_forecast: 5`, and the `pairs` list.

**B9. Data fetch call and exposed timestamps — CONFIRMED**
- Provider/function: `yfinance.download` at `fx_monte_carlo.py:178`, with `interval`/`period` from `TF_CFG` (`:142-159`) — D: `1d`/`1y`; W: `1wk`/`5y`.
- The returned object is a `pandas.DataFrame` whose index is a `DatetimeIndex` (i.e., **bar timestamps are exposed**), `dropna()` applied (`:199`). However, only `Close` values are used (`:223-224`); **no bar timestamp, timezone, or fetch time is ever extracted or written.**
- Therefore: the data *exposes* bar timestamps; the *output records none of them*.

**B10. Output records algorithm identity / config snapshot / config fingerprint / source-batch identity — NOT FOUND**
- Algorithm identity (module/version/hash): **NOT FOUND**.
- Configuration snapshot: **NOT FOUND** (only `simulations`, `lookback`, `forecast` are echoed; `confidence`, `student_t_df`, `pairs` are not).
- Configuration fingerprint: **NOT FOUND**.
- Source/batch identity: **NOT FOUND** (the only identity is `generated_utc` + the timestamp embedded in the filename).

**B11. Random seed and simulation parameters — DIFFERS (values located, not written to output)**
- Seed: `np.random.seed(42)` at `fx_monte_carlo.py:237` — **hard-coded, NOT written to output.**
- Parameters: `SIMULATIONS` (`:71`, =5000), `CONFIDENCE` (`:72`, =0.90), `STUDENT_T_DF` (`:73`, =5) — read from YAML.
- Written to output: only `simulations` (`:384`, and per-pair `:310`). `confidence` and `student_t_df` are **NOT written**; `seed` is **NOT written**.

### C. Pair Integrity

**C12. `mc_data.yml` raw count and duplicates — DIFFERS (from the "29 unique" hypothesis)**
- Raw entries (`pairs:` list): **35**.
- Unique entries: **28**.
- Duplicated entries (each appears twice): `EURUSD`, `GBPUSD`, `NZDCHF`, `NZDUSD`, `USDCAD`, `USDCHF`, `USDJPY` → **7 duplicate occurrences** → 35 − 7 = 28 unique.
- ⚠️ The pre-Stage-A baseline/Phase-0 hypothesis of "29 unique" is **incorrect for the current config**; 29 was the count under the *earlier* config (see C12-note).

**C12-note. The pair set changed mid-history — CONFIRMED**
- Old-config artifacts contain `CADNZD` and `CHFNZD` and do **not** contain `NZDCAD` (e.g. `mc_results/mc_D_all_pairs_20261012_0931.json`; `mc_cron.log:26-27` lists `CADNZD=X`, `CHFNZD=X`).
- New-config artifacts (from `20261027` onward) contain `NZDCAD` and **not** `CADNZD`/`CHFNZD` (e.g. `mc_results/mc_D_all_pairs_20261103_2015.json`).
- Distribution of unique-result counts across all `mc_results/*.json`: **51 D with 29 keys + 10 W with 29 keys** (old config) vs **9 D with 28 keys + 1 W with 28 keys** (new config, from `20261027_0000` onward).

**C13. Pair iteration / deduplication mechanism — CONFIRMED**
- Iteration: `for pair in PAIRS:` at `fx_monte_carlo.py:360`.
- Suffix append: `PAIRS = [p if p.endswith("=X") else f"{p}=X" for p in RAW_PAIRS]` at `:70`.
- **No explicit deduplication.** Duplicate YAML entries result in duplicate fetch + duplicate simulation runs. The only implicit collapse is the results map `pairs_results_map[pair] = data` at `:369` (a dict, so duplicate keys overwrite).

**C14. Where the pair count is written; raw vs unique — DIFFERS**
- `fx_monte_carlo.py:383` writes `"total_pairs": len(all_results)`.
- `all_results` is appended once per **successful processed pair, including duplicate YAML entries** (`:368`). It is therefore the **raw successful-attempt count (35), not the unique-result count (28)**.
- Confirmed by artifact: `mc_D_all_pairs_20261103_2015.json` has `metadata.total_pairs = 35` while `results` contains **28** keys.

**C15. Per-pair fetch-failure handling — CONFIRMED (logged only; not recorded)**
- Data-fetch exception: `print(f"❌ Data failed {pair} [{TF}]: {e}")` at `:205-207`, returns empty DataFrame.
- Empty/short data: `return None, False` (`:187`, `:201`, `:221`, `:227`, `:231`).
- Main loop: `print(f"⚠️ Skipped {pair} [{TF}]")` then `continue` at `:364-366`.
- Failure is **logged to stdout only**; it is **not recorded in the JSON artifact** (no failed-pair list, no count).

**C16. Pair identifier formation — CONFIRMED**
- In output JSON: `"pair": pair` where `pair` already carries the `=X` suffix (e.g. `"EURUSD=X"`) — `fx_monte_carlo.py:292`; results key is also `EURUSD=X` (`:369`).
- In YAML: clean symbol (`EURUSD`) — `mc_data.yml:14`.
- Suffix appended only at `fx_monte_carlo.py:70`.
- Suffix stripped downstream: `build_api.py:27-28` (`clean_pair_name`) and `get_mc_data.py:56-57` (`_clean_pair`).

### D. Timestamp Integrity

**D17. Every timestamp written to output — CONFIRMED**
- Per-pair `generated_utc`: `datetime.now(timezone.utc).isoformat()` at `fx_monte_carlo.py:311`.
- Batch-level `generated_utc`: `now_dt.isoformat()` at `:382` (where `now_dt` is captured at `:351`).
- Both are **wall-clock generation instants**. There is **no fetch timestamp** and **no last-bar / market-data timestamp**.

**D18. Is fetch time used as market-data time? — DIFFERS (conflation present downstream)**
- The engine records no fetch time and no bar time.
- `build_api.py` derives the **date bucket** from the generation timestamp when no `date` field is present: `_group_by_date` at `:94-98` and `_ensure_clean_payload` at `:120-124` both call `_utc_from_iso(r["generated_utc"])` then `strftime("%Y-%m-%d")`.
- Observed effect: `api/latest/all.json:2` shows `"date": "2026-10-26"` derived from the run, while each pair object carries its own `generated_utc` (e.g. `:30` `2026-10-26T02:02:26...`). The published "date" is the **generation date**, not a market-data date.

**D19. Cross-check real artifacts — CONFIRMED**
- Newest Daily file: `mc_results/mc_D_all_pairs_20261103_2015.json` → `metadata.generated_utc = 2026-11-03T20:15:51.649099+00:00`.
- Newest Weekly file: `mc_results/mc_W_all_pairs_20261102_0000.json` → `metadata.generated_utc = 2026-11-02T00:00:05.910765+00:00`.
- **No market-bar timestamp appears anywhere** in either file (no `bar`/`last_bar`/`fetch` keys; `grep` for such keys across `mc_results/*.json` → none).

**D20. Weekly window: full week or partial? — NOT VERIFIED (insufficient evidence)**
- W cadence confirmed as Monday-only (`mc_weekly.yml:7,11`); W artifacts are dated `2026-10-12`, `2026-10-19`, `2026-10-26`, `2026-11-02` (all Mondays).
- However, weekly fetch config is `interval="1wk", period="5y"`, and the engine records **no bar timestamps and no window bounds**, so the data window cannot be observed from the artifacts.
- **Missing evidence:** the actual first/last weekly bar timestamps fed into the simulation. The weekday alone is **not** used to infer window completeness, per the prompt's rule.

### E. Output Integrity

**E21. Write call and atomicity — CONFIRMED (atomic)**
- `save_batch_mc_safely` at `fx_monte_carlo.py:319-343`.
- Temp file: `temp_file = target_file.with_suffix(f".tmp{os.getpid()}")` at `:326`; JSON written to temp at `:328-329`; atomic rename via `temp_file.replace(target_file)` at `:331`.
- Old-file pruning uses `sorted(glob(...), key=os.path.getmtime)` at `:333-343` (retains newest `max_files=100`).
- A partial write would land in the `.tmp<pid>` file, not the `.json` artifact → **atomic; corrupt-artifact risk is low.**

**E22. Validation of computed results before write — CONFIRMED (none)**
- Checks that exist are *input guards* only: required columns present (`:195-197`), `len(df) < lookback` (`:200`), `len(df) < lookback` (`:220`), `current <= 0` (`:226`), `len(log_returns) < 2` (`:230`).
- **Not checked:** finiteness of `final`/percentiles, probability bounds (`p_up`/`p_down` ∈ [0,100] and summing to 100), `range_90` ordering (`lower <= upper`), monotonicity, NaN/None.

**E23. Anomaly inspection of real files — CONFIRMED (no anomalies found)**
- Scan across all `mc_results/*.json` and `api/latest/*.json` for `Infinity|NaN|null` → **none**.
- Scan for zero-width or reversed `range_90` (`range_90[0] >= range_90[1]`) → **none**.
- Per-pair key set is uniform (21 keys) in the newest D file: `ann_drift_pct, ann_vol_pct, current_price, cvar_95, expected_price, forecast, generated_utc, lookback, p_down, p_down_pct, p_up, p_up_pct, pair, percentile_rank, range_90, regime, simulations, timeframe, touch_lower_pct, touch_upper_pct, var_95` → no key-set inconsistency across pairs.

**E24. `range_90` handling and `confidence` recording — CONFIRMED**
- Computed at `fx_monte_carlo.py:258-259` via `np.percentile(final, (1-CONFIDENCE)/2*100)` and `np.percentile(final, (1+CONFIDENCE)/2*100)`.
- Rounded at `:296`: `[round(lower, dec), round(upper, dec)]` where `dec = 3 if "JPY" in pair else 5` (`:288`).
- The configured `confidence` (=0.90) is **NOT recorded anywhere** in the output JSON.

### F. API Isolation

**F25. `build_api.py` scan/glob, filters, and "latest" selection — CONFIRMED**
- Scan: `for path in sorted(results_dir.glob("*.json"))` at `build_api.py:44`.
- Filter: `if timeframe and not path.name.startswith(f"mc_{timeframe}_"): continue` at `:47` (prefix match `mc_D_` / `mc_W_`).
- Latest selection: `_group_latest` at `:65-83` compares `generated_utc` timestamps (`new_ts >= old_ts`) → **timestamp-based, not filename/mtime based.**
- Nested handling: if a file's top-level `results` is a dict, each value is spread into results (`:51-56`).

**F26. Actual output layout vs Phase 0 description — DIFFERS**
- Actual layout produced (verified on disk):
  - Daily: `api/latest/{PAIR}.json`, `api/latest/all.json`, `api/{YYYY}/{MM}/{DD}/{PAIR}.json`, `api/{YYYY}/{MM}/{DD}/all.json`, `api/dates.json`.
  - Weekly: `api/weekly/latest/{PAIR}.json`, `api/weekly/{YYYY}/{MM}/{DD}/...`, `api/weekly_dates.json`.
- Phase 0 described `api/{daily,weekly}/latest/{pair}.json`. Actual **daily** tree is at `api/latest/...` (there is **no** `api/daily/` directory). → **DIFFERS.**
- Side observation (staleness, recorded not fixed): `api/latest/` holds **29 pair files** and includes legacy names `CADNZD.json` and `CHFNZD.json` (not in the current YAML) while **`NZDCAD.json` is absent**; because dated files and latest files are only ever written/overwritten, **never removed** (`:174-177`, `:188-189`), stale pairs accumulate. `api/latest/all.json` is still `"date": "2026-10-26"` (last committed build), i.e. the API lags the newest untracked `mc_results` files.

**F27. Could any scanner ingest a filename containing `_fib`? — CONFIRMED (defect exists); no Fib files exist**
- `build_api.py:47` filters by **prefix** (`startswith("mc_D_")` / `startswith("mc_W_")`). A file named e.g. `mc_D_all_pairs_...._fib.json` **would pass** this filter and be ingested. There is **no explicit `_fib` exclusion** in the scanner.
- `get_mc_data.py:69` uses a strict regex `^mc_{tf}_all_pairs_(\d{8})_(\d{4})\.json$` for the local path → would **reject** a `_fib`-suffixed name.
- **No `*_fib*` file exists anywhere in the repo** (see A6). Therefore the scanner-side isolation defect is **CONFIRMED**, but no Fib artifact is available to be ingested.

**F28. Every consumer reading `mc_results/*` or `api/*` — CONFIRMED**
- `build_api.py` — reads `mc_results/*.json`; accepts glob `*.json` **filtered by prefix** `mc_D_`/`mc_W_`; **does not filter Fib**.
- `get_mc_data.py` — reads local `mc_results/` via strict regex (`:69`), and remote `api/` (`:18`, `:234`, `:239`, `:264`); accepts only `mc_{D,W}_all_pairs_YYYYMMDD_HHMM.json` locally.
- `.github/workflows/mc_daily.yml:40` and `mc_weekly.yml:58` — `git add mc_results/ api/` (stages whole dirs).
- `index.html` — static HTML referencing `api/latest/...` (no script; the markup is malformed). Not a runtime consumer.
- `test_api_pipeline.py` — consumes the **remote** GitHub API/Pages (`:116-120`) and the Actions REST API; no local `mc_results/*`/`api/*` file patterns.
- `trigger_missing_mc.sh` — invokes `get_mc_data.py` for date indexes only.

**F29. What `test_api_pipeline.py` and `API.md` assert/promise — CONFIRMED**
- `test_api_pipeline.py` **asserts nothing about the pipeline**: it is a PAT-gated remote script (`GITHUB_TOKEN = "YOUR_GITHUB_PAT"` at `:15`) that triggers `mc_daily.yml`, polls until completion, downloads a dated `api/YYYY/MM/DD/PAIR.json`, and optionally deletes API files. It contains no assertions on data validity.
- `API.md` promises: base URL `https://liqinsg.github.io/fx_monte_carlo` (`:16`); endpoints `GET /api/latest/all.json`, `GET /api/latest/<PAIR>.json` (`:27-31`); historical `GET /api/YYYY/MM/DD/all.json` and `.../<PAIR>.json` (`:37-38`); "runs daily at **00:00 UTC**" (`:3`); dated files preserve the **first** snapshot of the day and are not overwritten by re-runs (`:40`).
- Consistency: API.md's daily endpoint layout **matches** `build_api.py`'s actual output; API.md does **not** document the weekly endpoints (`api/weekly/...`, `api/weekly_dates.json`) that `get_mc_data.py` and `build_api.py` actually serve.

### G. Phase 0 claim re-verification (§G item 30)

- **The Phase 0 report is not present in this repository** (`PHASE_0_ARCHITECTURE_REVIEW.md` / `Master_Blueprint_v1.0.md` / `MC_FIB_SHADOW_SYSTEM_BLUEPRINT.md` all absent). Individual claims `B-1 … B-12` and the §2.2 execution flow **cannot be enumerated or checked against their source text**. → **NOT VERIFIED.**

| Claim ID | Verified? | Evidence (path:line) | Correction if any |
|----------|-----------|----------------------|-------------------|
| B-1 … B-12 | **NOT VERIFIED** | Phase 0 document absent from repo (EG-1) | Cannot enumerate without source text |
| §2.2 execution flow | **NOT VERIFIED** | Phase 0 document absent from repo (EG-1) | Observed flow: `mc_daily.yml:31,34` → `fx_monte_carlo.py` then `build_api.py` |

**Interpretation-rule hypotheses that CAN be checked (from prompt §2):**

| Hypothesis (prompt §2) | Result | Evidence |
|------------------------|--------|----------|
| Fib boundary convention is half-open with global `1.0` included | **NOT VERIFIED** | No Fib/zone code exists in this repo (`fib_mc_segment.py` NOT FOUND). |
| Public API may be contaminated by Fib data | **NOT VERIFIED** | No `*_fib*` file exists (A6); scanner defect exists (F27) but no evidence of ingestion. |
| Phase split: Fib algorithm issues belong to Phase 2 | **CONFIRMED (scope)** | No Fib code present, so all Fib logic is out of this repo/phase. |
| `generated_utc`, fetch time, last-bar time must not be conflated | **DIFFERS** | Fetch time and last-bar time are not recorded; `generated_utc` is used to derive the API date (D18). |
| Config fingerprint must cover the complete normalized config incl. unique pair set | **NOT FOUND** | No fingerprint is computed or stored (B10). |
| Out-of-range price must stay eligible and be recorded with explicit status | **NOT VERIFIED** | No such status field or logic exists in `fx_monte_carlo.py`. |

---

## 3. THE FIVE REVIEW QUESTIONS

**Q1 — Data Provenance: Can each MC batch be traced to the algorithm, configuration, and data window used?**
**No.** A batch records only `timeframe`, `generated_utc`, `total_pairs`, `simulations`, `lookback`, `forecast` (`fx_monte_carlo.py:379-389`). There is **no algorithm identity, no configuration snapshot, no configuration fingerprint, no seed, and no data window / bar timestamps** (B10, B11, B9, D19). Two files produced from different configs are distinguishable only by `generated_utc`/filename, not by a recorded fingerprint — as demonstrated by the silent pair-set change between `20261026` and `20261027` (C12-note).

**Q2 — Pair Integrity: How are configured entries counted, and how are unique/successful/failed pairs represented?**
Configured = **35 raw / 28 unique** (`mc_data.yml`; 7 duplicates). The engine iterates **without dedup** (`:360`), so duplicates are fetched and simulated twice, then collapsed only by the results dict key (`:369`). The written count `total_pairs = len(all_results)` (`:383`) is the **raw successful-attempt count (35)**, which **does not equal the number of unique results (28)** — verified in `mc_D_all_pairs_20261103_2015.json` (`total_pairs=35`, 28 results keys). **Failures are logged to stdout only and are never recorded** in the artifact (C15).

**Q3 — Timestamp Integrity: Are generation, fetch, and last-bar times separated or conflated?**
**Conflated / incomplete.** Only the **generation** time is stored (`:311`, `:382`). The **fetch time** and the **last market-bar time** are never captured (D17). Downstream, `build_api.py` derives the published `date` from `generated_utc` (`:94-98`, `:120-124`), treating a generation instant as if it were the market date (D18).

**Q4 — Output Integrity: Is output validated, and written atomically?**
**Written atomically; not validated.** The write is temp-file + `os.replace` (`:326-331`) → **atomic, CONFIRMED**. No semantic validation of results is performed (`:195-231` guards only) (`E22`). No actual anomalies (non-finite, null, reversed/zero-width `range_90`, inconsistent key sets) were found in the existing artifacts (`E23`).

**Q5 — API Isolation: Can Fib files (or any non-MC file) enter the public MC API, and is there direct evidence of past contamination?**
**A path exists but contamination is not evidenced.** `build_api.py` selects by **prefix only** (`:47`), so a file like `mc_D_all_pairs_..._fib.json` would be ingested; there is no explicit `_fib` exclusion. However, **no `*_fib*` file exists** in the repo (A6), so there is **no direct evidence of past contamination**. Status: scanner isolation defect = **CONFIRMED**; actual API contamination = **NOT VERIFIED**.

---

## 4. CONFIRMED FACTS / DIFFERENCES FROM PHASE 0 / UNVERIFIED / EVIDENCE GAPS

### 4.1 Confirmed Facts
- CF-1. Root is `/home/ubuntu/projects/fx_monte_carlo`; working tree is **dirty**, ahead of `origin/main` by 1.
- CF-2. Untracked files = **43** (1 prompt + 38 Daily + 4 Weekly); `mc_results/` = 71 files (29 tracked + 42 untracked).
- CF-3. `mc_data.yml` = 35 raw entries / **28 unique** / 7 duplicates (`EURUSD, GBPUSD, NZDCHF, NZDUSD, USDCAD, USDCHF, USDJPY`).
- CF-4. Metadata written = `timeframe, generated_utc, total_pairs, simulations, lookback, forecast` (`fx_monte_carlo.py:379-389`).
- CF-5. `total_pairs = len(all_results)` = raw successful attempts (35), ≠ unique results (28) (`:383`).
- CF-6. `np.random.seed(42)` (`:237`) and `confidence`/`student_t_df` are **not** written to output.
- CF-7. Output write is **atomic** (temp + `os.replace`, `:326-331`).
- CF-8. No result validation before write (`E22`); no anomalies found in existing artifacts (`E23`).
- CF-9. `build_api.py` selects files by **prefix** (`:47`) and chooses "latest" by **`generated_utc` timestamp** (`:65-83`).
- CF-10. **No `*_fib*` file exists** anywhere in the repo.
- CF-11. Daily cron `0 0 * * 1-5`; Weekly cron Mondays `17 0` + `30 6`.
- CF-12. `fib_mc_segment.py`, `utils/`, and `tests/` do **not** exist; the `utils.mc_loader_local` import is silently disabled (`:40-46`).
- CF-13. `config.py` and `copula.py` are empty; `copula_mc.py` / `four_d_mc.py` are unwired research scripts.

### 4.2 Differences from Phase 0 / pre-Stage-A baseline
- D-1. **Untracked count**: baseline stated 41 (36 Daily); actual = **43 (38 Daily)**.
- D-2. **"29 unique pairs"**: current config has **28 unique**; 29 corresponds to the *earlier* config (which included `CADNZD`/`CHFNZD`, absent today). Artifacts split: 61 files with 29 keys vs 10 files with 28 keys.
- D-3. **API layout**: Phase 0 said `api/{daily,weekly}/latest/{pair}.json`; actual daily path is `api/latest/...` (no `api/daily/`).
- D-4. **Timestamp handling**: Phase 0 hypothesis of a *missing separation* is **confirmed** in the opposite direction — fetch/bar times are absent entirely, and generation time is reused as the published date.
- D-5. **`total_pairs` semantics**: the recorded `total_pairs` (35) is a raw **attempt** count, not a unique/successful-match count.

### 4.3 Unverified Items
- U-1. All Phase 0 claims `B-1 … B-12` and §2.2 flow (source document absent).
- U-2. Weekly data window completeness (full vs partial week) — no bar timestamps recorded (D20).
- U-3. Actual API contamination by Fib data — no Fib file exists to test (F27).
- U-4. Fib boundary-zone behaviour and out-of-range eligibility status — **no Fib code exists** in this repo.
- U-5. Runtime behaviour of `copula_mc.py` (imports `scipy`, which is **not** in `requirements.txt`).

### 4.4 Evidence Gaps
- EG-1. **Phase 0 / Blueprint documents are not in the repository.** §G cannot be executed against source text; the claim table in §2.G is therefore structured by claim ID with result NOT VERIFIED. *Missing evidence: the actual `PHASE_0_ARCHITECTURE_REVIEW.md` and `Master_Blueprint_v1.0.md` files.*
- EG-2. **No market-data timestamps anywhere in artifacts.** Bar time, fetch time, and data-window bounds are unobservable from stored output. *Missing evidence: recorded bar/fetch timestamps.*
- EG-3. **No configuration snapshot/fingerprint in artifacts.** *Missing evidence: a stored normalized-config hash.*
- EG-4. **No failed-pair records in artifacts.** *Missing evidence: a per-batch failed-pair list/count.*
- EG-5. `requirements.txt` lists only `numpy, pandas, yfinance, PyYAML`; the local environment clearly also ran other Python versions (`__pycache__` has 3.12 and 3.13 bytecode), but the exact runtime used for each artifact is not recorded.

---

## 5. ASSUMPTIONS PHASE 1 (STAGE B) WOULD NEED TO RELY ON — *REQUIRING HUMAN APPROVAL, NOT DECISIONS*

1. That the **"35 configured"** figure should be interpreted as *raw YAML entries* and **"28"** as *unique pairs*, and that any future fingerprint must hash the **deduplicated** unique pair set (per prompt §2).
2. That `total_pairs` should mean **unique successfully-simulated pairs**, implying a change of semantics from today's raw-attempt count. *(Requires approval — this is a behavioural change.)*
3. That **fetch time** and **last market-bar time** must be captured and stored **separately** from `generated_utc`.
4. That a **configuration snapshot/fingerprint** and the **random seed** must be written into each batch.
5. That **failed/skipped pairs** must be recorded explicitly per batch rather than only printed.
6. That the API scanner must gain an **explicit exclusion** for non-MC files (e.g. `_fib`), and that the **prefix filter** must be tightened to the exact `mc_{D,W}_all_pairs_YYYYMMDD_HHMM.json` form.
7. That legacy/stale API entries (`CADNZD`, `CHFNZD`) and the missing `NZDCAD` are a **data-consistency issue to be scoped**, and whether the API must prune stale pairs — **not assumed here.**
8. That the Phase 0 / Blueprint reference documents will be **supplied or re-created** before any Phase-1 §G verification can be valid.

---

## 6. STAGE A STATUS

**COMPLETE** — read-only discovery performed; hard stop reached. No file other than `PHASE_1_STAGE_A_DISCOVERY.md` was created, modified, or deleted. No generator/consumer process was executed; no packages installed; no market data fetched; no mutating git command run. Stage B is **NOT** authorized and was **NOT** started.
