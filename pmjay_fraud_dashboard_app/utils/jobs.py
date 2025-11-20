"""
Background Job Abstractions

This module defines the architectural interfaces for executing long-running asynchronous tasks.
It enforces a strict separation of concerns to allow seamless migration between backends (e.g. from Sync -> Celery -> SQS).
"""
import uuid
import datetime
from typing import Dict, Any, Optional

class JobStore:
    """
    Interface for querying and persisting job state.
    Implementation will typically wrap Django Models (e.g., BackgroundJob).
    """
    def create_job(self, task_name: str, payload: Dict[str, Any], owner_id: Optional[str] = None, idempotency_key: Optional[str] = None, payload_version: str = "1.0") -> str:
        raise NotImplementedError

    def get_job(self, job_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def update_job_status(self, job_id: str, status: str, progress: int = 0) -> None:
        raise NotImplementedError
        
    def add_artifact(self, job_id: str, artifact_name: str, artifact_url: str, artifact_type: str) -> None:
        raise NotImplementedError


class JobDispatcher:
    """
    Interface used by the synchronous Web layer to submit work.
    """
    def __init__(self, store: JobStore):
        self.store = store

    def enqueue(self, task_name: str, payload: Dict[str, Any], owner_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> str:
        """Puts a job into the queue immediately."""
        raise NotImplementedError

    def schedule(self, task_name: str, payload: Dict[str, Any], execute_at: datetime.datetime, owner_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> str:
        """Schedules a job for future execution."""
        raise NotImplementedError

    def cancel(self, job_id: str) -> bool:
        """Attempts to cancel a Queued, Pending, or Running job."""
        raise NotImplementedError


class JobExecutor:
    """
    Interface for the worker node executing the job logic.
    Provides hooks for lifecycle management (progress tracking, failure catching).
    """
    def __init__(self, store: JobStore):
        self.store = store
        
    def execute(self, job_id: str) -> None:
        """Wraps the actual task function with observability, state updates, and error handling."""
        raise NotImplementedError
        
    def report_progress(self, job_id: str, progress: int) -> None:
        raise NotImplementedError
