import logging
from celery import shared_task
# from apps.core.utils.whatsapp import send_whatsapp_otp, send_sms_otp

logger = logging.getLogger(__name__)


# @shared_task(bind=True, max_retries=3, default_retry_delay=10)
# def send_otp_task(self, phone: str, otp: str, purpose: str):
#     """
#     Dispatch OTP via WhatsApp (primary) and SMS (fallback).
#     Retries up to 3 times on transient failures.
#     """
#     try:
#         send_whatsapp_otp(phone, otp, purpose)
#         logger.info(f"WhatsApp OTP dispatched to {phone} for {purpose}")
#     except Exception as whatsapp_exc:
#         logger.warning(f"WhatsApp OTP failed for {phone}: {whatsapp_exc}. Trying SMS.")
#         try:
#             send_sms_otp(phone, otp, purpose)
#             logger.info(f"SMS OTP dispatched to {phone} for {purpose}")
#         except Exception as sms_exc:
#             logger.error(f"SMS OTP also failed for {phone}: {sms_exc}")
#             raise self.retry(exc=sms_exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_otp_task(self, phone: str, otp: str, purpose: str):
    """
    Dispatch OTP via both WhatsApp AND SMS independently.
    Both channels are always attempted. Retries only if both fail.
    """
    # Both functions live in the same whatsapp.py utility module
    from apps.core.utils.whatsapp import send_whatsapp_otp, send_sms_otp
 
    errors = []
 
    # ── WhatsApp ──────────────────────────────────────────────────────────────
    try:
        sid = send_whatsapp_otp(phone, otp, purpose)
        logger.info(f"WhatsApp OTP sent to {phone} | SID={sid}")
    except Exception as exc:
        logger.warning(f"WhatsApp OTP failed for {phone}: {exc}")
        errors.append(exc)
 
    # ── SMS (always sent, not just a fallback) ────────────────────────────────
    try:
        sid = send_sms_otp(phone, otp, purpose)
        logger.info(f"SMS OTP sent to {phone} | SID={sid}")
    except Exception as exc:
        logger.error(f"SMS OTP failed for {phone}: {exc}")
        errors.append(exc)
 
    # Retry the task only if both channels failed
    if len(errors) == 2:
        raise self.retry(exc=errors[-1])


@shared_task
def deactivate_expired_labs():
    """
    Housekeeping task: flip is_active=False for labs whose plan has expired.
    This is a secondary gate — the login view already enforces plan_end.
    Run via Celery beat every 30 minutes.
    """
    from django.utils import timezone
    from apps.accounts.models import LabHospital

    count = LabHospital.objects.filter(
        is_active=True,
        plan_end__lt=timezone.now(),
    ).update(is_active=False)

    if count:
        logger.info(f"Deactivated {count} expired lab(s).")
    return count
