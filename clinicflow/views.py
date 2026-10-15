from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from appointments.models import AppointmentStatus
from clinicflow.access import appointment_scope, user_clinics


def _today_window_for_user(user):
    clinics = list(user_clinics(user)[:1])
    tz_name = clinics[0].timezone if clinics else "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    today = timezone.now().astimezone(tz).date()
    start = datetime.combine(today, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return today, start, end, tz_name


@login_required
def dashboard(request):
    today, start, end, tz_name = _today_window_for_user(request.user)
    clinics = user_clinics(request.user)
    scoped = appointment_scope(request.user).filter(
        scheduled_at__gte=start, scheduled_at__lt=end
    )
    counts = scoped.aggregate(
        scheduled=Count("id", filter=Q(status=AppointmentStatus.SCHEDULED)),
        completed=Count("id", filter=Q(status=AppointmentStatus.COMPLETED)),
        cancelled=Count("id", filter=Q(status=AppointmentStatus.CANCELLED)),
        no_show=Count("id", filter=Q(status=AppointmentStatus.NO_SHOW)),
    )
    return render(
        request,
        "core/dashboard.html",
        {
            "today": today,
            "tz_name": tz_name,
            "clinics": clinics,
            "counts": counts,
            "todays_appointments": scoped.order_by("scheduled_at")[:20],
        },
    )


def forbidden(request):
    return render(request, "core/forbidden.html", status=403)
