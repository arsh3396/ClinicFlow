from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models

from clinicflow.validators import TimezoneValidator, e164_phone_validator


class Clinic(models.Model):
    name: models.CharField = models.CharField(max_length=150)
    address_line1: models.CharField = models.CharField(max_length=255)
    address_line2: models.CharField = models.CharField(max_length=255, blank=True)
    city: models.CharField = models.CharField(max_length=100)
    state: models.CharField = models.CharField(max_length=100)
    postal_code: models.CharField = models.CharField(max_length=20)
    phone: models.CharField = models.CharField(
        max_length=20,
        validators=[e164_phone_validator],
        help_text="E.164 format, e.g. +919876543210",
    )
    timezone: models.CharField = models.CharField(
        max_length=64,
        default="Asia/Kolkata",
        validators=[TimezoneValidator()],
        help_text="IANA timezone name used when rendering local appointment times.",
    )
    is_active: models.BooleanField = models.BooleanField(default=True)
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["name"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["name", "postal_code"],
                name="uniq_clinic_name_postal_code",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Doctor(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="doctor_profile",
    )
    full_name: models.CharField = models.CharField(max_length=150)
    specialization: models.CharField = models.CharField(max_length=100)
    license_number: models.CharField = models.CharField(max_length=50, unique=True)
    email: models.EmailField = models.EmailField(blank=True)
    clinics = models.ManyToManyField(
        Clinic,
        through="DoctorClinic",
        related_name="doctors",
    )
    is_active: models.BooleanField = models.BooleanField(default=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["full_name"]

    def __str__(self) -> str:
        return self.full_name

    @property
    def last_name(self) -> str:
        parts = self.full_name.strip().split()
        return parts[-1] if parts else self.full_name


class DoctorClinic(models.Model):
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="clinic_affiliations",
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="doctor_affiliations",
    )
    consulting_days: models.CharField = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optional consulting days, e.g. Mon,Wed,Fri",
    )

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["doctor", "clinic"],
                name="uniq_doctor_clinic",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.doctor} @ {self.clinic}"


class StaffRole(models.TextChoices):
    CLINIC_ADMIN = "CLINIC_ADMIN", "Clinic Admin"
    RECEPTIONIST = "RECEPTIONIST", "Receptionist"
    DOCTOR = "DOCTOR", "Doctor"


class StaffProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="staff_profile",
    )
    role: models.CharField = models.CharField(max_length=20, choices=StaffRole.choices)
    clinics = models.ManyToManyField(Clinic, related_name="staff_members", blank=True)

    def __str__(self) -> str:
        return f"{self.user} ({self.get_role_display()})"
