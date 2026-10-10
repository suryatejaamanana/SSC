#!/bin/sh
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
cd "$ROOT/frontend"
HOSTNAME=0.0.0.0 PORT="${PORT:-3000}" node server.js &
WEB_PID=$!
# Exit (so Render restarts us) as soon as either process dies.
while kill -0 $API_PID 2>/dev/null && kill -0 $WEB_PID 2>/dev/null; do sleep 2; done
kill $API_PID $WEB_PID 2>/dev/null
exit 1
