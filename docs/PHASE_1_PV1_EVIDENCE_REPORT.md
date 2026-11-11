# PHASE 1 — PV-1 EVIDENCE REPORT

**Contract:** `PHASE_1_DATA_CONTRACT_v1.0.md` Revision 5a (§5.1 PV-1)
**Environment:** WSL workstation, `/home/qili/projects/fx_monte_carlo` (E-1)
**Executed:** 2026-11-04, under owner authorization recorded in `PHASE_1_PV1_READ_ONLY_PREFLIGHT_PROMPT.md` §10
**Nature:** Read-only. No production script run. No writes to `mc_results/` or `api/`. No source, YAML, or Git change.
**Overall verdict: PARTIAL — D and W differ; neither is FAIL.**

---

## 1. Environment record (S-1)

| Item | Value |
|------|-------|
| Interpreter | `.venv`, Python 3.12.3 (system interpreter untouched) |
| Install command | `.venv/bin/pip install -r requirements.txt` — succeeded |
| numpy | 2.5.4 |
| pandas | 3.1.0 |
| **yfinance** | **1.8.0** |
| PyYAML | 6.0.3 |

**Observation:** `requirements.txt` uses open lower bounds (`yfinance>=0.2.30`). The resolved `yfinance` is **1.8.0** — far newer than the floor and newer than the version any historical artifact was likely produced with. This is pinned by nothing and is a reproducibility gap for Stage B, but it is **not** a finding about timestamp semantics. No package was pinned and `requirements.txt` was not modified.

---

## 2. Answers to Q-1 … Q-7

### Q-1 / Q-2 / Q-3 — Index type and shape

| TF | type | dtype | **tz** | rows | lookback met | time-of-day | weekdays |
|----|------|-------|--------|------|--------------|-------------|----------|
| D | `DatetimeIndex` | `datetime64[s]` | **None (naive)** | 260 | yes (≥90) | **`00:00` ×260** | Tue/Wed/Thu/Fri/Mon |
| W | `DatetimeIndex` | `datetime64[s]` | **None (naive)** | 262 | yes (≥104) | **`00:00` ×262** | **Mon only** |

**No DST shift is visible in the library index at all.** Every bar reads `00:00:00`, all year. This is the single most important observation in this report: the library has already erased the timezone, so the index alone cannot reveal which instant it refers to.

### Q-4 — Is the epoch series shifted, or is `gmtoffset` current-day only?

The raw source carries per-bar instants that **do** shift at DST. `meta.gmtoffset` does **not** describe them.

| TF | bars | Europe/London offset required across bars | `meta.gmtoffset` (as reported) |
|----|------|-------------------------------------------|-------------------------------|
| D | 262 | **0.0 h ×111, 1.0 h ×150** | **0 (0.0 h)** |
| W | 263 | **0.0 h ×110, 1.0 h ×152** | **0 (0.0 h)** |

Sample rows (raw endpoint, `EURUSD=X`):

| interval | raw epoch | as UTC | `+gmtoffset` | Europe/London |
|---|---|---|---|---|
| 1d | 1762214400 | 2025-11-04T00:00:00+00:00 | 2025-11-04T00:00:00+00:00 | 2025-11-04T00:00:00+00:00 |
| 1d | 1778022000 | 2026-05-05T23:00:00+00:00 | 2026-05-05T23:00:00+00:00 | **2026-05-06T00:00:00+01:00** |
| 1wk | 1714950000 | 2024-05-05T23:00:00+00:00 | 2024-05-05T23:00:00+00:00 | **2024-05-06T00:00:00+01:00** |

**Finding:** adding `meta.gmtoffset` changes nothing — it is a current-day meta attribute, **not** a per-bar offset. The per-bar offset is implied by the epoch series itself: each epoch is the instant of **exchange-local midnight** (Europe/London), so its UTC rendering moves 23:00 ↔ 00:00 across DST. As you corrected, this is the normal, valid signature of an exchange-local bar boundary. A Unix epoch is an absolute instant; the shifting UTC hour is not evidence of a label.

### Q-5 — Which interpretation does the evidence support?

