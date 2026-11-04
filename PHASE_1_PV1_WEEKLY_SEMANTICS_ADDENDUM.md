# PHASE 1 — PV-1 WEEKLY TIMESTAMP SEMANTICS ADDENDUM

**Purpose:** Resolve the Weekly (`1wk`) timestamp semantics contradiction identified in `PHASE_1_PV1_EVIDENCE_REPORT.md`.

**Environment:** WSL workstation, `/home/qili/projects/fx_monte_carlo`, `.venv`, Python 3.12.3, yfinance 1.8.0
**Date:** 2026-11-04
**Nature:** Read-only investigation. No source, config, contract, or Git changes. No production scripts executed.

---

## 1. The Contradiction in the Original Report

The original PV-1 report (§4, §5) classifies Weekly timestamps as **B + C**:

> Weekly buckets are library resampling labels (`W-MON`), not exchange bar boundaries... No instant semantics can be established from the index alone.

However, the same report (§Q-4, sample table row 3) presents this raw observation:

```
interval: 1wk
raw epoch: 1714950000
UTC:      2024-05-05T23:00:00+00:00
Europe/London: 2024-05-06T00:00:00+01:00
```

This single sample is consistent with a real Monday 00:00 Europe/London weekly boundary. The report does not explain why this evidence is dismissed. This addendum resolves the contradiction through targeted verification.

---

## 2. WQ-1 — Raw Yahoo Weekly Timestamps

### 2.1 Methodology

Direct HTTP queries to `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1wk&range={range}&includePrePost=false`

No yfinance library involvement. Pure Yahoo raw API response.

### 2.2 5-Year Distribution (EURUSD=X)

| Statistic | Value |
|-----------|-------|
| Total timestamps | 263 |
| Boundary timestamps (Europe/London Monday 00:00) | 262 |
| — Completed weekly bar boundaries | 261 |
| — Current-week start boundary (2026-11-02, closes 2026-11-09) | 1 |
| Non-boundary observation timestamp (role not verified) | 1 |

**UTC rendering of the 262 boundary timestamps:**

| Weekday | Count | Hour |
|---------|-------|------|
| Monday | 110 | 00:00 (GMT, Nov–Mar) |
| Sunday | 152 | 23:00 (BST, Mar–Oct) |
| Wednesday | 1 | 03:00 (non-boundary observation) |

**Europe/London rendering:**

| Weekday | Count | Hour |
|---------|-------|------|
| **Monday** | **262** | **00:00** (261 completed week starts + 1 current week start) |
| Wednesday | 1 | 03:00 (non-boundary observation, role NOT VERIFIED) |

**Arithmetic:** 263 = 262 boundary timestamps + 1 non-boundary observation. Of the 262 boundary timestamps, 261 correspond to weeks that have completed; 1 is the start boundary of the currently open week. The boundary/timestamp distinction is direct observation; the completion-state assignment to 261 vs 1 is a classification inference based on the current run date (2026-11-04) and the known weekly cadence. The non-boundary observation timestamp's functional role (whether it is a live tick, whether it feeds OHLC) is NOT VERIFIED.

### 2.3 Interpretation

**Every single boundary timestamp (262/262) corresponds to Monday 00:00 Europe/London.** This includes 261 completed weekly bar boundaries and 1 current-week start boundary. No boundary timestamp deviates from this pattern.

The UTC rendering shifts between `Monday 00:00` (GMT: Nov–Mar) and `Sunday 23:00` (BST: Mar–Oct). This is **not** evidence of two different boundary types. It is the normal, expected signature of a single fixed-instant boundary rendered in two different time zones across DST transitions.

The 1 Wednesday entry is **NOT** a boundary timestamp. Its functional role (whether it is a live tick, whether it participates in OHLC construction) is NOT VERIFIED.

### 2.4 Cross-Symbol Verification

Identical result for `EURUSD=X`, `GBPUSD=X`, `USDJPY=X`, `AUDUSD=X`, `USDCAD=X`. All five pairs show the same pattern: London Monday 00:00, with UTC rendering shifting 23:00↔00:00 across DST.

### 2.5 Meta Data

