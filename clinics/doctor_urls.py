from django.urls import path

from clinics import views

app_name = "doctors"

urlpatterns = [
    path("", views.doctor_list, name="list"),
    path("new/", views.doctor_create, name="create"),
    path("<int:pk>/edit/", views.doctor_update, name="update"),
]
