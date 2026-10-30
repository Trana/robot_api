# Runbook: robot_api

## CAN reset cutover (September 19, source only)

CAN reset now defaults to HTTP 410 `ROBOT_CAN_RESET_RETIRED`, after authentication;
the service method is guarded too. Deploy/restart the updated API and verify that
response before enabling control-plane maintenance. The Training UI no longer
calls the legacy reset endpoint. Logs/status are unchanged. Update Jobs are removed; see below.

`ROBOT_API_CAN_RESET_ENABLED=true` is an explicit rollback flag, only while the
new maintenance path is disabled. Never run both reset owners. Remove old generic
`ip link` sudo permissions during supervised cutover after reviewing installed
rules. See robot_control_ros2/docs/CAN_MAINTENANCE.md for the guarded replacement,
writer audit, scoped helper, systemd opt-ins and physical validation checklist.
No robot installation/restart/reset was performed as part of local implementation.

## Local Development
```bash
cd /home/trana/Development/robot_api
python -m venv .venv
source .venv/bin/activate
pip install ".[dev]"
uvicorn robot_api.main:app --host 127.0.0.1 --port 8200 --reload
```

## Production-like Robot Run
```bash
cd /home/trana/Development/robot_api
source .venv/bin/activate
uvicorn robot_api.main:app --host 0.0.0.0 --port 8200 --workers 1
```

## Production Service Install (`systemd`)
Install:
```bash
cd /opt/robot_api
sudo ROBOT_API_APP_DIR=/opt/robot_api \
  ROBOT_API_SERVICE_USER=ubuntu \
  ROBOT_API_SERVICE_GROUP=ubuntu \
  ./scripts/install_systemd_service.sh
```

Install managed runtime service:
```bash
cd /opt/robot_api
sudo ROBOT_API_APP_DIR=/opt/robot_api \
  ROBOT_RUNTIME_SERVICE_USER=ubuntu \
  ROBOT_RUNTIME_SERVICE_GROUP=ubuntu \
  ./scripts/install_runtime_systemd_service.sh
```
Default behavior: runtime unit is installed but not enabled at boot.  
Set `ROBOT_RUNTIME_ENABLE_ON_BOOT=1` when running the install script if boot auto-start is required.

Configure env file:
```bash
sudoedit /etc/default/robot-api
```

Start and verify:
```bash
sudo systemctl restart robot-api
sudo systemctl status robot-api
sudo systemctl start robot-runtime
sudo systemctl status robot-runtime
sudo journalctl -u robot-api -f
```

## Required Environment Variables
- `ROBOT_API_MANAGED_SERVICE=robot-runtime.service`
- `ROBOT_API_CAN_IFACE=can0`
- `ROBOT_API_WORKSPACE_DIR=/opt/robot_ws`
- `ROBOT_API_MAX_LOG_LINES=4000`
- `ROBOT_API_CORS_ALLOWED_ORIGINS=*`
- optional: `ROBOT_API_TOKEN=<strong-token>`
- `ROBOT_RUNTIME_WORKDIR=/opt/robot_ws`
- `ROBOT_RUNTIME_ROS_SETUP=/opt/ros/humble/setup.bash`
- `ROBOT_RUNTIME_WORKSPACE_SETUP=/opt/robot_ws/install/setup.bash`
- `ROBOT_RUNTIME_LAUNCH_COMMAND=ros2 launch robot_bringup bringup.launch.py`

Service/runtime envs used by `scripts/run_uvicorn.sh`:
- `ROBOT_API_APP_DIR=/opt/robot_api`
- `ROBOT_API_VENV=/opt/robot_api/.venv`
- `ROBOT_API_BIND_HOST=0.0.0.0`
- `ROBOT_API_BIND_PORT=8200`
- `ROBOT_API_WORKERS=1`

Runtime launch sequence used by `scripts/run_robot_runtime.sh`:
1. `cd ${ROBOT_RUNTIME_WORKDIR}`
2. `source ${ROBOT_RUNTIME_ROS_SETUP}`
3. `source ${ROBOT_RUNTIME_WORKSPACE_SETUP}`
4. `exec ${ROBOT_RUNTIME_LAUNCH_COMMAND}`

## Robot Smoke Validation
- Run the full checklist in `docs/ROBOT_SMOKE_CHECKLIST.md` after deployment updates.

## Rollback Procedure
1. Deploy previous known-good `robot_api` revision.
2. Restore `/etc/default/robot-api` if changed.
3. Restart service:
```bash
sudo systemctl restart robot-api
sudo systemctl status robot-api
```

## Control-plane lifecycle cutover (staged)

After deploying the matching Robot Control Plane runtime manager, set
`ROBOT_API_RUNTIME_CONTROL_ENABLED=false` in the Robot API service environment
and restart Robot API. Default is `true` for existing deployments; invalid values
fail startup.

With the flag false, authenticated `/api/v1/robot/start`, `/stop`, `/restart`
return HTTP 410, code `ROBOT_RUNTIME_CONTROL_RETIRED`, before any commands execute.
Use the control plane's durable runtime operation API instead. Status and logs
remain available. CAN reset has its own retirement gate described above.
Retain the existing operator safety procedure. Existing root/manual systemctl
access is not restricted by an HTTP gate.

Deploying this source alone does not retire legacy controls. Activate the flag
as part of the coordinated migration and validate with no-side-effect requests
before starting the new physical backend. Runtime-manager mock validation must
not grant permission for hardware activation.

## Update Jobs removal (2026-09-19, source only)

The git pull/build/optional restart API, worker, job list/detail and UI are removed.
All /api/v1/ops/* routes return 404 after deployment. The repo/branch, ROS build
setup, build command, update timeout and max-jobs settings are no longer read.
ROBOT_API_WORKSPACE_DIR remains for disk metrics; ROBOT_RUNTIME_* launch settings
are unchanged. Remove obsolete ROBOT_API_REPO_DIR, ROBOT_API_REPO_BRANCH,
ROBOT_API_ROS_SETUP_PATH, ROBOT_API_BUILD_COMMAND, ROBOT_API_UPDATE_TIMEOUT_S and
ROBOT_API_MAX_JOBS entries during the next explicit deployment.

Before upgrading an older running API, ensure no old update job is still running;
do not interrupt an active build by restarting the API. Deploy/restart through the
operator workflow, then verify OpenAPI has no /api/v1/ops/ routes and logs work.
No robot service was changed by this source cleanup.
