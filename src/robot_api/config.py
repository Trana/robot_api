from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class RobotApiSettings:
    managed_service: str
    can_iface: str
    workspace_dir: Path
    repo_dir: Path
    repo_branch: str
    ros_setup_path: Path
    build_command: str
    update_timeout_s: float
    max_log_lines: int
    max_jobs: int
    api_token: str | None
    cors_allowed_origins: tuple[str, ...] = ("*",)

    @classmethod
    def from_env(cls) -> "RobotApiSettings":
        managed_service = os.getenv("ROBOT_API_MANAGED_SERVICE", "robot-runtime.service").strip() or "robot-runtime.service"
        can_iface = os.getenv("ROBOT_API_CAN_IFACE", "can0").strip()
        workspace_dir = Path(os.getenv("ROBOT_API_WORKSPACE_DIR", "/opt/robot_ws").strip() or "/opt/robot_ws")
        repo_dir = Path(os.getenv("ROBOT_API_REPO_DIR", "/opt/robot_ws/src/robot_stack").strip() or "/opt/robot_ws/src/robot_stack")
        repo_branch = os.getenv("ROBOT_API_REPO_BRANCH", "main").strip() or "main"
        ros_setup_path = Path(os.getenv("ROBOT_API_ROS_SETUP_PATH", "/opt/ros/humble/setup.bash").strip() or "/opt/ros/humble/setup.bash")
        build_command = os.getenv("ROBOT_API_BUILD_COMMAND", "colcon build --symlink-install").strip() or "colcon build --symlink-install"
        update_timeout_s = float(os.getenv("ROBOT_API_UPDATE_TIMEOUT_S", "1800"))
        max_log_lines = int(os.getenv("ROBOT_API_MAX_LOG_LINES", "4000"))
        max_jobs = int(os.getenv("ROBOT_API_MAX_JOBS", "50"))
        api_token_raw = os.getenv("ROBOT_API_TOKEN", "").strip()
        api_token = api_token_raw or None
        cors_allowed_origins = _parse_cors_allowed_origins(os.getenv("ROBOT_API_CORS_ALLOWED_ORIGINS", "*"))

        if not managed_service:
            raise ValueError("ROBOT_API_MANAGED_SERVICE must not be empty")
        if not repo_branch:
            raise ValueError("ROBOT_API_REPO_BRANCH must not be empty")
        if not build_command:
            raise ValueError("ROBOT_API_BUILD_COMMAND must not be empty")
        if update_timeout_s <= 0:
            raise ValueError("ROBOT_API_UPDATE_TIMEOUT_S must be > 0")
        if max_log_lines <= 0:
            raise ValueError("ROBOT_API_MAX_LOG_LINES must be > 0")
        if max_jobs <= 0:
            raise ValueError("ROBOT_API_MAX_JOBS must be > 0")

        return cls(
            managed_service=managed_service,
            can_iface=can_iface,
            workspace_dir=workspace_dir,
            repo_dir=repo_dir,
            repo_branch=repo_branch,
            ros_setup_path=ros_setup_path,
            build_command=build_command,
            update_timeout_s=update_timeout_s,
            max_log_lines=max_log_lines,
            max_jobs=max_jobs,
            api_token=api_token,
            cors_allowed_origins=cors_allowed_origins,
        )


def _parse_cors_allowed_origins(raw: str) -> tuple[str, ...]:
    normalized = str(raw or "").strip()
    if not normalized:
        return tuple()

    parsed: list[str] = []
    for part in normalized.split(","):
        origin = part.strip()
        if not origin:
            continue
        if origin not in parsed:
            parsed.append(origin)
    return tuple(parsed)
