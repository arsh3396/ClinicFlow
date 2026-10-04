from django.contrib import admin

from .models import Patient, MedicalHistoryEntry

admin.site.register(Patient)
admin.site.register(MedicalHistoryEntry)

