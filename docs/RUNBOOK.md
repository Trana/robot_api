# Runbook: robot_api

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
- `ROBOT_API_REPO_DIR=/opt/robot_ws/src/robot_stack`
- `ROBOT_API_REPO_BRANCH=main`
- `ROBOT_API_ROS_SETUP_PATH=/opt/ros/humble/setup.bash`
- `ROBOT_API_BUILD_COMMAND=colcon build --symlink-install`
- `ROBOT_API_UPDATE_TIMEOUT_S=1800`
- `ROBOT_API_MAX_LOG_LINES=4000`
- `ROBOT_API_MAX_JOBS=50`
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
