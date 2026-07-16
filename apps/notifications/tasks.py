import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=20)
def dispatch_notification_task(self, notification_id: str):
    """
    Dispatch a Notification record via its configured channel.
    Updates status to SENT or FAILED.
    """
    from apps.notifications.models import Notification

    try:
        notif = Notification.objects.select_related('sent_to_lab').get(id=notification_id)
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found.")
        return

    lab = notif.sent_to_lab
    channel = notif.channel
    message = notif.message

    try:
        if channel == Notification.Channel.INAPP:
            # Already persisted — in-app means it's visible in the DB
            pass

        elif channel == Notification.Channel.WHATSAPP:
            from apps.core.utils.whatsapp import send_whatsapp_message
            send_whatsapp_message(lab.phone, message)

        elif channel == Notification.Channel.SMS:
            from apps.core.utils.whatsapp import send_sms_message
            send_sms_message(lab.phone, message)

        elif channel == Notification.Channel.EMAIL:
            from apps.core.utils.email import send_notification_email
            send_notification_email(
                to_email=lab.email,
                to_name=lab.name,
                subject='HealthVault — Admin Notification',
                message=message,
            )

        notif.status = Notification.Status.SENT
        notif.save(update_fields=['status'])
        logger.info(f"Notification {notification_id} sent via {channel}.")

    except Exception as exc:
        logger.error(f"Notification {notification_id} dispatch failed: {exc}")
        notif.status = Notification.Status.FAILED
        notif.error_detail = str(exc)[:500]
        notif.save(update_fields=['status', 'error_detail'])
        raise self.retry(exc=exc)
