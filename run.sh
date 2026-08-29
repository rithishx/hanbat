#!/usr/bin/env bash
# Start Hanbat: one process, one port, loopback only.
#
# Builds the frontend if it has not been built, then runs the backend, which
# serves the built files itself. For frontend development run `npm run dev`
# in frontend/ instead and leave this server running alongside it.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
port="${HANBAT_PORT:-8756}"

if [ ! -d "$here/frontend/dist" ]; then
  echo "Building the frontend (first run only)…"
  ( cd "$here/frontend" && npm install --silent && npm run build )
fi

cd "$here/backend"
python3 -m pip install -q -r requirements.txt 2>/dev/null || true
echo "Hanbat is at http://127.0.0.1:$port"
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port "$port"
