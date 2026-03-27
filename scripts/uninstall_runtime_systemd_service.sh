#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_UNIT_PATH="/etc/systemd/system/robot-runtime.service"

if systemctl list-unit-files | grep -q '^robot-runtime.service'; then
  systemctl disable --now robot-runtime || true
fi

rm -f "${SYSTEMD_UNIT_PATH}"
systemctl daemon-reload

echo "Removed ${SYSTEMD_UNIT_PATH}"
echo "Environment file kept: /etc/default/robot-api"
