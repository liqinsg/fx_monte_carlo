#!/usr/bin/env bash
set -euo pipefail

TODAY="$(date +%F)"
DATES_JSON="$(python get_mc_data.py --dates)"

if jq -e --arg today "$TODAY" \
  '.available_dates | index($today) != null' \
  <<<"$DATES_JSON" >/dev/null; then
  echo "MC data for $TODAY already exists; nothing to run."
else
  echo "MC data for $TODAY is missing; dispatching weekly MC workflow."
  gh workflow run mc_weekly.yml --ref main
fi
