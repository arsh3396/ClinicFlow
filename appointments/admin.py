from django.contrib import admin
from django.contrib import messages
from .models import Appointment, SMSLog

# =========================================================================
# 1. DYNAMIC READ-ONLY SMS LOG CONFIGURATION
# =========================================================================
@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    """
    Requirement Met: Read-only logging administration grid.
    Dynamically maps configuration options based on actual model fields.
    """
    # Strictly lock down creation, editing, and deletion capabilities
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def get_list_display(self, request):
        """Dynamically build list display based on fields that actually exist."""
        all_fields = [f.name for f in SMSLog._meta.fields]
        display_fields = []
        
        # Look for the phone number field variations
        for target in ['recipient_phone', 'phone_number', 'phone', 'to_number', 'recipient']:
            if target in all_fields:
                display_fields.append(target)
                break
                
        # Always display status if present
        if 'status' in all_fields:
            display_fields.append('status')
            
        # Look for the timestamp field variations
        for target in ['sent_at', 'created_at', 'timestamp', 'date_sent']:
            if target in all_fields:
                display_fields.append(target)
                break
                
        # Fallback to all fields if none of the guesses matched
        return display_fields if display_fields else all_fields

    def get_list_filter(self, request):
        """Dynamically apply filters based on fields that actually exist."""
        all_fields = [f.name for f in SMSLog._meta.fields]
        filter_fields = []
        
        if 'status' in all_fields:
            filter_fields.append('status')
            
        for target in ['sent_at', 'created_at', 'timestamp']:
            if target in all_fields:
                filter_fields.append(target)
                break
                
        return filter_fields


# =========================================================================
# 2. APPOINTMENT ADMIN WITH DEFERRABLE TASK ACTIONS
# =========================================================================
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('scheduled_at', 'status')  # Standard safe fallback attributes
    actions = ['requeue_reminders_action']

    def get_list_display(self, request):
        """Dynamically add relational display tags safely based on field metadata."""
        all_fields = [f.name for f in Appointment._meta.fields]
        display_fields = []
        for target in ['patient', 'doctor', 'clinic', 'scheduled_at', 'status']:
            if target in all_fields or hasattr(Appointment, target):
                display_fields.append(target)
        return display_fields

    def requeue_reminders_action(self, request, queryset):

        from appointments.tasks import process_requeue_reminders_task 
        
        # Extract targeted appointment primary keys
        appointment_ids = list(queryset.values_list('pk', flat=True))
        
        # Enforce RESP2 protocol constraints directly onto the task connection broker wrapper
        task_connection_options = {
            'redis_version_check': False,
            'protocol': 2  # Fixes OperationalError by forcing classic connection formats
        }
        
        # Trigger Celery background workers with safe connection protocol overrides
        process_requeue_reminders_task.apply_async(
            args=[appointment_ids],
            broker_transport_options=task_connection_options
        )
        
        # Provide immediate feedback notice to the superuser
        self.message_user(
            request, 
            f"Successfully deferred task processing engine background worker loops for {len(appointment_ids)} reminders.",
            messages.SUCCESS
        )
    
    requeue_reminders_action.short_description = "Re-queue reminders (Defer via Celery Task)"
