from rest_framework import serializers
from django.utils import timezone
from apps.reports.models import Report
from apps.accounts.models import User
from apps.core.utils.timezone_utils import now_ist

# class ReportUploadSerializer(serializers.ModelSerializer):
#     """Used by lab to upload a new report for a user."""
#     user_phone = serializers.CharField(write_only=True)

#     class Meta:
#         model = Report
#         fields = [
#             'user_phone', 'original_filename', 'description',
#             'issued_date', 'file_key', 'file_size_mb',
#         ]

#     def validate_user_phone(self, value):
#         try:
#             return User.objects.get(phone=value, is_active=True)
#         except User.DoesNotExist:
#             raise serializers.ValidationError('No active user found with this phone number.')

#     def validate(self, attrs):
#         user = attrs['user_phone']  # resolved to User object in validate_user_phone
#         lab = self.context['lab']
#         file_size_mb = attrs.get('file_size_mb', 0)

#         if not lab.is_plan_active:
#             raise serializers.ValidationError('Lab subscription is inactive or expired.')

#         if not lab.has_storage_capacity(file_size_mb):
#             raise serializers.ValidationError(
#                 f'Storage limit exceeded. '
#                 f'Available: {round(lab.storage_limit_mb - lab.storage_used_mb, 2)} MB, '
#                 f'Required: {file_size_mb} MB.'
#             )
#         # attrs['user'] = user
#         # attrs['belongs_to_user'] = user   #added
#         return attrs

#     def create(self, validated_data):
#         from django.db.models import F
#         user = validated_data.pop('user_phone')  # already resolved User object
#         lab = self.context['lab']
#         file_size_mb = validated_data.get('file_size_mb', 0)

#         report = Report.objects.create(
#             uploaded_by_lab=lab,
#             belongs_to_user=user,
#             **validated_data,
#         )

#         # Update lab storage usage atomically
#         lab.__class__.objects.filter(pk=lab.pk).update(
#             storage_used_mb=F('storage_used_mb') + file_size_mb
#         )
#         return report

class ReportUploadSerializer(serializers.ModelSerializer):
    user_phone = serializers.CharField(write_only=True)
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Report
        fields = [
            'user_phone', 'file', 'description', 'issued_date',
        ]

    def validate_user_phone(self, value):
        try:
            return User.objects.get(phone=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError('No active user found with this phone number.')

    def validate_file(self, value):
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError('Only PDF files are allowed.')
        file_size_mb = value.size / (1024 * 1024)
        if file_size_mb > 50:
            raise serializers.ValidationError('File size cannot exceed 50MB.')
        return value

    def validate(self, attrs):
        lab = self.context['lab']
        file = attrs.get('file')
        file_size_mb = round(file.size / (1024 * 1024), 4)

        if not lab.is_plan_active:
            raise serializers.ValidationError('Lab subscription is inactive or expired.')
        if not lab.has_storage_capacity(file_size_mb):
            raise serializers.ValidationError(
                f'Storage limit exceeded. '
                f'Available: {round(lab.storage_limit_mb - lab.storage_used_mb, 2)} MB, '
                f'Required: {file_size_mb} MB.'
            )
        return attrs

    def create(self, validated_data):
        import uuid
        import boto3
        from botocore.client import Config
        from django.conf import settings
        from django.db.models import F

        user = validated_data.pop('user_phone')
        file = validated_data.pop('file')
        lab = self.context['lab']

        file_size_mb = round(file.size / (1024 * 1024), 4)
        file_extension = file.name.split('.')[-1].lower()
        file_key = f"reports/{lab.lab_id}/{uuid.uuid4()}.{file_extension}"

        # Upload to S3/MinIO
        s3_kwargs = {
            'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
            'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY,
            'region_name': settings.AWS_S3_REGION_NAME,
            'config': Config(signature_version='s3v4'),
        }
        if settings.AWS_S3_ENDPOINT_URL:
            s3_kwargs['endpoint_url'] = settings.AWS_S3_ENDPOINT_URL

        s3_client = boto3.client('s3', **s3_kwargs)
        s3_client.upload_fileobj(
            file,
            settings.AWS_STORAGE_BUCKET_NAME,
            file_key,
            ExtraArgs={
                'ContentType': 'application/pdf',
                'ContentDisposition': 'inline',
            }
        )

        report = Report.objects.create(
            uploaded_by_lab=lab,
            belongs_to_user=user,
            file_key=file_key,
            original_filename=file.name,
            file_size_mb=file_size_mb,
            **validated_data,
        )

        # Update lab storage usage atomically
        lab.__class__.objects.filter(pk=lab.pk).update(
            storage_used_mb=F('storage_used_mb') + file_size_mb
        )

        return report

class ReportListSerializer(serializers.ModelSerializer):
    """Lightweight listing — no signed URL generated here."""
    user_name = serializers.CharField(source='belongs_to_user.name', read_only=True)
    user_uid = serializers.CharField(source='belongs_to_user.user_uid', read_only=True)
    user_phone = serializers.CharField(source='belongs_to_user.phone', read_only=True)
    lab_name = serializers.CharField(source='uploaded_by_lab.name', read_only=True)
    lab_id = serializers.CharField(source='uploaded_by_lab.lab_id', read_only=True)
    is_consent_based = serializers.SerializerMethodField()
    consent_expires_at = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id', 'report_uid', 'original_filename', 'description',
            'file_size_mb', 'issued_date', 'created_at',
            'user_name', 'user_uid', 'user_phone',
            'lab_name', 'lab_id',
            'is_consent_based', 'consent_expires_at',
            'is_deleted',
        ]

    # def get_is_consent_based(self, obj):
    #     # Annotated by view queryset for performance
    #     return getattr(obj, 'is_consent_based', False)

    # def get_consent_expires_at(self, obj):
    #     return getattr(obj, 'consent_expires_at', None)


    def get_is_consent_based(self, obj):
        from apps.consent.models import ConsentFile
        from django.utils import timezone
        return ConsentFile.objects.filter(
            report=obj,
            is_active=True,
            # expires_at__gt=timezone.now(),
            expires_at__gt=now_ist(),
        ).exists()

    def get_consent_expires_at(self, obj):
        from apps.consent.models import ConsentFile
        from django.utils import timezone
        consent_file = ConsentFile.objects.filter(
            report=obj,
            is_active=True,
            # expires_at__gt=timezone.now(),
            expires_at__gt=now_ist(),
        ).order_by('-expires_at').first()
        return consent_file.expires_at if consent_file else None


class ReportDetailSerializer(ReportListSerializer):
    """Full detail — still no signed URL (generated on /stream/ endpoint)."""
    class Meta(ReportListSerializer.Meta):
        fields = ReportListSerializer.Meta.fields + ['deleted_at']


class UserReportSerializer(serializers.ModelSerializer):
    """User-facing report listing — no lab internal fields exposed."""
    lab_name = serializers.CharField(source='uploaded_by_lab.name', read_only=True)
    lab_id = serializers.CharField(source='uploaded_by_lab.lab_id', read_only=True)

    class Meta:
        model = Report
        fields = [
            'id', 'report_uid', 'original_filename', 'description',
            'file_size_mb', 'issued_date', 'created_at',
            'lab_name', 'lab_id',
        ]
