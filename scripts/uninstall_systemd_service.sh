#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_UNIT_PATH="/etc/systemd/system/robot-api.service"
ENV_FILE_PATH="/etc/default/robot-api"

if systemctl list-unit-files | grep -q '^robot-api.service'; then
  systemctl disable --now robot-api || true
fi

rm -f "${SYSTEMD_UNIT_PATH}"
systemctl daemon-reload

echo "Removed ${SYSTEMD_UNIT_PATH}"
echo "Environment file kept: ${ENV_FILE_PATH}"
