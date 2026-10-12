#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$SCRIPT_DIR/trigger_missing_mc.sh"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_DIR"' EXIT

mkdir -p "$TEMP_DIR/bin"
MOCK_BIN="$TEMP_DIR/bin"
MOCK_LOG="$TEMP_DIR/calls.log"

cat >"$MOCK_BIN/date" <<'MOCK_DATE'
#!/usr/bin/env bash
if [[ "$#" -eq 2 && "$1" == "-u" && "$2" == "+%F" ]]; then
  printf '%s\n' "$TEST_DATE"
else
  exec /usr/bin/date "$@"
fi
MOCK_DATE

cat >"$MOCK_BIN/python" <<'MOCK_PYTHON'
#!/usr/bin/env bash
printf 'python' >>"$MOCK_LOG"
printf ' %s' "$@" >>"$MOCK_LOG"
printf '\n' >>"$MOCK_LOG"
if [[ "${MOCK_PYTHON_FAIL:-0}" == "1" ]]; then
  exit 1
fi
for arg in "$@"; do
  case "$arg" in
    --dates) printf '%s\n' "$DATES_JSON"; exit 0 ;;
    --weeks) printf '%s\n' "$WEEKS_JSON"; exit 0 ;;
  esac
done
exit 2
MOCK_PYTHON

cat >"$MOCK_BIN/gh" <<'MOCK_GH'
#!/usr/bin/env bash
if [[ "$1" == "run" && "$2" == "list" ]]; then
  if [[ "${MOCK_GH_FAIL:-0}" == "1" ]]; then
    exit 1
  fi

  query=''
  workflow=''
  previous=''
  for arg in "$@"; do
    if [[ "$previous" == "-q" ]]; then
      query="$arg"
    fi
    case "$arg" in
      --workflow=*) workflow="${arg#--workflow=}" ;;
    esac
    previous="$arg"
  done

  statuses_value="${MOCK_STATUSES:-completed}"
  if [[ "$workflow" == "mc_weekly.yml" && -n "${MOCK_WEEKLY_STATUSES:-}" ]]; then
    statuses_value="$MOCK_WEEKLY_STATUSES"
  fi
  IFS=, read -r -a statuses <<<"$statuses_value"
  status_json="$(printf '%s\n' "${statuses[@]}" | jq -R . | jq -s '[.[] | {status: .}]')"
  jq -r "$query" <<<"$status_json"
elif [[ "$1" == "workflow" && "$2" == "run" ]]; then
  printf 'gh %s\n' "$*" >>"$MOCK_LOG"
  printf 'mocked %s\n' "$*"
else
  printf 'Unexpected gh call: %s\n' "$*" >&2
  exit 2
fi
MOCK_GH

chmod +x "$MOCK_BIN/date" "$MOCK_BIN/python" "$MOCK_BIN/gh"

run_case() {
  local name="$1"
  local expected_output="$2"
  local expected_dispatch="$3"
  local test_date="$4"
  local dates_json="$5"
  local weeks_json="$6"
  local statuses="$7"
  local python_fail="$8"
  local gh_fail="$9"
  local run_daily="${10}"
  local run_weekly="${11}"
  local use_local="${12}"
  local weekly_statuses="${13:-$statuses}"
  local output status

  : >"$MOCK_LOG"
  if output="$(
    env -i \
      PATH="$MOCK_BIN:/usr/bin:/bin" \
      MOCK_LOG="$MOCK_LOG" \
      TEST_DATE="$test_date" \
      DATES_JSON="$dates_json" \
      WEEKS_JSON="$weeks_json" \
      MOCK_STATUSES="$statuses" \
      MOCK_WEEKLY_STATUSES="$weekly_statuses" \
      MOCK_PYTHON_FAIL="$python_fail" \
      MOCK_GH_FAIL="$gh_fail" \
      RUN_DAILY="$run_daily" \
      RUN_WEEKLY="$run_weekly" \
      USE_LOCAL="$use_local" \
      "$SCRIPT" 2>&1
  )"; then
    status=0
  else
    status=$?
  fi

  if [[ "$output" != *"$expected_output"* ]]; then
    printf 'FAIL: %s (missing output: %s)\n' "$name" "$expected_output"
    printf '%s\n' "$output"
    return 1
  fi

  if [[ "$expected_dispatch" == "none" ]]; then
    if grep -Fq 'gh workflow run ' "$MOCK_LOG"; then
      printf 'FAIL: %s (unexpected workflow dispatch)\n' "$name"
      cat "$MOCK_LOG"
      return 1
    fi
  elif ! grep -Fq "gh workflow run $expected_dispatch --ref main" "$MOCK_LOG"; then
    printf 'FAIL: %s (expected dispatch of %s)\n' "$name" "$expected_dispatch"
    cat "$MOCK_LOG"
    return 1
  fi

  if [[ "$name" == "remote index failure aborts without local fallback" ]]; then
    if [[ "$status" -eq 0 ]] || grep -Fq -- '--local' "$MOCK_LOG"; then
      printf 'FAIL: %s (did not fail cleanly without local fallback)\n' "$name"
      cat "$MOCK_LOG"
      return 1
    fi
  elif [[ "$status" -ne 0 ]]; then
    printf 'FAIL: %s (unexpected exit status %s)\n' "$name" "$status"
    printf '%s\n' "$output"
    return 1
  fi

  if [[ "$name" == "default uses remote index" ]] &&
    grep -Fq -- '--local' "$MOCK_LOG"; then
    printf 'FAIL: %s (passed --local by default)\n' "$name"
    cat "$MOCK_LOG"
    return 1
  fi
  if [[ "$name" == "USE_LOCAL selects local index" ]] &&
    ! grep -Fq 'python get_mc_data.py --local --weeks' "$MOCK_LOG"; then
    printf 'FAIL: %s (did not pass --local)\n' "$name"
    cat "$MOCK_LOG"
    return 1
  fi

  printf 'PASS: %s\n' "$name"
}

