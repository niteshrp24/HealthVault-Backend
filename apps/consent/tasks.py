import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_consent_otp_task(self, consent_id: str, phone: str, otp: str):
    """
    Send consent OTP to user via WhatsApp (primary) + SMS (fallback).
    """
    try:
        from apps.consent.models import ConsentRequest
        from apps.core.utils.whatsapp import send_whatsapp_otp, send_sms_otp

        consent = ConsentRequest.objects.select_related('from_lab').get(id=consent_id)
        lab_name = consent.from_lab.name

        custom_message = (
            f"HealthVault: {lab_name} is requesting access to your medical reports.\n"
            f"Your OTP is: *{otp}*\n"
            f"Valid for 5 minutes. Do not share this with anyone.\n"
            f"If you did not expect this, ignore this message."
        )

        try:
            from apps.core.utils.whatsapp import send_whatsapp_message
            send_whatsapp_message(phone, custom_message)
            logger.info(f"Consent OTP sent via WhatsApp to {phone}")
        except Exception as exc:
            logger.warning(f"WhatsApp failed for consent OTP {phone}: {exc}. Trying SMS.")
            from apps.core.utils.whatsapp import send_sms_message
            send_sms_message(phone, f"HealthVault consent OTP: {otp}. Valid 5 mins.")

    except Exception as exc:
        logger.error(f"send_consent_otp_task failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def notify_lab_consent_active(self, consent_id: str):
    """
    Notify lab (via email) when a user has shared their files.
    """
    try:
        from apps.consent.models import ConsentRequest
        from apps.core.utils.email import send_notification_email

        consent = ConsentRequest.objects.select_related(
            'from_lab', 'to_user'
        ).prefetch_related('consent_files').get(id=consent_id)

        lab = consent.from_lab
        user = consent.to_user
        file_count = consent.consent_files.count()

        subject = f"HealthVault: Patient {user.name} has shared {file_count} report(s)"
        message = (
            f"Patient {user.name} (UID: {user.user_uid}) has approved your consent request "
            f"and shared {file_count} report(s) with {lab.name}.\n\n"
            f"Access expires at: {consent.consent_expires_at.strftime('%d %b %Y %H:%M')}.\n\n"
            f"Log in to your HealthVault lab portal to view the reports."
        )
        send_notification_email(lab.email, lab.name, subject, message)

    except Exception as exc:
        logger.error(f"notify_lab_consent_active failed for {consent_id}: {exc}")
        raise self.retry(exc=exc)
