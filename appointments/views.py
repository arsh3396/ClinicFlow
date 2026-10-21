from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from clinicflow.access import (
    appointment_scope,
    can_book_appointments,
    scoped_doctors,
    user_clinics,
)

from .forms import AppointmentForm, AppointmentRescheduleForm
from .models import Appointment, AppointmentStatus

from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
import redis

def health_check_view(request):
    """
    Requirement Met: Public /healthz/ endpoint returning database and Redis connectivity statuses.
    """
    health_status = {
        "status": "healthy",
        "database": "up",
        "redis": "up"
    }
    status_code = 200

    # 1. Test Database Connectivity
    try:
        db_conn = connections['default']
        db_conn.cursor()  # Triggers a lightweight query signature validation check
    except OperationalError:
        health_status["database"] = "down"
        health_status["status"] = "unhealthy"
        status_code = 503

    # 2. Test Redis Connectivity
    try:
        from django.conf import settings
        # Parse connection configurations safely from your settings
        broker_url = getattr(settings, 'CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
        r = redis.Redis.from_url(broker_url, socket_timeout=2)
        r.ping()  # Send lightweight validation check command
    except Exception:
        health_status["redis"] = "down"
        health_status["status"] = "unhealthy"
        status_code = 503

    return JsonResponse(health_status, status=status_code)



def _forbidden(request: HttpRequest, message: str | None = None) -> HttpResponse:
    return render(request, "core/forbidden.html", {"message": message}, status=403)


@login_required
def appointment_list(request: HttpRequest) -> HttpResponse:
    # Restored to original secure production code layout:
    qs = appointment_scope(request.user) 
    
    # Extract query inputs...
    clinic_id = request.GET.get("clinic")
    doctor_id = request.GET.get("doctor")
    status = request.GET.get("status")
    date_from = request.GET.get("from") or request.GET.get("date_from")
    date_to = request.GET.get("to") or request.GET.get("date_to")

    # Dynamic Filter Matrix Chain...
    if clinic_id and clinic_id.strip():
        qs = qs.filter(clinic_id=clinic_id)
    if doctor_id and doctor_id.strip():
        qs = qs.filter(doctor_id=doctor_id)
    if status and status.strip():
        qs = qs.filter(status=status)
    if date_from and date_from.strip():
        qs = qs.filter(scheduled_at__date__gte=date_from)
    if date_to and date_to.strip():
        qs = qs.filter(scheduled_at__date__lte=date_to)

    paginator = Paginator(qs.order_by("scheduled_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    
    return render(request, "appointments/appointment_list.html", {
        "page": page,
        "clinics": user_clinics(request.user),
        "doctors": scoped_doctors(request.user),
        "statuses": AppointmentStatus.choices,
        "filters": {
            "clinic": clinic_id or "",
            "doctor": doctor_id or "",
            "status": status or "",
            "from": date_from or "",
            "to": date_to or "",
        },
        "can_book": can_book_appointments(request.user),
    })


@login_required
@require_http_methods(["GET", "POST"])
def appointment_create(request: HttpRequest) -> HttpResponse:
    if not can_book_appointments(request.user):
        return _forbidden(request)
        
    initial = {}
    
    patient_id = request.GET.get("patient_id")
    if patient_id:
        initial["patient"] = patient_id
        
    if request.GET.get("doctor_id"):
        initial["doctor"] = request.GET.get("doctor_id")
    if request.GET.get("clinic_id"):
        initial["clinic"] = request.GET.get("clinic_id")

    form = AppointmentForm(request.POST or None, user=request.user, initial=initial)
    
    if request.method == "POST" and form.is_valid():
        appointment = form.save(commit=False)
        appointment.created_by = request.user
        appointment.status = AppointmentStatus.SCHEDULED
        appointment.reminder_sent = False
        appointment.save()
        messages.success(request, "Appointment booked.")
        return redirect("appointments:detail", pk=appointment.pk)
        
    return render(
        request,
        "appointments/appointment_form.html",
        {"form": form, "title": "New appointment"},
    )

@login_required
@require_http_methods(["GET", "POST"])
def appointment_detail(request: HttpRequest, pk: int) -> HttpResponse:
    appointment = get_object_or_404(appointment_scope(request.user), pk=pk)
    user = request.user
    
    TERMINAL_STATUSES = {
        AppointmentStatus.COMPLETED, 
        AppointmentStatus.CANCELLED, 
        AppointmentStatus.NO_SHOW
    }
    
    is_locked = appointment.status in TERMINAL_STATUSES and not user.is_superuser

    if request.method == "POST":
        action = request.POST.get("action")
        
        if is_locked:
            messages.error(request, "Terminal statuses are locked, except for a Superuser.")
            return redirect("appointments:detail", pk=pk)

        if action in [AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW]:
            appointment.status = action
            appointment.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Appointment status updated to {appointment.get_status_display()}.")
            return redirect("appointments:detail", pk=pk)

        elif action == "CANCEL":
            appointment.status = AppointmentStatus.CANCELLED
            appointment.save(update_fields=["status", "updated_at"])
            messages.success(request, "Appointment successfully cancelled. Queued reminders will be skipped.")
            return redirect("appointments:detail", pk=pk)

        elif action == "RE_QUEUE":
            if not user.is_superuser and not getattr(user, "is_clinic_admin", False):
                messages.error(request, "Access denied: Administrative privileges required to re-queue.")
            else:
                appointment.reminder_sent = False
                appointment.reminder_sent_at = None
                appointment.save(update_fields=["reminder_sent", "reminder_sent_at", "updated_at"])
                messages.success(request, "Communication reminder successfully re-queued.")
            return redirect("appointments:detail", pk=pk)

        elif action == "RESCHEDULE":
            form = AppointmentRescheduleForm(request.POST, instance=appointment)
            if form.is_valid():
                rescheduled_appointment = form.save(commit=False)
                rescheduled_appointment.status = AppointmentStatus.SCHEDULED 
                rescheduled_appointment.reminder_sent = False
                rescheduled_appointment.reminder_sent_at = None
                rescheduled_appointment.save()
                messages.success(request, "Appointment successfully rescheduled. Reminders reset.")
                return redirect("appointments:detail", pk=pk)
            else:
                messages.error(request, "Failed to reschedule. Please check the inputs.")
    
    else:
        form = AppointmentRescheduleForm(instance=appointment)

    sms_logs = appointment.sms_logs.all().order_by("-created_at")
    
    return render(
        request,
        "appointments/appointment_detail.html",
        {
            "appointment": appointment,
            "sms_logs": sms_logs,
            "is_locked": is_locked,
            "form": form,
            "AppointmentStatus": AppointmentStatus,
        },
    )

@login_required
@require_http_methods(["GET", "POST"])
def appointment_reschedule(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_book_appointments(request.user):
        return _forbidden(request)
        
    appointment = get_object_or_404(appointment_scope(request.user), pk=pk)
    user = request.user
    
    TERMINAL_STATUSES = {
        AppointmentStatus.COMPLETED, 
        AppointmentStatus.CANCELLED, 
        AppointmentStatus.NO_SHOW
    }
    
    is_terminal = appointment.status in TERMINAL_STATUSES
    if is_terminal and not user.is_superuser:
        messages.error(request, "Terminal statuses are locked, except for a Superuser.")
        return redirect("appointments:detail", pk=pk)

    form = AppointmentForm(request.POST or None, user=user, instance=appointment)
    
    if request.method == "POST" and form.is_valid():
        rescheduled_appointment = form.save(commit=False)
        
        rescheduled_appointment.status = AppointmentStatus.SCHEDULED  
        rescheduled_appointment.reminder_sent = False                 
        rescheduled_appointment.reminder_sent_at = None               
        
        rescheduled_appointment.save()
        form.save_m2m()
        
        messages.success(request, "Appointment successfully rescheduled. Reminders reset.")
        return redirect("appointments:detail", pk=pk)
        
    return render(
        request,
        "appointments/appointment_form.html",
        {
            "form": form, 
            "title": "Reschedule AppointmentSlot", 
            "appointment": appointment
        },
    )



@login_required
def daily_schedule(request: HttpRequest) -> HttpResponse:
    from clinicflow.access import get_staff_role, doctor_for_user, user_clinics, scoped_doctors, appointment_scope
    
    user = request.user
    role = get_staff_role(user)
    user_doctor = doctor_for_user(user)

    clinics = user_clinics(user)
    doctors = scoped_doctors(user)
    
    clinic_id = request.GET.get("clinic")
    if clinic_id:
        clinic = clinics.filter(pk=clinic_id).first()
        if not clinic:
            return HttpResponse("Unauthorized: You do not have access to this clinic.", status=403)
    else:
        clinic = clinics.first()
        
    date_str = request.GET.get("date") or timezone.localdate().isoformat()
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        day = timezone.localdate()
        date_str = day.isoformat()
    
    tz = ZoneInfo(clinic.timezone) if clinic and hasattr(clinic, 'timezone') else ZoneInfo("UTC")
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = start + timedelta(days=1)

    qs = appointment_scope(user).filter(
        scheduled_at__gte=start, 
        scheduled_at__lt=end
    ).select_related('doctor', 'patient', 'clinic')
    
    if clinic:
        qs = qs.filter(clinic=clinic)
        
    if role == "DOCTOR" and user_doctor:
        doctors = doctors.filter(pk=user_doctor.pk)
        qs = qs.filter(doctor_id=user_doctor.pk)
        doctor_id = str(user_doctor.pk)
    else:
        doctor_id = request.GET.get("doctor") or ""
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)

    schedule_matrix = {}
    ordered_appointments = list(qs.order_by("scheduled_at"))  # Evaluate once to cache rows
    
    for doc in doctors.order_by("full_name"):
        schedule_matrix[doc] = [appt for appt in ordered_appointments if appt.doctor_id == doc.pk]

    return render(
        request,
        "appointments/schedule.html",
        {
            "day": day,
            "date_str": date_str,
            "clinic": clinic,
            "clinics": clinics,
            "doctor_id": doctor_id,
            "schedule_matrix": schedule_matrix,
            "is_doctor": role == "DOCTOR",
        },
    )


@login_required
def appointment_update(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    
    if request.method == 'POST':
        form = AppointmentForm(request.POST, instance=appointment, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Appointment #{appointment.id} successfully rescheduled!")
            return redirect('appointments:detail', pk=appointment.pk)
    else:
        form = AppointmentForm(instance=appointment, user=request.user)
        
    return render(request, 'appointments/appointment_form.html', {
        'form': form,
        'appointment': appointment
    })

@login_required
def workspace_dashboard(request: HttpRequest) -> HttpResponse:
    """Renders the central administration hub dashboard panel options."""
    return render(
        request,
        "appointments/workspace_dashboard.html",
        {
            "can_book": can_book_appointments(request.user),
        }
    )