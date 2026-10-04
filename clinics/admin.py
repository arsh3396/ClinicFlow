from django.contrib import admin

from .models import Clinic, Doctor, DoctorClinic, StaffProfile

admin.site.register(Clinic)
admin.site.register(Doctor)
admin.site.register(DoctorClinic)
admin.site.register(StaffProfile)

