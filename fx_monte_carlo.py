# fx_monte_carlo.py
"""
FX MONTE CARLO ENGINE — DAILY + WEEKLY (PURE NUMERICAL CALCULATION)
===================================================================

Usage:
    python fx_monte_carlo.py

Timeframes:
    D = Daily MC (90 days)
    W = Weekly MC (104 weeks)

Design:
    - Pure statistical and numerical simulation core
    - Student-t fat-tailed path generation
    - Dynamic fallback to internal defaults if config.py options are missing
    - Atomic JSON output & historical file pruning
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import yfinance as yf

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

# ==========================================
# PATH & CONFIG LOADING WITH FALLBACK
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

try:
    import config
except ImportError:
    config = None


def cfg(name, default):
    """Retrieve configuration attribute or return default fallback."""
    if config is not None:
        return getattr(config, name, default)
    return default


# ==========================================
# PAIRS
# ==========================================

DEFAULT_PAIRS = [
    "EURUSD=X",
    "GBPUSD=X",
    "AUDUSD=X",
    "USDCHF=X",
    "NZDUSD=X",
    "USDCAD=X",
    "EURGBP=X",
    "USDJPY=X",
    "EURJPY=X",
    "GBPJPY=X",
    "AUDJPY=X",
    "CADJPY=X",
    "CHFJPY=X",
    "NZDJPY=X",
    "GBPAUD=X",
    "EURCHF=X",
]

PAIRS = cfg("PAIRS", cfg("DEFAULT_PAIRS", DEFAULT_PAIRS))


# ==========================================
# MC PARAMETERS
# ==========================================

SIMULATIONS = cfg("MC_SIMULATIONS", 5000)
CONFIDENCE = cfg("MC_CONFIDENCE", 0.90)

# Student-t degrees of freedom for fat-tailed shocks
STUDENT_T_DF = cfg("MC_STUDENT_T_DF", 5)

# Keep maximum history files per pair/timeframe
MAX_HISTORY_FILES = cfg("MC_MAX_HISTORY_FILES", 100)


# ==========================================
# TIMEFRAME CONFIGURATION
# ==========================================

DAILY_LOOKBACK = cfg("DAILY_LOOKBACK", 90)
DAILY_FORECAST = cfg("DAILY_FORECAST", 5)

WEEKLY_LOOKBACK = cfg("WEEKLY_LOOKBACK", 104)
WEEKLY_FORECAST = cfg("WEEKLY_FORECAST", 5)

TIMEFRAME_CONFIG = {
    "D": {
        "yf_interval": "1d",
        "yf_period": cfg("DAILY_YF_PERIOD", "1y"),
        "lookback": DAILY_LOOKBACK,
        "forecast": DAILY_FORECAST,
        "periods_year": cfg("DAILY_PERIODS_YEAR", 252),
    },
    "W": {
        "yf_interval": "1wk",
        "yf_period": cfg("WEEKLY_YF_PERIOD", "5y"),
        "lookback": WEEKLY_LOOKBACK,
        "forecast": WEEKLY_FORECAST,
        "periods_year": cfg("WEEKLY_PERIODS_YEAR", 52),
    },
}

TIMEFRAMES = cfg("MC_TIMEFRAMES", ["D", "W"])


# ==========================================
# DIRECTORY ROUTING
# ==========================================

RESULTS_DIR = BASE_DIR / cfg("DAILY_RESULTS_DIR_NAME", "daily_results")
RESULTS_DIR.mkdir(exist_ok=True)

WEEKLY_RESULTS_DIR = BASE_DIR / cfg("WEEKLY_RESULTS_DIR_NAME", "weekly_results")
WEEKLY_RESULTS_DIR.mkdir(exist_ok=True)

TIMEFRAME_RESULTS_DIR = {
    "D": RESULTS_DIR,
    "W": WEEKLY_RESULTS_DIR,
}


def results_dir_for(timeframe: str) -> Path:
    """Return the output directory for a given timeframe."""
    return TIMEFRAME_RESULTS_DIR.get(timeframe, RESULTS_DIR)


REPORT_TITLE = "FX MONTE CARLO SIMULATION"


# ==========================================
# MARKET STATUS CHECK
# ==========================================

def forex_market_closed() -> bool:
    """FX market schedule check using London timezone."""
    now = datetime.now(ZoneInfo("Europe/London"))
    wd = now.weekday()

    return (
        wd == 5
        or (wd == 6 and now.hour < 21)
        or (wd == 4 and now.hour >= 21)
    )


if forex_market_closed():
    print("⏸️ FX MC: Market closed — skipped")
    raise SystemExit(0)


# ==========================================
# DATA FETCHING
# ==========================================

def fetch_data(pair: str, timeframe: str) -> pd.DataFrame:
    """Fetch native Yahoo Finance data for the requested timeframe."""
    if timeframe not in TIMEFRAME_CONFIG:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    tf = TIMEFRAME_CONFIG[timeframe]
    interval = tf["yf_interval"]
    period = tf["yf_period"]
    lookback = tf["lookback"]

    try:
        df = yf.download(
            pair,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False,
        )

        if df.empty:
            print(f"⚠️ No data {pair} [{timeframe}] (interval={interval}, period={period})")
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                pass

        required = ["Open", "High", "Low", "Close"]
        missing = [c for c in required if c not in df.columns]

        if missing:
            print(f"⚠️ Missing columns {pair} [{timeframe}]: {missing}")
            return pd.DataFrame()

        df = df[required].dropna()

        if len(df) < lookback:
            print(f"⚠️ Insufficient native {timeframe} data for {pair}: {len(df)} < {lookback}")
            return pd.DataFrame()

        return df

    except Exception as e:
        print(f"❌ Data fetch failed for {pair} [{timeframe}]: {e}")
        return pd.DataFrame()


# ==========================================
# MONTE CARLO CALCULATION ENGINE
# ==========================================

def run_mc(pair: str, timeframe: str):
    """Run pure Monte Carlo simulation and return numerical metrics."""
    if timeframe not in TIMEFRAME_CONFIG:
        return None, False

    tf = TIMEFRAME_CONFIG[timeframe]
    lookback = tf["lookback"]
    forecast = tf["forecast"]
    periods_year = tf["periods_year"]

    df = fetch_data(pair, timeframe)

    if len(df) < lookback:
        return None, False

    closes = df["Close"].values[-lookback:]
    current = float(closes[-1].item())

    if current <= 0:
        return None, False

    log_returns = np.log(closes[1:] / closes[:-1])

    if len(log_returns) < 2:
        return None, False

    # Drift & Volatility
    drift = float(np.mean(log_returns) * periods_year)
    vol = float(np.std(log_returns) * np.sqrt(periods_year))
    dt = 1 / periods_year

    # Student-t Fat-Tailed Shocks
    np.random.seed(cfg("MC_RANDOM_SEED", 42))

    scale_factor = (
        np.sqrt((STUDENT_T_DF - 2) / STUDENT_T_DF)
        if STUDENT_T_DF > 2
        else 1.0
    )

    t_shocks = (
        np.random.standard_t(
            STUDENT_T_DF,
            size=(SIMULATIONS, forecast),
        )
        * scale_factor
    )

    # Path Generation
    step_drift = drift / periods_year - 0.5 * (vol ** 2) / periods_year
    step_diffusion = vol * np.sqrt(dt) * t_shocks
    log_returns_matrix = step_drift + step_diffusion

    paths = np.empty((SIMULATIONS, forecast + 1))
    paths[:, 0] = current
    paths[:, 1:] = current * np.exp(np.cumsum(log_returns_matrix, axis=1))

    final = paths[:, -1]

    # Confidence Interval
    lower = float(np.percentile(final, (1 - CONFIDENCE) / 2 * 100))
    upper = float(np.percentile(final, (1 + CONFIDENCE) / 2 * 100))

    # Return Distribution Metrics
    pct_changes = (final - current) / current
    var_95 = float(np.percentile(pct_changes, 5))
    tail = pct_changes[pct_changes <= var_95]
    cvar_95 = float(np.mean(tail)) if len(tail) else var_95

    # Probabilities
    percentile = round(float((np.sum(final <= current) / SIMULATIONS) * 100), 1)
    p_up = round(float((np.sum(final > current) / SIMULATIONS) * 100), 1)
    p_down = round(float(100.0 - p_up), 1)

    dec = 3 if "JPY" in pair else 5

    return {
        "timeframe": timeframe,
        "pair": pair,
        "current_price": round(current, dec),
        "ann_drift_pct": round(drift * 100, 2),
        "ann_vol_pct": round(vol * 100, 2),
        "range_90": [round(lower, dec), round(upper, dec)],
        "percentile_rank": percentile,
        "p_up": p_up,
        "p_down": p_down,
        "var_95": round(var_95, 4),
        "cvar_95": round(cvar_95, 4),
        "expected_price": round(float(np.mean(final)), dec),
        "lookback": lookback,
        "forecast": forecast,
        "simulations": SIMULATIONS,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }, True


# ==========================================
# ATOMIC SAVE & CLEANUP
# ==========================================

def save_mc_result_safely(
    data: dict,
    target_file: Path,
    glob_pattern: str,
    max_files: int = MAX_HISTORY_FILES,
) -> None:
    """Atomically write JSON output and remove old history files."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = target_file.with_suffix(f".tmp{os.getpid()}")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    temp_file.replace(target_file)

    history_files = sorted(
        target_file.parent.glob(glob_pattern),
        key=os.path.getmtime,
    )

    if len(history_files) > max_files:
        for old_file in history_files[:-max_files]:
            try:
                old_file.unlink()
            except OSError:
                pass


