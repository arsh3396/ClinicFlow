from __future__ import annotations

from typing import ClassVar, Self

from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from django.utils import timezone

from clinicflow.validators import e164_phone_validator

from datetime import date
from typing import ClassVar
from django.db import models
from django.conf import settings
from django.utils import timezone

class Patient(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('UNKNOWN', 'Not Specified'),
    ]
    
    # Corrected: Replaced colons (:) with equal signs (=) so Django registers the fields
    first_name = models.CharField(max_length=75)
    last_name = models.CharField(max_length=75)
    date_of_birth = models.DateField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        default='UNKNOWN',
    )

    phone_number = models.CharField(
        max_length=16,
        validators=[e164_phone_validator],
        help_text="E.164 format, e.g. +919876543210",
    )
    consent_given = models.BooleanField(default=False)
    consent_updated_at = models.DateTimeField(null=True, blank=True)
    consent_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consent_updates",
    )
    sms_opt_out = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(
                fields=["last_name", "first_name"],
                name="idx_patient_name",
            ),
            models.Index(fields=["phone_number"], name="idx_patient_phone"),
        ]

    def __str__(self) -> str:
        return f"{self.last_name}, {self.first_name}"

    def set_consent(self, given: bool, actor) -> None:
        if self.consent_given == given and self.pk:
            return
        self.consent_given = given
        self.consent_updated_at = timezone.now()
        self.consent_updated_by = actor
        self.save()

    @property
    def name(self) -> str:
        """Combines names to satisfy the '{{ patient.name }}' lookups."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def phone(self) -> str:
        """Maps phone field directly to satisfy '{{ patient.phone }}' lookups."""
        return self.phone_number

    @property
    def age(self) -> str:
        """Dynamically calculates age based on date_of_birth safely."""
        if self.date_of_birth:
            today = date.today()
            has_birthday_passed = (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            calculated_age = today.year - self.date_of_birth.year - has_birthday_passed
            return str(calculated_age)
        return "N/A"




class ConsentedHistoryQuerySet(models.QuerySet["MedicalHistoryEntry"]):
    def consented(self) -> Self:
        return self.filter(patient__consent_given=True)

    def all_unfiltered(self) -> Self:
        return self


class MedicalHistoryManager(models.Manager.from_queryset(ConsentedHistoryQuerySet)):
    pass


class MedicalHistoryEntry(models.Model):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="history_entries",
    )
    author = models.ForeignKey(
        "clinics.Doctor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authored_history_entries",
    )
    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="history_entries",
    )
    entry_text: models.TextField = models.TextField(
        validators=[MaxLengthValidator(10_000)],
    )
    recorded_at: models.DateTimeField = models.DateTimeField(default=timezone.now)

    objects = MedicalHistoryManager()

    class Meta:
        ordering: ClassVar[list[str]] = ["-recorded_at"]
        verbose_name_plural = "medical history entries"

    def __str__(self) -> str:
        return f"History #{self.pk} for {self.patient_id}"
