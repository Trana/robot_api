#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${ROBOT_API_APP_DIR:-/opt/robot_api}"
VENV_DIR="${ROBOT_API_VENV:-${APP_DIR}/.venv}"
BIND_HOST="${ROBOT_API_BIND_HOST:-0.0.0.0}"
BIND_PORT="${ROBOT_API_BIND_PORT:-8200}"
WORKERS="${ROBOT_API_WORKERS:-1}"

if [[ "${WORKERS}" != "1" ]]; then
  echo "ROBOT_API_WORKERS=${WORKERS} requested; forcing workers=1 for operational safety" >&2
  WORKERS="1"
fi

if [[ ! -x "${VENV_DIR}/bin/uvicorn" ]]; then
  echo "uvicorn not found at ${VENV_DIR}/bin/uvicorn" >&2
  exit 1
fi

cd "${APP_DIR}"
exec "${VENV_DIR}/bin/uvicorn" robot_api.main:app \
  --host "${BIND_HOST}" \
  --port "${BIND_PORT}" \
  --workers "${WORKERS}"
