import uuid
from django.db import models
from django.utils import timezone
from apps.core.models import BaseModel
from apps.core.utils.uid_generator import generate_12_digit_uid


class Admin(BaseModel):
    """Single system administrator. Username + password login."""
    username = models.CharField(max_length=50, unique=True)
    password_hash = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    last_login = models.DateTimeField(null=True, blank=True)

    # portal identifier used in JWT claims
    portal = 'admin'

    class Meta:
        db_table = 'admins'
        verbose_name = 'Admin'

    def __str__(self):
        return self.username


class SubscriptionPlan(BaseModel):
    """
    Template plans created by admin.
    Assigned to a lab at registration time.
    """
    name = models.CharField(max_length=100)
    storage_gb = models.PositiveIntegerField(help_text='Storage in GB')
    duration_days = models.PositiveIntegerField(help_text='Plan duration in days')
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'subscription_plans'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} — {self.storage_gb}GB / {self.duration_days}d"


class LabHospital(BaseModel):
    """
    Pathlab or Hospital entity.
    Registered only by admin. Login via phone + password.
    """
    class Type(models.TextChoices):
        LAB = 'LAB', 'Pathlab'
        HOSPITAL = 'HOSPITAL', 'Hospital'

    lab_id = models.CharField(
        max_length=12, unique=True,
        help_text='Auto-generated 12-digit numeric ID'
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True)
    password_hash = models.CharField(max_length=255)
    address = models.TextField()
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.LAB)
    is_active = models.BooleanField(default=True)

    # Storage tracking (in MB for precision)
    storage_used_mb = models.FloatField(default=0.0)
    storage_limit_mb = models.FloatField(
        help_text='Derived from plan on registration, overridable by admin'
    )

    # Plan timing
    plan_start = models.DateTimeField(null=True, blank=True)
    plan_end = models.DateTimeField(null=True, blank=True)
    subscription_plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='labs'
    )
    registered_by = models.ForeignKey(
        Admin, on_delete=models.SET_NULL,
        null=True, related_name='registered_labs'
    )
    last_login = models.DateTimeField(null=True, blank=True)

    # portal identifier used in JWT claims
    portal = 'lab'

    class Meta:
        db_table = 'lab_hospitals'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.lab_id})"

    @property
    def is_plan_active(self) -> bool:
        """True if current time is within plan window and manually active."""
        if not self.is_active:
            return False
        if not self.plan_end:
            return False
        return timezone.now() < self.plan_end

    @property
    def storage_limit_gb(self) -> float:
        return round(self.storage_limit_mb / 1024, 2)

    @property
    def storage_used_gb(self) -> float:
        return round(self.storage_used_mb / 1024, 4)

    def has_storage_capacity(self, file_size_mb: float) -> bool:
        return (self.storage_used_mb + file_size_mb) <= self.storage_limit_mb

    def save(self, *args, **kwargs):
        if not self.lab_id:
            self.lab_id = generate_12_digit_uid(LabHospital, 'lab_id')
        super().save(*args, **kwargs)


class User(BaseModel):
    """
    Patient/end-user. Self-registers. Login via WhatsApp OTP only.
    """
    class Gender(models.TextChoices):
        MALE = 'M', 'Male'
        FEMALE = 'F', 'Female'
        OTHER = 'O', 'Other'
        PREFER_NOT = 'N', 'Prefer not to say'

    class BloodGroup(models.TextChoices):
        A_POS = 'A+', 'A+'
        A_NEG = 'A-', 'A-'
        B_POS = 'B+', 'B+'
        B_NEG = 'B-', 'B-'
        AB_POS = 'AB+', 'AB+'
        AB_NEG = 'AB-', 'AB-'
        O_POS = 'O+', 'O+'
        O_NEG = 'O-', 'O-'

    user_uid = models.CharField(
        max_length=12, unique=True,
        help_text='Auto-generated 12-digit numeric ID'
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=15, unique=True)
    birth_date = models.DateField(null=True, blank=True)
    blood_group = models.CharField(
        max_length=5, choices=BloodGroup.choices, blank=True
    )
    gender = models.CharField(
        max_length=1, choices=Gender.choices, blank=True
    )
    address = models.TextField(blank=True)
    profile_photo_key = models.CharField(
        max_length=500, blank=True,
        help_text='S3 object key for profile photo'
    )
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)

    # portal identifier used in JWT claims
    portal = 'user'

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.user_uid})"

    def save(self, *args, **kwargs):
        if not self.user_uid:
            self.user_uid = generate_12_digit_uid(User, 'user_uid')
        super().save(*args, **kwargs)


class OTPVerification(BaseModel):
    """
    Stores hashed OTPs for all verification flows.
    purpose distinguishes login vs consent verification.
    """
    class Purpose(models.TextChoices):
        USER_LOGIN = 'USER_LOGIN', 'User Login'
        CONSENT_VERIFY = 'CONSENT_VERIFY', 'Consent Verification'

    phone = models.CharField(max_length=15)
    otp_hash = models.CharField(max_length=64)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    # Optional link to the consent request this OTP belongs to
    consent_request_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'otp_verifications'
        indexes = [
            models.Index(fields=['phone', 'purpose', 'is_used']),
        ]

    def __str__(self):
        return f"OTP({self.purpose}) — {self.phone}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired
