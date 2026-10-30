# Architecture: robot_api

## Purpose
Define runtime architecture and contracts for the robot operations API.

## Repository Boundaries
In scope:
- FastAPI service implementation.
- Service layer for status/log reads and guarded systemctl compatibility operations.
- Deploy scripts and systemd artifacts.
- Tests and runbooks.

Out of scope:
- Robot control algorithms.
- Tuning policy logic.
- Frontend UI implementation.

## Runtime Topology
- robot_api process (FastAPI/Uvicorn).
- Managed robot runtime service (default: `robot-runtime.service`).
- Optional journal access via `journalctl`.

## Components
1. `main.py`
- API routes, auth checks, error mapping, structured operation logs.

2. `config.py`
- Environment-driven settings and validation.

3. `services/robot_service.py`
- Encapsulates command execution and operation semantics.
- Handles status/log reads and gated lifecycle/CAN compatibility actions.

4. `models.py`
- Pydantic request/response models.

## Control Flow
Runtime action:
1. API receives authenticated action.
2. After checking the runtime compatibility flag, RobotService executes `systemctl` command.
3. For start/restart, the managed runtime service executes `scripts/run_robot_runtime.sh`, which sources ROS + workspace install setup files before launch command execution.
4. API returns normalized action response.

## Removed deployment feature (2026-09-19)

The Update Jobs UI, /api/v1/ops/* routes, background worker, in-memory job store,
job models and git/build settings are removed. Old routes return 404 regardless
of lifecycle compatibility flags. Robot Control Plane does not replace this
deployment feature; git/build remains an explicit operator workflow outside APIs.
The deployed robot is unchanged until the new revision is installed/restarted.

## Safety Rules
- No user-provided raw shell commands.
- Whitelisted operation sequence only.
- Token auth on all `/api/v1/*` routes when configured.
