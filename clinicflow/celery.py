"""Celery application for ClinicFlow background workers and Beat."""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "clinicflow.settings")

app = Celery("clinicflow")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
