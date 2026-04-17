# Robot Smoke Checklist

Use this checklist after deploying a new `robot_api` revision or changing service env settings.

## Preconditions
- `robot-api` service installed and running.
- Managed runtime service configured (default `robot-runtime.service`).
- `robot_api` token available if auth is enabled.

## 0) Code + Runtime Sync Verification (After Pull/Deploy)
```bash
cd /home/mikael/Development/robot_api
git rev-parse HEAD
./.venv/bin/python -c "import robot_api.main; print(robot_api.main.__file__)"
curl -s http://127.0.0.1:8200/openapi.json | jq '.paths["/api/v1/robot/start"].post.requestBody'
```
Expected:
- revision matches intended deployed commit
- import path resolves to `src/robot_api/main.py` (editable install), not stale `.venv/lib/.../site-packages/robot_api/main.py`
- `requestBody` for `POST /api/v1/robot/start` is non-null on versions with `use_imu` start override support

If import path is stale site-packages:
```bash
cd /home/mikael/Development/robot_api
./.venv/bin/pip install -e .
sudo systemctl restart robot-api
```

## 1) API Reachability
```bash
curl -s http://127.0.0.1:8200/api/health | python3 -m json.tool
```
Expected:
- `service` is `robot-api`
- `status` is `ok`
- `managed_service` matches expected runtime unit

## 2) Runtime Status
```bash
curl -s -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8200/api/v1/robot/status | python3 -m json.tool
```
Expected:
- `active_state` and `sub_state` are populated
- `main_pid` is non-negative

## 3) Start/Stop/Restart Commands
Start:
```bash
curl -s -X POST -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8200/api/v1/robot/start | python3 -m json.tool
```
Stop:
```bash
curl -s -X POST -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8200/api/v1/robot/stop | python3 -m json.tool
```
Restart:
```bash
curl -s -X POST -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8200/api/v1/robot/restart | python3 -m json.tool
```
Expected:
- each returns `status: ok`
- `action` matches request

## 4) Logs Endpoint
```bash
curl -s -H "Authorization: Bearer <TOKEN>" "http://127.0.0.1:8200/api/v1/robot/logs?lines=100&scope=current_run" | python3 -m json.tool
```
Expected:
- `lines` contains recent journal entries for managed service

## 5) Update Job (Dry Operational Validation)
Start update job:
```bash
curl -s -X POST -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"restart_service": true}' \
  http://127.0.0.1:8200/api/v1/ops/update | python3 -m json.tool
```
Get `job_id`, then poll:
```bash
curl -s -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8200/api/v1/ops/jobs/<JOB_ID> | python3 -m json.tool
```
Expected:
- terminal state is `succeeded` or clear `failed` with `error_message`
- `logs` shows step-by-step output

## 6) UI Validation (Training UI Robot Tab)
- Open Training UI and go to `Robot` tab.
- Set Robot API URL and token.
- Click `Refresh All`.
- Verify runtime status and logs render.
- Trigger one lifecycle action and verify status updates.
- Trigger update job and verify job progress logs populate.
- Start once with IMU disabled in UI and verify logs show `use_imu=False` in `RobotControllerNode initialized with parameters`.

Direct API cross-check for IMU override:
```bash
curl -s -X POST -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8200/api/v1/robot/stop | python3 -m json.tool
curl -s -X POST -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"use_imu": false}' \
  http://127.0.0.1:8200/api/v1/robot/start | python3 -m json.tool
journalctl -u robot-runtime -n 200 --no-pager | rg "RobotControllerNode initialized|use_imu"
```
Expected:
- start request returns `status: ok`
- runtime logs include `use_imu=False` for that start

## Rollback Trigger Conditions
Rollback immediately if any of these occur:
- runtime service can no longer be started by API
- update jobs consistently fail at same step after config verification
- auth behavior is broken (unexpected open access or rejects valid token)
