from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import uuid


JobStatus = str


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    created_at: str
    restart_service: bool
    started_at: str | None = None
    finished_at: str | None = None
    current_step: str | None = None
    error_message: str | None = None
    logs: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "current_step": self.current_step,
            "restart_service": self.restart_service,
            "error_message": self.error_message,
        }

    def detail(self) -> dict[str, object]:
        payload = self.summary()
        payload["logs"] = list(self.logs)
        return payload


class JobStore:
    def __init__(self, max_jobs: int = 50) -> None:
        self._max_jobs = max_jobs
        self._lock = threading.Lock()
        self._jobs: OrderedDict[str, JobRecord] = OrderedDict()

    def create_job(self, *, restart_service: bool) -> JobRecord:
        with self._lock:
            job_id = uuid.uuid4().hex
            record = JobRecord(
                job_id=job_id,
                status="queued",
                created_at=_utcnow_iso(),
                restart_service=restart_service,
            )
            self._jobs[job_id] = record
            self._trim_unsafe()
            return record

    def start(self, job_id: str) -> None:
        with self._lock:
            record = self._require_unsafe(job_id)
            record.status = "running"
            record.started_at = _utcnow_iso()

    def set_step(self, job_id: str, step: str) -> None:
        with self._lock:
            record = self._require_unsafe(job_id)
            record.current_step = step

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            record = self._require_unsafe(job_id)
            record.logs.append(f"[{_utcnow_iso()}] {message}")

    def succeed(self, job_id: str) -> None:
        with self._lock:
            record = self._require_unsafe(job_id)
            record.status = "succeeded"
            record.finished_at = _utcnow_iso()

    def fail(self, job_id: str, error_message: str) -> None:
        with self._lock:
            record = self._require_unsafe(job_id)
            record.status = "failed"
            record.error_message = error_message
            record.finished_at = _utcnow_iso()

    def get_summary(self, job_id: str) -> dict[str, object] | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            return record.summary()

    def get_detail(self, job_id: str) -> dict[str, object] | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            return record.detail()

    def list_summaries(self) -> list[dict[str, object]]:
        with self._lock:
            values = list(self._jobs.values())
        values.reverse()
        return [item.summary() for item in values]

    def _require_unsafe(self, job_id: str) -> JobRecord:
        record = self._jobs.get(job_id)
        if record is None:
            raise KeyError(f"Unknown job id: {job_id}")
        return record

    def _trim_unsafe(self) -> None:
        while len(self._jobs) > self._max_jobs:
            self._jobs.popitem(last=False)
