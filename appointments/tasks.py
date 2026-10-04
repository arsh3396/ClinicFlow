"""Celery task signatures (Section 4.3). Implementations land in the next phase."""

from __future__ import annotations

from celery import shared_task


@shared_task
def scan_and_queue_reminders() -> int:
    """Periodic Beat entrypoint — returns count of send tasks enqueued."""
    return 0


@shared_task(bind=True, max_retries=3, acks_late=True)
def send_appointment_reminder(self, appointment_id: int) -> str:
    """
    Returns one of: SENT, SKIPPED_ALREADY_SENT, SKIPPED_CANCELLED,
    SKIPPED_OPT_OUT, FAILED.
    """
    return "SKIPPED_ALREADY_SENT"
