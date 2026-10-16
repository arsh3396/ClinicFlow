from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from clinicflow.access import (
    can_add_history,
    can_edit_patients,
    can_search_history,
    can_toggle_consent,
    can_view_history,
    doctor_for_user,
    user_clinics,
)

from .forms import HistoryEntryForm, PatientForm
from .models import MedicalHistoryEntry, Patient


def _forbidden(request: HttpRequest) -> HttpResponse:
    return render(request, "core/forbidden.html", status=403)


@login_required
def patient_list(request: HttpRequest) -> HttpResponse:
    query = (request.GET.get("q") or "").strip()
    qs = Patient.objects.all()
    if query:
        name_filter = Q(first_name__icontains=query) | Q(last_name__icontains=query)
        if query.startswith("+") or query.isdigit():
            qs = qs.filter(name_filter | Q(phone_number__endswith=query.lstrip()))
        else:
            qs = qs.filter(name_filter)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "patients/patient_list.html",
        {
            "page": page,
            "query": query,
            "can_edit": can_edit_patients(request.user),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def patient_create(request: HttpRequest) -> HttpResponse:
    if not can_edit_patients(request.user):
        return _forbidden(request)
    form = PatientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        patient = form.save(commit=False)
        if patient.consent_given:
            patient.set_consent(True, request.user)
        patient.save()
        messages.success(request, "Patient created.")
        return redirect("patients:detail", pk=patient.pk)
    return render(request, "patients/patient_form.html", {"form": form, "title": "New patient"})


@login_required
@require_http_methods(["GET", "POST"])
def patient_update(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_edit_patients(request.user):
        return _forbidden(request)
    patient = get_object_or_404(Patient, pk=pk)
    form = PatientForm(request.POST or None, instance=patient)
    if "consent_given" in form.fields:
        form.fields.pop("consent_given")
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Patient updated.")
        return redirect("patients:detail", pk=patient.pk)
    return render(
        request,
        "patients/patient_form.html",
        {"form": form, "title": "Edit patient", "patient": patient},
    )


@login_required
def patient_detail(request: HttpRequest, pk: int) -> HttpResponse:
    patient = get_object_or_404(Patient, pk=pk)
    show_history_panel = can_view_history(request.user)
    history_entries = []
    history_form = None
    consent_blocked = not patient.consent_given

    if show_history_panel and patient.consent_given:
        history_entries = list(
            MedicalHistoryEntry.objects.consented()
            .filter(patient=patient)
            .select_related("author", "clinic")
        )
        if can_add_history(request.user):
            history_form = HistoryEntryForm(
                clinic_queryset=user_clinics(request.user).filter(is_active=True)
            )

    appointments = patient.appointments.select_related("doctor", "clinic").order_by(
        "-scheduled_at"
    )[:20]

    return render(
        request,
        "patients/patient_detail.html",
        {
            "patient": patient,
            "show_history_panel": show_history_panel,
            "consent_blocked": consent_blocked,
            "history_entries": history_entries,
            "history_form": history_form,
            "appointments": appointments,
            "can_edit": can_edit_patients(request.user),
            "can_toggle_consent": can_toggle_consent(request.user),
            "can_add_history": can_add_history(request.user) and patient.consent_given,
            "can_book": True,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def consent_confirm(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_toggle_consent(request.user):
        return _forbidden(request)
    patient = get_object_or_404(Patient, pk=pk)
    new_value = not patient.consent_given
    if request.method == "POST":
        if request.POST.get("confirm") != "yes":
            messages.error(request, "Confirmation is required to change consent.")
            return redirect("patients:consent", pk=patient.pk)
        patient.set_consent(new_value, request.user)
        messages.success(
            request,
            "Consent granted." if new_value else "Consent revoked. History is now hidden.",
        )
        return redirect("patients:detail", pk=patient.pk)
    return render(
        request,
        "patients/consent_confirm.html",
        {"patient": patient, "new_value": new_value},
    )


@login_required
@require_http_methods(["POST"])
def history_create(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_add_history(request.user):
        return _forbidden(request)
    patient = get_object_or_404(Patient, pk=pk)
    if not patient.consent_given:
        return render(
            request,
            "core/forbidden.html",
            {"message": "Patient consent required."},
            status=403,
        )
    form = HistoryEntryForm(
        request.POST,
        clinic_queryset=user_clinics(request.user).filter(is_active=True),
    )
    if form.is_valid():
        entry = form.save(commit=False)
        entry.patient = patient
        entry.author = doctor_for_user(request.user)
        entry.save()
        messages.success(request, "Medical history entry added.")
        return redirect("patients:detail", pk=patient.pk)
    messages.error(request, "Could not save the history entry. Check the form.")
    return redirect("patients:detail", pk=patient.pk)


@login_required
def history_search(request: HttpRequest) -> HttpResponse:
    if not can_search_history(request.user):
        return _forbidden(request)
    query = (request.GET.get("q") or "").strip()
    error = ""
    page = None
    if query and len(query) < 3:
        error = "Enter at least 3 characters."
    elif query:
        # Enforce the privacy filter gate directly inside the active query logic
        qs = MedicalHistoryEntry.objects.filter(
            patient__consent_given=True,
            entry_text__icontains=query
        ).select_related("patient", "author", "clinic")


        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "patients/history_search.html",
        {"query": query, "error": error, "page": page},
    )