**The two timeframes land in different classes.**

I proved the library transformation empirically. `yf.download` and `yf.Ticker.history` return the *same series*, one with timezone, one without:

```
download index tz      : None       last: 2026-11-04 00:00:00
Ticker.history tz      : Europe/London  last: 2026-11-04 00:00:00+00:00

download == history converted to UTC then stripped : False
download == history LOCAL wall clock stripped      : True     <-- match
```

Root cause is `yfinance/scrapers/history.py` → `PriceHistory._resample()`:

```python
df2 = df.resample(resample_period, label='left', closed='left', offset=offset).agg(resample_map)
#  origin='epoch', no tz_convert; for '1wk' uses 'W-MON'
```

The raw endpoint does **not** return daily/weekly bars; `yfinance` **resamples intraday data** and labels each bucket at the **left edge of the local wall-clock period**, then drops the timezone. Consequence, for the same naive label:

```
label 2026-03-31 00:00  as UTC instant       -> 2026-03-31T00:00:00+00:00
label 2026-03-31 00:00  as London-local wall -> 2026-03-31T00:00:00+01:00
difference: 1 hour
```

| Interpretation | D | W |
|---|---|---|
| **A.** real instant = exchange-local bar boundary | **YES** — supported | **NO** |
| **B.** session-date label, no established instant semantics | not on this evidence | **YES** |
| **C.** library transformation that loses timezone semantics | **YES** | **YES** |

- **D → class C (and A).** The underlying epoch is a real instant (exchange-local midnight). But `yf.download` strips the tz and prints `00:00` for every bar. The instant is recoverable **only** by re-localizing to `Europe/London`; reading `00:00` as UTC is wrong by one hour for ~150 of 260 bars (~58%).
- **W → class B, plus C.** Weekly buckets are not exchange bar boundaries. `W-MON` relabels the week by its local Monday start, producing one bucket per week that begins **Sunday 23:00 UTC** in summer. The raw API's own weekly bars start *Sunday 23:00*; `yfinance`'s resampled label is *Monday 00:00 local*. **The library even emits a partial current-week row** (e.g. index `2026-11-02` while the raw last bar is `2026-11-04T03:10:30`), so the last week is incomplete in both cases.

### Q-6 — Last bar and live bar

- Now (UTC) `2026-11-04T03:11`, last index `2026-11-04 00:00:00`, close `1.12511`.
- The last row is a **live, in-progress bar** — it carries the current price, not a closed daily close. `fx_monte_carlo.py:223` uses `df["Close"].values[-lookback:]`, so **the current partial bar feeds `current_price` and the log-return sample**. This is a pre-existing behavioral fact, not introduced by PV-1.
- Weekly: last lib label `2026-11-02` (Monday), raw last bar `2026-11-04T03:10:30` — a partial week.

### Q-7 — Artifact provenance

47 artifacts in `mc_results/`. Metadata keys are only `forecast, generated_utc, lookback, simulations, timeframe, total_pairs` — **no generator version, no host, no timezone record**.

| Artifact | `generated_utc` | filename stamp | mtime |
|---|---|---|---|
| `mc_D_all_pairs_20260913_0503.json` | `2026-09-13T05:03:11+00:00` | `0503` | 2026-09-13 13:03 |
| `mc_D_all_pairs_20260914_0200.json` | `2026-09-14T02:00:50+00:00` | `0200` | **2026-09-15 14:24** |
| `mc_D_all_pairs_20261022_0210.json` | `2026-10-22T02:10:25+00:00` | `0210` | **2026-11-03 13:04** |
| `mc_W_all_pairs_20261103_0505.json` | `2026-11-03T05:05:57+00:00` | `0505` | 2026-11-03 13:06 |

`generated_utc` matches the filename stamp in every sampled artifact (UTC confirmed). But mtimes cluster on unrelated dates (many on `2026-11-03 13:04`) — a **copy signature**, consistent with files arriving from E-2 or a backup. That weakens per-file attribution but does **not** contradict the UTC generator evidence, since committed sources all use `datetime.now(timezone.utc)`.

