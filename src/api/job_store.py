"""In-memory job store for asynchronous underwriting evaluations."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


class EvaluationJobStore:
    """Simple process-local job state storage for status/result endpoints."""

    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}

    def create_job(self, job_id: str, application_id: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "job_id": job_id,
            "application_id": application_id,
            "status": "QUEUED",
            "current_agent": "FetchData",
            "progress_pct": 0,
            "created_at": now,
            "updated_at": now,
            "agent_progress": {
                "FetchData": "PENDING",
                "DocReview": "PENDING",
                "RiskScoring": "PENDING",
                "Compliance": "PENDING",
            },
            "result": None,
            "error": None,
        }
        self._jobs[job_id] = record
        return deepcopy(record)

    def update_job(self, job_id: str, **updates: Any) -> dict[str, Any]:
        record = self._jobs[job_id]
        record.update(updates)
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        return deepcopy(record)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        record = self._jobs.get(job_id)
        if record is None:
            return None
        return deepcopy(record)
