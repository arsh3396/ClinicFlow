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
        
        # FIXED: Dynamic Clinic Filter Check for Doctor Field Pool
        # If the form is processing incoming POST data, filter doctor options down to that chosen clinic branch immediately.
        if self.is_bound and self.data.get("clinic"):
            try:
                clinic_id = int(self.data.get("clinic"))
                self.fields["doctor"].queryset = scoped_doctors(user).filter(
                    clinic_affiliations__clinic_id=clinic_id,
                    is_active=True
                ).distinct()
            except (ValueError, TypeError):
                self.fields["doctor"].queryset = scoped_doctors(user).filter(is_active=True)
        elif self.instance.pk and self.instance.clinic:
            self.fields["doctor"].queryset = self.instance.clinic.doctors.filter(is_active=True)
        else:
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
            # FIXED: Updated validation text string to match Section 8 constraints exactly
            self.add_error("doctor", "Doctor not linked to the clinic.")

        if doctor and not doctor.is_active:
            self.add_error("doctor", "Doctor is not active.")

        if clinic and scheduled_local:
            tz = ZoneInfo(clinic.timezone)
            naive = scheduled_local.replace(tzinfo=None) if timezone.is_aware(scheduled_local) else scheduled_local
            aware = naive.replace(tzinfo=tz)
            utc_dt = aware.astimezone(ZoneInfo("UTC"))
            if utc_dt < timezone.now():
                # FIXED: Updated string constraint message to match Section 8 requirements
                self.add_error("scheduled_local", "Past date.")
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
                            # FIXED: Enforced the exact specified string constraint message 
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
