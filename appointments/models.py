from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q


class AppointmentStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Scheduled"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"
    NO_SHOW = "NO_SHOW", "No-Show"


class Appointment(models.Model):
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    doctor = models.ForeignKey(
        "clinics.Doctor",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    scheduled_at: models.DateTimeField = models.DateTimeField(
        help_text="Stored in UTC (USE_TZ=True). Render in the clinic timezone.",
    )
    duration_minutes: models.PositiveSmallIntegerField = models.PositiveSmallIntegerField(
        default=30,
    )
    status: models.CharField = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.SCHEDULED,
    )
    reason: models.CharField = models.CharField(
        max_length=255,
        blank=True,
        help_text="Must not contain clinical detail.",
    )
    reminder_sent: models.BooleanField = models.BooleanField(default=False, db_index=True)
    reminder_sent_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_appointments",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)
    reminder_sent = models.BooleanField(default=False)
    class Meta:
        ordering: ClassVar[list[str]] = ["scheduled_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["status", "reminder_sent", "scheduled_at"],
                name="idx_appt_reminder_scan",
            ),
        ]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            # Partial unique: blocks double-booking a doctor at the same start
            # time among SCHEDULED rows (FR-APT-4 / Section 3.0).
            models.UniqueConstraint(
                fields=["doctor", "scheduled_at"],
                condition=Q(status=AppointmentStatus.SCHEDULED),
                name="uniq_doctor_scheduled_at_when_scheduled",
            ),
        ]

    def __str__(self) -> str:
        return f"Appt #{self.pk} {self.scheduled_at}"


class SMSProvider(models.TextChoices):
    TWILIO = "twilio", "Twilio"
    MOCK = "mock", "Mock"


class SMSLogStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class SMSLog(models.Model):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="sms_logs",
    )
    to_number: models.CharField = models.CharField(max_length=16)
    body: models.CharField = models.CharField(max_length=320)
    provider: models.CharField = models.CharField(max_length=20, choices=SMSProvider.choices)
    provider_message_sid: models.CharField = models.CharField(max_length=64, blank=True)
    status: models.CharField = models.CharField(max_length=20, choices=SMSLogStatus.choices)
    error_message: models.CharField = models.CharField(max_length=255, blank=True)
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        return f"SMS {self.status} for appointment {self.appointment_id}"
