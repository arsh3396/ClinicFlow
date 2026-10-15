from django.urls import path

from . import views

app_name = "appointments"

urlpatterns = [
    path("", views.appointment_list, name="list"),
    path("new/", views.appointment_create, name="create"),
    path("schedule/", views.daily_schedule, name="schedule"),
    path("<int:pk>/", views.appointment_detail, name="detail"),
    path("<int:pk>/reschedule/", views.appointment_reschedule, name="reschedule"),
    path("<int:pk>/status/", views.appointment_status, name="status"),
]
