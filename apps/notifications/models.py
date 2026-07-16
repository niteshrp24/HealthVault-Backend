from django.db import models
from apps.core.models import BaseModel


class Notification(BaseModel):
    """
    Messages sent by admin to a lab/hospital via one or more channels.
    """
    class Channel(models.TextChoices):
        INAPP = 'INAPP', 'In-App'
        EMAIL = 'EMAIL', 'Email'
        SMS = 'SMS', 'SMS'
        WHATSAPP = 'WHATSAPP', 'WhatsApp'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'

    sent_by = models.ForeignKey(
        'accounts.Admin',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_notifications',
    )
    sent_to_lab = models.ForeignKey(
        'accounts.LabHospital',
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    message = models.TextField()
    channel = models.CharField(max_length=10, choices=Channel.choices)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    error_detail = models.TextField(blank=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification to {self.sent_to_lab.name} via {self.channel}"