EMPTY='{"available_dates":[]}'

run_case "weekly non-Monday key matches current week" \
  '[weekly] data for 2026-10-13 exists in UTC window 2026-10-12..2026-10-18; skipping.' \
  none 2026-10-14 "$EMPTY" '{"available_dates":["2026-10-13"]}' completed 0 0 0 1 0
run_case "weekly previous-week key dispatches" \
  '[weekly] data for 2026-10-12 is missing; dispatching mc_weekly.yml.' \
  mc_weekly.yml 2026-10-14 "$EMPTY" '{"available_dates":["2026-10-09"]}' completed 0 0 0 1 0
run_case "Sunday window includes Monday key" \
  '[weekly] data for 2026-10-12 exists in UTC window 2026-10-12..2026-10-18; skipping.' \
  none 2026-10-18 "$EMPTY" '{"available_dates":["2026-10-12"]}' completed 0 0 0 1 0
run_case "daily exact match skips" \
  '[daily] data for 2026-10-12 already exists; skipping.' \
  none 2026-10-12 '{"available_dates":["2026-10-12"]}' "$EMPTY" completed 0 0 1 0 0
run_case "queued run skips dispatch" \
  '[daily] mc_daily.yml already has a queued or in-progress run; skipping.' \
  none 2026-10-12 "$EMPTY" "$EMPTY" queued 0 0 1 0 0
run_case "in-progress run skips dispatch" \
  '[daily] mc_daily.yml already has a queued or in-progress run; skipping.' \
  none 2026-10-12 "$EMPTY" "$EMPTY" in_progress 0 0 1 0 0
run_case "completed run does not block dispatch" \
  '[daily] data for 2026-10-12 is missing; dispatching mc_daily.yml.' \
  mc_daily.yml 2026-10-12 "$EMPTY" "$EMPTY" completed 0 0 1 0 0
run_case "run-list failure skips safely" \
  '[daily] cannot check running workflows; skipping.' \
  none 2026-10-12 "$EMPTY" "$EMPTY" completed 0 1 1 0 0
run_case "default uses remote index" \
  '[weekly] data for 2026-10-12 exists in UTC window 2026-10-12..2026-10-18; skipping.' \
  none 2026-10-12 "$EMPTY" '{"available_dates":["2026-10-12"]}' completed 0 0 0 1 0
run_case "USE_LOCAL selects local index" \
  '[weekly] data for 2026-10-12 exists in UTC window 2026-10-12..2026-10-18; skipping.' \
  none 2026-10-12 "$EMPTY" '{"available_dates":["2026-10-12"]}' completed 0 0 0 1 1
run_case "remote index failure aborts without local fallback" \
  '[weekly] cannot read data index; aborting.' \
  none 2026-10-12 "$EMPTY" "$EMPTY" completed 1 0 0 1 0
run_case "daily weekend skip does not block weekly" \
  '[daily] UTC weekend; skipping.' \
  mc_weekly.yml 2026-10-17 "$EMPTY" "$EMPTY" completed 0 0 1 1 0
run_case "busy daily guard does not block weekly dispatch" \
  '[daily] mc_daily.yml already has a queued or in-progress run; skipping.' \
  mc_weekly.yml 2026-10-12 "$EMPTY" "$EMPTY" queued 0 0 1 1 0 completed
