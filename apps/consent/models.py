from django.db import models
from django.utils import timezone
from apps.core.models import BaseModel


class ConsentRequest(BaseModel):
    """
    Initiated by a lab asking a user to share their reports.
    Flow: PENDING → OTP_VERIFIED → ACTIVE → EXPIRED / CANCELLED
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending OTP verification'
        OTP_VERIFIED = 'OTP_VERIFIED', 'OTP verified, awaiting file selection'
        ACTIVE = 'ACTIVE', 'Active — files shared'
        EXPIRED = 'EXPIRED', 'Expired'
        CANCELLED = 'CANCELLED', 'Cancelled (OTP timed out or lab cancelled)'

    from_lab = models.ForeignKey(
        'accounts.LabHospital',
        on_delete=models.CASCADE,
        related_name='sent_consents',
    )
    to_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='received_consents',
    )
    description = models.TextField(
        help_text='Lab-provided reason for requesting access'
    )
    otp_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    otp_expires_at = models.DateTimeField()
    consent_expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Set by user when sharing files; null until user defines expiry'
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'consent_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['from_lab', 'status']),
            models.Index(fields=['to_user', 'status']),
        ]

    def __str__(self):
        return f"Consent {self.from_lab.lab_id} → {self.to_user.user_uid} [{self.status}]"

    @property
    def is_otp_window_open(self) -> bool:
        """True while OTP can still be verified (5-minute window)."""
        return (
            self.status == self.Status.PENDING
            and timezone.now() < self.otp_expires_at
        )

    @property
    def is_access_live(self) -> bool:
        """
        True if the lab currently has live access to the shared files.
        Evaluated at request time — no background job needed for enforcement.
        """
        if self.status != self.Status.ACTIVE:
            return False
        if not self.consent_expires_at:
            return False
        return timezone.now() < self.consent_expires_at

    @property
    def is_expired(self) -> bool:
        if not self.consent_expires_at:
            return False
        return timezone.now() >= self.consent_expires_at


class ConsentFile(BaseModel):
    """
    Junction: a specific Report shared under a ConsentRequest.
    Expiry is re-evaluated at every access — is_active is housekeeping only.
    """
    consent_request = models.ForeignKey(
        ConsentRequest,
        on_delete=models.CASCADE,
        related_name='consent_files',
    )
    report = models.ForeignKey(
        'reports.Report',
        on_delete=models.CASCADE,
        related_name='consent_files',
    )
    expires_at = models.DateTimeField(
        help_text='Mirrors consent_request.consent_expires_at at time of sharing'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Housekeeping flag — views re-check expires_at directly'
    )

    class Meta:
        db_table = 'consent_files'
        unique_together = [('consent_request', 'report')]
        indexes = [
            models.Index(fields=['consent_request', 'is_active']),
            models.Index(fields=['report', 'is_active']),
        ]

    def __str__(self):
        return f"ConsentFile: {self.report.report_uid} under {self.consent_request_id}"

    @property
    def is_access_live(self) -> bool:
        """Request-time check — always re-evaluates clock."""
        return self.is_active and timezone.now() < self.expires_at
