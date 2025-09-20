from __future__ import annotations

import threading
from typing import Dict, Optional


class JobProgress:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Optional[int]]] = {}

    def start(self, job_id: str, total: int = 0) -> None:
        with self._lock:
            self._jobs[job_id] = {"processed": 0, "total": total, "status": "running"}

    def set_total(self, job_id: str, total: int) -> None:
        with self._lock:
            if job_id not in self._jobs:
                return
            self._jobs[job_id]["total"] = total

    def update(self, job_id: str, processed: int) -> None:
        with self._lock:
            if job_id not in self._jobs:
                return
            self._jobs[job_id]["processed"] = processed

    def finish(self, job_id: str) -> None:
        with self._lock:
            if job_id not in self._jobs:
                return
            self._jobs[job_id]["status"] = "completed"

    def error(self, job_id: str) -> None:
        with self._lock:
            if job_id not in self._jobs:
                return
            self._jobs[job_id]["status"] = "error"

    def pop(self, job_id: str) -> Optional[Dict[str, Optional[int]]]:
        with self._lock:
            return self._jobs.pop(job_id, None)

    def snapshot(self, job_id: str) -> Optional[Dict[str, Optional[int]]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return dict(job)


progress_tracker = JobProgress()

__all__ = ["progress_tracker"]
