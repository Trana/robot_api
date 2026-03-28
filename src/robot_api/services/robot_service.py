from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
import shutil
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
        main_pid = max(_parse_int(values.get("MainPID", "0"), default=0), 0)
        active_since = values.get("ActiveEnterTimestamp") or None
        payload: dict[str, object] = {
            "service_name": self.settings.managed_service,
            "active": active_state in {"active", "activating", "reloading"},
            "active_state": active_state,
            "sub_state": sub_state,
            "main_pid": main_pid,
            "active_since": active_since,
        }
        payload.update(_collect_host_metrics(self.settings.workspace_dir))
        payload.update(_collect_pi_throttle_metrics(self._run_command))
        payload.update(_collect_can_metrics(self._run_command, self.settings.can_iface))
        payload.update(_collect_process_metrics(main_pid))
        payload.update(_collect_launch_child_metrics(main_pid))
        return payload

    def start_runtime(self) -> None:
        self._run_systemctl_action("start")

    def stop_runtime(self) -> None:
        self._run_systemctl_action("stop")

    def restart_runtime(self) -> None:
        self._run_systemctl_action("restart")

    def reset_can_bus(self) -> None:
        iface = str(self.settings.can_iface or "").strip()
        if not iface:
            raise RuntimeError("ROBOT_API_CAN_IFACE is not configured")

        down_command = ["ip", "link", "set", iface, "down"]
        down_result = self._run_command(down_command, None, None, 5.0)
        if down_result.returncode != 0:
            raise RuntimeError(_format_command_failure(down_command, down_result))

        up_command = ["ip", "link", "set", iface, "up"]
        up_result = self._run_command(up_command, None, None, 5.0)
        if up_result.returncode != 0:
            raise RuntimeError(_format_command_failure(up_command, up_result))

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


def _collect_host_metrics(workspace_dir: Path) -> dict[str, object]:
    payload: dict[str, object] = {
        "host_cpu_count": None,
        "host_load_1m": None,
        "host_load_5m": None,
        "host_load_15m": None,
        "host_load_percent_1m": None,
        "host_memory_total_bytes": None,
        "host_memory_available_bytes": None,
        "host_memory_used_percent": None,
        "host_disk_used_percent": None,
        "host_uptime_s": None,
        "host_cpu_temp_c": None,
    }

    cpu_count = os.cpu_count()
    if cpu_count and cpu_count > 0:
        payload["host_cpu_count"] = int(cpu_count)

    try:
        load_1m, load_5m, load_15m = os.getloadavg()
        payload["host_load_1m"] = round(float(load_1m), 3)
        payload["host_load_5m"] = round(float(load_5m), 3)
        payload["host_load_15m"] = round(float(load_15m), 3)
        if cpu_count and cpu_count > 0:
            payload["host_load_percent_1m"] = round((float(load_1m) / float(cpu_count)) * 100.0, 2)
    except Exception:
        pass

    mem_total_bytes, mem_available_bytes = _read_meminfo_bytes()
    if mem_total_bytes is not None:
        payload["host_memory_total_bytes"] = mem_total_bytes
    if mem_available_bytes is not None:
        payload["host_memory_available_bytes"] = mem_available_bytes
    if mem_total_bytes and mem_available_bytes is not None and mem_total_bytes > 0:
        used_bytes = max(mem_total_bytes - mem_available_bytes, 0)
        payload["host_memory_used_percent"] = round((used_bytes / mem_total_bytes) * 100.0, 2)

    disk_candidates = [workspace_dir, Path("/")]
    for candidate in disk_candidates:
        try:
            usage = shutil.disk_usage(str(candidate))
            if usage.total > 0:
                payload["host_disk_used_percent"] = round(((usage.total - usage.free) / usage.total) * 100.0, 2)
            break
        except Exception:
            continue

    payload["host_uptime_s"] = _read_uptime_seconds()
    payload["host_cpu_temp_c"] = _read_cpu_temp_c()
    return payload


