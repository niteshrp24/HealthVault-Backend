import secrets
import hashlib


def generate_otp(length=6) -> str:
    """Generate a cryptographically secure numeric OTP."""
    return f"{secrets.randbelow(10**length):0{length}d}"


def hash_otp(otp: str) -> str:
    """SHA-256 hash an OTP for safe storage."""
    return hashlib.sha256(otp.encode()).hexdigest()


def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    """Constant-time comparison of plain OTP against stored hash."""
    return secrets.compare_digest(hash_otp(plain_otp), hashed_otp)
