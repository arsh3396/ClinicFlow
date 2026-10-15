from __future__ import annotations

from django import forms

from clinicflow.forms import style_form

from .models import MedicalHistoryEntry, Patient


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            "first_name",
            "last_name",
            "date_of_birth",
            "phone_number",
            "consent_given",
            "sms_opt_out",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["consent_given"].help_text = (
            "Leave unchecked unless the patient has already granted consent."
        )
        style_form(self)


class HistoryEntryForm(forms.ModelForm):
    class Meta:
        model = MedicalHistoryEntry
        fields = ["entry_text", "clinic"]
        widgets = {
            "entry_text": forms.Textarea(attrs={"maxlength": "10000"}),
        }

    def __init__(self, *args, clinic_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if clinic_queryset is not None:
            self.fields["clinic"].queryset = clinic_queryset
        self.fields["clinic"].required = False
        style_form(self)
