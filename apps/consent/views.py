from django.utils import timezone
from rest_framework import status, generics, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.permissions import IsLabPortal, IsUserPortal
from apps.core.utils.otp import generate_otp, hash_otp, verify_otp
from apps.core.utils.redis_otp import (
    is_attempt_limit_reached, record_otp_attempt, clear_otp_attempts,
    get_remaining_attempts,
)
from apps.accounts.models import OTPVerification
from apps.consent.models import ConsentRequest, ConsentFile
from apps.consent.serializers import (
    ConsentRequestCreateSerializer, ConsentRequestListSerializer,
    ConsentRequestDetailSerializer, UserConsentVerifyOTPSerializer,
    UserConsentShareSerializer,
)
from apps.core.utils.timezone_utils import now_ist


# ─── Lab Portal ───────────────────────────────────────────────────────────────

class LabConsentListView(generics.ListAPIView):
    """
    Lab sees all consent requests it has sent.
    Filter by status: PENDING | OTP_VERIFIED | ACTIVE | EXPIRED | CANCELLED
    Live/expired is re-evaluated per record via is_access_live property.
    """
    permission_classes = [IsLabPortal]
    serializer_class = ConsentRequestListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['to_user__name', 'to_user__phone', 'to_user__user_uid', 'description']
    ordering_fields = ['created_at', 'consent_expires_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            ConsentRequest.objects
            .filter(from_lab=self.request.user)
            .select_related('from_lab', 'to_user')
            .prefetch_related('consent_files')
        )


class LabConsentRequestView(APIView):
    """
    Lab initiates consent request.
    Looks up user by phone, creates ConsentRequest, generates + sends OTP.
    """
    permission_classes = [IsLabPortal]

    def post(self, request):
        serializer = ConsentRequestCreateSerializer(
            data=request.data,
            context={'lab': request.user},
        )
        serializer.is_valid(raise_exception=True)
        consent = serializer.save()

        # Generate OTP and store hash on the consent record
        otp = generate_otp()
        consent.otp_hash = hash_otp(otp)
        consent.save(update_fields=['otp_hash'])

        # Also store in OTPVerification for unified tracking
        OTPVerification.objects.create(
            phone=consent.to_user.phone,
            otp_hash=hash_otp(otp),
            purpose=OTPVerification.Purpose.CONSENT_VERIFY,
            expires_at=consent.otp_expires_at,
            consent_request_id=consent.id,
        )

        # Dispatch OTP async
        from apps.consent.tasks import send_consent_otp_task
        send_consent_otp_task.delay(
            str(consent.id), consent.to_user.phone, otp
        )

        return Response(
            ConsentRequestDetailSerializer(consent).data,
            status=status.HTTP_201_CREATED,
        )


class LabConsentDetailView(generics.RetrieveAPIView):
    permission_classes = [IsLabPortal]
    serializer_class = ConsentRequestDetailSerializer

    def get_queryset(self):
        return ConsentRequest.objects.filter(
            from_lab=self.request.user
        ).select_related('from_lab', 'to_user').prefetch_related('consent_files__report')


# ─── User Portal ──────────────────────────────────────────────────────────────

class UserConsentListView(generics.ListAPIView):
    """
    User sees consent requests:
    - Default: live/pending only (status=PENDING or ACTIVE with expiry in future)
    - ?history=true: all including expired/cancelled
    """
    permission_classes = [IsUserPortal]
    serializer_class = ConsentRequestListSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        # now = timezone.now()
        now = now_ist()
        show_history = self.request.query_params.get('history', 'false').lower() == 'true'

        qs = ConsentRequest.objects.filter(
            to_user=user
        ).select_related('from_lab', 'to_user').prefetch_related('consent_files')

        if not show_history:
            # Show only actionable/live items:
            # PENDING within OTP window, OTP_VERIFIED, or ACTIVE not yet expired
            from django.db.models import Q
            qs = qs.filter(
                Q(status=ConsentRequest.Status.PENDING, otp_expires_at__gt=now)
                | Q(status=ConsentRequest.Status.OTP_VERIFIED)
                | Q(status=ConsentRequest.Status.ACTIVE, consent_expires_at__gt=now)
            )
        return qs