Yahoo's raw meta for all three pairs:

```json
{
  "gmtoffset": 0,
  "timezone": "GMT",
  "exchangeTimezoneName": "Europe/London"
}
```

Confirmed: `gmtoffset` is a static current-day attribute, **not** per-bar. The true boundary semantics are carried by the epoch series itself.

**WQ-1 Finding:** The raw Yahoo Weekly chart endpoint returns boundary timestamps that are **real instants corresponding to Europe/London Monday 00:00**. This pattern holds across 262/262 boundary timestamps (261 completed + 1 current-week start) with zero deviation. The non-boundary observation timestamp's role is NOT VERIFIED. The Monday 00:00 label is not an arbitrary convention — it is the consistent anchor point of every boundary timestamp in the distribution. Whether this anchor is the *actual* exchange weekly bar start requires independent exchange-spec confirmation (NOT VERIFIED).

---

## 3. WQ-2 — Does yfinance Resample Weekly Data?

### 3.1 The Critical Source Code Line

`yfinance/scrapers/history.py`, line 647-648:

```python
if interval != interval_user:
    df = self._resample(df, interval, interval_user, period_user)
```

**`_resample()` is only called when the Yahoo-fetched interval differs from the user-requested interval.**

### 3.2 Default Behavior (repair=False)

`yf.download` signature (yfinance 1.8.0):

```
(tickers, ..., repair=False, ..., interval='1d', ...)
```

`Ticker.history` default repair is also `False`.

When calling `history(interval="1wk", repair=False)`:

1. Line 264: `params["interval"] = "1wk"` — requests **1wk directly** from Yahoo.
2. Line 293-301: Yahoo returns weekly bars — already aligned to exchange boundaries.
3. Line 647: `interval == interval_user` → `"1wk" == "1wk"` → **True** → `_resample is SKIPPED`.

**Empirical verification via monkey-patching:**

```python
# Patched PriceHistory._resample
resample_was_called = [False]
def traced_resample(self, df, df_interval, target_interval, period=None):
    resample_was_called[0] = True
    return original_resample(self, df, df_interval, target_interval, period)

# Then:
dl = yf.download("EURUSD=X", period="1y", interval="1wk", ...)
print(f"_resample was called? {resample_was_called[0]}")
# Output: _resample was called? False
```

### 3.3 When Does `_resample` Run For Weekly?

Line 172-198 shows the **only** path:

```python
if repair and interval in ["5d", "1wk", "1mo", "3mo"]:
    # Yahoo's way of adjusting multiday intervals is fundamentally broken.
    # Have to fetch 1d, adjust, then resample.
    interval = '1d'
```

When `repair=True`:
1. yfinance fetches `interval='1d'` (line 198)
2. At line 647: `interval='1d' != interval_user='1wk'`
3. `_resample(df, '1d', '1wk', ...)` is called
4. Line 816: `resample_period = 'W-MON'` — pandas resamples daily bars up to weekly buckets

**This is a repair-mode-only code path.**

### 3.4 What yfinance Actually Does (Default Path)

After Yahoo returns the raw weekly DataFrame, yfinance performs:

Line 439: `quotes = utils.set_df_tz(quotes, interval, tz_exchange)` — applies exchange timezone.
Line 510-513: Localizes to `Europe/London`:
```python
if not intraday:
    quotes.index = pd.to_datetime(quotes.index.date).tz_localize(
        tz_exchange, ambiguous=True, nonexistent='shift_forward')
```

Then `yf.download` (not `Ticker.history`) strips the timezone before returning.

**WQ-2 Finding:** Under default parameters (`repair=False`), yfinance does **not** resample weekly data. It fetches `interval=1wk` directly from Yahoo, receives bars already aligned to Europe/London Monday 00:00 boundaries, localizes them to that timezone, and returns them (with timezone stripped by `yf.download`). The `W-MON` resampling logic only executes in `repair=True` mode.

---

## 4. WQ-3 — Three-Path Cross-Validation

### 4.1 Test Setup

Symbol: `EURUSD=X`, period: `1y`, interval: `1wk`

Three parallel fetches:

