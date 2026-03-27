# Robot Smoke Checklist

Use this checklist after deploying a new `robot_api` revision or changing service env settings.

## Preconditions
- `robot-api` service installed and running.
- Managed runtime service configured (default `robot-runtime.service`).
- `robot_api` token available if auth is enabled.

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
curl -s -H "Authorization: Bearer <TOKEN>" "http://127.0.0.1:8200/api/v1/robot/logs?lines=100" | python3 -m json.tool
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

## Rollback Trigger Conditions
Rollback immediately if any of these occur:
- runtime service can no longer be started by API
- update jobs consistently fail at same step after config verification
- auth behavior is broken (unexpected open access or rejects valid token)
