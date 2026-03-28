from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient

from robot_api.config import RobotApiSettings
from robot_api.main import create_app


class FakeService:
    def __init__(self) -> None:
        self.start_called = False
        self.stop_called = False
        self.restart_called = False
        self.reset_can_called = False
        self.update_calls: list[bool] = []

    def snapshot(self) -> dict[str, object]:
        return {
            "service": "robot-api",
            "managed_service": "robot-stack.service",
            "workspace_dir": "/workspace",
            "repo_dir": "/workspace/repo",
            "repo_branch": "main",
            "active_update_job_id": None,
        }

    def get_runtime_status(self) -> dict[str, object]:
        return {
            "service_name": "robot-stack.service",
            "active": True,
            "active_state": "active",
            "sub_state": "running",
            "main_pid": 42,
            "active_since": "Fri 2026-03-27",
        }

    def get_recent_logs(self, lines: int) -> list[str]:
        return [f"l{lines}"]

    def start_runtime(self) -> None:
        self.start_called = True

    def stop_runtime(self) -> None:
        self.stop_called = True

    def restart_runtime(self) -> None:
        self.restart_called = True

    def reset_can_bus(self) -> None:
        self.reset_can_called = True

    def start_update_job(self, *, restart_service: bool) -> str:
        self.update_calls.append(restart_service)
        return "job-123"

    def list_jobs(self) -> list[dict[str, object]]:
        return [
            {
                "job_id": "job-123",
                "status": "running",
                "created_at": "2026-03-27T00:00:00Z",
                "started_at": "2026-03-27T00:00:01Z",
                "finished_at": None,
                "current_step": "git_pull",
                "restart_service": True,
                "error_message": None,
            }
        ]

    def get_job(self, job_id: str) -> dict[str, object] | None:
        if job_id != "job-123":
            return None
        return {
            "job_id": "job-123",
            "status": "running",
            "created_at": "2026-03-27T00:00:00Z",
            "started_at": "2026-03-27T00:00:01Z",
            "finished_at": None,
            "current_step": "git_pull",
            "restart_service": True,
            "error_message": None,
            "logs": ["hello"],
        }


def _settings(api_token: str | None = None) -> RobotApiSettings:
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
        api_token=api_token,
        cors_allowed_origins=("*",),
    )


def test_health_endpoint() -> None:
    app = create_app(settings=_settings(), service=FakeService())

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["service"] == "robot-api"


def test_auth_required_when_token_is_configured() -> None:
    app = create_app(settings=_settings(api_token="secret"), service=FakeService())

    with TestClient(app) as client:
        response = client.get("/api/v1/robot/status")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "ROBOT_AUTH_REQUIRED"


def test_status_endpoint_works_with_valid_token() -> None:
    app = create_app(settings=_settings(api_token="secret"), service=FakeService())

    with TestClient(app) as client:
        response = client.get("/api/v1/robot/status", headers={"Authorization": "Bearer secret"})

    assert response.status_code == 200
    assert response.json()["active"] is True


def test_start_endpoint_triggers_service() -> None:
    fake = FakeService()
    app = create_app(settings=_settings(), service=fake)

    with TestClient(app) as client:
        response = client.post("/api/v1/robot/start")

    assert response.status_code == 200
    assert fake.start_called is True


def test_reset_can_endpoint_triggers_service() -> None:
    fake = FakeService()
    app = create_app(settings=_settings(), service=fake)

    with TestClient(app) as client:
        response = client.post("/api/v1/robot/can/reset")

    assert response.status_code == 200
    assert fake.reset_can_called is True


def test_update_endpoints() -> None:
    app = create_app(settings=_settings(), service=FakeService())

    with TestClient(app) as client:
        response = client.post("/api/v1/ops/update", json={"restart_service": True})
        assert response.status_code == 200
        assert response.json()["job_id"] == "job-123"

        list_response = client.get("/api/v1/ops/jobs")
        assert list_response.status_code == 200
        assert list_response.json()["jobs"][0]["job_id"] == "job-123"

        detail_response = client.get("/api/v1/ops/jobs/job-123")
        assert detail_response.status_code == 200
        assert detail_response.json()["logs"] == ["hello"]
