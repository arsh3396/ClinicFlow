from django.urls import path

from . import views

app_name = "clinics"

urlpatterns = [
     # Clinic Routes
    path("", views.clinic_list, name="clinic_list"),
    path("new/", views.clinic_create, name="create"),
    path("<int:pk>/edit/", views.clinic_update, name="update"),
    path("<int:pk>/deactivate/", views.clinic_deactivate, name="deactivate"),
    
    # Doctor Routes (Added to resolve the NoReverseMatch error)
    path("doctors/", views.doctor_list, name="doctor_list"),
    path("doctors/new/", views.doctor_create, name="doctor_create"),
    path("doctors/<int:pk>/edit/", views.doctor_update, name="doctor_update"),
]
