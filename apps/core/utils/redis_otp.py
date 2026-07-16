from django.core.cache import cache
from django.conf import settings


OTP_ATTEMPTS_PREFIX = 'otp:attempts'
OTP_RESEND_PREFIX = 'otp:resend_block'


def _attempts_key(phone: str, purpose: str) -> str:
    return f"{OTP_ATTEMPTS_PREFIX}:{phone}:{purpose}"


def _resend_key(phone: str, purpose: str) -> str:
    return f"{OTP_RESEND_PREFIX}:{phone}:{purpose}"


def get_remaining_attempts(phone: str, purpose: str) -> int:
    """Return how many OTP attempts are left in the current window."""
    key = _attempts_key(phone, purpose)
    current = cache.get(key, 0)
    return max(0, settings.OTP_MAX_ATTEMPTS - current)


def record_otp_attempt(phone: str, purpose: str) -> int:
    """
    Increment the attempt counter for this phone+purpose.
    Sets TTL on first increment.
    Returns the current attempt count after incrementing.
    """
    key = _attempts_key(phone, purpose)
    pipe = cache.client.get_client().pipeline()
    pipe.incr(key)
    pipe.expire(key, settings.OTP_EXPIRY_SECONDS)
    results = pipe.execute()
    return results[0]  # current count after increment


def is_attempt_limit_reached(phone: str, purpose: str) -> bool:
    """True if the user has exhausted all OTP attempts."""
    key = _attempts_key(phone, purpose)
    current = cache.get(key, 0)
    return current >= settings.OTP_MAX_ATTEMPTS


def clear_otp_attempts(phone: str, purpose: str) -> None:
    """Clear attempt counter after successful verification."""
    cache.delete(_attempts_key(phone, purpose))


def is_resend_blocked(phone: str, purpose: str) -> bool:
    """True if a resend cooldown is active for this phone+purpose."""
    return cache.get(_resend_key(phone, purpose)) is not None


def set_resend_block(phone: str, purpose: str) -> None:
    """Block resend for RESEND_COOLDOWN_SECONDS after an OTP is sent."""
    cache.set(
        _resend_key(phone, purpose),
        '1',
        timeout=settings.OTP_RESEND_COOLDOWN_SECONDS,
    )


def clear_resend_block(phone: str, purpose: str) -> None:
    cache.delete(_resend_key(phone, purpose))
