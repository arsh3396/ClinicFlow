from django.urls import path

from . import views

app_name = "patients"

urlpatterns = [
    path("", views.patient_list, name="patient_list"),
    path("new/", views.patient_create, name="patient_create"),
    path("<int:pk>/", views.patient_detail, name="patient_detail"),
    path("<int:pk>/edit/", views.patient_update, name="patient_update"),
    path("<int:pk>/consent/", views.consent_confirm, name="consent_confirm"),
    path("history/<int:pk>/", views.history_create, name="history_create"),
    path("search/history", views.history_search, name="history_search"),
]
