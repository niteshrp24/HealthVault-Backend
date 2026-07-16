import secrets


def generate_12_digit_uid(model_class, field_name='user_uid'):
    """
    Generate a unique 12-digit numeric string for a given model field.
    Retries on collision (extremely rare in practice).
    """
    while True:
        uid = f"{secrets.randbelow(10**12):012d}"
        if not model_class.objects.filter(**{field_name: uid}).exists():
            return uid