| Path | Method | Result |
|------|--------|--------|
| **P1** | `yf.download(..., interval="1wk")` | 53 rows, naive DatetimeIndex |
| **P2** | `yf.Ticker(...).history(..., interval="1wk")` | 53 rows, Europe/London tz-aware |
| **P3** | Raw Yahoo `interval=1wk` HTTP request | 54 timestamps (53 boundary timestamps: 52 completed-week starts + 1 current-week start + 1 non-boundary observation) |

### 4.2 Results

**Path 1 (yf.download):**
```
Index tz: None
Index weekday: Monday only
Index hour: 00:00 × 53
freq='W-MON'
```

**Path 2 (Ticker.history):**
```
Index tz: Europe/London
DST offsets visible:
  2026-10-19 00:00:00+01:00   ← BST
  2026-10-26 00:00:00+00:00   ← GMT (BST→GMT transition visible)
  2026-11-02 00:00:00+00:00   ← GMT
Index hour: 00:00 × 53 (always local midnight)
```

**Path 3 (Raw Yahoo):**
```
54 timestamps:
  53 boundary timestamps (all Europe/London Monday 00:00)
    → 52 completed-week starts
    → 1 current-week start (2026-11-02)
  1 non-boundary observation timestamp (role NOT VERIFIED)
```

### 4.3 Cross-Path Matching

| Comparison | Result |
|------------|--------|
| P1 vs P2 (P2 converted to London local naive) | **True — identical** |
| P1 vs P3 (P3 London-naive boundary timestamps, skip non-boundary observation) | **True — identical** |

### 4.4 What This Proves

1. **`yf.download` output is exactly the naive version of `Ticker.history` output** — same bars, just tz stripped.
2. **Both library paths match the raw Yahoo weekly boundaries perfectly** — no resampling distortion.
3. **The timezone information exists in `Ticker.history`** (with DST offsets visible) and is only stripped at the final layer of `yf.download`.

**WQ-3 Finding:** All three paths agree. The Weekly index label IS a real instant — Europe/London Monday 00:00 — and `yf.download` merely strips the timezone representation.

---

## 5. WQ-4 — Partial Bar Behavior

### 5.1 The Correction

The initial WQ-4 conclusion in §5 (first edition of this addendum) stated that `yf.download()` Weekly output contains **completed weekly bars only**.

This was **incorrect**. Verification shows that `yf.download()` **includes the current in-progress week as its last row** whenever that week has started but not yet closed.

The initial error rested on a simple fact misreading: the example run showed `yf.download last row: 2026-11-02` on 2026-11-04 (Wednesday). The interpretation that "Nov 2 is the most recent completed Monday boundary" missed that **Nov 2 is the START of the current week, not the previous one**. The weekly completion boundary is the following Monday (Nov 9). On any day between Nov 2 and Nov 9 inclusive, `yf.download()` will show Nov 2 as its last row — an in-progress bar.

### 5.2 Verification Run

Run time (UTC): 2026-11-04T04:31:59+00:00 (Wednesday)

| Item | Value |
|------|-------|
| Current week start (Mon 00:00 GMT) | 2026-11-02 |
| Current week end (Mon 00:00 GMT) | 2026-11-09 |
| We are INSIDE this week? | **True** |
| yf.download last row index | **2026-11-02 00:00:00** |
| Raw Yahoo non-boundary observation timestamp | Wednesday, current UTC instant (role NOT VERIFIED) |

### 5.3 Five Required Distinctions

The analysis must cleanly separate:

| # | Concept | Meaning in this example |
|---|---------|------------------------|
| 1 | **Weekly bar start timestamp** | `2026-11-02 00:00 Europe/London (GMT)` — index label of the row |
| 2 | **Weekly bar completion boundary** | `2026-11-09 00:00 Europe/London (GMT)` — the Monday that closes the week |
| 3 | **Non-boundary observation timestamp** | The additional timestamp appended by Yahoo (Wednesday UTC instant). Its role (live tick, price feed, or other) is NOT VERIFIED. |
| 4 | **Latest COMPLETED weekly bar** | Index row at `2026-10-26 00:00 Europe/London` — closed on Nov 2 |
| 5 | **Current IN-PROGRESS weekly bar** | Index row at `2026-11-02 00:00 Europe/London` — open, close price provisional |

