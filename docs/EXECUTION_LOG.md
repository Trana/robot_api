# Execution Log

## 2026-04-17 - Enforce Runtime IMU Override Application
- Updated runtime start path so `POST /api/v1/robot/start` with `use_imu` always executes `systemctl restart` (not `start`) after setting one-shot manager env.
- Added preflight validation that the managed unit includes `PassEnvironment=ROBOT_RUNTIME_USE_IMU`; API now fails with a clear error instead of silently ignoring override.
- Added service tests for:
  - restart behavior with `use_imu` override
  - explicit failure when `PassEnvironment` is missing.

Validation commands:
- `cd /home/trana/Development/robot_api && ./.venv/bin/pytest -q`

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

## 2026-09-18 - TKT-002 Control-plane Lifecycle Guard (staged)

- Added opt-in `ROBOT_API_RUNTIME_CONTROL_ENABLED=false` to reject legacy
  start/stop/restart and update-with-restart before any commands/job creation.
  API rejection follows authentication and returns 410 with a stable code;
  service methods also guard direct calls. Reads and build-only updates remain.
- Default stays enabled until explicit robot cutover. No logging transport or
  CAN-reset semantics changed; existing dirty logging fixes preserved.
- Validation: 31 Python tests passed, including six new cutover cases.
- Deployment flag not yet installed on the robot; runtime rollout remains gated.

## 2026-09-18 - TKT-002 Canonical Source Promotion

- Backed up the robot checkout to
  `/home/mikael/Development/runtime-backup-jFtJgB/robot_api`, promoted reviewed
  source and restarted the existing API after canonical ROS workspace rebuild.
- Robot API: 31 tests passed in the canonical checkout; health is good with no
  active update job. No physical runtime start or motor activation performed.
- Explicit retirement flag is still pending operator installation. The ROS
  repo's `scripts/install-runtime-services` installs a separate environment-file
  drop-in, preserving credentials, alongside mock-default runtime management.
  Until installed, legacy lifecycle writes remain enabled. Live authenticated
  rejection and mock transport/recovery checks are the next validation gates.

## 2026-09-18 - TKT-002 Installed Guard Verified

- Operator installed the separate retirement environment/drop-in and restarted
  the API. Live legacy stop/start/restart and update-with-restart return 410
  `ROBOT_RUNTIME_CONTROL_RETIRED`; status/logs return 200; update job remains null.
  Stop rejection was verified first; no physical runtime startup occurred.
- Deployment has no HTTP bearer token configured. Live rejection checks were
  therefore unauthenticated; auth ordering remains unit-test evidence only.
  No credentials changed. Review access before physical runtime cutover.
- Robot manager remains mock; remote start/stop and actual management-restart
  deduplication passed. Physical runtime is inactive/static, PID/start timestamp 0.

## 2026-09-19 - TKT-003 default-retire legacy CAN reset (source only)

- Legacy reset authenticates then returns 410 ROBOT_CAN_RESET_RETIRED by default;
  direct RobotService reset is guarded too. ROBOT_API_CAN_RESET_ENABLED=true is an
  explicit rollback option, never concurrent with new control-plane maintenance.
- Updated rollback and default-denial tests. All 32 tests and fatal-error Python
  lint checks passed. Broad Ruff still reports pre-existing style findings; no
  unrelated cleanup was applied. Runbook and wiki record deployment prerequisites.
- No remote service/config change or hardware reset. Deploy/restart and verify
  live retirement before enabling the new path; remove old reset permissions then.

## 2026-09-19 - TKT-004 remove deployment Update Jobs (source only)

- Removed git fetch/checkout/pull/build/optional-restart worker, JobStore,
  /api/v1/ops/update and job list/detail routes, job models and deployment config.
  Removed health repo/branch/active-job fields; workspace disk metrics retained.
- Preserved runtime/CAN retirement gates, authenticated reads and log snapshots.
  Removed endpoints return 404 even with legacy lifecycle enabled; tests verify
  no commands and no update/job schemas in OpenAPI. Old env keys are ignored.
- Updated repo boundary, README/requirements/architecture/runbook/smoke checklist,
  deployment env example and wiki. Installation scripts remain; the ROS runtime
  installer's optional active-job health check stays compatible with older APIs.
- Validation: 29 Python tests and fatal-error Ruff checks pass; companion Training
  UI: 71 unit tests, build, Rust OpenAPI contract check and 41 mocked browser
  regressions pass, including desktop/mobile screenshots.
- No robot access, deployment, restart, hardware command or user data deletion.
  Removed JobStore source is recoverable from Git. Older running API installations
  still expose the old update routes until explicitly upgraded/restarted.
