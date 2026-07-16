import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def notify_user_new_report(self, report_id: str):
    """
    Notify user via WhatsApp + SMS when a lab uploads a new report for them.
    """
    try:
        from apps.reports.models import Report
        from apps.core.utils.whatsapp import send_whatsapp_message, send_sms_message

        report = Report.objects.select_related(
            'belongs_to_user', 'uploaded_by_lab'
        ).get(id=report_id)

        user = report.belongs_to_user
        lab = report.uploaded_by_lab
        message = (
            f"Hello {user.name}, a new report '{report.original_filename}' "
            f"has been uploaded by {lab.name}. "
            f"Log in to HealthVault to view it."
        )

        try:
            send_whatsapp_message(user.phone, message)
        except Exception as exc:
            logger.warning(f"WhatsApp notification failed for {user.phone}: {exc}")
            send_sms_message(user.phone, message)

    except Exception as exc:
        logger.error(f"notify_user_new_report failed for report {report_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task
def housekeeping_mark_expired_consents():
    """
    Housekeeping only — flips ConsentFile.is_active=False and
    ConsentRequest.status=EXPIRED for records past their deadline.
    NOT the enforcement layer — views enforce expiry at request time.
    Runs every 10 minutes via Celery beat.
    """
    from django.utils import timezone
    from apps.consent.models import ConsentFile, ConsentRequest

    now = timezone.now()

    # Expire consent files
    expired_files = ConsentFile.objects.filter(
        is_active=True,
        expires_at__lt=now,
    ).update(is_active=False)

    # Expire consent requests where all files have expired or OTP window lapsed
    expired_requests = ConsentRequest.objects.filter(
        status='ACTIVE',
        consent_expires_at__lt=now,
    ).update(status=ConsentRequest.Status.EXPIRED)

    # Auto-cancel pending requests whose OTP window passed without verification
    cancelled = ConsentRequest.objects.filter(
        status=ConsentRequest.Status.PENDING,
        otp_expires_at__lt=now,
    ).update(status=ConsentRequest.Status.CANCELLED)

    logger.info(
        f"Housekeeping: expired_files={expired_files}, "
        f"expired_requests={expired_requests}, "
        f"cancelled_pending={cancelled}"
    )
    return {
        'expired_files': expired_files,
        'expired_requests': expired_requests,
        'cancelled_pending': cancelled,
    }
