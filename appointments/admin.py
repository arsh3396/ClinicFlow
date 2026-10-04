from django.contrib import admin
from .models import Appointment, SMSLog


admin.site.register(Appointment)
admin.site.register(SMSLog)
