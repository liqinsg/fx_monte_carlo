# fx_monte_carlo.py
"""
FX MONTE CARLO ENGINE — DAILY PRIMARY (H4 OPTIONAL)
✅ Usage:
   python fx_monte_carlo.py              # runs Daily by default
   python fx_monte_carlo.py --timeframe H4
✅ Auto‑scales lookback / forecast / drift‑vol per timeframe
✅ Market‑closed skip per timeframe
✅ Consistent JSON output for trading bot
✅ Console + JSON output only (no Telegram, no OANDA)
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("fx_mc")

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import config

# ==========================================
# ⚙️ ARG PARSE + TIMEFRAME CONFIG
# ==========================================
import argparse

parser = argparse.ArgumentParser(description="FX Monte Carlo — Daily or H4")
parser.add_argument("--timeframe", choices=["D", "H4"], default="D", help="Timeframe: D (Daily, default) / H4 (4‑Hour)")
args = parser.parse_args()
TF = args.timeframe


def cfg(name: str, default: Any) -> Any:
    return getattr(config, name, default)


PAIRS: list[str] = cfg("DEFAULT_PAIRS", [
    "EURUSD=X", "GBPUSD=X", "EURJPY=X", "GBPJPY=X",
    "AUDUSD=X", "USDJPY=X", "GBPAUD=X", "USDCHF=X",
    "NZDUSD=X", "EURGBP=X", "CADJPY=X", "USDCAD=X", "CHFJPY=X"
])
SIMULATIONS: int = cfg("MC_SIMULATIONS", 5000)
CONFIDENCE: float = cfg("MC_CONFIDENCE", 0.90)
RESULTS_DIR: Path = BASE_DIR / "daily_results"
RESULTS_DIR.mkdir(exist_ok=True)

# ——— TIMEFRAME‑SPECIFIC PARAMS ———
if TF == "H4":
    YF_INTERVAL = "4h"
    YF_PERIOD_FULL = "30d"
    YF_PERIOD_RESAMPLE = "60d"
    LOOKBACK: int = cfg("H4_LOOKBACK", 90)
    FORECAST: int = cfg("H4_FORECAST", 8)
    PERIODS_YEAR: int = 252 * 6
    DT_SCALE: int = 1
    REPORT_TITLE = "FX H4 MONTE CARLO UPDATE"
else:
    YF_INTERVAL = "1d"
    YF_PERIOD_FULL = "120d"
    YF_PERIOD_RESAMPLE = "180d"
    LOOKBACK = cfg("DAILY_LOOKBACK", 90)
    FORECAST = cfg("DAILY_FORECAST", 5)
    PERIODS_YEAR = 252
    DT_SCALE = 1
    REPORT_TITLE = "FX DAILY MONTE CARLO UPDATE"


def clean_pair_name(raw: str) -> str:
    return raw.replace("=X", "").replace("=", "_")


# ==========================================
# 🛡️ MARKET STATUS — FAST SCHEDULE EXIT (London TZ, zero API cost)
# ==========================================
def forex_market_closed() -> bool:
    now = datetime.now(ZoneInfo("Europe/London"))
    wd = now.weekday()
    return (
        wd == 5
        or (wd == 6 and now.hour < 21)
        or (wd == 4 and now.hour >= 21)
    )


if forex_market_closed():
    logger.info("FX %s MC: Market closed — skipped", TF)
    raise SystemExit(0)

# ==========================================
# 📥 DATA FETCH — AUTO‑RESAMPLE FALLBACK
# ==========================================
def fetch_data(pair: str) -> pd.DataFrame:
    try:
        df = yf.download(pair, period=YF_PERIOD_FULL, interval=YF_INTERVAL, progress=False)
        if len(df) >= LOOKBACK:
            return df[["Open", "High", "Low", "Close"]].dropna()
    except Exception:
        pass
    try:
        fallback_interval = "1h" if TF == "H4" else "4h"
        df = yf.download(pair, period=YF_PERIOD_RESAMPLE, interval=fallback_interval, progress=False)
        if df.empty:
            return pd.DataFrame()
        return df[["Open", "High", "Low", "Close"]].resample(YF_INTERVAL).agg({
            "Open": "first", "High": "max", "Low": "min", "Close": "last"
        }).dropna()
    except Exception as exc:
        logger.error("Data failed for %s: %s", pair, exc)
        return pd.DataFrame()


# ==========================================
# 🧠 UNIFIED PROBABILITY ENGINE
# ==========================================
def run_mc(pair: str) -> tuple[dict[str, Any], bool]:
    df = fetch_data(pair)
    if len(df) < LOOKBACK:
        return {}, False

    closes = df["Close"].values[-LOOKBACK:]
    current = float(closes[-1].item())
    log_returns = np.log(closes[1:] / closes[:-1])

    drift = float(np.mean(log_returns) * PERIODS_YEAR)
    vol = float(np.std(log_returns) * np.sqrt(PERIODS_YEAR))
    dt = 1 / PERIODS_YEAR * DT_SCALE

    np.random.seed(42)
    paths = np.zeros((SIMULATIONS, FORECAST + 1))
    paths[:, 0] = current
    for t in range(1, FORECAST + 1):
        z = np.random.normal(0, 1, SIMULATIONS)
        paths[:, t] = paths[:, t - 1] * np.exp(
            (drift / PERIODS_YEAR - 0.5 * (vol ** 2) / PERIODS_YEAR)
            + (vol * np.sqrt(dt)) * z
        )

    final = paths[:, -1]
    lower = float(np.percentile(final, (1 - CONFIDENCE) / 2 * 100))
    upper = float(np.percentile(final, (1 + CONFIDENCE) / 2 * 100))

    percentile = round((np.sum(final <= current) / SIMULATIONS) * 100, 1)
    p_up = round((np.sum(final > current) / SIMULATIONS) * 100, 1)
    p_down = round(100 - p_up, 1)
    touch_upper = round((np.any(paths >= upper, axis=1).sum() / SIMULATIONS) * 100, 1)
    touch_lower = round((np.any(paths <= lower, axis=1).sum() / SIMULATIONS) * 100, 1)

    if percentile >= 85 and p_down > 55:
        regime = f"🔴 {TF} OVERBOUGHT | Mean‑Reversion Risk"
    elif percentile <= 15 and p_up > 55:
        regime = f"🟢 {TF} OVERSOLD | Bullish Reversal Chance"
    elif abs(drift) > vol * 0.7 and max(p_up, p_down) > 60:
        regime = f"⚡ {TF} STRONG MOMENTUM"
    elif abs(p_up - p_down) < 4 and abs(drift) < vol * 0.3:
        regime = f"⏳ {TF} CONSOLIDATION RANGE"
    else:
        regime = f"🔹 {TF} NEUTRAL"

    dec = 3 if "JPY" in pair else 5
    now_utc = datetime.now(timezone.utc)
    return {
        "timeframe": TF,
        "pair": clean_pair_name(pair),
        "date": now_utc.strftime("%Y-%m-%d"),
        "current_price": round(current, dec),
        "ann_drift_pct": round(drift * 100, 2),
        "ann_vol_pct": round(vol * 100, 2),
        "range_90": [round(lower, dec), round(upper, dec)],
        "percentile_rank": percentile,
        "p_up": p_up,
        "p_down": p_down,
        "p_up_pct": p_up,
        "p_down_pct": p_down,
        "touch_upper_pct": touch_upper,
        "touch_lower_pct": touch_lower,
        "regime": regime,
        "lookback": LOOKBACK,
        "forecast": FORECAST,
        "simulations": SIMULATIONS,
        "generated_utc": now_utc.isoformat(),
    }, True


# ==========================================
# 🚀 MAIN RUN
# ==========================================
def main() -> None:
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    all_results: list[dict[str, Any]] = []
    logger.info("MC RUN — %s UTC | TF=%s | Pairs=%d", now_str, TF, len(PAIRS))

    for pair in PAIRS:
        logger.info("Processing: %s", pair)
        data, ok = run_mc(pair)
        if not ok:
            logger.warning("Skipped %s", pair)
            continue
        all_results.append(data)
        safe = clean_pair_name(pair)
        tag = "daily" if TF == "D" else "h4"
        outfile = RESULTS_DIR / f"{tag}_mc_{safe}_{now_str}.json"
        outfile.write_text(json.dumps(data, indent=2))
        logger.info("Saved → %s", outfile.name)

    logger.info("Run complete — %d results written", len(all_results))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.exception("MC Run failed: %s", exc)
        raise SystemExit(1) from exc