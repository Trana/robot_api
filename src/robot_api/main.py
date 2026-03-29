from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
from time import perf_counter
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from robot_api.config import RobotApiSettings
from robot_api.models import (
    HealthResponse,
    JobDetailResponse,
    JobListResponse,
    JobSummaryResponse,
    RobotActionResponse,
    RobotLogsResponse,
    RobotStatusResponse,
    UpdateRequest,
    UpdateStartResponse,
)
from robot_api.services.robot_service import RobotService


logger = logging.getLogger("robot_api")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _raise_api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=_error_detail(code, message))


def _extract_api_token(authorization_header: str | None, x_api_key_header: str | None) -> str | None:
    if x_api_key_header:
        token = x_api_key_header.strip()
        return token or None

    if not authorization_header:
        return None

    raw = authorization_header.strip()
    bearer_prefix = "bearer "
    if raw.lower().startswith(bearer_prefix):
        token = raw[len(bearer_prefix) :].strip()
        return token or None
    return None


def _authorize_or_raise(
    *,
    expected_token: str | None,
    operation: str,
    start_s: float,
    authorization_header: str | None,
    x_api_key_header: str | None,
) -> None:
    if expected_token is None:
        return

    provided_token = _extract_api_token(authorization_header, x_api_key_header)
    if provided_token is None:
        message = "Missing API token"
        _log_operation(operation, success=False, status_code=401, start_s=start_s, error_code="ROBOT_AUTH_REQUIRED", error_message=message)
        raise _raise_api_error(401, "ROBOT_AUTH_REQUIRED", message)

    if provided_token != expected_token:
        message = "Invalid API token"
        _log_operation(operation, success=False, status_code=403, start_s=start_s, error_code="ROBOT_AUTH_INVALID", error_message=message)
        raise _raise_api_error(403, "ROBOT_AUTH_INVALID", message)


