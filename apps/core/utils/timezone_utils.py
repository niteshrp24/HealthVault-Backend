from django.utils import timezone
import pytz

IST = pytz.timezone('Asia/Kolkata')

def now_ist():
    """Return current time in IST timezone."""
    return timezone.now().astimezone(IST)

def to_ist(dt):
    """Convert any datetime to IST."""
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, pytz.utc)
    return dt.astimezone(IST)