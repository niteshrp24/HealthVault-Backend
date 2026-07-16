# import requests
# from django.conf import settings


# ZEPTO_API_URL = 'https://api.zeptomail.in/v1.1/email'


# def send_transactional_email(
#     to_email: str,
#     to_name: str,
#     subject: str,
#     html_body: str,
#     text_body: str = '',
# ) -> dict:
#     """
#     Send transactional email via ZeptoMail.
#     Returns the API response JSON.
#     """
#     headers = {
#         'accept': 'application/json',
#         'content-type': 'application/json',
#         'authorization': settings.ZEPTO_API_KEY,
#     }
#     payload = {
#         'from': {
#             'address': settings.ZEPTO_FROM_EMAIL,
#             'name': settings.ZEPTO_FROM_NAME,
#         },
#         'to': [{'email_address': {'address': to_email, 'name': to_name}}],
#         'subject': subject,
#         'htmlbody': html_body,
#         'textbody': text_body or '',
#     }
#     response = requests.post(ZEPTO_API_URL, json=payload, headers=headers, timeout=10)
#     response.raise_for_status()
#     return response.json()


# def send_notification_email(to_email: str, to_name: str, subject: str, message: str) -> dict:
#     """Convenience wrapper for plain notification emails."""
#     html_body = f"""
#     <html><body>
#     <p>Dear {to_name},</p>
#     <p>{message}</p>
#     <p>Regards,<br/>{settings.ZEPTO_FROM_NAME}</p>
#     </body></html>
#     """
#     return send_transactional_email(
#         to_email=to_email,
#         to_name=to_name,
#         subject=subject,
#         html_body=html_body,
#         text_body=message,
#     )




import smtplib
import ssl
from email.message import EmailMessage
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_transactional_email(
    to_email: str,
    to_name: str,
    subject: str,
    html_body: str,
    text_body: str = '',
) -> bool:
    """
    Send transactional email via ZeptoMail SMTP.
    Returns True on success, False on failure.
    """
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f"{settings.ZEPTO_FROM_NAME} <{settings.ZEPTO_FROM_EMAIL}>"
    msg['To'] = to_email
    msg.set_content(text_body or html_body)

    # Add HTML version
    if html_body:
        msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP(settings.ZEPTO_SMTP_HOST, settings.ZEPTO_SMTP_PORT) as server:
            server.starttls()
            server.login(settings.ZEPTO_SMTP_USERNAME, settings.ZEPTO_SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email sent to {to_email} — {subject}")
        return True
    except Exception as e:
        logger.error(f"Email failed to {to_email}: {e}")
        return False


def send_notification_email(
    to_email: str,
    to_name: str,
    subject: str,
    message: str,
) -> bool:
    """Convenience wrapper for plain notification emails."""
    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; padding: 20px;">
    <p>Dear {to_name},</p>
    <p>{message}</p>
    <br/>
    <p>Regards,<br/><strong>{settings.ZEPTO_FROM_NAME}</strong></p>
    </body></html>
    """
    return send_transactional_email(
        to_email=to_email,
        to_name=to_name,
        subject=subject,
        html_body=html_body,
        text_body=message,
    )