#!/usr/bin/env bash
set -euo pipefail

RUN_WEEKLY="${RUN_WEEKLY:-1}"
RUN_DAILY="${RUN_DAILY:-0}"
DRY_RUN="${DRY_RUN:-0}"
USE_LOCAL="${USE_LOCAL:-0}"
TODAY="$(date -u +%F)"
WEEKDAY="$(date -u -d "$TODAY" +%u)"

maybe_dispatch() {
  local label="$1"
  local list_flag="$2"
  local date_key="$3"
  local workflow="$4"
  local match_spec="${5:-exact}"
  local dates_json running_runs match_date range_start range_end
  local -a source_args=()

  if [[ "$USE_LOCAL" == "1" ]]; then
    source_args+=(--local)
  fi
  if ! dates_json="$(python get_mc_data.py ${source_args[@]+"${source_args[@]}"} "$list_flag")"; then
    echo "[$label] cannot read data index; aborting." >&2
    exit 1
  fi
  case "$match_spec" in
    exact)
      match_date="$(jq -r --arg date "$date_key" \
        'first(.available_dates[] | select(. == $date)) // empty' \
        <<<"$dates_json")"
      ;;
    range:*)
      IFS=: read -r range_start range_end <<<"${match_spec#range:}"
      if [[ -z "$range_start" || -z "$range_end" ]]; then
        echo "[$label] invalid date match range: $match_spec" >&2
        return 2
      fi
      match_date="$(jq -r --arg start "$range_start" --arg end "$range_end" \
        'first(.available_dates[] | select(. >= $start and . <= $end)) // empty' \
        <<<"$dates_json")"
      ;;
    *)
      echo "[$label] invalid date match mode: $match_spec" >&2
      return 2
      ;;
  esac

  if [[ -n "$match_date" ]]; then
    if [[ "$match_spec" == range:* ]]; then
      echo "[$label] data for $match_date exists in UTC window $range_start..$range_end; skipping."
    else
      echo "[$label] data for $match_date already exists; skipping."
    fi
    return
  fi

  if ! running_runs="$(gh run list --workflow="$workflow" --limit 10 --json status \
    -q '[.[] | select(.status=="in_progress" or .status=="queued")] | length')"; then
    echo "[$label] cannot check running workflows; skipping."
    return
  fi
  if [[ "$running_runs" != "0" ]]; then
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
  week_sunday="$(date -u -d "$week_monday +6 days" +%F)"
  maybe_dispatch weekly --weeks "$week_monday" mc_weekly.yml "range:$week_monday:$week_sunday"
fi
