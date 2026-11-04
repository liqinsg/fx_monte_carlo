# PHASE 1 — PV-1 READ-ONLY PREFLIGHT PROMPT

**File:** `PHASE_1_PV1_READ_ONLY_PREFLIGHT_PROMPT.md`
**Purpose:** Independently verify the market-timestamp semantics of the configured data source, resolving contract item **PV-1** (`PHASE_1_DATA_CONTRACT_v1.0.md` §5.1) before Human Freeze.
**Contract under test:** `PHASE_1_DATA_CONTRACT_v1.0.md` Revision 5a
**Environment:** WSL development workstation, root `/home/qili/projects/fx_monte_carlo` (contract §0.2 E-1)
**Prepared:** 2026-11-04, after the Revision 5a finalization audit
**Authorization:** **NONE YET.** This file is a prompt specification. Executing it requires separate human approval.

---

## 0. Why this preflight exists

Contract §5.1 / §5.4 require that `last_bar_timestamp` and `data_window_*` be written **only** when the data source's semantics establish a real UTC instant. If the source yields session-date labels, affected pairs MUST fail validation.

There is a concrete reason for concern rather than theoretical caution: Yahoo Finance returns bar times as Unix epochs, but the epochs are **not** universal instants — they are constructed in the exchange's local wall clock. The same raw epoch can mean different things under different interpretations. If the pipeline assumes "epoch ⇒ UTC midnight", the audit basis of every batch is wrong.

**PV-1 is currently NOT VERIFIED** in E-1. This preflight exists to change that status with evidence.

---

## 1. Instructions to the executing agent (read first)

1. This is a **read-only** task. It produces a report; it does not produce a fix.
2. Do **not** modify any file in the repository except the single new report file named in §7.
3. Do **not** run the production entry point `fx_monte_carlo.py`. It writes into `mc_results/` and `api/`.
4. Do **not** run `build_api.py`, any scheduler/trigger script, or any publication path.
5. Do **not** call `git clean`, `git checkout`, `git stash`, `git reset`, or delete/rename/move any tracked **or untracked** file. The untracked `mc_results/*.json` and `api/**` files are required historical data (contract §9.4, §10).
6. Do **not** modify `ai_training_cnn`, `blend_metric()`, Fib code, Shadow Observer code, OANDA/trading code, `mc_data.yml`, or any Python source.
7. If a fact cannot be established, record **NOT VERIFIED** with the reason. Never resolve a question by assumption.
8. Report raw observed output, not a summary of what you expected to see.

---

## 2. Preflight questions (the deliverable answers exactly these)

| ID | Question | Answer type |
|----|----------|-------------|
| Q-1 | What object type / dtype is the DataFrame index returned by `yf.download(...)` for `interval="1d"`? | `DatetimeIndex` / `tz` / naive? |
| Q-2 | For `interval="1d"`, what does the index *time-of-day* look like across a full year, and does it shift at a DST boundary? | distribution + boundary evidence |
| Q-3 | For `interval="1wk"`, what does the index *weekday* and time-of-day look like? | distribution + evidence |
| Q-4 | Is the underlying epoch series timezone-shifted by `meta.gmtoffset`, or is `gmtoffset` a current-day meta attribute that does not represent per-bar construction? | evidence from raw API vs library |
| Q-5 | Does the index represent a **real UTC instant** (PV-1 PASS), or a **session-date label tied to a wall-clock day** (PV-1 FAIL for that timeframe)? | PASS / FAIL / PARTIAL per timeframe |
| Q-6 | What is the date of the last usable bar relative to the run date, and what does "today's bar" look like while a session is still open? | observed facts |
| Q-7 | Are the historical E-1 artifacts attributable to an E-1 generator (provenance class L-A) or not (L-B)? | per-artifact classification evidence |

---

## 3. Preflight steps

### S-1 — Environment setup (isolated, no system changes)

1. From the E-1 root, create an isolated environment: `python3 -m venv .venv`. This path is already covered by `.gitignore` (`.venv`, line 153). Do not install into the system interpreter.
2. Install only the project requirements: `.venv/bin/pip install -r requirements.txt`. Record the resolved versions of `numpy`, `pandas`, `yfinance`, `PyYAML` and the Python version.
3. Record whether installation succeeded without pin drift. `requirements.txt` uses **open lower bounds** (`yfinance>=0.2.30`), so the resolved version is an observation to record, not a fixed input.
4. If installation fails, stop and report. Do not substitute another data source.

### S-2 — Library-level observation (mirrors the production call)

Reproduce the **exact** production call for both timeframes, without writing results:

- Timeframe D: `period="1y"`, `interval="1d"` (§4 TIMEFRAME_CONFIG "D")
- Timeframe W: `period="5y"`, `interval="1wk"` (§4 TIMEFRAME_CONFIG "W")

Call shape must match `fx_monte_carlo.py:178-184`: `yf.download(pair, period=..., interval=..., progress=False, auto_adjust=False)`.

For each timeframe, record:

- `type(df.index).__name__`, `df.index.dtype`, `df.index.tz`
- first 3 and last 3 index values, full ISO rendering
- row count, and whether the count meets `lookback` (90 daily / 104 weekly)
- the weekday and time-of-day distribution over the full index
- the index values bracketing at least one DST transition (late March and late October for Europe/London)
- the last row: is it a completed bar or the live in-progress bar?

### S-3 — Raw source cross-check (bypass the library)

Query the underlying chart endpoint directly for the same symbol and intervals to see the untouched `timestamp` array and `meta` block:

