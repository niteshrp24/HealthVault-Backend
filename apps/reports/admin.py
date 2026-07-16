from django.contrib import admin
from apps.reports.models import Report
from apps.consent.models import ConsentRequest, ConsentFile
from apps.notifications.models import Notification


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = [
        'report_uid', 'original_filename', 'uploaded_by_lab',
        'belongs_to_user', 'file_size_mb', 'is_deleted', 'created_at',
    ]
    list_filter = ['is_deleted', 'uploaded_by_lab']
    search_fields = [
        'report_uid', 'original_filename',
        'belongs_to_user__name', 'belongs_to_user__phone',
        'uploaded_by_lab__name',
    ]
    readonly_fields = ['id', 'report_uid', 'created_at', 'updated_at', 'deleted_at']
    # Never expose file_key in the admin list view
    exclude = []


@admin.register(ConsentRequest)
class ConsentRequestAdmin(admin.ModelAdmin):
    list_display = [
        'from_lab', 'to_user', 'status',
        'otp_expires_at', 'consent_expires_at', 'created_at',
    ]
    list_filter = ['status']
    search_fields = [
        'from_lab__name', 'from_lab__lab_id',
        'to_user__name', 'to_user__phone', 'to_user__user_uid',
    ]
    readonly_fields = ['id', 'otp_hash', 'created_at', 'updated_at', 'responded_at']


@admin.register(ConsentFile)
class ConsentFileAdmin(admin.ModelAdmin):
    list_display = ['consent_request', 'report', 'expires_at', 'is_active']
    list_filter = ['is_active']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['sent_to_lab', 'channel', 'status', 'created_at']
    list_filter = ['channel', 'status']
    search_fields = ['sent_to_lab__name', 'message']
    readonly_fields = ['id', 'created_at', 'updated_at']