def _collect_pi_throttle_metrics(command_runner: CommandRunner) -> dict[str, object]:
    payload: dict[str, object] = {
        "pi_throttled_hex": None,
        "pi_throttled_active_flags": None,
        "pi_undervoltage_now": None,
        "pi_throttled_now": None,
        "pi_freq_capped_now": None,
        "pi_soft_temp_limit_now": None,
        "pi_undervoltage_since_boot": None,
        "pi_throttled_since_boot": None,
        "pi_freq_capped_since_boot": None,
        "pi_soft_temp_limit_since_boot": None,
    }

    command = ["vcgencmd", "get_throttled"]
    try:
        result = command_runner(command, None, None, 1.5)
    except Exception:
        return payload
    if result.returncode != 0:
        return payload

    raw = result.stdout.strip()
    value = _parse_throttled_hex_value(raw)
    if value is None:
        return payload

    payload["pi_throttled_hex"] = f"0x{value:x}"
    flags = _decode_pi_throttle_flags(value)
    payload["pi_throttled_active_flags"] = [name for name, active in flags.items() if active]
    payload["pi_undervoltage_now"] = flags["undervoltage_now"]
    payload["pi_throttled_now"] = flags["throttled_now"]
    payload["pi_freq_capped_now"] = flags["freq_capped_now"]
    payload["pi_soft_temp_limit_now"] = flags["soft_temp_limit_now"]
    payload["pi_undervoltage_since_boot"] = flags["undervoltage_since_boot"]
    payload["pi_throttled_since_boot"] = flags["throttled_since_boot"]
    payload["pi_freq_capped_since_boot"] = flags["freq_capped_since_boot"]
    payload["pi_soft_temp_limit_since_boot"] = flags["soft_temp_limit_since_boot"]
    return payload


def _parse_throttled_hex_value(raw: str) -> int | None:
    match = re.search(r"0x([0-9a-fA-F]+)", str(raw))
    if not match:
        return None
    try:
        return int(match.group(1), 16)
    except Exception:
        return None


def _decode_pi_throttle_flags(value: int) -> dict[str, bool]:
    return {
        "undervoltage_now": bool(value & (1 << 0)),
        "freq_capped_now": bool(value & (1 << 1)),
        "throttled_now": bool(value & (1 << 2)),
        "soft_temp_limit_now": bool(value & (1 << 3)),
        "undervoltage_since_boot": bool(value & (1 << 16)),
        "freq_capped_since_boot": bool(value & (1 << 17)),
        "throttled_since_boot": bool(value & (1 << 18)),
        "soft_temp_limit_since_boot": bool(value & (1 << 19)),
    }


