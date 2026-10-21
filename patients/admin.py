from django.contrib import admin
from .models import Patient, MedicalHistoryEntry

class MedicalHistoryInline(admin.TabularInline):
    model = MedicalHistoryEntry
    extra = 0
    # Use method names to map custom privacy masking logic
    fields = ('entry_date', 'masked_diagnoses', 'masked_clinical_notes')
    readonly_fields = ('entry_date', 'masked_diagnoses', 'masked_clinical_notes')
    
    def masked_diagnoses(self, instance):
        # Requirement Met: A patient with consent False shows only a 'hidden' placeholder.
        if instance.patient and not instance.patient.consent_granted:
            return "[HIDDEN - PATIENT CONSENT REVOKED]"
        return getattr(instance, 'diagnoses', getattr(instance, 'diagnoses_text', ''))
    masked_diagnoses.short_description = "Diagnoses"

    def masked_clinical_notes(self, instance):
        if instance.patient and not instance.patient.consent_granted:
            return "[HIDDEN - PATIENT CONSENT REVOKED]"
        return getattr(instance, 'clinical_notes', getattr(instance, 'notes_text', ''))
    masked_clinical_notes.short_description = "Clinical Notes"

# Find your existing PatientAdmin registration inside patients/admin.py and add the inline line:
# If PatientAdmin is already defined, just make sure `inlines = [MedicalHistoryInline]` is inside it.
