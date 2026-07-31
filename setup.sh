#!/usr/bin/env bash
set -euo pipefail
VENV=".venv"

if [ -d "$VENV" ]; then
    echo "==> $VENV already exists, reusing it"
else
    echo "==> Creating virtual environment in $VENV"
    python3 -m venv "$VENV"
fi

echo "==> Upgrading pip"
"$VENV/bin/pip" install --upgrade pip

echo "==> Installing runtime dependencies"
"$VENV/bin/pip" install -r requirements.txt

if [ -f requirements-dev.txt ]; then
  echo "==> Installing dev dependencies"
  "$VENV/bin/pip" install -r requirements-dev.txt
fi

echo ""
echo "Done. Activating the virtual environment"
source "$VENV/bin/activate"

echo ""
echo "Setting env variables"
: "${GEMINI_API_KEY:?Set GEMINI_API_KEY before running (export GEMINI_API_KEY=...)}"
export JWT_SECRET="${JWT_SECRET:-dev-only-change-me}"

echo ""
echo "Done. Starting the server at http://127.0.0.1:${PORT:-8000}"
exec uvicorn main:app --reload --port "${PORT:-8000}"
