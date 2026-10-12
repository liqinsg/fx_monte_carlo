#!/usr/bin/env bash
set -euo pipefail

RUN_WEEKLY="${RUN_WEEKLY:-1}"
RUN_DAILY="${RUN_DAILY:-0}"
DRY_RUN="${DRY_RUN:-0}"
TODAY="$(date -u +%F)"
WEEKDAY="$(date -u -d "$TODAY" +%u)"

maybe_dispatch() {
  local label="$1"
  local list_flag="$2"
  local date_key="$3"
  local workflow="$4"
  local dates_json running_runs

  dates_json="$(python get_mc_data.py "$list_flag")"
  if jq -e --arg date "$date_key" \
    '.available_dates | index($date) != null' \
    <<<"$dates_json" >/dev/null; then
    echo "[$label] data for $date_key already exists; skipping."
    return
  fi

  running_runs="$(gh run list --workflow="$workflow" \
    --status in_progress --status queued --json databaseId -q '.[].databaseId')"
  if [[ -n "$running_runs" ]]; then
    echo "[$label] $workflow already has a queued or in-progress run; skipping."
    return
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[$label] data for $date_key is missing; dry run: gh workflow run $workflow --ref main"
  else
    echo "[$label] data for $date_key is missing; dispatching $workflow."
    gh workflow run "$workflow" --ref main
  fi
}

if [[ "$RUN_DAILY" == "1" ]]; then
  if (( WEEKDAY >= 6 )); then
    echo "[daily] UTC weekend; skipping."
  else
    maybe_dispatch daily --dates "$TODAY" mc_daily.yml
  fi
fi

if [[ "$RUN_WEEKLY" == "1" ]]; then
  week_monday="$(date -u -d "$TODAY -$((WEEKDAY - 1)) days" +%F)"
  maybe_dispatch weekly --weeks "$week_monday" mc_weekly.yml
fi
