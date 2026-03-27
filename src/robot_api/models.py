from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    service: str
    status: str
    managed_service: str
    workspace_dir: str
    repo_dir: str
    repo_branch: str
    active_update_job_id: str | None = None


class RobotStatusResponse(BaseModel):
    service_name: str
    active: bool
    active_state: str
    sub_state: str
    main_pid: int
    active_since: str | None = None


class RobotActionResponse(BaseModel):
    service_name: str
    action: str
    status: str


class RobotLogsResponse(BaseModel):
    service_name: str
    requested_lines: int
    lines: list[str]


class UpdateRequest(BaseModel):
    restart_service: bool = True


class UpdateStartResponse(BaseModel):
    job_id: str
    status: str


class JobSummaryResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    current_step: str | None = None
    restart_service: bool
    error_message: str | None = None


class JobDetailResponse(JobSummaryResponse):
    logs: list[str] = Field(default_factory=list)


class JobListResponse(BaseModel):
    jobs: list[JobSummaryResponse]
