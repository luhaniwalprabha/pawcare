# This is where all async background tasks live.
#
# Key concepts used here:
#
# @celery_app.task(bind=True)
#   bind=True means the task receives `self` as first argument
#   this lets us call self.retry() for retries
#
# autoretry_for: automatically retry if these exceptions occur
# max_retries: give up after this many attempts
# countdown: wait this many seconds before retrying
# exponential_backoff: each retry waits longer (1s, 2s, 4s, 8s...)
#   — this is important so we don't hammer a failing email server
#
# Why retry at all?
#   External services (email, SMS) fail sometimes.
#   Without retries, a temporary failure = permanent failure.
#   With retries, temporary failures are handled gracefully.

import logging
from datetime import datetime, timedelta
from celery import shared_task
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # wait 60 seconds before first retry
    autoretry_for=(Exception,),
    retry_backoff=True,       # exponential backoff: 60s, 120s, 240s
    retry_jitter=True,        # adds randomness to prevent thundering herd
    name="app.tasks.notifications.send_appointment_reminder",
)
def send_appointment_reminder(self, appointment_id: int, pet_name: str, owner_email: str, owner_name: str, scheduled_at: str):
    """
    Send appointment reminder to pet owner.

    This task is queued when an appointment is created or confirmed.
    It runs in the background so the API response is instant.

    In production: replace logger with actual email/SMS service (SendGrid, Twilio etc.)
    """
    try:
        logger.info(f"[TASK] Sending reminder for appointment {appointment_id}")
        logger.info(f"[TASK] To: {owner_email} | Pet: {pet_name} | Time: {scheduled_at}")

        # --- Replace this block with real email/SMS in production ---
        # sendgrid_client.send(
        #     to=owner_email,
        #     subject=f"Reminder: {pet_name}'s appointment tomorrow",
        #     body=f"Hi {owner_name}, this is a reminder..."
        # )
        # -----------------------------------------------------------

        logger.info(f"[TASK] Reminder sent successfully for appointment {appointment_id}")
        return {"status": "sent", "appointment_id": appointment_id}

    except Exception as exc:
        logger.error(f"[TASK] Failed to send reminder for appointment {appointment_id}: {exc}")
        # self.retry() raises Retry exception — Celery handles the rest
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    name="app.tasks.notifications.send_visit_summary",
)
def send_visit_summary(self, pet_name: str, owner_email: str, owner_name: str, diagnosis: str, prescriptions: str, follow_up_date: str = None):
    """
    Send post-visit summary to owner after appointment is completed.

    Triggered when a medical record is created.
    Contains: diagnosis, prescriptions, follow-up date.
    """
    try:
        logger.info(f"[TASK] Sending visit summary to {owner_email} for {pet_name}")

        follow_up_msg = f"Follow-up scheduled: {follow_up_date}" if follow_up_date else "No follow-up required"

        # --- Replace with real email in production ---
        # email_body = f"""
        # Hi {owner_name},
        # Here is the summary of {pet_name}'s visit today:
        # Diagnosis: {diagnosis}
        # Prescriptions: {prescriptions}
        # {follow_up_msg}
        # """
        # sendgrid_client.send(to=owner_email, subject=f"{pet_name}'s Visit Summary", body=email_body)
        # -------------------------------------------

        logger.info(f"[TASK] Visit summary sent to {owner_email}")
        return {"status": "sent", "owner_email": owner_email}

    except Exception as exc:
        logger.error(f"[TASK] Failed to send visit summary: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.notifications.send_daily_reminders")
def send_daily_reminders():
    """
    Periodic task — runs every 24 hours via Celery Beat.

    Finds all appointments scheduled for tomorrow and
    queues a reminder task for each one.

    This is the scheduler pattern:
      Beat (scheduler) → triggers this task every 24h
      This task → finds appointments → queues individual reminder tasks
      Individual tasks → send actual emails
    """
    from app.db.session import SessionLocal
    from app.models.clinic import Appointment, AppointmentStatus
    from app.models.patient import Pet, Owner

    db = SessionLocal()
    try:
        tomorrow_start = datetime.utcnow().replace(hour=0, minute=0, second=0) + timedelta(days=1)
        tomorrow_end = tomorrow_start + timedelta(days=1)

        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.scheduled_at >= tomorrow_start,
                Appointment.scheduled_at < tomorrow_end,
                Appointment.status.in_([
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED
                ])
            )
            .all()
        )

        logger.info(f"[BEAT] Found {len(appointments)} appointments for tomorrow")

        for appt in appointments:
            pet = db.query(Pet).filter(Pet.id == appt.pet_id).first()
            owner = db.query(Owner).filter(Owner.id == pet.owner_id).first() if pet else None

            if pet and owner:
                # Queue individual reminder task — each runs independently
                # delay() is shorthand for apply_async()
                send_appointment_reminder.delay(
                    appointment_id=appt.id,
                    pet_name=pet.name,
                    owner_email=owner.email,
                    owner_name=owner.full_name,
                    scheduled_at=appt.scheduled_at.isoformat(),
                )
                logger.info(f"[BEAT] Queued reminder for appointment {appt.id}")

        return {"queued": len(appointments)}

    finally:
        db.close()  # always close DB session in background tasks