from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import subprocess
import threading
from typing import Callable

from robot_api.config import RobotApiSettings
from robot_api.services.job_store import JobStore


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str], Path | None, dict[str, str] | None, float | None], CommandResult]


def default_command_runner(
    command: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout_s: float | None = None,
) -> CommandResult:
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    return CommandResult(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


class RobotService:
    def __init__(
        self,
        settings: RobotApiSettings,
        *,
        command_runner: CommandRunner | None = None,
        job_store: JobStore | None = None,
    ) -> None:
        self.settings = settings
        self._run_command = command_runner or default_command_runner
        self._jobs = job_store or JobStore(max_jobs=settings.max_jobs)
        self._state_lock = threading.Lock()
        self._active_update_job_id: str | None = None

    @property
    def active_update_job_id(self) -> str | None:
        with self._state_lock:
            return self._active_update_job_id

    def snapshot(self) -> dict[str, object]:
        return {
            "service": "robot-api",
            "managed_service": self.settings.managed_service,
            "workspace_dir": str(self.settings.workspace_dir),
            "repo_dir": str(self.settings.repo_dir),
            "repo_branch": self.settings.repo_branch,
            "active_update_job_id": self.active_update_job_id,
        }

    def get_runtime_status(self) -> dict[str, object]:
        command = [
            "systemctl",
            "show",
            self.settings.managed_service,
            "--no-page",
            "--property",
            "ActiveState",
            "--property",
            "SubState",
            "--property",
            "MainPID",
            "--property",
            "ActiveEnterTimestamp",
        ]
        result = self._run_command(command, None, None, 10.0)
        if result.returncode != 0:
            raise RuntimeError(_format_command_failure(command, result))

        values: dict[str, str] = {}
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip()

        active_state = values.get("ActiveState", "unknown")
        sub_state = values.get("SubState", "unknown")
        main_pid = _parse_int(values.get("MainPID", "0"), default=0)
        active_since = values.get("ActiveEnterTimestamp") or None
        return {
            "service_name": self.settings.managed_service,
            "active": active_state in {"active", "activating", "reloading"},
            "active_state": active_state,
            "sub_state": sub_state,
            "main_pid": max(main_pid, 0),
            "active_since": active_since,
        }

    def start_runtime(self) -> None:
        self._run_systemctl_action("start")

    def stop_runtime(self) -> None:
        self._run_systemctl_action("stop")

    def restart_runtime(self) -> None:
        self._run_systemctl_action("restart")

    def _run_systemctl_action(self, action: str) -> None:
        command = ["systemctl", action, self.settings.managed_service]
        result = self._run_command(command, None, None, 20.0)
        if result.returncode != 0:
            raise RuntimeError(_format_command_failure(command, result))

    def get_recent_logs(self, lines: int) -> list[str]:
        requested = max(1, min(int(lines), self.settings.max_log_lines))
        command = [
            "journalctl",
            "-u",
            self.settings.managed_service,
            "-n",
            str(requested),
            "--no-pager",
            "-o",
            "short-iso",
        ]
        result = self._run_command(command, None, None, 10.0)
        if result.returncode != 0:
            raise RuntimeError(_format_command_failure(command, result))
        return [line for line in result.stdout.splitlines() if line.strip()]

    def start_update_job(self, *, restart_service: bool) -> str:
        with self._state_lock:
            if self._active_update_job_id is not None:
                raise RuntimeError("Another update job is already running")
            record = self._jobs.create_job(restart_service=restart_service)
            self._active_update_job_id = record.job_id

        thread = threading.Thread(
            target=self._run_update_job,
            args=(record.job_id, restart_service),
            daemon=True,
            name=f"robot-api-update-{record.job_id[:8]}",
        )
        thread.start()
        return record.job_id

    def _run_update_job(self, job_id: str, restart_service: bool) -> None:
        self._jobs.start(job_id)
        try:
            self._run_update_step(
                job_id,
                "git_fetch",
                ["git", "-C", str(self.settings.repo_dir), "fetch", "--prune", "origin"],
                timeout_s=self.settings.update_timeout_s,
            )
            self._run_update_step(
                job_id,
                "git_checkout",
                ["git", "-C", str(self.settings.repo_dir), "checkout", self.settings.repo_branch],
                timeout_s=30.0,
            )
            self._run_update_step(
                job_id,
                "git_pull",
                ["git", "-C", str(self.settings.repo_dir), "pull", "--ff-only", "origin", self.settings.repo_branch],
                timeout_s=self.settings.update_timeout_s,
            )

            build_command = f"source {shlex.quote(str(self.settings.ros_setup_path))} && {self.settings.build_command}"
            self._run_update_step(
                job_id,
                "build",
                ["bash", "-lc", build_command],
                cwd=self.settings.workspace_dir,
                env=dict(os.environ),
                timeout_s=self.settings.update_timeout_s,
            )

            if restart_service:
                self._run_update_step(
                    job_id,
                    "restart_service",
                    ["systemctl", "restart", self.settings.managed_service],
                    timeout_s=20.0,
                )

            self._jobs.set_step(job_id, "completed")
            self._jobs.append_log(job_id, "Update job completed successfully")
            self._jobs.succeed(job_id)
        except Exception as exc:
            message = str(exc).strip() or "update failed"
            self._jobs.append_log(job_id, f"ERROR: {message}")
            self._jobs.fail(job_id, message)
        finally:
            with self._state_lock:
                if self._active_update_job_id == job_id:
                    self._active_update_job_id = None

    def _run_update_step(
        self,
        job_id: str,
        step_name: str,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self._jobs.set_step(job_id, step_name)
        self._jobs.append_log(job_id, f"$ {_command_to_text(command)}")
        result = self._run_command(command, cwd, env, timeout_s)

        if result.stdout.strip():
            for line in result.stdout.splitlines():
                if line.strip():
                    self._jobs.append_log(job_id, line)
        if result.stderr.strip():
            for line in result.stderr.splitlines():
                if line.strip():
                    self._jobs.append_log(job_id, f"stderr: {line}")

        if result.returncode != 0:
            raise RuntimeError(_format_command_failure(command, result))

    def list_jobs(self) -> list[dict[str, object]]:
        return self._jobs.list_summaries()

    def get_job(self, job_id: str) -> dict[str, object] | None:
        return self._jobs.get_detail(job_id)


def _parse_int(raw: str, *, default: int) -> int:
    try:
        return int(str(raw).strip())
    except Exception:
        return default


def _command_to_text(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _format_command_failure(command: list[str], result: CommandResult) -> str:
    text = f"Command failed ({result.returncode}): {_command_to_text(command)}"
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    if stderr:
        return f"{text}; stderr={stderr}"
    if stdout:
        return f"{text}; stdout={stdout}"
    return text
