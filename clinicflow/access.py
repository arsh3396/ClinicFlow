"""Role checks and clinic-scoped query helpers for the prototype."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet
from django.http import HttpRequest

from clinics.models import Clinic, Doctor, StaffRole
from patients.models import Patient


def get_staff_role(user: AbstractBaseUser) -> str | None:
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return "SUPERUSER"
    profile = getattr(user, "staff_profile", None)
    return profile.role if profile else None


def user_clinics(user: AbstractBaseUser) -> QuerySet[Clinic]:
    if not user.is_authenticated:
        return Clinic.objects.none()
    if user.is_superuser:
        return Clinic.objects.all()
    profile = getattr(user, "staff_profile", None)
    if profile is not None:
        return profile.clinics.all()
    doctor = getattr(user, "doctor_profile", None)
    if doctor is not None:
        return doctor.clinics.all()
    return Clinic.objects.none()


def user_clinic_ids(user: AbstractBaseUser) -> list[int]:
    return list(user_clinics(user).values_list("pk", flat=True))


def can_manage_clinics(user: AbstractBaseUser) -> bool:
    return get_staff_role(user) == "SUPERUSER"


def can_manage_doctors(user: AbstractBaseUser) -> bool:
    return get_staff_role(user) in {"SUPERUSER", "CLINIC_ADMIN"}


def can_edit_patients(user: AbstractBaseUser) -> bool:
    return get_staff_role(user) in {"SUPERUSER", "CLINIC_ADMIN", "RECEPTIONIST"}


def can_toggle_consent(user: AbstractBaseUser) -> bool:
    return get_staff_role(user) in {
        "SUPERUSER",
        "CLINIC_ADMIN",
        "DOCTOR",
        "RECEPTIONIST",
    }


def can_view_history(user: AbstractBaseUser) -> bool:
    return get_staff_role(user) in {"SUPERUSER", "CLINIC_ADMIN", "DOCTOR"}


def can_add_history(user: AbstractBaseUser) -> bool:
    return get_staff_role(user) == "DOCTOR"


def can_book_appointments(user: AbstractBaseUser) -> bool:
    return get_staff_role(user) in {"SUPERUSER", "CLINIC_ADMIN", "RECEPTIONIST"}


def can_search_history(user: AbstractBaseUser) -> bool:
    return can_view_history(user)


def doctor_for_user(user: AbstractBaseUser) -> Doctor | None:
    return getattr(user, "doctor_profile", None)


def scoped_doctors(user: AbstractBaseUser) -> QuerySet[Doctor]:
    qs = Doctor.objects.all()
    if user.is_superuser:
        return qs
    return qs.filter(clinics__in=user_clinics(user)).distinct()


def appointment_scope(user: AbstractBaseUser):
    from appointments.models import Appointment

    qs = Appointment.objects.select_related("patient", "doctor", "clinic", "created_by")
    if user.is_superuser:
        return qs
    doctor = doctor_for_user(user)
    role = get_staff_role(user)
    if role == StaffRole.DOCTOR and doctor is not None:
        return qs.filter(doctor=doctor, clinic__in=user_clinics(user))
    return qs.filter(clinic__in=user_clinics(user))


def staff_nav_context(request: HttpRequest) -> dict:
    user = request.user
    if not user.is_authenticated:
        return {
            "staff_role": None,
            "can_manage_clinics": False,
            "can_manage_doctors": False,
            "can_edit_patients": False,
            "can_view_history": False,
            "can_add_history": False,
            "can_book_appointments": False,
            "can_search_history": False,
        }
    return {
        "staff_role": get_staff_role(user),
        "can_manage_clinics": can_manage_clinics(user),
        "can_manage_doctors": can_manage_doctors(user),
        "can_edit_patients": can_edit_patients(user),
        "can_view_history": can_view_history(user),
        "can_add_history": can_add_history(user),
        "can_book_appointments": can_book_appointments(user),
        "can_search_history": can_search_history(user),
    }


# Imported by patients views for type checkers; keep Patient in module graph.
_ = Patient
