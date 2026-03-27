from pathlib import Path

import pytest

from robot_api.config import RobotApiSettings


def test_from_env_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ROBOT_API_MANAGED_SERVICE", raising=False)
    monkeypatch.delenv("ROBOT_API_REPO_BRANCH", raising=False)
    monkeypatch.delenv("ROBOT_API_CORS_ALLOWED_ORIGINS", raising=False)

    settings = RobotApiSettings.from_env()

    assert settings.managed_service == "robot-runtime.service"
    assert settings.repo_branch == "main"
    assert settings.ros_setup_path == Path("/opt/ros/humble/setup.bash")
    assert isinstance(settings.workspace_dir, Path)
    assert settings.cors_allowed_origins == ("*",)


def test_from_env_custom_values(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROBOT_API_MANAGED_SERVICE", "marvin-runtime.service")
    monkeypatch.setenv("ROBOT_API_REPO_BRANCH", "release")
    monkeypatch.setenv("ROBOT_API_CORS_ALLOWED_ORIGINS", "http://a.local,http://b.local")
    monkeypatch.setenv("ROBOT_API_TOKEN", "secret")

    settings = RobotApiSettings.from_env()

    assert settings.managed_service == "marvin-runtime.service"
    assert settings.repo_branch == "release"
    assert settings.cors_allowed_origins == ("http://a.local", "http://b.local")
    assert settings.api_token == "secret"


@pytest.mark.parametrize(
    "name,value",
    [
        ("ROBOT_API_UPDATE_TIMEOUT_S", "0"),
        ("ROBOT_API_MAX_LOG_LINES", "0"),
        ("ROBOT_API_MAX_JOBS", "0"),
    ],
)
def test_from_env_rejects_non_positive_numeric(monkeypatch: pytest.MonkeyPatch, name: str, value: str):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        RobotApiSettings.from_env()