```
https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X?interval=1d&range=1y
https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X?interval=1wk&range=5y
```

For each, record and compare:

- `meta.exchangeTimezoneName`, `meta.timezone`, `meta.gmtoffset`, `meta.dataGranularity`
- the raw `timestamp` array: render each epoch three ways and compare:
  1. as raw UTC (no shift)
  2. shifted by `meta.gmtoffset` (`fromtimestamp(t + gmtoffset, UTC)`)
  3. converted to `ZoneInfo("Europe/London")`
- whether the three renderings agree, and for which bars they disagree

**This is the decisive comparison.** Q-4 is answered by whether the epoch series itself moves at DST, independently of what `meta` reports on the day the request was made.

### S-4 — Supplementary sampling

- Repeat S-2/S-3 for a small holdout set (2–3 non-EUR majors, e.g. `GBPUSD=X`, `USDJPY=X`) to confirm the behavior is a source-wide property, not symbol-specific.
- Include one non-forex control if convenient (an equity with a known exchange timezone, e.g. a US-listed ticker) to demonstrate that the timezone machinery does vary by instrument. This is diagnostic only and is **not** a market-data input for Phase 1.
- Intraday sanity check: fetch `interval="1h", range="2d"` for one pair and record how index values render (expects names that are intraday instants, not day labels). Used only to characterize source behavior.

### S-5 — Artifact provenance evidence (Q-7)

Read-only inspection of the existing `mc_results/` artifacts. For a sample spanning early and late files:

- list `metadata` keys present and the `generated_utc` value
- compare `generated_utc` with the filename `YYYYMMDD_HHMM`
- record file mtimes as a **copy-trail indicator** (a file copied from another machine loses its generator relationship; batch mtimes clustering across unrelated filename dates is a copy signature)

Do not conclude L-A/L-B from the filename rule alone (contract §5.3). Record the evidence and hand the judgment to a human.

---

## 4. Interpretation rules (do not deviate)

1. **A session-date label is not an instant.** If the daily index is a wall-clock day that moves by an hour at DST, it is a day label anchored to exchange local time — never a UTC instant.
2. **Do not accept a shift if it is contradicted by the epoch series.** If `meta.gmtoffset` reports `0` but the epoch series itself shifts by an hour mid-year, `gmtoffset` does not describe per-bar construction. Report the contradiction, do not "pick one".
3. **No normalization during preflight.** Do not convert, floor, round, or "fix" index values before reporting. Report what the source produced.
4. **Per-timeframe verdicts.** D and W may differ; they must be reported separately. A PASS for one does not carry to the other.
5. **No downstream design.** This preflight does not select a mitigation. If PV-1 fails, that is a finding for Human Freeze, not a cue to design a workaround.

---

## 5. Prohibited actions (explicit)

| # | Prohibited |
|---|-----------|
| P-1 | Running `fx_monte_carlo.py` (any timeframe) — it writes batches into `mc_results/` |
| P-2 | Running `build_api.py`, `run_fx_mc.sh`, `trigger_missing_mc.sh`, `test_trigger_missing_mc.sh`, or any scheduler |
| P-3 | Writing, moving, renaming, or deleting anything in `mc_results/` or `api/` |
| P-4 | `git clean`, `git add`, `git commit`, `git stash`, `git reset`, `git checkout -- <path>` |
| P-5 | Editing `mc_data.yml`, any `*.py`, any workflow, or any existing `PHASE_*` document |
| P-6 | Installing packages into the system Python (venv only) |
| P-7 | Claiming any result that was not directly observed in this run |
| P-8 | Starting Stage B work of any kind, or treating any verdict as Stage B authorization |

---

## 6. Verdict format

The report must end with a decision table using only these values:

| Verdict | Meaning for contract |
|---------|----------------------|
| **PASS** | Source semantics establish a real instant; §5.1 serialization is achievable for that timeframe without change. |
| **FAIL** | Source yields session-date labels; §5.1/§7 require affected pairs to fail validation. **The pipeline would produce zero valid pairs** if §5.1 is applied literally — this is a contract-level decision, not an implementation detail. |
| **PARTIAL** | D and W differ, or some pairs/symbols differ. State exactly which. |
| **NOT VERIFIED** | Evidence insufficient or blocked. State what was blocked and why. |

---

## 7. Expected deliverable

Create exactly **one** new file: `PHASE_1_PV1_EVIDENCE_REPORT.md`, containing:

1. Environment record (step S-1 versions and outcomes).
2. Q-1 … Q-7, each with observed raw output and its verdict.
3. The S-3 three-way epoch rendering comparison, including the DST boundary rows verbatim.
4. Per-timeframe verdict table (§6) for D and W.
5. A **Consequence statement** — factual only — describing what §5.1/§7 would do to the production pipeline under each verdict.
6. An explicit list of anything **NOT VERIFIED**.

Then stop. Do not proceed to Freeze or Stage B.

---

## 8. What happens after this preflight

1. Human reviews the evidence report.
2. Human decides the PV-1 disposition (§5.1 rule unchanged, amended, or accepted with a documented consequence).
3. Human decides H-4 (L-A/L-B evidence practice) and H-5 (legacy/API fallback acceptance).
4. Only then may Human Freeze be signed and Stage B authorization issued.

---

## 9. Status of this preflight as of preparation

**NOT EXECUTED.** No environment was created, no data was fetched through the project's library path, and no verdict exists. PV-1 remains **OPEN — NOT VERIFIED**.

No file in the repository was modified in preparing this prompt.