# ==========================================
# MAIN EXECUTION
# ==========================================

def main():
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    all_results = []

    print(f"🔬 {REPORT_TITLE} — {now_str} UTC")
    print(f"📈 Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"🔹 Pairs: {len(PAIRS)}")

    for timeframe in TIMEFRAMES:
        if timeframe not in TIMEFRAME_CONFIG:
            print(f"⚠️ Unsupported timeframe: {timeframe} — skipped")
            continue

        tf = TIMEFRAME_CONFIG[timeframe]

        print("\n" + "=" * 60)
        print(f"📊 TIMEFRAME: {timeframe}")
        print(f"   Lookback: {tf['lookback']}")
        print(f"   Forecast: {tf['forecast']}")
        print(f"   Interval: {tf['yf_interval']}")
        print("=" * 60)

        for pair in PAIRS:
            print(f"🔄 Processing: {pair} [{timeframe}]")

            data, ok = run_mc(pair, timeframe)

            if not ok:
                print(f"⚠️ Skipped {pair} [{timeframe}]")
                continue

            all_results.append(data)

            safe = pair.replace("=X", "").replace("=", "_")
            filename = f"mc_{timeframe}_{safe}_{now_str}.json"

            save_mc_result_safely(
                data,
                results_dir_for(timeframe) / filename,
                glob_pattern=f"mc_{timeframe}_{safe}_*.json",
            )

            print(f"✅ Saved → {results_dir_for(timeframe).name}/{filename}")

    print(f"\n✅ Run complete — {len(all_results)} MC results calculated.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ MC Error: {e}")