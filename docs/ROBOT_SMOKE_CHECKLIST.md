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

## 3) Legacy Start/Stop/Restart Compatibility

Normal operations use Robot Control Plane. With ROBOT_API_RUNTIME_CONTROL_ENABLED=false,
authenticated requests below must return 410 without touching the runtime. Only
exercise successful legacy actions in an explicitly approved rollback test.

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
- retired profile returns 410 ROBOT_RUNTIME_CONTROL_RETIRED
- explicitly enabled rollback profile returns `status: ok` and matching `action`

## 4) Logs Endpoint
```bash
curl -s -H "Authorization: Bearer <TOKEN>" "http://127.0.0.1:8200/api/v1/robot/logs?lines=100&scope=current_run" | python3 -m json.tool
```
Expected:
- `lines` contains recent journal entries for managed service

## 5) Deployment API Removal

After deploying this revision, confirm `/openapi.json` lists no `/api/v1/ops/`
routes and GET `/api/v1/ops/jobs` returns 404. Do not send an update POST to an
unverified older installation: it may still start a real git/build operation.

## 6) UI Validation (Training UI Robot Tab)
- Open Training UI and go to `Robot` tab.
- Set Robot API URL and token.
- Verify runtime status and logs render.
- Verify Control Plane status and, only with physical safety approval, a runtime operation.
- Confirm Update Jobs and the git pull/build button are absent.

## Rollback Trigger Conditions
Rollback immediately if any of these occur:
- runtime service can no longer be started by API
- auth behavior is broken (unexpected open access or rejects valid token)
