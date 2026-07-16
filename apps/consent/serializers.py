from rest_framework import serializers
from django.utils import timezone
from apps.consent.models import ConsentRequest, ConsentFile
from apps.reports.models import Report
from apps.core.utils.timezone_utils import now_ist


class ConsentRequestCreateSerializer(serializers.ModelSerializer):
    """Lab initiates a consent request by supplying user phone + description."""
    user_phone = serializers.CharField(write_only=True)

    class Meta:
        model = ConsentRequest
        fields = ['user_phone', 'description']

    def validate_user_phone(self, value):
        from apps.accounts.models import User
        try:
            return User.objects.get(phone=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError('No active user found with this phone number.')

    def create(self, validated_data):
        user = validated_data.pop('user_phone')  # resolved User object
        lab = self.context['lab']

        # otp_expires_at = timezone.now() + timezone.timedelta(seconds=300)
        otp_expires_at = now_ist() + timezone.timedelta(seconds=300)

        consent = ConsentRequest.objects.create(
            from_lab=lab,
            to_user=user,
            otp_expires_at=otp_expires_at,
            **validated_data,
        )
        return consent


class ConsentFileSerializer(serializers.ModelSerializer):
    report_uid = serializers.CharField(source='report.report_uid', read_only=True)
    filename = serializers.CharField(source='report.original_filename', read_only=True)
    issued_date = serializers.DateField(source='report.issued_date', read_only=True)

    class Meta:
        model = ConsentFile
        fields = [
            'id', 'report_id', 'report_uid', 'filename',
            'issued_date', 'expires_at', 'is_active',
        ]


class ConsentRequestListSerializer(serializers.ModelSerializer):
    lab_name = serializers.CharField(source='from_lab.name', read_only=True)
    lab_id = serializers.CharField(source='from_lab.lab_id', read_only=True)
    user_name = serializers.CharField(source='to_user.name', read_only=True)
    user_uid = serializers.CharField(source='to_user.user_uid', read_only=True)
    is_access_live = serializers.BooleanField(read_only=True)
    file_count = serializers.SerializerMethodField()

    class Meta:
        model = ConsentRequest
        fields = [
            'id', 'lab_name', 'lab_id', 'user_name', 'user_uid',
            'description', 'status', 'is_access_live',
            'otp_expires_at', 'consent_expires_at',
            'created_at', 'responded_at', 'file_count',
        ]

    def get_file_count(self, obj):
        return obj.consent_files.count()


class ConsentRequestDetailSerializer(ConsentRequestListSerializer):
    files = ConsentFileSerializer(source='consent_files', many=True, read_only=True)

    class Meta(ConsentRequestListSerializer.Meta):
        fields = ConsentRequestListSerializer.Meta.fields + ['files']


class UserConsentVerifyOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, min_length=6)


class UserConsentShareSerializer(serializers.Serializer):
    """User selects which reports to share and sets an expiry datetime."""
    report_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
    )
    expires_at = serializers.DateTimeField()

    def validate_expires_at(self, value):
        # if value <= timezone.now():
        if value <= now_ist():
            raise serializers.ValidationError('Expiry must be in the future.')
        return value

    def validate_report_ids(self, value):
        user = self.context['user']
        reports = Report.objects.filter(
            id__in=value,
            belongs_to_user=user,
            is_deleted=False,
        )
        if reports.count() != len(value):
            raise serializers.ValidationError(
                'One or more report IDs are invalid or do not belong to you.'
            )
        return list(reports)
