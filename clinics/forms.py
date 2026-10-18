from __future__ import annotations

from django import forms

from clinicflow.forms import style_form
from clinicflow.validators import e164_phone_validator

from .models import Clinic, Doctor, DoctorClinic, StaffRole


class ClinicForm(forms.ModelForm):
    class Meta:
        model = Clinic
        fields = [
            "name",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "phone",
            "timezone",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)


class DoctorForm(forms.ModelForm):
    clinics = forms.ModelMultipleChoiceField(
        queryset=Clinic.objects.filter(is_active=True),
        widget=forms.SelectMultiple,
        required=True,
        help_text="Active doctors must belong to at least one clinic.",
    )
    consulting_days = forms.CharField(
        max_length=50,
        required=False,
        help_text="Optional, e.g. Mon,Wed,Fri (applied to all selected clinics).",
    )

    class Meta:
        model = Doctor
        fields = [
            "full_name",
            "specialization",
            "license_number",
            "email",
            "is_active",
            "clinics",
        ]

    def __init__(self, *args, clinic_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if clinic_queryset is not None:
            self.fields["clinics"].queryset = clinic_queryset
        if self.instance.pk:
            # Prefetch clinic affiliations cache data to minimize database overhead loops
            self.fields["clinics"].initial = self.instance.clinics.all()
            
            # Pre-populate the input fields with current consulting days if uniform
            first_link = self.instance.clinic_affiliations.first()
            if first_link and not self.files and not self.data:
                self.initial["consulting_days"] = first_link.consulting_days
                
        style_form(self)
        for name in ("clinics",):
            self.fields[name].widget.attrs["class"] = "form-check-input"

    def save(self, commit: bool = True) -> Doctor:
        doctor = super().save(commit=commit)
        if commit:
            self._sync_clinics(doctor)
        else:
            # FIX: Plugs the commit=False structural gap by chaining tracking tasks into Django's save_m2m hook architecture
            self.save_m2m = lambda: self._sync_clinics(doctor)
        return doctor

    def _sync_clinics(self, doctor: Doctor) -> None:
        selected = list(self.cleaned_data["clinics"])
        days = self.cleaned_data.get("consulting_days") or ""
        selected_ids = {c.pk for c in selected}
        
        existing = {link.clinic_id: link for link in doctor.clinic_affiliations.all()}
        
        for clinic in selected:
            if clinic.pk not in existing:
                DoctorClinic.objects.create(
                    doctor=doctor, clinic=clinic, consulting_days=days
                )
            else:
                link = existing[clinic.pk]
                if link.consulting_days != days:
                    link.consulting_days = days
                    link.save(update_fields=["consulting_days"])
                    
        doctor.clinic_affiliations.exclude(clinic_id__in=selected_ids).delete()
