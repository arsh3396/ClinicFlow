from django.urls import path

from . import views

app_name = "clinics"

urlpatterns = [
    path("", views.clinic_list, name="list"),
    path("new/", views.clinic_create, name="create"),
    path("<int:pk>/edit/", views.clinic_update, name="update"),
    path("<int:pk>/deactivate/", views.clinic_deactivate, name="deactivate"),
]
