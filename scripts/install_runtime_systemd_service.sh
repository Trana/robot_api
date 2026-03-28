#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_PATH="${REPO_DIR}/deploy/systemd/robot-runtime.service.template"
ENV_EXAMPLE_PATH="${REPO_DIR}/deploy/systemd/robot-api.env.example"

APP_DIR="${ROBOT_API_APP_DIR:-/opt/robot_api}"
SERVICE_USER="${ROBOT_RUNTIME_SERVICE_USER:-$(id -un)}"
SERVICE_GROUP="${ROBOT_RUNTIME_SERVICE_GROUP:-$(id -gn)}"
ENABLE_ON_BOOT="${ROBOT_RUNTIME_ENABLE_ON_BOOT:-0}"
SYSTEMD_UNIT_PATH="/etc/systemd/system/robot-runtime.service"
ENV_FILE_PATH="/etc/default/robot-api"

if [[ ! -f "${TEMPLATE_PATH}" ]]; then
  echo "Missing template: ${TEMPLATE_PATH}" >&2
  exit 1
fi

TMP_UNIT="$(mktemp)"
sed \
  -e "s|__ROBOT_API_APP_DIR__|${APP_DIR}|g" \
  -e "s|__ROBOT_RUNTIME_USER__|${SERVICE_USER}|g" \
  -e "s|__ROBOT_RUNTIME_GROUP__|${SERVICE_GROUP}|g" \
  "${TEMPLATE_PATH}" > "${TMP_UNIT}"

echo "Installing systemd unit to ${SYSTEMD_UNIT_PATH}"
install -m 0644 "${TMP_UNIT}" "${SYSTEMD_UNIT_PATH}"
rm -f "${TMP_UNIT}"

if [[ ! -f "${ENV_FILE_PATH}" ]]; then
  echo "Creating ${ENV_FILE_PATH} from example"
  install -m 0644 "${ENV_EXAMPLE_PATH}" "${ENV_FILE_PATH}"
else
  echo "Keeping existing ${ENV_FILE_PATH}"
fi

systemctl daemon-reload

if [[ "${ENABLE_ON_BOOT}" == "1" || "${ENABLE_ON_BOOT}" == "true" || "${ENABLE_ON_BOOT}" == "yes" ]]; then
  systemctl enable robot-runtime
  echo "Enabled robot-runtime.service at boot."
else
  systemctl disable robot-runtime >/dev/null 2>&1 || true
  echo "Left robot-runtime.service disabled at boot (manual/API start only)."
fi

echo "Installed robot-runtime.service"
echo "Next steps:"
echo "  1) Edit ${ENV_FILE_PATH}"
echo "  2) systemctl start robot-runtime (manual/API trigger)"
echo "  3) systemctl status robot-runtime"
