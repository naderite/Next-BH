#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo 'Usage: bash scripts/check_dashboard_review.sh PATH_TO_DEMO_PYTHON' >&2
  exit 2
fi

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
review_work=$(mktemp -d)
bash "$repo_root/scripts/run_dashboard_review_pilot.sh" "$1" > "$review_work/runner.log" 2>&1 &
review_runner=$!

cleanup() {
  kill "$review_runner" 2>/dev/null || true
  wait "$review_runner" || true
  rm -rf -- "$review_work"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for attempt in $(seq 1 120); do
  if ! kill -0 "$review_runner" 2>/dev/null; then break; fi
  awk '/^\{"url"/ { print; exit }' "$review_work/runner.log" > "$review_work/session.json"
  if [[ -s "$review_work/session.json" ]]; then
    node "$repo_root/scripts/check_dashboard_review.cjs" "$review_work/session.json"
    exit
  fi
  sleep 1
done

awk '!/^\{"url"/' "$review_work/runner.log" >&2
echo 'The dashboard pilot did not start.' >&2
exit 1
