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
    host_cpu_count: int | None = None
    host_load_1m: float | None = None
    host_load_5m: float | None = None
    host_load_15m: float | None = None
    host_load_percent_1m: float | None = None
    host_memory_total_bytes: int | None = None
    host_memory_available_bytes: int | None = None
    host_memory_used_percent: float | None = None
    host_disk_used_percent: float | None = None
    host_uptime_s: float | None = None
    host_cpu_temp_c: float | None = None
    pi_throttled_hex: str | None = None
    pi_throttled_active_flags: list[str] | None = None
    pi_undervoltage_now: bool | None = None
    pi_throttled_now: bool | None = None
    pi_freq_capped_now: bool | None = None
    pi_soft_temp_limit_now: bool | None = None
    pi_undervoltage_since_boot: bool | None = None
    pi_throttled_since_boot: bool | None = None
    pi_freq_capped_since_boot: bool | None = None
    pi_soft_temp_limit_since_boot: bool | None = None
    can_iface: str | None = None
    can_present: bool | None = None
    can_link_up: bool | None = None
    can_oper_state: str | None = None
    can_bus_state: str | None = None
    can_bitrate: int | None = None
    can_berr_tx: int | None = None
    can_berr_rx: int | None = None
    can_rx_packets: int | None = None
    can_rx_errors: int | None = None
    can_tx_packets: int | None = None
    can_tx_errors: int | None = None
    process_running: bool | None = None
    process_rss_bytes: int | None = None
    process_threads: int | None = None
    process_cmdline: str | None = None
    launch_process_pid: int | None = None
    launch_process_cmdline: str | None = None


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
