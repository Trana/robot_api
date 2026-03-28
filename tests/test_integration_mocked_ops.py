from __future__ import annotations

from pathlib import Path
import time

import pytest

fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient

from robot_api.config import RobotApiSettings
from robot_api.main import create_app
from robot_api.services.robot_service import CommandResult, RobotService


class IntegrationRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(
        self,
        command: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> CommandResult:
        self.calls.append(list(command))

        if command[:2] == ["systemctl", "show"]:
            return CommandResult(returncode=0, stdout="ActiveState=active\nSubState=running\nMainPID=321\nActiveEnterTimestamp=now\n", stderr="")
        if command[:1] == ["journalctl"]:
            return CommandResult(returncode=0, stdout="entry1\nentry2\n", stderr="")
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
        api_token="secret",
        cors_allowed_origins=("*",),
    )


def test_integration_lifecycle_and_update_flow() -> None:
    runner = IntegrationRunner()
    service = RobotService(_settings(), command_runner=runner)
    app = create_app(settings=_settings(), service=service)

    with TestClient(app) as client:
        status = client.get("/api/v1/robot/status", headers={"Authorization": "Bearer secret"})
        assert status.status_code == 200

        logs = client.get("/api/v1/robot/logs", headers={"Authorization": "Bearer secret"})
        assert logs.status_code == 200
        assert logs.json()["lines"] == ["entry1", "entry2"]

        update = client.post("/api/v1/ops/update", headers={"Authorization": "Bearer secret"}, json={"restart_service": False})
        assert update.status_code == 200
        job_id = update.json()["job_id"]

        deadline = time.time() + 4.0
        final_status = None
        while time.time() < deadline:
            detail = client.get(f"/api/v1/ops/jobs/{job_id}", headers={"Authorization": "Bearer secret"})
            assert detail.status_code == 200
            final_status = detail.json()["status"]
            if final_status in {"succeeded", "failed"}:
                break
            time.sleep(0.02)

        assert final_status == "succeeded"
        assert ["git", "-C", "/workspace/repo", "fetch", "--prune", "origin"] in runner.calls