def _collect_can_metrics(command_runner: CommandRunner, iface: str) -> dict[str, object]:
    can_iface = str(iface or "").strip()
    payload: dict[str, object] = {
        "can_iface": can_iface or None,
        "can_present": None,
        "can_link_up": None,
        "can_oper_state": None,
        "can_bus_state": None,
        "can_bitrate": None,
        "can_berr_tx": None,
        "can_berr_rx": None,
        "can_rx_packets": None,
        "can_rx_errors": None,
        "can_tx_packets": None,
        "can_tx_errors": None,
    }
    if not can_iface:
        return payload

    command = ["ip", "-details", "-statistics", "link", "show", can_iface]
    try:
        result = command_runner(command, None, None, 2.0)
    except Exception:
        payload["can_present"] = False
        return payload
    if result.returncode != 0:
        payload["can_present"] = False
        return payload

    payload["can_present"] = True
    lines = [line.rstrip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return payload

    first_line = lines[0]
    flags_match = re.search(r"<([^>]+)>", first_line)
    if flags_match:
        flags = {part.strip().upper() for part in flags_match.group(1).split(",") if part.strip()}
        payload["can_link_up"] = "UP" in flags and "LOWER_UP" in flags
    state_match = re.search(r"\bstate\s+([A-Z_]+)\b", first_line)
    if state_match:
        payload["can_oper_state"] = state_match.group(1)

    for index, line in enumerate(lines):
        stripped = line.strip()
        bus_state_match = re.search(r"\bcan state\s+([A-Z0-9_-]+)\b", stripped)
        if bus_state_match:
            payload["can_bus_state"] = bus_state_match.group(1)

        berr_match = re.search(r"\bberr-counter\s+tx\s+(\d+)\s+rx\s+(\d+)\b", stripped)
        if berr_match:
            payload["can_berr_tx"] = int(berr_match.group(1))
            payload["can_berr_rx"] = int(berr_match.group(2))

        bitrate_match = re.search(r"\bbitrate\s+(\d+)\b", stripped)
        if bitrate_match:
            payload["can_bitrate"] = int(bitrate_match.group(1))

        if stripped.startswith("RX:") and index + 1 < len(lines):
            rx_values = [_extract_first_int(part) for part in lines[index + 1].split()]
            if len(rx_values) >= 3:
                payload["can_rx_packets"] = rx_values[1]
                payload["can_rx_errors"] = rx_values[2]
        if stripped.startswith("TX:") and index + 1 < len(lines):
            tx_values = [_extract_first_int(part) for part in lines[index + 1].split()]
            if len(tx_values) >= 3:
                payload["can_tx_packets"] = tx_values[1]
                payload["can_tx_errors"] = tx_values[2]

    return payload


def _read_meminfo_bytes() -> tuple[int | None, int | None]:
    mem_total_kib: int | None = None
    mem_available_kib: int | None = None
    try:
        raw = Path("/proc/meminfo").read_text(encoding="utf-8")
    except Exception:
        return None, None

    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed = _extract_first_int(value)
        if parsed is None:
            continue
        if key.strip() == "MemTotal":
            mem_total_kib = parsed
        elif key.strip() == "MemAvailable":
            mem_available_kib = parsed

    mem_total_bytes = mem_total_kib * 1024 if mem_total_kib is not None else None
    mem_available_bytes = mem_available_kib * 1024 if mem_available_kib is not None else None
    return mem_total_bytes, mem_available_bytes


def _read_uptime_seconds() -> float | None:
    try:
        raw = Path("/proc/uptime").read_text(encoding="utf-8").strip()
        first = raw.split()[0]
        return round(float(first), 2)
    except Exception:
        return None


def _read_cpu_temp_c() -> float | None:
    try:
        raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text(encoding="utf-8").strip()
        milli_c = int(raw)
        return round(milli_c / 1000.0, 2)
    except Exception:
        return None


def _collect_process_metrics(main_pid: int) -> dict[str, object]:
    payload: dict[str, object] = {
        "process_running": False,
        "process_rss_bytes": None,
        "process_threads": None,
        "process_cmdline": None,
    }
    if main_pid <= 0:
        return payload

    process_dir = Path(f"/proc/{main_pid}")
    if not process_dir.exists():
        return payload

    payload["process_running"] = True

    status_path = process_dir / "status"
    try:
        raw_status = status_path.read_text(encoding="utf-8")
        for line in raw_status.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            parsed = _extract_first_int(value)
            normalized_key = key.strip()
            if normalized_key == "VmRSS" and parsed is not None:
                payload["process_rss_bytes"] = parsed * 1024
            elif normalized_key == "Threads" and parsed is not None:
                payload["process_threads"] = parsed
    except Exception:
        pass

    cmdline_path = process_dir / "cmdline"
    payload["process_cmdline"] = _read_cmdline_from_path(cmdline_path)

    return payload


def _collect_launch_child_metrics(main_pid: int) -> dict[str, object]:
    payload: dict[str, object] = {
        "launch_process_pid": None,
        "launch_process_cmdline": None,
    }
    if main_pid <= 0:
        return payload

    descendants = _collect_descendant_pids(main_pid, max_nodes=128)
    if not descendants:
        return payload

    selected_pid: int | None = None
    selected_cmdline: str | None = None
    selected_score = -1

    for pid in descendants:
        cmdline = _read_cmdline_for_pid(pid)
        if not cmdline:
            continue
        lowered = cmdline.lower()
        score = 0
        if "ros2 launch" in lowered:
            score = 100
        elif "launch.py" in lowered:
            score = 80
        elif " launch " in lowered:
            score = 60
        elif "python" in lowered:
            score = 30
        else:
            score = 10

        if score > selected_score:
            selected_pid = pid
            selected_cmdline = cmdline
            selected_score = score

    if selected_pid is None:
        return payload

    payload["launch_process_pid"] = selected_pid
    payload["launch_process_cmdline"] = selected_cmdline
    return payload


def _collect_descendant_pids(root_pid: int, *, max_nodes: int) -> list[int]:
    visited: set[int] = set()
    queue: list[int] = [root_pid]
    descendants: list[int] = []

    while queue and len(visited) < max_nodes:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        children = _read_children_pids(current)
        for child_pid in children:
            if child_pid <= 0 or child_pid in visited:
                continue
            descendants.append(child_pid)
            queue.append(child_pid)

    return descendants


def _read_children_pids(pid: int) -> list[int]:
    children_path = Path(f"/proc/{pid}/task/{pid}/children")
    try:
        raw = children_path.read_text(encoding="utf-8").strip()
    except Exception:
        return []
    if not raw:
        return []

    parsed: list[int] = []
    for token in raw.split():
        value = _parse_int(token, default=0)
        if value > 0:
            parsed.append(value)
    return parsed


def _read_cmdline_for_pid(pid: int) -> str | None:
    return _read_cmdline_from_path(Path(f"/proc/{pid}/cmdline"))


def _read_cmdline_from_path(cmdline_path: Path) -> str | None:
    try:
        raw_cmd = cmdline_path.read_bytes()
    except Exception:
        return None
    parts = [part.decode("utf-8", errors="replace") for part in raw_cmd.split(b"\x00") if part]
    if not parts:
        return None
    return " ".join(parts)


def _extract_first_int(raw: str) -> int | None:
    digits: list[str] = []
    started = False
    for char in str(raw):
        if char.isdigit():
            digits.append(char)
            started = True
            continue
        if started:
            break
    if not digits:
        return None
    try:
        return int("".join(digits))
    except Exception:
        return None


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
