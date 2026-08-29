#!/usr/bin/env bash
# Start a backend on a throwaway database, build the frontend, walk the app in
# a headless browser, then stop the server. The smoke test starts from first
# run, so it needs an empty database every time.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
data="${SMOKE_DATA:-/tmp/hanbat-smoke}"
port="${PORT:-8756}"

rm -rf "$data" && mkdir -p "$data"
( cd "$here/.." && npm --prefix frontend run build >/dev/null )

( cd "$here/../backend" && HANBAT_DATA_DIR="$data" HANBAT_DB="$data/app.sqlite3" \
    python3 -m uvicorn app.main:app --host 127.0.0.1 --port "$port" >"$data/server.log" 2>&1 ) &
server=$!
trap 'kill $server 2>/dev/null || true' EXIT

for _ in $(seq 40); do
  if curl -fsS "http://127.0.0.1:$port/api/health" >/dev/null 2>&1; then break; fi
  sleep 0.5
done

cd "$here" && node ui-smoke.mjs
