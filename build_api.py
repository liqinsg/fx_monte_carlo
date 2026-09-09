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
    """Return {date_iso: {clean_pair_name: result_dict}}."""
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


def main() -> None:
    logger.info("build_api starting")
    results = load_results()
    build_all(results)
    logger.info("build_api complete")


if __name__ == "__main__":
    main()