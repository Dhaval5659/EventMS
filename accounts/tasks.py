from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from .models import Event, EventRegistration, User

 
@shared_task
def send_registration_email(event_id, user_id):
    event = Event.objects.get(pk=event_id)
    user = User.objects.get(pk=user_id)

    subject = f"Event Registration Confirmation - {event.title}"
    message = (
        f"Hello {user.username},\n\n"
        f"You have successfully registered for the event \"{event.title}\" "
        f"organized by {event.created_by.username}.\n"
        f"Location: {event.location}\n"
        f"Start Time: {event.start_time}"
    )
    send_mail(subject, message, None, [user.email])


@shared_task
def send_event_reminder_email(event_id, user_id):
    event = Event.objects.get(pk=event_id)
    user = User.objects.get(pk=user_id)

    subject = f"Event Reminder - {event.title}"
    message = (
        f"Hello {user.username},\n\n"
        f"This is a reminder that your event \"{event.title}\" starts in 30 minutes.\n"
        f"See you at {event.location}."
    )
    send_mail(subject, message, None, [user.email])


@shared_task
def check_and_send_event_reminders():
    now = timezone.now()
    window_start = now + timedelta(minutes=29)
    window_end = now + timedelta(minutes=31)

    upcoming_registrations = EventRegistration.objects.filter(
        event__start_time__range=(window_start, window_end),
        reminder_sent=False,
    )

    for registration in upcoming_registrations:
        send_event_reminder_email.delay(registration.event_id, registration.user_id)
        registration.reminder_sent = True
        registration.save()