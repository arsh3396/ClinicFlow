from django.urls import path
from clinicflow.access import get_staff_role, doctor_for_user, user_clinics, scoped_doctors


from . import views

app_name = "appointments"

urlpatterns = [
    path("", views.appointment_list, name="appointment_list"),
    path("new/", views.appointment_create, name="appointment_create"),
    path("schedule/", views.daily_schedule, name="schedule"),
    path("<int:pk>/", views.appointment_detail, name="detail"),
    path("<int:pk>/reschedule/", views.appointment_reschedule, name="reschedule"),
    path('<int:pk>/edit/', views.appointment_update, name='appointment_update'),
     path("dashboard/", views.workspace_dashboard, name="workspace_dashboard"),
]