### 5.4 What yf.download Returns (Corrected)

- **All rows except the last** correspond to **completed weekly bars**. Their OHLC values are expected to be final (NOT VERIFIED — two successive fetches have not been compared to confirm stability).
- **The last row** corresponds to the **current in-progress week** if that week has started. Its OHLC values are **provisional and expected to update** until the bar completes at the next Monday 00:00 Europe/London (NOT VERIFIED — provisionality is inferred from the in-progress state; actual value-change has not been demonstrated across two successive fetches).
- `yf.download()` does **not** include a row for a week that has not yet started.
- The index timestamp for every row — completed or in-progress — is the **Monday 00:00 Europe/London start boundary** of that week.

### 5.5 What RAW Yahoo Returns

Yahoo appends **two classes of timestamps** to the weekly chart response:

1. **Boundary timestamps** — Monday 00:00 Europe/London epochs for every week including the current one.
2. **Non-boundary observation timestamp** — a single epoch representing an observation that does not fall on a Monday 00:00 Europe/London boundary. Its functional role (live tick, price feed, or other) is NOT VERIFIED.

The current week's boundary timestamp IS present in the raw series (it IS a Monday 00:00 LON). Whether Yahoo provides a separate, additional non-boundary observation that yfinance uses to update the last row's OHLC — and whether such updates actually occur — is NOT VERIFIED.

The raw Yahoo weekly timestamps for 1y data: **54 = 53 boundary timestamps (52 completed-week starts + 1 current-week start) + 1 non-boundary observation timestamp**.

### 5.6 Cross-Path Consistency

| Path | Last row index | Last row bar status | Close value |
|------|---------------|--------------------|-------------|
| yf.download | 2026-11-02 (Mon 00:00) | **In-progress** | **NOT VERIFIED** — provisionality inferred, not demonstrated |
| Ticker.history | 2026-11-02 00:00+00:00 (Europe/London) | **In-progress** | **NOT VERIFIED** — same as yf.download above |
| Raw Yahoo boundary at index 52 | epoch → Mon 00:00 LON | Boundary exists | **NOT VERIFIED** — boundary epoch confirmed; OHLC mapping from Yahoo response not traced |
| Raw Yahoo non-boundary observation at index 53 | epoch → Wednesday current time | Observation present | **NOT VERIFIED** — functional role of this entry unknown |

Both library paths show the same in-progress bar at the same Monday 00:00 boundary — the index alignment is directly observed. The raw Yahoo API provides both the boundary timestamp and an additional non-boundary observation timestamp. Whether the latter participates in OHLC construction is NOT VERIFIED.

### 5.7 Why This Matters

The previous conclusion ("completed bars only") was comforting but incorrect. The correct analysis has two consequences:

1. The **timestamp semantics** (WQ-1 through WQ-3 conclusions) remain **unchanged and correct**. The Nov 2 row's index label IS a real instant — the Monday 00:00 start. The fact that this bar is in progress does not erase the semantic finding that the label represents a real boundary.

