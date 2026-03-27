# Architecture: robot_api

## Purpose
Define runtime architecture and contracts for the robot operations API.

## Repository Boundaries
In scope:
- FastAPI service implementation.
- Service layer for systemctl/git/build operations.
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
- Handles lifecycle actions and update workflow orchestration.

4. `services/job_store.py`
- In-memory job state + logs for async update jobs.

5. `models.py`
- Pydantic request/response models.

## Control Flow
Runtime action:
1. API receives authenticated action.
2. RobotService executes `systemctl` command.
3. For start/restart, the managed runtime service executes `scripts/run_robot_runtime.sh`, which sources ROS + workspace install setup files before launch command execution.
4. API returns normalized action response.

Update job:
1. API creates job and starts background thread.
2. Service runs sequence:
   - `git fetch --prune`
   - `git checkout <branch>`
   - `git pull --ff-only origin <branch>`
   - `source <ros_setup> && <build_command>`
   - optional service restart
3. Job state updates after each step.
4. UI polls `/api/v1/ops/jobs/{job_id}`.

## Safety Rules
- No user-provided raw shell commands.
- Whitelisted operation sequence only.
- Single active update job.
- Token auth on all `/api/v1/*` routes when configured.
