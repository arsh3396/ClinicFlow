"""URL configuration for ClinicFlow."""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from clinicflow import views as core_views
from patients import views as patient_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    # Change line 23 from a RedirectView to your core workspace home view
    path('', core_views.dashboard, name='dashboard'),

    path("clinics/", include("clinics.urls")),
    path("doctors/", include("clinics.doctor_urls")),
    path("patients/", include("patients.urls")),
    path("search/history/", patient_views.history_search, name="history_search"),
    path("appointments/", include("appointments.urls")),
    path("schedule/", patient_views.history_search, name="schedule_alias_unused"),
]
