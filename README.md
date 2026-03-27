# robot_api

FastAPI backend for real robot lifecycle and deployment operations.

## Purpose
- expose HTTP endpoints to start/stop/restart the real robot runtime
- expose status/log views for operational debugging
- run controlled update flow (`git pull` + build + optional restart)
- provide async job tracking for update operations

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
- `GET /api/v1/robot/logs?lines=200`
- `POST /api/v1/robot/start`
- `POST /api/v1/robot/stop`
- `POST /api/v1/robot/restart`
- `POST /api/v1/ops/update`
- `GET /api/v1/ops/jobs`
- `GET /api/v1/ops/jobs/{job_id}`

## Notes
- For real robot runtime, use a single worker process (`--workers 1`).
- Runtime start/stop/restart is managed through `systemctl` on `ROBOT_API_MANAGED_SERVICE` (default `robot-runtime.service`).
- `robot-runtime.service` launches via `scripts/run_robot_runtime.sh`, which sources:
  - `ROBOT_RUNTIME_ROS_SETUP` (default `/opt/ros/humble/setup.bash`)
  - `ROBOT_RUNTIME_WORKSPACE_SETUP` (default `/opt/robot_ws/install/setup.bash`)
  then executes `ROBOT_RUNTIME_LAUNCH_COMMAND`.
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
