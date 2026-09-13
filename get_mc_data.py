#!/usr/bin/env python3
"""FX Monte Carlo CLI Client (Daily & Weekly).

Fetches published forecasts from the remote GitHub API (default), or reads
the local unified ``mc_results/`` directory with ``--local`` — daily/weekly
files there already encode the timeframe in their names.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

DEFAULT_BASE_URL = "https://raw.githubusercontent.com/liqinsg/fx_monte_carlo/main/api"
LOCAL_RESULTS_DIR = Path(__file__).resolve().parent / "mc_results"


def fetch_json(url: str, debug: bool = False):
    if debug:
        print(f"[DEBUG] Fetching: {url}", file=sys.stderr)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "FX-MonteCarlo-Client/1.0", "Cache-Control": "no-cache"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} Error for URL: {url}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Network/JSON Error: {e}", file=sys.stderr)
        sys.exit(1)


def _iso_week_to_date(s: str) -> str | None:
    m = re.fullmatch(r"(\d{4})-W(\d{2})", s)
    if not m:
        return None
    year, week = int(m.group(1)), int(m.group(2))
    try:
        d = date.fromisocalendar(year, week, 1)
        return d.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _utc_from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _clean_pair(label: str) -> str:
    return label.replace("=X", "").replace("=", "_")


# ==========================================
# 🗂️ LOCAL mc_results/ READING (--local)
# ==========================================

def _local_files(tf: str) -> list[tuple[Path, str]]:
    """Return ``(path, YYYY-MM-DD)`` for ``mc_{tf}_all_pairs_*.json``, newest first."""
    entries: list[tuple[Path, str]] = []
    if not LOCAL_RESULTS_DIR.is_dir():
        return entries
    pattern = re.compile(rf"^mc_{tf}_all_pairs_(\d{{8}})_(\d{{4}})\.json$")
    for path in LOCAL_RESULTS_DIR.glob(f"mc_{tf}_all_pairs_*.json"):
        m = pattern.match(path.name)
        if m:
            yyyymmdd = m.group(1)
            entries.append((path, f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"))
    entries.sort(key=lambda e: e[0].name, reverse=True)
    return entries


def _local_available_dates(tf: str) -> list[str]:
    seen: set[str] = set()
    dates: list[str] = []
    for _, fdate in _local_files(tf):
        if fdate not in seen:
            seen.add(fdate)
            dates.append(fdate)
    return dates


def _local_load(tf: str, date_key: str | None):
    """Newest ``mc_{tf}_`` file (optionally for ``date_key``) -> (path, fdate, raw, pairs)."""
    selected = None
    for path, fdate in _local_files(tf):
        if date_key is not None and fdate != date_key:
            continue
        selected = (path, fdate)
        break
    if selected is None:
        return None

    path, fdate = selected
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"❌ Failed to parse {path}: {exc}", file=sys.stderr)
        sys.exit(1)

    results = raw.get("results")
    if not isinstance(results, dict):
        print(f"❌ Unexpected format: {path} has no 'results' map", file=sys.stderr)
        sys.exit(1)

    pairs = []
    for pair_key in sorted(results):
        pair_data = results[pair_key]
        if not isinstance(pair_data, dict):
            continue
        cleaned = dict(pair_data)
        cleaned["pair"] = _clean_pair(cleaned.get("pair", str(pair_key)))
        if "date" not in cleaned:
            try:
                ts = _utc_from_iso(cleaned["generated_utc"])
                cleaned["date"] = ts.strftime("%Y-%m-%d")
            except (KeyError, ValueError):
                pass
        pairs.append(cleaned)
    return path, fdate, raw, pairs


def _run_local(args, parser) -> None:
    if args.dates:
        dates = _local_available_dates("D")
        print(
            json.dumps({"available_dates": dates, "total": len(dates)}, indent=2, ensure_ascii=False)
        )
        return

    if args.weeks:
        dates = _local_available_dates("W")
        print(
            json.dumps({"available_dates": dates, "total": len(dates)}, indent=2, ensure_ascii=False)
        )
        return

    if not args.date and not args.week:
        parser.error("one of --date, --week, --dates, or --weeks is required")

    tf = "D" if args.date else "W"
    label = "Daily" if tf == "D" else "Weekly"
    snapshot_arg = args.date if args.date else args.week
    date_key = None if snapshot_arg == "latest" else (_iso_week_to_date(snapshot_arg) or snapshot_arg)

    loaded = _local_load(tf, date_key)
    if loaded is None:
        if date_key:
            print(
                f"❌ No mc_{tf}_ all-pairs file found for date {date_key} in {LOCAL_RESULTS_DIR}",
                file=sys.stderr,
            )
        else:
            print(f"❌ No mc_{tf}_ all-pairs file found in {LOCAL_RESULTS_DIR}", file=sys.stderr)
        sys.exit(1)

    path, fdate, raw, pairs = loaded

    if args.pair:
        want = args.pair.upper()
        for p in pairs:
            if p["pair"].upper() == want:
                print(json.dumps(p, indent=2, ensure_ascii=False))
                return
        print(f"❌ Pair {want} not found in {path.name} ({label} snapshot {fdate})", file=sys.stderr)
        sys.exit(1)

    aggregate = {
        "date": fdate,
        "generated_utc": raw.get("metadata", {}).get(
            "generated_utc",
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
        "count": len(pairs),
        "pairs": pairs,
    }
    print(json.dumps(aggregate, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="FX Monte Carlo Data Client (Daily & Weekly)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python get_mc_data.py --dates                      # List all available daily dates
  python get_mc_data.py --weeks                      # List all available weekly dates
  python get_mc_data.py --date latest                # Get latest daily snapshot (all pairs)
  python get_mc_data.py --date 2026-09-09            # Get daily snapshot for a specific day
  python get_mc_data.py --week latest                # Get latest weekly snapshot (all pairs)
  python get_mc_data.py --week 2026-09-10            # Get weekly snapshot for that date
  python get_mc_data.py --local --dates              # Local: list daily snapshots in mc_results/
  python get_mc_data.py --local --week latest        # Local: latest weekly from mc_results/
        """,
    )

    parser.add_argument("--pair", type=str, help="Currency pair (e.g. EURUSD)")
    parser.add_argument("--date", type=str, help="Daily: YYYY-MM-DD or latest")
    parser.add_argument(
        "--week", type=str, help="Weekly: YYYY-MM-DD, YYYY-Www, or latest"
    )
    parser.add_argument(
        "--dates", action="store_true", help="List available daily dates"
    )
    parser.add_argument(
        "--weeks", action="store_true", help="List available weekly dates"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Read from the local mc_results/ directory instead of the remote API",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print request URL to stderr"
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.local:
        _run_local(args, parser)
        return

    if args.dates:
        data = fetch_json(f"{DEFAULT_BASE_URL}/dates.json", debug=args.debug)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if args.weeks:
        data = fetch_json(f"{DEFAULT_BASE_URL}/weekly_dates.json", debug=args.debug)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not args.date and not args.week:
        parser.error("one of --date, --week, --dates, or --weeks is required")

    if args.date and args.week:
        parser.error("--date and --week are mutually exclusive")

    if args.date:
        path_prefix = ""
        path_dir = args.date.replace("-", "/") if args.date != "latest" else "latest"
    else:
        path_prefix = "weekly/"
        if args.week == "latest":
            path_dir = "latest"
        else:
            resolved = _iso_week_to_date(args.week)
            if resolved:
                path_dir = resolved.replace("-", "/")
            else:
                path_dir = args.week.replace("-", "/")

    filename = f"{args.pair.upper()}.json" if args.pair else "all.json"
    target_url = f"{DEFAULT_BASE_URL}/{path_prefix}{path_dir}/{filename}"

    data = fetch_json(target_url, debug=args.debug)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
