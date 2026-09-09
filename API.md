# FX Monte Carlo API

The FX Monte Carlo forecast engine runs daily at **00:00 UTC** and publishes JSON forecasts to this repository. These JSON files can be served publicly via **GitHub Pages**.

## Enable GitHub Pages

1. Go to your repository on GitHub.
2. Open **Settings** → **Pages**.
3. Under **Source**, select **Deploy from a branch**.
4. Choose branch `main` and folder `/ (root)`.
5. Click **Save**.

Within a minute, GitHub will publish your site. The public base URL will be:

```
https://liqinsg.github.io/fx_monte_carlo
```

> ⚠️ Replace `liqinsg` with your own GitHub username if different.

## Endpoints

### Latest forecast (always current)

| Endpoint | Description |
|----------|-------------|
| `GET /api/latest/all.json` | Aggregate of all pairs — most recent run |
| `GET /api/latest/EURUSD.json` | Most recent EURUSD forecast |
| `GET /api/latest/GBPUSD.json` | Most recent GBPUSD forecast |
| `GET /api/latest/USDJPY.json` | Most recent USDJPY forecast |
| `GET /api/latest/<PAIR>.json` | Any pair (pair names use `EURUSD` style, no `=X`) |

### Historical forecast (first snapshot of the day)

| Endpoint | Example |
|----------|---------|
| `GET /api/YYYY/MM/DD/all.json` | `https://liqinsg.github.io/fx_monte_carlo/api/2026/09/09/all.json` |
| `GET /api/YYYY/MM/DD/<PAIR>.json` | `https://liqinsg.github.io/fx_monte_carlo/api/2026/09/09/EURUSD.json` |

Historical endpoints preserve the **first forecast generated each day**. Manual re-runs (`workflow_dispatch`) will not overwrite that day's dated files — only `/api/latest/*` is updated.

## Response format

Single pair (`EURUSD.json`):

```json
{
  "timeframe": "D",
  "pair": "EURUSD",
  "date": "2026-09-09",
  "current_price": 1.10234,
  "ann_drift_pct": 1.24,
  "ann_vol_pct": 7.81,
  "range_90": [1.07120, 1.13450],
  "percentile_rank": 48.3,
  "p_up": 61.2,
  "p_down": 38.8,
  "p_up_pct": 61.2,
  "p_down_pct": 38.8,
  "touch_upper_pct": 18.4,
  "touch_lower_pct": 14.1,
  "regime": "🔹 D NEUTRAL",
  "lookback": 90,
  "forecast": 5,
  "simulations": 5000,
  "generated_utc": "2026-09-09T00:00:10+00:00"
}
```

Aggregate (`all.json`):

```json
{
  "date": "2026-09-09",
  "generated_utc": "2026-09-09T00:00:10Z",
  "count": 13,
  "pairs": [
    {
      "pair": "EURUSD",
      "p_up": 61.2,
      "p_down": 38.8,
      "...": "..."
    }
  ]
}
```

## Usage examples

### curl

```bash
curl -s https://liqinsg.github.io/fx_monte_carlo/api/latest/EURUSD.json | jq .
curl -s https://liqinsg.github.io/fx_monte_carlo/api/latest/all.json | jq '.pairs[] | {pair, p_up, p_down}'
```

### Python

```python
import requests

BASE = "https://liqinsg.github.io/fx_monte_carlo/api/latest"

resp = requests.get(f"{BASE}/EURUSD.json", timeout=10)
resp.raise_for_status()
data = resp.json()

print(f"EURUSD current: {data['current_price']}")
print(f"  P(up)   = {data['p_up']}%")
print(f"  P(down) = {data['p_down']}%")
print(f"  Regime  = {data['regime']}")
print(f"  90% range: {data['range_90']}")
```

### JavaScript (Browser / Node)

```javascript
const BASE = "https://liqinsg.github.io/fx_monte_carlo/api/latest";

async function getPair(pair) {
  const resp = await fetch(`${BASE}/${pair}.json`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

getPair("EURUSD").then((d) => {
  console.log(`EURUSD: ${d.current_price}`);
  console.log(`  P(up)   = ${d.p_up}%`);
  console.log(`  P(down) = ${d.p_down}%`);
  console.log(`  Regime  = ${d.regime}`);
});
```

## Running manually

You can trigger an immediate run from GitHub:

1. Open the **Actions** tab.
2. Click **FX Monte Carlo Daily** on the left.
3. Click **Run workflow** on the right → select `main` → **Run workflow**.

## Pair name reference

All pair names use the clean `EURUSD` form (Yahoo Finance `=X` suffix is stripped). Supported pairs:

| Pair | Yahoo symbol |
|------|-------------|
| EURUSD | EURUSD=X |
| GBPUSD | GBPUSD=X |
| EURJPY | EURJPY=X |
| GBPJPY | GBPJPY=X |
| AUDUSD | AUDUSD=X |
| USDJPY | USDJPY=X |
| GBPAUD | GBPAUD=X |
| USDCHF | USDCHF=X |
| NZDUSD | NZDUSD=X |
| EURGBP | EURGBP=X |
| CADJPY | CADJPY=X |
| USDCAD | USDCAD=X |
| CHFJPY | CHFJPY=X |