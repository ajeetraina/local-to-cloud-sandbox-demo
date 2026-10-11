#!/usr/bin/env bash
# Simulates what `sbx move` does to the catalog job, without sbx:
# run on the "laptop", hard-kill mid-job, copy the data folder (the
# filesystem snapshot), then resume on the "cloud" copy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export JOB_DELAY=0.01

# `timeout` is standard on Linux (and in the sandbox) but absent on stock
# macOS. Use coreutils' gtimeout if present, otherwise a tiny shell fallback,
# so `bash tests/simulate_move.sh` runs anywhere.
if ! command -v timeout >/dev/null 2>&1; then
  if command -v gtimeout >/dev/null 2>&1; then
    timeout() { gtimeout "$@"; }
  else
    timeout() {
      local sig=TERM
      while [[ "$1" == -* ]]; do
        case "$1" in -s) sig="$2"; shift 2;; *) shift;; esac
      done
      local secs="$1"; shift
      "$@" & local pid=$!
      ( sleep "$secs"; kill -s "$sig" "$pid" 2>/dev/null ) & local killer=$!
      wait "$pid"; local rc=$?
      kill "$killer" 2>/dev/null || true
      return "$rc"
    }
  fi
fi

echo "== laptop: start the job, then hard-kill it after 4 seconds"
JOB_DIR="$WORK/laptop" JOB_SITE=laptop timeout -s KILL 4 python3 "$ROOT/catalog_job.py" run || true
JOB_DIR="$WORK/laptop" python3 "$ROOT/catalog_job.py" status

echo "== move: copy the data folder"
cp -r "$WORK/laptop" "$WORK/cloud"

echo "== cloud: resume"
JOB_DIR="$WORK/cloud" JOB_SITE=cloud python3 "$ROOT/catalog_job.py" run
JOB_DIR="$WORK/cloud" python3 "$ROOT/catalog_job.py" report

python3 - "$WORK/cloud/report.json" <<'EOF'
import json, sys
r = json.load(open(sys.argv[1]))
sites = r["processed_on"]
assert r["products_done"] == 500, r
assert sum(sites.values()) == 500, sites
assert sites.get("laptop", 0) > 0 and sites.get("cloud", 0) > 0, sites
assert len(r["duplicate_upcs"]) == 10, r["duplicate_upcs"]
print("PASS: job resumed after the move,", sites)
EOF
