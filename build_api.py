"""Build public API from mc_daily_results and weekly_results JSON files."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "mc_daily_results"
WEEKLY_RESULTS_DIR = BASE_DIR / "mc_weekly_results"
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


def _load_results(results_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not results_dir.is_dir():
        logger.warning("%s/ not found — nothing to build.", results_dir.name)
        return results

    for path in sorted(results_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            results.append(data)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to parse %s: %s", path.name, exc)
    logger.info("Loaded %d files from %s/", len(results), results_dir.name)
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


def _build_timeframe(
    results: list[dict[str, Any]],
    api_subdir: Path,
    label: str,
) -> None:
    if not results:
        logger.info("No %s results — nothing to build.", label)
        return

    latest_by_pair = _group_latest(results)
    dated_results = _group_by_date(results)

    latest_dir = api_subdir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    all_latest: list[dict[str, Any]] = []
    for clean_pair, result in sorted(latest_by_pair.items()):
        payload = _ensure_clean_payload(result)
        _write_json(latest_dir / f"{clean_pair}.json", payload)
        all_latest.append(payload)
        logger.info("%s/latest/%s.json written", label, clean_pair)

    latest_aggregate = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generated_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "count": len(all_latest),
        "pairs": all_latest,
    }
    _write_json(latest_dir / "all.json", latest_aggregate)
    logger.info("%s/latest/all.json written (%d pairs)", label, len(all_latest))

    for date_key, pairs in sorted(dated_results.items()):
        yyyy, mm, dd = date_key.split("-")
        dated_dir = api_subdir / yyyy / mm / dd
        dated_dir.mkdir(parents=True, exist_ok=True)

        written_today: list[dict[str, Any]] = []
        for clean_pair, result in sorted(pairs.items()):
            payload = _ensure_clean_payload(result)
            outfile = dated_dir / f"{clean_pair}.json"
            if outfile.exists():
                written_today.append(payload)
                continue
            _write_json(outfile, payload)
            logger.info("%s/%s/%s/%s/%s.json written", label, yyyy, mm, dd, clean_pair)
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


def _scan_archive_dirs(api_dir: Path) -> list[tuple[str, str, str]]:
    archive: list[tuple[str, str, str]] = []
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
                archive.append((yyyy_dir.name, mm_dir.name, dd_dir.name))
    return sorted(archive, reverse=True)


def generate_date_index(api_dir: Path = API_DIR) -> None:
    api_path = Path(api_dir)
    dates = _scan_archive_dirs(api_path)
    iso_dates = sorted([f"{y}-{m}-{d}" for y, m, d in dates], reverse=True)
    index_file = api_path / "dates.json"
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump({"available_dates": iso_dates, "total": len(iso_dates)}, f, indent=2)
    logger.info("Updated %s (%d dates)", index_file.name, len(iso_dates))


def generate_weekly_date_index(api_dir: Path = API_DIR) -> None:
    weekly_path = api_dir / "weekly"
    dates = _scan_archive_dirs(weekly_path)
    iso_dates = sorted([f"{y}-{m}-{d}" for y, m, d in dates], reverse=True)
    index_file = api_dir / "weekly_dates.json"
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump({"available_dates": iso_dates, "total": len(iso_dates)}, f, indent=2)
    logger.info("Updated %s (%d weekly dates)", index_file.name, len(iso_dates))


def main() -> None:
    logger.info("build_api starting")

    daily = _load_results(RESULTS_DIR)
    weekly = _load_results(WEEKLY_RESULTS_DIR)

    _build_timeframe(daily, API_DIR, "api")
    _build_timeframe(weekly, API_DIR / "weekly", "api/weekly")

    generate_date_index(API_DIR)
    generate_weekly_date_index(API_DIR)

    logger.info("build_api complete")


if __name__ == "__main__":
    main()