Note `mc_W_all_pairs_20261103_fib.json` has the *same* `generated_utc` as `..._0505.json` but a `_fib` name — it is excluded by §8.1 anyway.

---

## 3. S-3 three-way comparison — conclusion

| Comparison | Result |
|---|---|
| raw epoch as UTC | correct instant rendering |
| raw epoch + `meta.gmtoffset` | **identical to previous** — offset is always 0 here, so this is a no-op |
| raw epoch → `ZoneInfo("Europe/London")` | **same instant**, different wall clock; the rendering that matches the true bar boundary |
| `yf.download` index | naive `00:00`, equals London-local wall clock **stripped** |

The three renderings do not "compete"; the first and third are the same instant in two zones. `+gmtoffset` is not a valid conversion because `gmtoffset` is current-day, not per-bar.

Also confirmed: `yf.download` lib dates ⊆ raw-London days but **not** ⊆ raw-UTC days (multiple bars land on the prior UTC day). Reading D labels as UTC dates is **wrong for ~58% of bars**.

---

## 4. Verdict

| TF | Verdict | Basis |
|----|---------|-------|
| **D** | **PARTIAL** — class **C**, with class **A** underneath | Epoch is a genuine exchange-local-midnight instant; `yf.download` destroys the tz and emits a naive label. §5.1 forbids relabelling a naive value as UTC, so the current `00:00` **cannot** be written as `+00:00` as-is, and cannot be rejected as a mere label either. |
| **W** | **PARTIAL** — class **B + C** | Weekly buckets are library resampling labels (`W-MON`), not exchange bar boundaries; the print is naive. No instant semantics can be established from the index alone. |
| Overall | **PARTIAL** | D and W are **not** the same class. Neither is FAIL. |

Neither timeframe is **FAIL**: in both cases a real instant is *derivable* from the raw source, so the data is not inherently unusable — the loss is introduced by the library call the project currently uses.

---

## 5. Consequence statement (factual, no recommendation)

- Under **§5.1 read literally**: a naive `00:00` index is neither a verified instant nor a value that may be written with `+00:00`. Applying the rule as written to the *current* `yf.download` output would fail D and W for **every pair** → **zero valid pairs → zero `ok` batches**.
- Under **§5.1 applied to the raw source**: D's instant is recoverable (localize to `Europe/London`, then convert to UTC). W's is not, because the weekly bucket is a resampling label with no exchange bar boundary behind it.
- If D and W are treated identically, the conservative outcome is that **W cannot supply §5.1-compliant timestamps at all** while the `1wk` path is used, even though D can.
- The **live-bar** issue (Q-6) is independent of PV-1 but compounds it: `last_bar_timestamp` pointing at a still-open bar is an instant in the future-relative-to-close sense, and the "close" it supports is not final.

No code was changed. Whether to revise §5.1, change the fetch path, or accept a documented consequence is a **human decision** (prompt §8).

---

## 6. NOT VERIFIED

| # | Item | Reason |
|---|------|--------|
| NV-1 | Behavior of the `yfinance` version that produced historical artifacts (vs 1.8.0) | Not installed; version unresolvable from artifacts (no version recorded). |
| NV-2 | Whether E-2's environment would produce the same resampling | E-2 not accessible from here; by contract §0.2 no assumption may be transferred. |
| NV-3 | Official Yahoo/yfinance **documentation** on day/weekly label semantics | Not consulted this run; only observed behavior and source are cited. |
| NV-4 | Whether a confirmed instant holds for every one of the 35 configured pairs | Sampled 3 majors (EURUSD, GBPUSD, USDJPY); all behaved identically, but not all 35 were tested. |
| NV-5 | Why mtimes cluster on `2026-11-03 13:04` | Copy trail observed; origin not established. |

---

## 7. Compliance

- No `fx_monte_carlo.py`, `build_api.py`, scheduler, or trigger script executed.
- Nothing written to `mc_results/` or `api/`.
- No source, YAML, or existing `PHASE_*` file modified; no Git operation performed.
- Only additions: `.venv/` (gitignored) and this report.

**Stage B remains UNAUTHORIZED. Revision 5a remains NOT FROZEN.**
