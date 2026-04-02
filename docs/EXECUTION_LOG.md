# Execution Log

## 2026-03-27 - Initial robot_api plan + scaffold
- Created `robot_api` repository scaffold under `/home/trana/Development/robot_api`.
- Added planning docs (`PRD`, `ARCHITECTURE`, `MILESTONES`, `RUNBOOK`).
- Started MVP service implementation for runtime lifecycle and update jobs.
- Added deploy script/template placeholders and tests for API/service/config behavior.
- Added local `.venv` setup and editable install path for reproducible validation.

Validation commands:
- `cd /home/trana/Development/robot_api && pytest`
- `cd /home/trana/Development/robot_api && ./.venv/bin/pytest`

## 2026-03-27 - MVP Runtime + Update API Implemented
- Implemented FastAPI endpoints for:
  - runtime status/logs
  - start/stop/restart actions
  - async update job start/list/detail
- Added env-driven config validation and structured API error mapping.
- Added in-memory job store with step/log tracking and single-active-update guard.
- Added systemd deployment templates/scripts and uvicorn wrapper script.
- Added robot smoke checklist and linked it in runbook/docs index.

Validation commands:
- `cd /home/trana/Development/robot_api && ./.venv/bin/pytest`
  - Passed: `17` tests

## 2026-03-30 - Runtime Start `use_imu` Override
- Added optional start payload model: `POST /api/v1/robot/start` now accepts `{ "use_imu": true|false }`.
- Wired runtime start action to pass optional `use_imu` through service layer.
- Added one-shot systemd manager env handling in `RobotService`:
  - set `ROBOT_RUNTIME_USE_IMU` before `systemctl start`
  - best-effort unset after start attempt
- Updated systemd unit template to forward `ROBOT_RUNTIME_USE_IMU` to runtime service via `PassEnvironment`.
- Added tests for API payload forwarding and service command behavior for set/start/unset flow.

Validation commands:
- `cd /home/trana/Development/robot_api && ./.venv/bin/pytest -q`
  - Passed: `24` tests

## 2026-03-27 - Runtime Launch Service Sourcing ROS + Workspace
- Added runtime service launcher script `scripts/run_robot_runtime.sh`.
- Added `robot-runtime.service` template and install/uninstall scripts.
- Updated default managed service to `robot-runtime.service`.
- Updated ROS setup defaults to Humble path (`/opt/ros/humble/setup.bash`).
- Extended env example and runbook with runtime launch variables and startup sequence.

Validation commands:
- `cd /home/trana/Development/robot_api && ./.venv/bin/pytest`
