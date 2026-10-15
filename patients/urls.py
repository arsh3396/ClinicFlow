from django.urls import path

from . import views

app_name = "patients"

urlpatterns = [
    path("", views.patient_list, name="list"),
    path("new/", views.patient_create, name="create"),
    path("<int:pk>/", views.patient_detail, name="detail"),
    path("<int:pk>/edit/", views.patient_update, name="update"),
    path("<int:pk>/consent/", views.consent_confirm, name="consent"),
    path("<int:pk>/history/", views.history_create, name="history_create"),
]