class UserConsentVerifyOTPView(APIView):
    """
    User enters the OTP received on WhatsApp to verify consent request.
    Enforces 5-attempt Redis limit. On success moves status to OTP_VERIFIED.
    """
    permission_classes = [IsUserPortal]

    def post(self, request, pk):
        serializer = UserConsentVerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = serializer.validated_data['otp']

        try:
            consent = ConsentRequest.objects.get(
                pk=pk, to_user=request.user
            )
        except ConsentRequest.DoesNotExist:
            return Response({'detail': 'Consent request not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Gate 1: request-time expiry check (no background job dependency)
        if not consent.is_otp_window_open:
            return Response(
                {'detail': 'OTP window has expired. The consent request is no longer valid.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        phone = request.user.phone
        purpose = OTPVerification.Purpose.CONSENT_VERIFY

        # Gate 2: Redis attempt limit
        if is_attempt_limit_reached(phone, purpose):
            return Response(
                {'detail': 'Maximum OTP attempts reached. Request a new consent.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Increment before checking (prevents timing attacks)
        attempt_count = record_otp_attempt(phone, purpose)

        if not verify_otp(otp, consent.otp_hash):
            remaining = max(0, 5 - attempt_count)
            return Response(
                {'detail': f'Invalid OTP. {remaining} attempts remaining.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Success
        clear_otp_attempts(phone, purpose)
        consent.status = ConsentRequest.Status.OTP_VERIFIED
        # consent.responded_at = timezone.now()
        consent.responded_at = now_ist()
        consent.save(update_fields=['status', 'responded_at'])

        return Response({
            'detail': 'OTP verified. Please select files to share.',
            'consent_id': str(consent.id),
        })


class UserConsentShareView(APIView):
    """
    User selects which reports to share and sets expiry.
    Only accessible after OTP_VERIFIED status.
    Creates ConsentFile records and moves status to ACTIVE.
    """
    permission_classes = [IsUserPortal]

    def post(self, request, pk):
        try:
            consent = ConsentRequest.objects.get(
                pk=pk,
                to_user=request.user,
                status=ConsentRequest.Status.OTP_VERIFIED,
            )
        except ConsentRequest.DoesNotExist:
            return Response(
                {'detail': 'Consent request not found or not in OTP_VERIFIED state.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UserConsentShareSerializer(
            data=request.data,
            context={'user': request.user},
        )
        serializer.is_valid(raise_exception=True)

        reports = serializer.validated_data['report_ids']  # list of Report objects
        expires_at = serializer.validated_data['expires_at']

        # Create ConsentFile records (ignore duplicates via get_or_create)
        for report in reports:
            ConsentFile.objects.get_or_create(
                consent_request=consent,
                report=report,
                defaults={'expires_at': expires_at, 'is_active': True},
            )

        consent.status = ConsentRequest.Status.ACTIVE
        consent.consent_expires_at = expires_at
        consent.save(update_fields=['status', 'consent_expires_at'])

        # Notify lab async
        from apps.consent.tasks import notify_lab_consent_active
        notify_lab_consent_active.delay(str(consent.id))

        return Response(
            ConsentRequestDetailSerializer(consent).data,
            status=status.HTTP_200_OK,
        )


class UserConsentRevokeView(APIView):
    """User immediately revokes an active consent."""
    permission_classes = [IsUserPortal]

    def post(self, request, pk):
        try:
            consent = ConsentRequest.objects.get(
                pk=pk,
                to_user=request.user,
                status=ConsentRequest.Status.ACTIVE,
            )
        except ConsentRequest.DoesNotExist:
            return Response(
                {'detail': 'Active consent request not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Deactivate all consent files immediately
        ConsentFile.objects.filter(consent_request=consent).update(
            is_active=False,
            # expires_at=timezone.now(),
            expires_at=now_ist(),
        )
        consent.status = ConsentRequest.Status.CANCELLED
        # consent.consent_expires_at = timezone.now()
        consent.consent_expires_at = now_ist()

        consent.save(update_fields=['status', 'consent_expires_at'])

        return Response({'detail': 'Consent revoked successfully.'})


class UserActiveSharesView(generics.ListAPIView):
    """
    User sees a summary of which labs currently have live access
    to which of their files — with expiry dates.
    """
    permission_classes = [IsUserPortal]
    serializer_class = ConsentRequestDetailSerializer

    def get_queryset(self):
        # now = timezone.now()
        now = now_ist()
        return (
            ConsentRequest.objects
            .filter(
                to_user=self.request.user,
                status=ConsentRequest.Status.ACTIVE,
                consent_expires_at__gt=now,
            )
            .select_related('from_lab', 'to_user')
            .prefetch_related('consent_files__report')
        )
