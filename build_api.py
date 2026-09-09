"""Build public API from daily_results JSON files."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "daily_results"
API_DIR = BASE_DIR / "api"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("build_api")


def clean_pair_name(raw: str) -> str:
    return raw.replace("=X", "").replace("=", "_")


def _utc_from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_results() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not RESULTS_DIR.is_dir():
        logger.warning("daily_results/ not found — nothing to build.")
        return results

    for path in sorted(RESULTS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            results.append(data)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to parse %s: %s", path.name, exc)
    logger.info("Loaded %d result files from daily_results/", len(results))
    return results


def _group_latest(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for r in results:
        pair = clean_pair_name(r.get("pair", ""))
        if not pair:
            continue
        existing = latest.get(pair)
        if existing is None:
            latest[pair] = r
            continue
        try:
            new_ts = _utc_from_iso(r["generated_utc"])
            old_ts = _utc_from_iso(existing["generated_utc"])
        except (KeyError, ValueError):
            latest[pair] = r
            continue
        if new_ts >= old_ts:
            latest[pair] = r
    return latest


def _group_by_date(
    results: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for r in results:
        pair = clean_pair_name(r.get("pair", ""))
        if not pair:
            continue
        date_key = r.get("date")
        if not date_key:
            try:
                ts = _utc_from_iso(r["generated_utc"])
                date_key = ts.strftime("%Y-%m-%d")
            except (KeyError, ValueError):
                logger.warning("Cannot determine date for %s", pair)
                continue
        bucket = grouped.setdefault(date_key, {})
        if pair not in bucket:
            bucket[pair] = r
            continue
        try:
            new_ts = _utc_from_iso(r["generated_utc"])
            old_ts = _utc_from_iso(bucket[pair]["generated_utc"])
        except (KeyError, ValueError):
            continue
        if new_ts >= old_ts:
            bucket[pair] = r
    return grouped


def _ensure_clean_payload(result: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(result)
    if "pair" in cleaned:
        cleaned["pair"] = clean_pair_name(cleaned["pair"])
    if "date" not in cleaned:
        try:
            ts = _utc_from_iso(cleaned["generated_utc"])
            cleaned["date"] = ts.strftime("%Y-%m-%d")
        except (KeyError, ValueError):
            pass
    return cleaned


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def build_all(
    results: list[dict[str, Any]],
) -> None:
    if not results:
        logger.info("No results — nothing to build.")
        return

    latest_by_pair = _group_latest(results)
    dated_results = _group_by_date(results)

    latest_dir = API_DIR / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    all_latest: list[dict[str, Any]] = []
    for clean_pair, result in sorted(latest_by_pair.items()):
        payload = _ensure_clean_payload(result)
        _write_json(latest_dir / f"{clean_pair}.json", payload)
        all_latest.append(payload)
        logger.info("api/latest/%s.json written", clean_pair)

    latest_aggregate = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generated_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "count": len(all_latest),
        "pairs": all_latest,
    }
    _write_json(latest_dir / "all.json", latest_aggregate)
    logger.info("api/latest/all.json written (%d pairs)", len(all_latest))

    for date_key, pairs in sorted(dated_results.items()):
        yyyy, mm, dd = date_key.split("-")
        dated_dir = API_DIR / yyyy / mm / dd
        dated_dir.mkdir(parents=True, exist_ok=True)

        written_today: list[dict[str, Any]] = []
        for clean_pair, result in sorted(pairs.items()):
            payload = _ensure_clean_payload(result)
            outfile = dated_dir / f"{clean_pair}.json"
            if outfile.exists():
                logger.debug(
                    "api/%s/%s/%s/%s.json already exists — skipped",
                    yyyy, mm, dd, clean_pair,
                )
                written_today.append(payload)
                continue
            _write_json(outfile, payload)
            logger.info("api/%s/%s/%s/%s.json written", yyyy, mm, dd, clean_pair)
            written_today.append(payload)

        dated_aggregate = {
            "date": date_key,
            "generated_utc": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "count": len(written_today),
            "pairs": written_today,
        }
        all_path = dated_dir / "all.json"
        if not all_path.exists():
            _write_json(all_path, dated_aggregate)
            logger.info(
                "api/%s/%s/%s/all.json written (%d pairs)",
                yyyy, mm, dd, len(written_today),
            )
        else:
            logger.debug(
                "api/%s/%s/%s/all.json already exists — skipped", yyyy, mm, dd,
            )


def _scan_archive_dirs(api_dir: Path) -> list[str]:
    """Return sorted list of YYYY/MM/DD strings found under api/YYYY/MM/DD/."""
    archive: list[str] = []
    if not api_dir.is_dir():
        return archive
    for yyyy_dir in sorted(api_dir.iterdir()):
        if not yyyy_dir.is_dir() or not yyyy_dir.name.isdigit() or len(yyyy_dir.name) != 4:
            continue
        for mm_dir in sorted(yyyy_dir.iterdir()):
            if not mm_dir.is_dir() or not mm_dir.name.isdigit() or len(mm_dir.name) != 2:
                continue
            for dd_dir in sorted(mm_dir.iterdir()):
                if not dd_dir.is_dir() or not dd_dir.name.isdigit() or len(dd_dir.name) != 2:
                    continue
                archive.append(f"{yyyy_dir.name}/{mm_dir.name}/{dd_dir.name}")
    return sorted(archive, reverse=True)


def generate_index(api_dir: Path) -> None:
    latest_dir = api_dir / "latest"

    pair_files = sorted(
        [f for f in latest_dir.glob("*.json") if f.name != "all.json"]
    ) if latest_dir.is_dir() else []

    archive_paths = _scan_archive_dirs(api_dir)

    html_pairs_rows: list[str] = []
    for file in pair_files:
        pair = file.stem
        html_pairs_rows.append(
            f"""
