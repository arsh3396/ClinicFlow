from __future__ import annotations

from zoneinfo import available_timezones

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.deconstruct import deconstructible

E164_REGEX = r"^\+[1-9]\d{7,14}$"

e164_phone_validator = RegexValidator(
    regex=E164_REGEX,
    message="Enter phone in international format, e.g., +919876543210",
)

@deconstructible
class TimezoneValidator:
    def __call__(self, value: str) -> None:
        if value not in available_timezones():
            raise ValidationError(
                "%(value)s is not a valid IANA timezone identifier.",
                params={"value": value},
                code="invalid_timezone",
            )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TimezoneValidator)
