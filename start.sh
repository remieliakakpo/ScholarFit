#!/usr/bin/env bash
# Démarrage local sans Docker : API (port 8000) + site (port 3000).
set -e
cd "$(dirname "$0")"

if [ ! -x backend/.venv/bin/python ]; then
  python3 -m venv backend/.venv
fi
if ! backend/.venv/bin/python -c "import fastapi, uvicorn, sqlalchemy, pydantic_settings, jwt, httpx, bs4" 2>/dev/null; then
  backend/.venv/bin/pip install -q -r backend/requirements-dev.txt
fi
# Crée la base ou la met à jour sans doublons
(cd backend && .venv/bin/python -m app.cli seed)
if [ ! -d frontend/node_modules/next ]; then
  (cd frontend && npm install --no-audit --no-fund)
fi

(cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT
for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:8000/api/health >/dev/null && break
  kill -0 $API_PID 2>/dev/null || { echo "L'API ne démarre pas (voir l'erreur ci-dessus)."; exit 1; }
  sleep 1
done
export API_URL_INTERNAL=http://127.0.0.1:8000
unset NEXT_PUBLIC_API_URL
cd frontend && npm run dev -- -p 3000