2. The **data freshness / contract implications** change: the last row is an in-progress week, and its OHLC values are expected to be provisional (NOT VERIFIED — value-change has not been directly demonstrated but follows from the in-progress state). Any consumer that treats the last row of a Weekly yf.download DataFrame as final may be wrong. The Contract should explicitly state whether partial bars are included and how to detect them (see §3 of user's opening analysis for a proposed field structure).

**WQ-4 Finding (Corrected):** `yf.download()` Weekly output includes the current in-progress week as its last row. Every row's timestamp IS a real Monday 00:00 Europe/London boundary instant (confirming WQ-1 through WQ-3). The last row's OHLC values are expected to be provisional until the next Monday 00:00 Europe/London, but this value-change behavior is NOT VERIFIED by successive-fetch comparison. Completed bars have final timestamps; their OHLC stability is expected but not re-verified here.

---

## 6. WQ-5 — Final Semantic Classification

### 6.1 Recalibrating the A/B/C Framework

| Class | Definition | Weekly Status |
|-------|------------|---------------|
| **A** | Real instant corresponding to an exchange bar boundary | **LIKELY YES** — 262/262 boundary timestamps are Europe/London Monday 00:00; whether this is *the actual exchange* boundary is NOT VERIFIED |
| **B** | Session-date label with no established instant semantics | **NO** — this was the original misclassification, disproved by WQ-1 |
| **C** | Library transformation that loses timezone semantics | **YES** — `yf.download` strips tz from the tz-aware `Ticker.history` output |
| NOT VERIFIED | Insufficient evidence | — |

### 6.2 Coexistence of A and C

A and C are **not mutually exclusive**:
- **A is what the data is.** The underlying epochs are real weekly boundary instants.
- **C is what yf.download does.** It removes the timezone representation, leaving a naive label.

This is the **exact same A+C relationship** as Daily. Weekly and Daily share the same semantic structure — they differ only in the resampling code path (which Weekly does not use under default parameters).

### 6.3 Correction of Original Report's Error

The original report's Weekly → B+C classification rested on a **false premise**: that yfinance resamples weekly data using `W-MON`. In fact:
- Default path (repair=False): **no resampling** — direct Yahoo `interval=1wk` fetch
- `W-MON` resampling only occurs in repair=True mode, which the project does not use

The report also misinterpreted the UTC rendering of BST-era weekly boundaries (`Sunday 23:00 UTC`) as evidence of a "different" boundary type. This is simply the same Europe/London Monday 00:00 instant rendered in UTC during British Summer Time.

### 6.4 Per-Pair Verification

All sampled pairs show identical behavior:

| Pair | Weekly boundaries match London Mon 00:00 |
|------|------------------------------------------|
| EURUSD=X | YES |
| GBPUSD=X | YES |
| USDJPY=X | YES |
| AUDUSD=X | YES |
| USDCAD=X | YES |

Cross-pair consistency is high for these five major FX pairs.

---

## 7. Evidence Summary

| Question | Answer | Confidence | Evidence Nature |
|----------|--------|------------|-----------------|
| Q1: Do raw Yahoo Weekly timestamps represent real instants? | **YES** — each of the 262 boundary timestamps maps to Europe/London Monday 00:00 | **HIGH** — zero-deviation distribution across 262 boundary timestamps, 5 pairs | Direct distributional observation (not exchange-spec confirmation) |
| Q2: Does yfinance resample Weekly data by default? | **NO** — `_resample` guard at line 647 skips when `interval == interval_user` | **HIGH** — source code inspection + single-run monkey-patch | Source code is direct; monkey-patch is empirical (not reproduced here) |
| Q3: Do all three fetch paths agree? | **YES** — download index == Ticker.history index == raw Yahoo boundary timestamps | **HIGH** — exact match verified on single run | Empirical single-run observation |
| Q4: Does yf.download include partial current week? | **YES** — last row IS the in-progress week (its index is the current-week start boundary) | **HIGH** — index alignment vs known weekly cadence | Calendar + index comparison, direct observation |
| Q5: Is Weekly A, B, or C? | **LIKELY A (real instant) + C (library tz-loss)** — B classification disproved | **MEDIUM-HIGH** — boundary instant confirmed; exchange-bar correspondence NOT VERIFIED | Synthesis of Q1–Q4 |
| Q6: Does the last row's OHLC actually change during the week? | **EXPECTED YES** but **NOT VERIFIED** | **LOW** — inferred from in-progress state, no successive-fetch comparison | Inference only |

**Key principle:** A timestamp can identify a bar's temporal position. It does not, by itself, establish whether that bar is complete or how its OHLC values were constructed.

---

## 8. Limitations

| # | Limitation | Impact |
|---|-----------|--------|
| L-1 | Only verified for FX pairs (`*=X`) | Low — the exchange timezone semantics are exchange-specific, but all sampled FX pairs use Europe/London |
| L-2 | Not verified for historical yfinance versions | Same as original PV-1 NV-1 — the original report already noted this gap |
| L-3 | repair=True behavior not fully explored (sklearn not installed) | Low — project does not use repair=True; default path is what matters |
| L-4 | DST transition boundaries not exhaustively mapped across all years | Low — the distribution analysis confirmed all 262 boundary timestamps land on Monday 00:00 Europe/London |
| L-5 | Only yfinance 1.8.0 tested | Same as NV-1 in original report — reproducibility gap for older artifacts |

---

## 9. Correction to Original PV-1 Report

The original report's §4 Verdict table should be revised as follows:

### Original (incorrect):
| TF | Verdict | Basis |
|----|---------|-------|
| **W** | **PARTIAL — class B + C** | Weekly buckets are library resampling labels (`W-MON`), not exchange bar boundaries |

### Revised (addendum-corrected):
| TF | Verdict | Basis |
|----|---------|-------|
| **W** | **PARTIAL — class A + C** | Weekly buckets are real Europe/London Monday 00:00 exchange boundaries (A), but `yf.download` strips timezone (C) |

Weekly and Daily are now confirmed to have **identical semantic structure**: real exchange-local-midnight instants, with yf.download stripping the timezone representation.

---

## 10. Consequence for Revision 5a §5.1

The addendum changes nothing about the **practical compliance problem**: `yf.download` still outputs a naive `00:00` DatetimeIndex that cannot be written with `+00:00` per §5.1 read literally.

However, it changes **what kind of problem this is**:

| Before (original report) | After (addendum correction) |
|-------------------------|------------------------------|
| Weekly timestamps may be fundamentally un-recoverable session-date labels | Weekly timestamps are recoverable real instants — same as Daily |
| D and W are semantically different, requiring different handling | D and W are semantically identical, requiring the same handling |
| §5.1 compliance requires different solutions per timeframe | §5.1 compliance requires one solution for both timeframes |

**The data underneath is recoverable.** The obstacle is the library's timezone-stripped output format, not Yahoo's original data semantics.

---

## 11. Source Code Citations

All paths relative to `.venv/lib/python3.12/site-packages/yfinance/`

| File | Line(s) | Statement |
|------|---------|-----------|
| `scrapers/history.py` | 110-114 | `history()` signature, default `repair=False` |
| `scrapers/history.py` | 172-198 | `repair=True` path: fetches `'1d'`, triggers later resample |
| `scrapers/history.py` | 264 | `params["interval"] = interval.lower()` — passes user interval directly to Yahoo |
| `scrapers/history.py` | 647-648 | `if interval != interval_user: df = self._resample(...)` — resample guard |
| `scrapers/history.py` | 803-856 | `_resample()` method — only invoked when guard at 647 passes |
| `scrapers/history.py` | 816 | `resample_period = 'W-MON'` — inside repair-only code path |
| `scrapers/history.py` | 439 | `quotes = utils.set_df_tz(quotes, interval, tz_exchange)` — timezone localization |
| `scrapers/history.py` | 510-513 | Non-intraday timezone-localization to `tz_exchange` (Europe/London for FX) |
| `utils.py` | — | Function removing tz for download output (separate from history.py) |

---

## 12. Correction History

### Revision 2 (2026-11-04, same day as original)

**Issue:** §5 WQ-4 initial conclusion claimed that `yf.download()` Weekly output contains **completed bars only**. This was incorrect.

**Root cause:** The initial run example showed:
```
Run time: 2026-11-04 (Wednesday)
yf.download last row: 2026-11-02 (Monday 00:00)
```

The initial interpretation assumed `2026-11-02` was the "most recent completed Monday boundary." It missed that **2026-11-02 is the START of the current week**, which completes on 2026-11-09. The error was a simple calendar misreading, not a data anomaly.

**Corrected finding:** `yf.download()` includes the current in-progress week as its last row. All timestamp semantics findings (WQ-1 through WQ-3) remain correct and unaffected by this correction. The in-progress row's OHLC values are provisional and will update until the weekly bar closes.

**Sections changed:**
- §5 WQ-4 — completely rewritten
- §7 Evidence Summary Q4 row — corrected from NO to YES

---

### Revision 3 (2026-11-04, same day as Revision 2)

**Issue:** Three distinct problems identified in a read-only verification pass:

1. **§2.2 completion-state misclassification:** The summary table stated 262 of 263 timestamps were "completed weekly boundaries." This conflated two separate claims — (a) 262 of the 263 timestamps are Monday 00:00 Europe/London boundary timestamps (direct observation), and (b) all 262 correspond to weeks that have completed (false; 2026-11-02 is the current week's start boundary, week completes 2026-11-09). The correct split is 261 completed-week start boundaries + 1 current-week start boundary = 262 boundary timestamps, plus 1 non-boundary observation timestamp of unknown role.
2. **§5.5 arithmetic error:** The claim "54 = 53 completed weeks + 1 current-week boundary + 1 live tick" is arithmetically wrong (53+1+1=55 ≠ 54). It also incorrectly assumed the non-boundary timestamp was a "live tick" with a known role.
3. **OHLC mapping claims presented as verified:** Revision 2 (and the original) described OHLC value behavior (provisionality of last row, update mechanism via live tick, boundary Close = fixed open) as directly verified. No successive-fetch comparison or raw API response parsing had been performed to establish these claims. They are inferences, not observations, and must be marked NOT VERIFIED.
4. **Missing sub-section numbers:** Two §2.3 headers and one §2.4 header created duplicate numbering.

**Root cause:** A single empirical fetch run was over-interpreted. Timestamp distribution patterns were correctly observed but then extended into completion-state claims and OHLC-mechanism claims without additional evidence. The boundary/timestamp/completion-state distinction was not explicitly maintained.

**Key principle established:** A timestamp can identify a bar's temporal position. It does not, by itself, establish whether that bar is complete or how its OHLC values were constructed.

**Corrected findings:**
- Boundary timestamps are clearly separated from non-boundary observation timestamps.
- Completion-state counts (261 completed vs 1 current) are now classified inferences, not direct observations.
- All OHLC-related claims are marked NOT VERIFIED where direct evidence is lacking.
- The non-boundary observation timestamp is no longer assumed to be a "live tick" — its functional role is explicitly NOT VERIFIED.
- Evidence Nature column added to §7 to distinguish source-code inspection, empirical single-run observation, and inference.
- Section A classification softened from "YES" to "LIKELY YES" with exchange-bar correspondence marked NOT VERIFIED.

**Sections changed:**
- §2.2 — table restructured, counts corrected, NOT VERIFIED markings added
- §2.3 — rewritten to distinguish boundary-timestamp distribution (262/262) from completion-state classification
- §2.4, §2.5 — section numbers corrected (were duplicate §2.3 + §2.4)
- §2.5 (WQ-1 Finding) — softened "actual exchange" claim, added NOT VERIFIED
- §4.1 P3 row — corrected classification: 53 boundary timestamps (52 completed + 1 current) + 1 non-boundary observation
- §4.2 Path 3 output — corrected to match §4.1 classification
- §5.2 — "live tick" → "non-boundary observation timestamp (role NOT VERIFIED)"
- §5.3 row 3 — renamed "Non-boundary observation timestamp", role NOT VERIFIED
- §5.4 — OHLC provisionality claims marked NOT VERIFIED
- §5.5 — arithmetic corrected: 54 = 53 boundary timestamps + 1 non-boundary observation; "live tick" claim removed; role of non-boundary entry marked NOT VERIFIED
- §5.6 — all four Close value cells marked NOT VERIFIED
- §5.7 — WQ-4 Finding softened; OHLC change marked NOT VERIFIED
- §6.1 — Class A softened to "LIKELY YES" with exchange-bar correspondence NOT VERIFIED; removed "262/262 completed bars"
- §7 — Evidence Nature column added; Q1–Q5 reworded; Q6 added (OHLC change, NOT VERIFIED); key principle added
- §8 L-4 — "262 completed bars" → "262 boundary timestamps"

---

## 13. Compliance

- No production source modified
- No contract or YAML changed
- No Git operations performed
- No production scripts executed
- No writes to `mc_results/` or `api/`
- Only new file created: this addendum

**Stage B remains NOT AUTHORIZED. Revision 5a remains NOT FROZEN.**