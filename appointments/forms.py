from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from django import forms
from django.utils import timezone

from clinics.models import Clinic, Doctor
from clinicflow.access import scoped_doctors, user_clinics
from clinicflow.forms import style_form
from patients.models import Patient

from .models import Appointment, AppointmentStatus


class AppointmentForm(forms.ModelForm):
    scheduled_local = forms.DateTimeField(
        label="Appointment date and time",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
        help_text="Interpreted in the selected clinic's timezone.",
    )

    class Meta:
        model = Appointment
        fields = ["patient", "clinic", "doctor", "duration_minutes", "reason"]

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        clinics = user_clinics(user).filter(is_active=True)
        if self.instance.pk and self.instance.clinic_id:
            clinics = (clinics | Clinic.objects.filter(pk=self.instance.clinic_id)).distinct()
        self.fields["clinic"].queryset = clinics
        self.fields["doctor"].queryset = scoped_doctors(user).filter(is_active=True)
        self.fields["patient"].queryset = Patient.objects.all()
        if self.instance.pk and self.instance.scheduled_at:
            tz = ZoneInfo(self.instance.clinic.timezone)
            local = timezone.localtime(self.instance.scheduled_at, timezone=tz)
            self.fields["scheduled_local"].initial = local.strftime("%Y-%m-%dT%H:%M")
        style_form(self)

    def clean(self):
        cleaned = super().clean()
        clinic: Clinic | None = cleaned.get("clinic")
        doctor: Doctor | None = cleaned.get("doctor")
        scheduled_local = cleaned.get("scheduled_local")
        duration = cleaned.get("duration_minutes") or 30

        if clinic and not clinic.is_active and not (self.instance and self.instance.pk):
            self.add_error("clinic", "Inactive clinics cannot be used for new bookings.")

        if clinic and doctor and not doctor.clinics.filter(pk=clinic.pk).exists():
            self.add_error("doctor", "Selected doctor is not linked to the chosen clinic.")

        if doctor and not doctor.is_active:
            self.add_error("doctor", "Doctor is not active.")

        if clinic and scheduled_local:
            tz = ZoneInfo(clinic.timezone)
            naive = scheduled_local.replace(tzinfo=None) if timezone.is_aware(scheduled_local) else scheduled_local
            aware = naive.replace(tzinfo=tz)
            utc_dt = aware.astimezone(ZoneInfo("UTC"))
            if utc_dt < timezone.now():
                self.add_error("scheduled_local", "Appointment time cannot be in the past.")
            else:
                cleaned["scheduled_at"] = utc_dt
                if doctor:
                    start = utc_dt
                    end = utc_dt + timedelta(minutes=duration)
                    qs = Appointment.objects.filter(
                        doctor=doctor,
                        status=AppointmentStatus.SCHEDULED,
                    )
                    if self.instance.pk:
                        qs = qs.exclude(pk=self.instance.pk)
                    for other in qs.only("scheduled_at", "duration_minutes"):
                        other_end = other.scheduled_at + timedelta(minutes=other.duration_minutes)
                        if start < other_end and other.scheduled_at < end:
                            self.add_error(
                                "scheduled_local",
                                "Doctor already booked at this time.",
                            )
                            break
        return cleaned

    def save(self, commit: bool = True) -> Appointment:
        appointment = super().save(commit=False)
        appointment.scheduled_at = self.cleaned_data["scheduled_at"]
        if self.instance.pk:
            previous = Appointment.objects.get(pk=self.instance.pk)
            if previous.scheduled_at != appointment.scheduled_at:
                appointment.reminder_sent = False
                appointment.reminder_sent_at = None
        if commit:
            appointment.save()
        return appointment
