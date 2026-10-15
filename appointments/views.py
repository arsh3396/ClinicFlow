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

from .forms import AppointmentForm
from .models import Appointment, AppointmentStatus


def _forbidden(request: HttpRequest, message: str | None = None) -> HttpResponse:
    return render(request, "core/forbidden.html", {"message": message}, status=403)


@login_required
def appointment_list(request: HttpRequest) -> HttpResponse:
    qs = appointment_scope(request.user)
    clinic_id = request.GET.get("clinic")
    doctor_id = request.GET.get("doctor")
    status = request.GET.get("status")
    date_from = request.GET.get("from")
    date_to = request.GET.get("to")

    if clinic_id:
        qs = qs.filter(clinic_id=clinic_id)
    if doctor_id:
        qs = qs.filter(doctor_id=doctor_id)
    if status:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(scheduled_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(scheduled_at__date__lte=date_to)

    paginator = Paginator(qs.order_by("scheduled_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "appointments/appointment_list.html",
        {
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
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def appointment_create(request: HttpRequest) -> HttpResponse:
    if not can_book_appointments(request.user):
        return _forbidden(request)
    initial = {}
    if request.GET.get("patient"):
        initial["patient"] = request.GET.get("patient")
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
def appointment_detail(request: HttpRequest, pk: int) -> HttpResponse:
    appointment = get_object_or_404(appointment_scope(request.user), pk=pk)
    return render(
        request,
        "appointments/appointment_detail.html",
        {
            "appointment": appointment,
            "can_book": can_book_appointments(request.user),
            "is_scheduled": appointment.status == AppointmentStatus.SCHEDULED,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def appointment_reschedule(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_book_appointments(request.user):
        return _forbidden(request)
    appointment = get_object_or_404(appointment_scope(request.user), pk=pk)
    if appointment.status != AppointmentStatus.SCHEDULED:
        messages.error(request, "Only scheduled appointments can be rescheduled.")
        return redirect("appointments:detail", pk=pk)
    form = AppointmentForm(request.POST or None, user=request.user, instance=appointment)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Appointment rescheduled. Reminder flag was reset.")
        return redirect("appointments:detail", pk=pk)
    return render(
        request,
        "appointments/appointment_form.html",
        {"form": form, "title": "Reschedule appointment", "appointment": appointment},
    )


@login_required
@require_http_methods(["POST"])
def appointment_status(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_book_appointments(request.user):
        return _forbidden(request)
    appointment = get_object_or_404(appointment_scope(request.user), pk=pk)
    new_status = request.POST.get("status")
    allowed = {
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    }
    if appointment.status != AppointmentStatus.SCHEDULED:
        messages.error(request, "Terminal statuses cannot be changed except by a superuser.")
        if not request.user.is_superuser:
            return redirect("appointments:detail", pk=pk)
    if new_status not in allowed and not (
        request.user.is_superuser and new_status in AppointmentStatus.values
    ):
        messages.error(request, "Invalid status.")
        return redirect("appointments:detail", pk=pk)
    appointment.status = new_status
    appointment.save(update_fields=["status", "updated_at"])
    messages.success(request, f"Appointment marked {appointment.get_status_display()}.")
    return redirect("appointments:detail", pk=pk)


@login_required
def daily_schedule(request: HttpRequest) -> HttpResponse:
    clinics = user_clinics(request.user)
    doctors = scoped_doctors(request.user)
    clinic_id = request.GET.get("clinic") or (str(clinics.first().pk) if clinics.exists() else "")
    doctor_id = request.GET.get("doctor") or ""
    date_str = request.GET.get("date") or timezone.localdate().isoformat()
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        day = timezone.localdate()
        date_str = day.isoformat()

    clinic = clinics.filter(pk=clinic_id).first() if clinic_id else clinics.first()
    tz = ZoneInfo(clinic.timezone) if clinic else ZoneInfo("UTC")
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = start + timedelta(days=1)

    qs = appointment_scope(request.user).filter(scheduled_at__gte=start, scheduled_at__lt=end)
    if clinic:
        qs = qs.filter(clinic=clinic)
    if doctor_id:
        qs = qs.filter(doctor_id=doctor_id)

    return render(
        request,
        "appointments/schedule.html",
        {
            "day": day,
            "date_str": date_str,
            "clinic": clinic,
            "clinics": clinics,
            "doctors": doctors,
            "doctor_id": doctor_id,
            "appointments": qs.order_by("doctor__full_name", "scheduled_at"),
        },
    )
