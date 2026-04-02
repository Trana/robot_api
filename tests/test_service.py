from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

import pytest

from robot_api.config import RobotApiSettings
from robot_api.services.robot_service import CommandResult, RobotService


@dataclass
class FakeRunner:
    fail_prefix: list[str] | None = None
    sleep_seconds: float = 0.0

    def __post_init__(self) -> None:
        self.calls: list[tuple[list[str], Path | None, float | None]] = []

    def __call__(
        self,
        command: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> CommandResult:
        self.calls.append((list(command), cwd, timeout_s))

        if self.sleep_seconds > 0 and command[:4] == ["git", "-C", "/workspace/repo", "fetch"]:
            time.sleep(self.sleep_seconds)

        if self.fail_prefix and command[: len(self.fail_prefix)] == self.fail_prefix:
            return CommandResult(returncode=1, stdout="", stderr="forced failure")

        if command[:2] == ["systemctl", "show"]:
            return CommandResult(
                returncode=0,
                stdout="\n".join(
                    [
                        "ActiveState=active",
                        "SubState=running",
                        "MainPID=1234",
                        "ActiveEnterTimestamp=Fri 2026-03-27 12:00:00 UTC",
                    ]
                ),
                stderr="",
            )

        if command[:1] == ["journalctl"]:
            return CommandResult(returncode=0, stdout="line1\nline2\n", stderr="")

        if command[:2] == ["vcgencmd", "get_throttled"]:
            return CommandResult(returncode=0, stdout="throttled=0x0\n", stderr="")

        if command[:4] == ["ip", "-details", "-statistics", "link"]:
            return CommandResult(
                returncode=0,
                stdout="\n".join(
                    [
                        "6: can0: <NOARP,UP,LOWER_UP,ECHO> mtu 16 qdisc pfifo_fast state UP mode DEFAULT group default qlen 10",
                        "    link/can ",
                        "    can state ERROR-ACTIVE (berr-counter tx 0 rx 0) restart-ms 0",
                        "          bitrate 500000 sample-point 0.875",
                        "    RX: bytes  packets  errors  dropped overrun mcast   ",
                        "    12757      1032     0       0       0       0",
                        "    TX: bytes  packets  errors  dropped carrier collsns ",
                        "    3850       107      0       0       0       0",
                    ]
                ),
                stderr="",
            )

        return CommandResult(returncode=0, stdout="ok\n", stderr="")


def _settings() -> RobotApiSettings:
    return RobotApiSettings(
        managed_service="robot-stack.service",
        can_iface="can0",
        workspace_dir=Path("/workspace"),
        repo_dir=Path("/workspace/repo"),
        repo_branch="main",
        ros_setup_path=Path("/opt/ros/jazzy/setup.bash"),
        build_command="colcon build --symlink-install",
        update_timeout_s=10,
        max_log_lines=4000,
        max_jobs=50,
        api_token=None,
        cors_allowed_origins=("*",),
    )


def _wait_job(service: RobotService, job_id: str, timeout_s: float = 4.0) -> dict[str, object]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        payload = service.get_job(job_id)
        if payload and str(payload.get("status")) in {"succeeded", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"Timed out waiting for job {job_id}")


def test_get_runtime_status_parses_systemctl_show() -> None:
    runner = FakeRunner()
    service = RobotService(_settings(), command_runner=runner)

    payload = service.get_runtime_status()

    assert payload["active"] is True
    assert payload["active_state"] == "active"
    assert payload["sub_state"] == "running"
    assert payload["main_pid"] == 1234
    assert "host_memory_used_percent" in payload
    assert "host_cpu_temp_c" in payload
    assert "process_running" in payload
    assert payload["pi_throttled_hex"] == "0x0"
    assert payload["can_iface"] == "can0"
    assert payload["can_present"] is True
    assert payload["can_bus_state"] == "ERROR-ACTIVE"
    assert "launch_process_pid" in payload
    assert "launch_process_cmdline" in payload


def test_start_stop_restart_runtime_and_reset_can_call_expected_commands() -> None:
    runner = FakeRunner()
    service = RobotService(_settings(), command_runner=runner)

    service.start_runtime()
    service.stop_runtime()
    service.restart_runtime()
    service.reset_can_bus()

    commands = [call[0] for call in runner.calls]
    assert ["systemctl", "start", "robot-stack.service"] in commands
    assert ["systemctl", "stop", "robot-stack.service"] in commands
    assert ["systemctl", "restart", "robot-stack.service"] in commands
    assert ["ip", "link", "set", "can0", "down"] in commands
    assert ["ip", "link", "set", "can0", "up"] in commands


def test_start_runtime_with_use_imu_sets_and_unsets_manager_env() -> None:
    runner = FakeRunner()
    service = RobotService(_settings(), command_runner=runner)

    service.start_runtime(use_imu=False)

    commands = [call[0] for call in runner.calls]
    assert ["systemctl", "set-environment", "ROBOT_RUNTIME_USE_IMU=false"] in commands
    assert ["systemctl", "start", "robot-stack.service"] in commands
    assert ["systemctl", "unset-environment", "ROBOT_RUNTIME_USE_IMU"] in commands


def test_get_recent_logs_clamps_requested_lines() -> None:
    runner = FakeRunner()
    settings = _settings()
    settings = RobotApiSettings(
        managed_service=settings.managed_service,
        can_iface=settings.can_iface,
        workspace_dir=settings.workspace_dir,
        repo_dir=settings.repo_dir,
        repo_branch=settings.repo_branch,
        ros_setup_path=settings.ros_setup_path,
        build_command=settings.build_command,
        update_timeout_s=settings.update_timeout_s,
        max_log_lines=10,
        max_jobs=settings.max_jobs,
        api_token=settings.api_token,
        cors_allowed_origins=settings.cors_allowed_origins,
    )
    service = RobotService(settings, command_runner=runner)

    lines = service.get_recent_logs(500)

    assert lines == ["line1", "line2"]
    journalctl_call = next(call for call in runner.calls if call[0][0] == "journalctl")
    assert journalctl_call[0][4] == "10"
    assert "--since" in journalctl_call[0]


def test_get_recent_logs_history_scope_skips_current_run_since_lookup() -> None:
    runner = FakeRunner()
    service = RobotService(_settings(), command_runner=runner)

    lines = service.get_recent_logs(20, scope="history")

    assert lines == ["line1", "line2"]
    journalctl_call = next(call for call in runner.calls if call[0][0] == "journalctl")
    assert "--since" not in journalctl_call[0]


def test_get_recent_logs_explicit_since_takes_priority() -> None:
    runner = FakeRunner()
    service = RobotService(_settings(), command_runner=runner)

    lines = service.get_recent_logs(20, scope="current_run", since="2026-03-29 13:03:00")

    assert lines == ["line1", "line2"]
    journalctl_call = next(call for call in runner.calls if call[0][0] == "journalctl")
    assert journalctl_call[0][-2:] == ["--since", "2026-03-29 13:03:00"]
    systemctl_show_calls = [call for call in runner.calls if call[0][:2] == ["systemctl", "show"]]
    assert systemctl_show_calls == []


def test_update_job_success_runs_expected_steps() -> None:
    runner = FakeRunner()
    service = RobotService(_settings(), command_runner=runner)

    job_id = service.start_update_job(restart_service=True)
    payload = _wait_job(service, job_id)

    assert payload["status"] == "succeeded"
    commands = [call[0] for call in runner.calls]
    assert ["git", "-C", "/workspace/repo", "fetch", "--prune", "origin"] in commands
    assert ["git", "-C", "/workspace/repo", "checkout", "main"] in commands
    assert ["git", "-C", "/workspace/repo", "pull", "--ff-only", "origin", "main"] in commands
    assert ["systemctl", "restart", "robot-stack.service"] in commands


def test_update_job_rejects_parallel_runs() -> None:
    runner = FakeRunner(sleep_seconds=0.25)
    service = RobotService(_settings(), command_runner=runner)

    first_job_id = service.start_update_job(restart_service=False)
    with pytest.raises(RuntimeError):
        service.start_update_job(restart_service=False)

    payload = _wait_job(service, first_job_id)
    assert payload["status"] in {"succeeded", "failed"}


def test_update_job_failure_sets_failed_status() -> None:
    runner = FakeRunner(fail_prefix=["git", "-C", "/workspace/repo", "pull"])
    service = RobotService(_settings(), command_runner=runner)

    job_id = service.start_update_job(restart_service=False)
    payload = _wait_job(service, job_id)

    assert payload["status"] == "failed"
    assert payload["error_message"]
