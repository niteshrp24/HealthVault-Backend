from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import Admin, LabHospital, User, OTPVerification, SubscriptionPlan

from apps.core.utils.timezone_utils import now_ist

# ─── Admin ───────────────────────────────────────────────────────────────────

class AdminLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            admin = Admin.objects.get(username=attrs['username'])
        except Admin.DoesNotExist:
            raise serializers.ValidationError('Invalid credentials.')
        if not check_password(attrs['password'], admin.password_hash):
            raise serializers.ValidationError('Invalid credentials.')
        attrs['admin'] = admin
        return attrs


# ─── Lab / Hospital ──────────────────────────────────────────────────────────

class LabLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            lab = LabHospital.objects.get(phone=attrs['phone'])
        except LabHospital.DoesNotExist:
            raise serializers.ValidationError('Invalid credentials.')
        if not check_password(attrs['password'], lab.password_hash):
            raise serializers.ValidationError('Invalid credentials.')
        if not lab.is_active:
            raise serializers.ValidationError('Account has been deactivated.')
        if not lab.is_plan_active:
            raise serializers.ValidationError('Subscription plan has expired.')
        attrs['lab'] = lab
        return attrs


# class LabRegistrationSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(write_only=True, min_length=8)
#     subscription_plan_id = serializers.UUIDField(write_only=True)
#     plan_duration_days = serializers.IntegerField(write_only=True)
#     storage_gb = serializers.FloatField(write_only=True)

#     class Meta:
#         model = LabHospital
#         fields = [
#             'name', 'email', 'phone', 'password', 'address', 'type',
#             'subscription_plan_id', 'plan_duration_days', 'storage_gb',
#         ]

#     def validate_subscription_plan_id(self, value):
#         try:
#             return SubscriptionPlan.objects.get(id=value)
#         except SubscriptionPlan.DoesNotExist:
#             raise serializers.ValidationError('Subscription plan not found.')

#     def create(self, validated_data):
#         plan = validated_data.pop('subscription_plan_id')
#         duration_days = validated_data.pop('plan_duration_days')
#         storage_gb = validated_data.pop('storage_gb')
#         password = validated_data.pop('password')
#         admin = self.context['request'].user

#         now = timezone.now()
#         lab = LabHospital.objects.create(
#             **validated_data,
#             password_hash=make_password(password),
#             subscription_plan=plan,
#             storage_limit_mb=storage_gb * 1024,
#             plan_start=now,
#             plan_end=now + timezone.timedelta(days=duration_days),
#             registered_by=admin,
#         )
#         return lab

class LabRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    subscription_plan_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    plan_duration_days = serializers.IntegerField(write_only=True)
    storage_gb = serializers.FloatField(write_only=True)

    class Meta:
        model = LabHospital
        fields = [
            'name', 'email', 'phone', 'password', 'address', 'type',
            'subscription_plan_id', 'plan_duration_days', 'storage_gb',
        ]

    def validate_subscription_plan_id(self, value):
        if value is None:
            return None
        try:
            return SubscriptionPlan.objects.get(id=value)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError('Subscription plan not found.')

    def create(self, validated_data):
        plan = validated_data.pop('subscription_plan_id', None)
        duration_days = validated_data.pop('plan_duration_days')
        storage_gb = validated_data.pop('storage_gb')
        password = validated_data.pop('password')
        admin = self.context['request'].user

        # now = timezone.now()
        now = now_ist()

        lab = LabHospital.objects.create(
            **validated_data,
            password_hash=make_password(password),
            subscription_plan=plan,
            storage_limit_mb=storage_gb * 1024,
            plan_start=now,
            plan_end=now + timezone.timedelta(days=duration_days),
            registered_by=admin,
        )
        return lab


class LabDetailSerializer(serializers.ModelSerializer):
    storage_used_gb = serializers.FloatField(read_only=True)
    storage_limit_gb = serializers.FloatField(read_only=True)
    is_plan_active = serializers.BooleanField(read_only=True)
    subscription_plan_name = serializers.CharField(
        source='subscription_plan.name', read_only=True
    )
    report_count = serializers.SerializerMethodField()

    class Meta:
        model = LabHospital
        exclude = ['password_hash']

    def get_report_count(self, obj):
        return obj.reports.filter(is_deleted=False).count()


class LabUpdateSerializer(serializers.ModelSerializer):
    """Admin use: update storage, plan dates, active status."""
    storage_gb = serializers.FloatField(write_only=True, required=False)

    class Meta:
        model = LabHospital
        fields = [
            'name', 'email', 'phone', 'address', 'type',
            'is_active', 'plan_start', 'plan_end',
            'subscription_plan', 'storage_gb',
        ]

    def update(self, instance, validated_data):
        storage_gb = validated_data.pop('storage_gb', None)
        if storage_gb is not None:
            instance.storage_limit_mb = storage_gb * 1024
        return super().update(instance, validated_data)


# ─── User ────────────────────────────────────────────────────────────────────

class UserRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'name', 'email', 'phone', 'birth_date',
            'blood_group', 'gender', 'address',
        ]

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError('Phone number already registered.')
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ['profile_photo_key']
        read_only_fields = ['id', 'user_uid', 'phone', 'created_at', 'updated_at', 'last_login']


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'name', 'email', 'birth_date',
            'blood_group', 'gender', 'address',
        ]


class UserListSerializer(serializers.ModelSerializer):
    """Lightweight listing for admin view."""
    class Meta:
        model = User
        fields = [
            'id', 'user_uid', 'name', 'phone', 'email',
            'blood_group', 'gender', 'is_active', 'created_at',
        ]


# ─── OTP ─────────────────────────────────────────────────────────────────────

class RequestOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)

    def validate_phone(self, value):
        if not User.objects.filter(phone=value, is_active=True).exists():
            raise serializers.ValidationError('No active account found for this number.')
        return value


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6, min_length=6)
