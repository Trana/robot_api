# robot_api

Legacy FastAPI backend for robot status/log reads and gated runtime/CAN compatibility controls.

## Purpose
- expose HTTP endpoints to start/stop/restart the real robot runtime
- expose status/log views for operational debugging

## Project Workflow Docs
Canonical planning/execution docs:
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/MILESTONES.md`
- `docs/tickets/`
- `docs/EXECUTION_LOG.md`
- `docs/RUNBOOK.md`

## Stack
- Python 3.10+
- FastAPI
- Uvicorn

## Quick Start
```bash
cd /home/trana/Development/robot_api
python -m venv .venv
source .venv/bin/activate
pip install ".[dev]"
uvicorn robot_api.main:app --host 127.0.0.1 --port 8200 --reload
```

## OpenAPI + Swagger
- OpenAPI JSON: `http://127.0.0.1:8200/openapi.json`
- Swagger UI: `http://127.0.0.1:8200/docs`

## API (MVP)
- `GET /api/health`
- `GET /api/v1/robot/status`
- `GET /api/v1/robot/logs?lines=200&scope=current_run`
- `POST /api/v1/robot/start`
- `POST /api/v1/robot/stop`
- `POST /api/v1/robot/restart`
- `POST /api/v1/robot/can/reset`

Update Jobs (git pull/build/optional restart) and all `/api/v1/ops/*` routes
were removed on 2026-09-19. They return 404 and are absent from OpenAPI.
Deploy code explicitly through the operator's SSH/build workflow; there is no
replacement deployment endpoint in Robot Control Plane. Existing robot installs
retain the old feature until this revision is deployed and Robot API restarted.

## Notes
- For real robot runtime, use a single worker process (`--workers 1`).
- Use Robot Control Plane for normal runtime/CAN operations. Legacy runtime writes return 410 with `ROBOT_API_RUNTIME_CONTROL_ENABLED=false`; CAN reset defaults to 410 unless explicitly enabled for rollback.
- Legacy runtime start/stop/restart is managed through `systemctl` on `ROBOT_API_MANAGED_SERVICE` (default `robot-runtime.service`).
- Runtime logs endpoint supports `scope=current_run|history`; default is `current_run` to focus on the latest runtime session.
- `robot-runtime.service` launches via `scripts/run_robot_runtime.sh`, which sources:
  - `ROBOT_RUNTIME_ROS_SETUP` (default `/opt/ros/humble/setup.bash`)
  - `ROBOT_RUNTIME_WORKSPACE_SETUP` (default `/opt/robot_ws/install/setup.bash`)
  then executes `ROBOT_RUNTIME_LAUNCH_COMMAND`.
- `scripts/install_runtime_systemd_service.sh` keeps `robot-runtime.service` disabled at boot by default (manual/API start only). Set `ROBOT_RUNTIME_ENABLE_ON_BOOT=1` to enable boot auto-start.
- Configure env vars documented in `docs/RUNBOOK.md`.
- Browser clients can be enabled via `ROBOT_API_CORS_ALLOWED_ORIGINS` (default `*`).
- For managed deployment, use:
  - `deploy/systemd/robot-api.service.template`
  - `deploy/systemd/robot-runtime.service.template`
  - `deploy/systemd/robot-api.env.example`
  - `scripts/install_systemd_service.sh`
  - `scripts/install_runtime_systemd_service.sh`
  - `scripts/uninstall_systemd_service.sh`
  - `scripts/uninstall_runtime_systemd_service.sh`
