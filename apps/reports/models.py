import uuid
from django.db import models
from django.db.models import F
from apps.core.models import BaseModel


class Report(BaseModel):
    """
    A medical report file uploaded by a lab for a specific user.
    File content lives in S3/MinIO. Only the storage key is persisted here.
    """
    report_uid = models.CharField(
        max_length=12, unique=True,
        help_text='Auto-generated 12-digit unique ID'
    )
    uploaded_by_lab = models.ForeignKey(
        'accounts.LabHospital',
        on_delete=models.CASCADE,
        related_name='reports',
    )
    belongs_to_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='reports',
    )
    file_key = models.CharField(
        max_length=500,
        help_text='S3/MinIO object key — never exposed directly to clients'
    )
    original_filename = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file_size_mb = models.FloatField(default=0.0)
    issued_date = models.DateField(
        null=True, blank=True,
        help_text='Date the report was issued (may differ from upload date)'
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['uploaded_by_lab', 'belongs_to_user']),
            models.Index(fields=['belongs_to_user', 'is_deleted']),
        ]

    def __str__(self):
        return f"{self.report_uid} — {self.original_filename}"

    def save(self, *args, **kwargs):
        from apps.core.utils.uid_generator import generate_12_digit_uid
        if not self.report_uid:
            self.report_uid = generate_12_digit_uid(Report, 'report_uid')
        super().save(*args, **kwargs)

    def soft_delete(self):
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])
        # Release storage quota back to lab
        self.uploaded_by_lab.__class__.objects.filter(
            pk=self.uploaded_by_lab_id
        ).update(storage_used_mb=F('storage_used_mb') - self.file_size_mb)
