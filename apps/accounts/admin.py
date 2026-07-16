from django.contrib import admin
from apps.accounts.models import Admin, LabHospital, User, OTPVerification, SubscriptionPlan


@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'created_at', 'last_login']
    search_fields = ['username', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login']
    exclude = ['password_hash']


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'storage_gb', 'duration_days', 'created_at']
    search_fields = ['name']


@admin.register(LabHospital)
class LabHospitalAdmin(admin.ModelAdmin):
    list_display = [
        'lab_id', 'name', 'type', 'phone', 'is_active',
        'storage_used_mb', 'storage_limit_mb', 'plan_end',
    ]
    list_filter = ['type', 'is_active']
    search_fields = ['name', 'lab_id', 'phone', 'email']
    readonly_fields = ['id', 'lab_id', 'created_at', 'updated_at', 'last_login']
    exclude = ['password_hash']


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['user_uid', 'name', 'phone', 'blood_group', 'is_active', 'created_at']
    list_filter = ['is_active', 'blood_group', 'gender']
    search_fields = ['name', 'phone', 'email', 'user_uid']
    readonly_fields = ['id', 'user_uid', 'created_at', 'updated_at', 'last_login']


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ['phone', 'purpose', 'is_used', 'expires_at', 'created_at']
    list_filter = ['purpose', 'is_used']
    search_fields = ['phone']
    readonly_fields = ['id', 'otp_hash', 'created_at', 'updated_at']
