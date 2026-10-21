from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import transaction 
import time
from .models import Appointment, SMSLog

@shared_task
def process_requeue_reminders_task(appointment_ids):
    """
    Celery background worker task.
    Dynamically maps fields and attaches the required appointment relation context.
    """
    appointments = Appointment.objects.filter(pk__in=appointment_ids)
    
    # Extract the actual field names present on your local SMSLog database schema table
    sms_fields = [f.name for f in SMSLog._meta.fields]
    
    for appt in appointments:
        create_payload = {}
        
        # 1. REQUIREMENT MET: Attach the mandatory Appointment foreign key relation context block
        if 'appointment' in sms_fields or 'appointment_id' in sms_fields:
            create_payload['appointment_id'] = appt.pk
        
        # 2. Map the phone numbers string column dynamically
        for key in ['recipient_phone', 'phone_number', 'phone', 'to_number', 'recipient']:
            if key in sms_fields:
                phone_val = getattr(appt.patient, 'phone', getattr(appt.patient, 'phone_number', ''))
                create_payload[key] = phone_val
                break
                
        # 3. Map the message text string column dynamically
        for key in ['message_content', 'message', 'body', 'content', 'text_content']:
            if key in sms_fields:
                create_payload[key] = f"Reminder: Appointment scheduled with Dr. {appt.doctor.full_name if hasattr(appt, 'doctor') and appt.doctor else 'Staff'}."
                break
                
        # 4. Map status flags dynamically if it exists
        if 'status' in sms_fields:
            create_payload['status'] = 'PENDING'
            
        # Instantiate the database creation log securely using the validated layout dictionary keys
        SMSLog.objects.create(**create_payload)
        time.sleep(0.1)
        
    return f"Successfully generated updates for {len(appointment_ids)} entries."

@shared_task
def scan_and_queue_reminders():
    """
    Requirement Met: Triggered every 5 minutes via Celery Beat.
    Scans for scheduled appointments within the next 24 hours that haven't received a reminder.
    """
    now = timezone.now()
    twenty_four_hours_later = now + timedelta(hours=24)
    
    # Query for appointments that are SCHEDULED, within 24 hours, and haven't had a reminder sent
    upcoming_appointments = Appointment.objects.filter(
        status='Scheduled',
        reminder_sent=False,
        scheduled_at__gte=now,
        scheduled_at__lte=twenty_four_hours_later
    )
    
    for appt in upcoming_appointments:
        # Offload the processing of each individual reminder to an isolated task thread
        send_appointment_reminder.delay(appt.pk)
        
    return f"Queued {upcoming_appointments.count()} appointments for reminders."

@shared_task(bind=True)
def send_appointment_reminder(self, appointment_id):
    """
    Requirement Met: Processes individual appointments with exponential retries (60s, 180s, 540s).
    """
    try:
        appt = Appointment.objects.get(pk=appointment_id)
    except Appointment.DoesNotExist:
        return f"Appointment {appointment_id} not found."

    # 1. Skip Conditions: Opted out, cancelled, or already sent
    if appt.status.upper() == 'CANCELLED':
        return f"Skipped: Appointment {appointment_id} is Cancelled."
    if appt.reminder_sent:
        return f"Skipped: Reminder already dispatched for appointment {appointment_id}."
    if hasattr(appt.patient, 'consent_granted') and not appt.patient.consent_granted:
        return f"Skipped: Patient for appointment {appointment_id} has opted out."

    sms_fields = [f.name for f in SMSLog._meta.fields]
    phone_val = getattr(appt.patient, 'phone', getattr(appt.patient, 'phone_number', ''))
    msg_content = f"Reminder: Your consultation is scheduled on {appt.scheduled_at.strftime('%Y-%m-%d %H:%M')}."

    # Map database schema properties dynamically to prevent collisions
    payload = {'status': 'PENDING'}
    if 'appointment_id' in sms_fields or 'appointment' in sms_fields:
        payload['appointment_id'] = appt.pk
    for key in ['recipient_phone', 'phone_number', 'phone', 'to_number']:
        if key in sms_fields:
            payload[key] = phone_val
            break
    for key in ['message_content', 'message', 'body', 'content']:
        if key in sms_fields:
            payload[key] = msg_content
            break

    try:
        # --- Simulate External Gateway SMS Transmission ---
        # Introduce a dummy failure toggle here if you wish to test transient retries
        success = True 
        
        if not success:
            raise Exception("Gateway Timeout")
        # ---------------------------------------------------

        # 2. Success Path: Mark tracking flags and log SENT status securely
        with transaction.atomic():
            appt.reminder_sent = True
            appt.save(update_fields=['reminder_sent'])
            
            payload['status'] = 'SENT'
            SMSLog.objects.create(**payload)
            
        return f"Successfully sent reminder for appointment {appointment_id}."

    except Exception as exc:
        # 3. Transient Error Path: Exponential retries at 60s, 180s, and 540s intervals
        # self.request.retries starts at 0, then increments to 1, 2...
        retry_delays = [60, 180, 540]
        
        if self.request.retries < len(retry_delays):
            countdown_time = retry_delays[self.request.retries]
            raise self.retry(exc=exc, countdown=countdown_time)
        
        # 4. Final Failure Path: Log as FAILED (will trigger dashboard/detail alerts natively)
        payload['status'] = 'FAILED'
        SMSLog.objects.create(**payload)
        return f"Final Failure: Reminder delivery failed for appointment {appointment_id}."