<tr>
  <td>{pair}</td>
  <td><a href="api/latest/{pair}.json">api/latest/{pair}.json</a></td>
  <td><a href="api/latest/{pair}.json" download>Download</a></td>
</tr>"""
        )

    html_archive_items: list[str] = []
    for ymd in archive_paths:
        iso = ymd.replace("/", "-")
        html_archive_items.append(
            f'  <li><a href="api/{ymd}/all.json">{iso} — api/{ymd}/all.json</a></li>'
        )

    if not html_archive_items:
        html_archive_items.append('  <li><em>No archives yet — daily run will populate this.</em></li>')

    pairs_section = "\n".join(html_pairs_rows) if html_pairs_rows else (
        '<tr><td colspan="3"><em>No pair data yet.</em></td></tr>'
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FX Monte Carlo API</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif;
      max-width: 960px;
      margin: 40px auto;
      padding: 0 20px;
      color: #222;
      line-height: 1.5;
    }}
    h1 {{ margin-bottom: 4px; }}
    h2 {{ margin-top: 36px; border-bottom: 1px solid #eee; padding-bottom: 6px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #ddd; padding: 10px 12px; text-align: left; }}
    th {{ background: #f5f5f5; }}
    tr:hover {{ background: #fafafa; }}
    a {{ color: #0366d6; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    ul {{ padding-left: 20px; }}
    li {{ margin: 4px 0; }}
    code {{
      background: #f4f4f4;
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 0.9em;
    }}
  </style>
</head>
<body>

<h1>FX Monte Carlo API</h1>
<p>Automated daily Monte Carlo forecasts. Runs every day at <strong>00:00 UTC</strong> via GitHub Actions and published via GitHub Pages.</p>

<h2>Latest Snapshot</h2>
<ul>
  <li><a href="api/latest/all.json"><code>api/latest/all.json</code></a> — all pairs, newest run</li>
</ul>

<h2>Available Pairs</h2>
<table>
<tr>
  <th>Pair</th>
  <th>Endpoint</th>
  <th>Download</th>
</tr>
{pairs_section}
</table>

<h2>Daily Archive</h2>
<p>First snapshot of each day — never overwritten.</p>
<ul>
{chr(10).join(html_archive_items)}
</ul>

<p style="margin-top: 40px; color: #888; font-size: 0.9em;">
  See <a href="API.md">API.md</a> for documentation and usage examples.
</p>

</body>
</html>
"""

    outfile = BASE_DIR / "index.html"
    outfile.write_text(html, encoding="utf-8")
    logger.info(
        "Generated index.html (%d pairs, %d archive days)",
        len(pair_files),
        len(archive_paths),
    )


def main() -> None:
    logger.info("build_api starting")
    results = load_results()
    build_all(results)
    generate_index(API_DIR)
    logger.info("build_api complete")


if __name__ == "__main__":
    main()