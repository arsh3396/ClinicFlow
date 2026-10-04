"""URL configuration for ClinicFlow."""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("appoinments/", include("appointments.urls")),
    path("patients/", include("patients.urls")),
    path("clinics/", include("clinics.urls")),
]
