from django.conf import settings
from twilio.rest import Client


def _get_client() -> Client:
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def send_whatsapp_otp(phone: str, otp: str, purpose: str = 'login') -> str:
    """
    Send OTP via Twilio WhatsApp.
    phone must be in E.164 format e.g. +919876543210
    Returns the Twilio message SID.
    """
    client = _get_client()
    purpose_label = 'login' if purpose == 'USER_LOGIN' else 'consent verification'
    body = (
        f"Your HealthVault OTP for {purpose_label} is: *{otp}*\n"
        f"Valid for 5 minutes. Do not share this with anyone."
    )
    message = client.messages.create(
        body=body,
        from_=settings.TWILIO_WHATSAPP_FROM,
        to=f"whatsapp:{phone}",
    )
    return message.sid


def send_sms_otp(phone: str, otp: str, purpose: str = 'login') -> str:
    """
    Fallback SMS OTP via Twilio.
    Returns the Twilio message SID.
    """
    client = _get_client()
    purpose_label = 'login' if purpose == 'USER_LOGIN' else 'consent verification'
    body = (
        f"HealthVault OTP for {purpose_label}: {otp}. "
        f"Valid 5 mins. Do not share."
    )
    message = client.messages.create(
        body=body,
        from_=settings.TWILIO_SMS_FROM,
        to=phone,
    )
    return message.sid


def send_whatsapp_message(phone: str, message_body: str) -> str:
    """Send a general WhatsApp message (admin notifications etc.)."""
    client = _get_client()
    message = client.messages.create(
        body=message_body,
        from_=settings.TWILIO_WHATSAPP_FROM,
        to=f"whatsapp:{phone}",
    )
    return message.sid


def send_sms_message(phone: str, message_body: str) -> str:
    """Send a general SMS message."""
    client = _get_client()
    message = client.messages.create(
        body=message_body,
        from_=settings.TWILIO_SMS_FROM,
        to=phone,
    )
    return message.sid
