from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from appointments.models import Appointment, AppointmentStatus
from clinicflow.access import (
    can_manage_clinics,
    can_manage_doctors,
    scoped_doctors,
    user_clinics,
)

from .forms import ClinicForm, DoctorForm
from .models import Clinic, Doctor
from django.db import models 


def _forbidden(request: HttpRequest) -> HttpResponse:
    return render(request, "core/forbidden.html", status=403)


@login_required
def clinic_list(request: HttpRequest) -> HttpResponse:
    qs = user_clinics(request.user).order_by("name")
    return render(
        request,
        "clinics/clinic_list.html",
        {"clinics": qs, "can_edit": can_manage_clinics(request.user)},
    )


@login_required
@require_http_methods(["GET", "POST"])
def clinic_create(request: HttpRequest) -> HttpResponse:
    if not can_manage_clinics(request.user):
        return _forbidden(request)
    form = ClinicForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Clinic created.")
        return redirect("clinics:clinic_list")
    return render(request, "clinics/clinic_form.html", {"form": form, "title": "Add clinic"})


@login_required
@require_http_methods(["GET", "POST"])
def clinic_update(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_manage_clinics(request.user):
        return _forbidden(request)
    clinic = get_object_or_404(Clinic, pk=pk)
    form = ClinicForm(request.POST or None, instance=clinic)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Clinic updated.")
        return redirect("clinics:clinic_list")
    return render(
        request,
        "clinics/clinic_form.html",
        {"form": form, "title": "Edit clinic", "clinic": clinic},
    )


@login_required
@require_http_methods(["POST"])
def clinic_deactivate(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_manage_clinics(request.user):
        return _forbidden(request)
    clinic = get_object_or_404(Clinic, pk=pk)
    clinic.is_active = False
    clinic.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"{clinic.name} deactivated. Existing appointments remain visible.")
    return redirect("clinics:clinic_list")


@login_required
def doctor_list(request: HttpRequest) -> HttpResponse:
    qs = scoped_doctors(request.user).prefetch_related("clinics")
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "clinics/doctor_list.html",
        {"page": page, "can_edit": can_manage_doctors(request.user)},
    )


def _blocking_future_appointments(doctor: Doctor, clinic_ids_to_remove: set[int]):
    if not clinic_ids_to_remove:
        return Appointment.objects.none()
    return Appointment.objects.filter(
        doctor=doctor,
        clinic_id__in=clinic_ids_to_remove,
        status=AppointmentStatus.SCHEDULED,
        scheduled_at__gte=timezone.now(),
    )


@login_required
@require_http_methods(["GET", "POST"])
def doctor_create(request: HttpRequest) -> HttpResponse:
    if not can_manage_doctors(request.user):
        return _forbidden(request)
    form = DoctorForm(
        request.POST or None,
        clinic_queryset=user_clinics(request.user).filter(is_active=True),
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Doctor profile created.")
        return redirect("clinics:doctor_list")
    return render(request, "clinics/doctor_form.html", {"form": form, "title": "Add doctor"})


@login_required
@require_http_methods(["GET", "POST"])
def doctor_update(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_manage_doctors(request.user):
        return _forbidden(request)

    doctor = get_object_or_404(
        scoped_doctors(request.user).prefetch_related("clinics"), 
        pk=pk
    )
    
    allowed_clinics = user_clinics(request.user).filter(
        models.Q(is_active=True) | models.Q(pk__in=doctor.clinics.all())
    )
    
    form = DoctorForm(
        request.POST or None,
        instance=doctor,
        clinic_queryset=allowed_clinics.distinct(),
    )
    
    if request.method == "POST" and form.is_valid():
        selected_ids = {c.pk for c in form.cleaned_data["clinics"]}
        
        current_ids = {c.pk for c in doctor.clinics.all()}
        
        removing = current_ids - selected_ids
        blocking = _blocking_future_appointments(doctor, removing)
        
        if blocking.exists():
            form.add_error(
                "clinics",
                "Cannot unlink clinics that still have future scheduled appointments: "
                + ", ".join(f"#{a.pk}" for a in blocking[:8]),
            )
        else:
            form.save()
            messages.success(request, "Doctor profile updated.")
            return redirect("clinics:doctor_list")
            
    return render(
        request,
        "clinics/doctor_form.html",
        {"form": form, "title": "Edit doctor", "doctor": doctor},
    )