def _log_operation(
    operation: str,
    *,
    success: bool,
    status_code: int,
    start_s: float,
    error_code: str | None = None,
    error_message: str | None = None,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "event": "robot_api_operation",
        "operation": operation,
        "success": success,
        "status_code": status_code,
        "duration_ms": round((perf_counter() - start_s) * 1000.0, 3),
    }
    if error_code is not None:
        payload["error_code"] = error_code
    if error_message is not None:
        payload["error_message"] = error_message
    payload.update(fields)

    level = logging.INFO
    if not success and status_code >= 500:
        level = logging.ERROR
    elif not success:
        level = logging.WARNING
    logger.log(level, json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _coerce_job_summary(record: dict[str, object]) -> JobSummaryResponse:
    return JobSummaryResponse(**record)


def _coerce_job_detail(record: dict[str, object]) -> JobDetailResponse:
    return JobDetailResponse(**record)


def create_app(settings: RobotApiSettings | None = None, service: RobotService | None = None) -> FastAPI:
    resolved_settings = settings or RobotApiSettings.from_env()
    resolved_service = service or RobotService(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.robot_service = resolved_service
        yield

    app = FastAPI(title="robot-api", version="0.1.0", lifespan=lifespan)

    if resolved_settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.cors_allowed_origins),
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
            allow_credentials=False,
        )

    @app.get("/")
    def root() -> dict[str, object]:
        return {
            "service": "robot-api",
            "status": "ok",
            "timestamp": _utcnow_iso(),
        }

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        snapshot = resolved_service.snapshot()
        return HealthResponse(
            service="robot-api",
            status="ok",
            managed_service=str(snapshot["managed_service"]),
            workspace_dir=str(snapshot["workspace_dir"]),
            repo_dir=str(snapshot["repo_dir"]),
            repo_branch=str(snapshot["repo_branch"]),
            active_update_job_id=snapshot.get("active_update_job_id"),
        )

    @app.get("/api/v1/robot/status", response_model=RobotStatusResponse)
    def robot_status(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> RobotStatusResponse:
        started = perf_counter()
        _authorize_or_raise(
            expected_token=resolved_settings.api_token,
            operation="robot_status",
            start_s=started,
            authorization_header=authorization,
            x_api_key_header=x_api_key,
        )
        try:
            payload = RobotStatusResponse(**resolved_service.get_runtime_status())
        except Exception as err:
            message = str(err)
            _log_operation("robot_status", success=False, status_code=503, start_s=started, error_code="ROBOT_STATUS_FAILED", error_message=message)
            raise _raise_api_error(503, "ROBOT_STATUS_FAILED", message) from err

        _log_operation("robot_status", success=True, status_code=200, start_s=started)
        return payload

    @app.get("/api/v1/robot/logs", response_model=RobotLogsResponse)
    def robot_logs(
        lines: int = Query(default=200, ge=1),
        scope: Literal["current_run", "history"] = Query(default="current_run"),
        since: str | None = Query(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> RobotLogsResponse:
        started = perf_counter()
        _authorize_or_raise(
            expected_token=resolved_settings.api_token,
            operation="robot_logs",
            start_s=started,
            authorization_header=authorization,
            x_api_key_header=x_api_key,
        )
        try:
            items = resolved_service.get_recent_logs(lines, scope=scope, since=since)
        except Exception as err:
            message = str(err)
            _log_operation("robot_logs", success=False, status_code=503, start_s=started, error_code="ROBOT_LOGS_FAILED", error_message=message)
            raise _raise_api_error(503, "ROBOT_LOGS_FAILED", message) from err

        payload = RobotLogsResponse(service_name=resolved_settings.managed_service, requested_lines=lines, scope=scope, since=since, lines=items)
        _log_operation("robot_logs", success=True, status_code=200, start_s=started, line_count=len(items), scope=scope, since=since)
        return payload

    @app.post("/api/v1/robot/start", response_model=RobotActionResponse)
    def robot_start(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> RobotActionResponse:
        return _robot_action(
            operation="robot_start",
            action="start",
            executor=resolved_service.start_runtime,
            settings=resolved_settings,
            authorization=authorization,
            x_api_key=x_api_key,
        )

    @app.post("/api/v1/robot/stop", response_model=RobotActionResponse)
    def robot_stop(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> RobotActionResponse:
        return _robot_action(
            operation="robot_stop",
            action="stop",
            executor=resolved_service.stop_runtime,
            settings=resolved_settings,
            authorization=authorization,
            x_api_key=x_api_key,
        )

    @app.post("/api/v1/robot/restart", response_model=RobotActionResponse)
    def robot_restart(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> RobotActionResponse:
        return _robot_action(
            operation="robot_restart",
            action="restart",
            executor=resolved_service.restart_runtime,
            settings=resolved_settings,
            authorization=authorization,
            x_api_key=x_api_key,
        )

    @app.post("/api/v1/robot/can/reset", response_model=RobotActionResponse)
    def robot_reset_can(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> RobotActionResponse:
        return _robot_action(
            operation="robot_reset_can",
            action="can_reset",
            executor=resolved_service.reset_can_bus,
            settings=resolved_settings,
            authorization=authorization,
            x_api_key=x_api_key,
        )

    @app.post("/api/v1/ops/update", response_model=UpdateStartResponse)
    def start_update(
        request: UpdateRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> UpdateStartResponse:
        started = perf_counter()
        _authorize_or_raise(
            expected_token=resolved_settings.api_token,
            operation="start_update",
            start_s=started,
            authorization_header=authorization,
            x_api_key_header=x_api_key,
        )

        try:
            job_id = resolved_service.start_update_job(restart_service=request.restart_service)
        except RuntimeError as err:
            message = str(err)
            status_code = 409 if "already running" in message.lower() else 503
            error_code = "ROBOT_UPDATE_IN_PROGRESS" if status_code == 409 else "ROBOT_UPDATE_FAILED"
            _log_operation("start_update", success=False, status_code=status_code, start_s=started, error_code=error_code, error_message=message)
            raise _raise_api_error(status_code, error_code, message) from err
        except Exception as err:
            message = str(err)
            _log_operation("start_update", success=False, status_code=500, start_s=started, error_code="ROBOT_INTERNAL_ERROR", error_message=message)
            raise _raise_api_error(500, "ROBOT_INTERNAL_ERROR", message) from err

        _log_operation("start_update", success=True, status_code=200, start_s=started, job_id=job_id)
        return UpdateStartResponse(job_id=job_id, status="queued")

    @app.get("/api/v1/ops/jobs", response_model=JobListResponse)
    def list_jobs(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> JobListResponse:
        started = perf_counter()
        _authorize_or_raise(
            expected_token=resolved_settings.api_token,
            operation="list_jobs",
            start_s=started,
            authorization_header=authorization,
            x_api_key_header=x_api_key,
        )
        payload = JobListResponse(jobs=[_coerce_job_summary(item) for item in resolved_service.list_jobs()])
        _log_operation("list_jobs", success=True, status_code=200, start_s=started, job_count=len(payload.jobs))
        return payload

    @app.get("/api/v1/ops/jobs/{job_id}", response_model=JobDetailResponse)
    def get_job(
        job_id: str,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> JobDetailResponse:
        started = perf_counter()
        _authorize_or_raise(
            expected_token=resolved_settings.api_token,
            operation="get_job",
            start_s=started,
            authorization_header=authorization,
            x_api_key_header=x_api_key,
        )
        record = resolved_service.get_job(job_id)
        if record is None:
            _log_operation("get_job", success=False, status_code=404, start_s=started, error_code="ROBOT_JOB_NOT_FOUND", error_message=job_id)
            raise _raise_api_error(404, "ROBOT_JOB_NOT_FOUND", f"Job not found: {job_id}")

        payload = _coerce_job_detail(record)
        _log_operation("get_job", success=True, status_code=200, start_s=started, job_id=job_id)
        return payload

    return app


def _robot_action(
    *,
    operation: str,
    action: str,
    executor: Any,
    settings: RobotApiSettings,
    authorization: str | None,
    x_api_key: str | None,
) -> RobotActionResponse:
    started = perf_counter()
    _authorize_or_raise(
        expected_token=settings.api_token,
        operation=operation,
        start_s=started,
        authorization_header=authorization,
        x_api_key_header=x_api_key,
    )

    try:
        executor()
    except Exception as err:
        message = str(err)
        _log_operation(operation, success=False, status_code=503, start_s=started, error_code="ROBOT_ACTION_FAILED", error_message=message)
        raise _raise_api_error(503, "ROBOT_ACTION_FAILED", message) from err

    _log_operation(operation, success=True, status_code=200, start_s=started, action=action)
    return RobotActionResponse(service_name=settings.managed_service, action=action, status="ok")


app = create_app()
