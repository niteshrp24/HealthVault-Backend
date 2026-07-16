from django.utils import timezone
from django.contrib.auth.hashers import make_password
from rest_framework import status, generics, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend

from apps.accounts.models import Admin, LabHospital, User, OTPVerification
from apps.accounts.serializers import (
    AdminLoginSerializer, LabLoginSerializer, LabRegistrationSerializer,
    LabDetailSerializer, LabUpdateSerializer, UserRegistrationSerializer,
    UserProfileSerializer, UserProfileUpdateSerializer, UserListSerializer,
    RequestOTPSerializer, VerifyOTPSerializer,
)
from apps.accounts.backends import (
    get_tokens_for_admin, get_tokens_for_lab, get_tokens_for_user,
)
from apps.accounts.tasks import send_otp_task
from apps.core.permissions import IsAdminPortal, IsUserPortal, IsLabPortal
from apps.core.utils.otp import generate_otp, hash_otp, verify_otp
from apps.core.utils.redis_otp import (
    is_attempt_limit_reached, record_otp_attempt, clear_otp_attempts,
    get_remaining_attempts, is_resend_blocked, set_resend_block,
)

from apps.core.utils.timezone_utils import now_ist
import json
from django.core.cache import cache

# ─── Auth views ──────────────────────────────────────────────────────────────

class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin = serializer.validated_data['admin']
        # admin.last_login = timezone.now()
        admin.last_login = now_ist()
        admin.save(update_fields=['last_login'])
        return Response(get_tokens_for_admin(admin))


class LabLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LabLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lab = serializer.validated_data['lab']
        # lab.last_login = timezone.now()
        lab.last_login = now_ist()
        lab.save(update_fields=['last_login'])
        return Response(get_tokens_for_lab(lab))


class UserRequestOTPView(APIView):
    """
    Step 1 of user login: request OTP.
    Generates OTP, hashes and stores it, dispatches via Celery (WhatsApp + SMS).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']

        if is_resend_blocked(phone, OTPVerification.Purpose.USER_LOGIN):
            return Response(
                {'detail': 'Please wait before requesting a new OTP.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        otp = generate_otp()
        # expires_at = timezone.now() + timezone.timedelta(
        #     seconds=300  # settings.OTP_EXPIRY_SECONDS
        # )
        expires_at = now_ist() + timezone.timedelta(seconds=300)

        # Invalidate any previous unused OTPs for this phone+purpose
        OTPVerification.objects.filter(
            phone=phone,
            purpose=OTPVerification.Purpose.USER_LOGIN,
            is_used=False,
        ).update(is_used=True)

        OTPVerification.objects.create(
            phone=phone,
            otp_hash=hash_otp(otp),
            purpose=OTPVerification.Purpose.USER_LOGIN,
            expires_at=expires_at,
        )

        set_resend_block(phone, OTPVerification.Purpose.USER_LOGIN)

        # Fire async — WhatsApp + SMS fallback
        send_otp_task.delay(phone, otp, OTPVerification.Purpose.USER_LOGIN)

        return Response({'detail': 'OTP sent to your WhatsApp and SMS.'})


class UserVerifyOTPView(APIView):
    """
    Step 2 of user login: verify OTP.
    Enforces 5-attempt limit via Redis. Returns JWT on success.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        otp = serializer.validated_data['otp']
        purpose = OTPVerification.Purpose.USER_LOGIN

        # Redis gate: check attempt limit before DB hit
        if is_attempt_limit_reached(phone, purpose):
            return Response(
                {'detail': 'Maximum OTP attempts reached. Please request a new OTP.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Fetch latest valid (not used) OTP record
        otp_record = (
            OTPVerification.objects
            .filter(phone=phone, purpose=purpose, is_used=False)
            .order_by('-created_at')
            .first()
        )

        # Always increment attempt BEFORE verifying (prevents timing attacks)
        attempt_count = record_otp_attempt(phone, purpose)

        if not otp_record or otp_record.is_expired:
            remaining = max(0, 5 - attempt_count)
            return Response(
                {'detail': f'OTP expired or not found. {remaining} attempts remaining.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not verify_otp(otp, otp_record.otp_hash):
            remaining = max(0, 5 - attempt_count)
            return Response(
                {'detail': f'Invalid OTP. {remaining} attempts remaining.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Success
        otp_record.is_used = True
        otp_record.save(update_fields=['is_used'])
        clear_otp_attempts(phone, purpose)

        try:
            user = User.objects.get(phone=phone, is_active=True)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User account not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # user.last_login = timezone.now()
        user.last_login = now_ist()

        user.save(update_fields=['last_login'])

        return Response(get_tokens_for_user(user))


# class UserRegisterView(APIView):
#     """User self-registration. No OTP needed at registration — just create account."""
#     permission_classes = [AllowAny]

#     def post(self, request):
#         serializer = UserRegistrationSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         user = serializer.save()
#         return Response(
#             {'detail': 'Account created. Please login using OTP.', 'user_uid': user.user_uid},
#             status=status.HTTP_201_CREATED,
#         )


class UserRegisterInitiateView(APIView):
    """
    Step 1: User submits registration form.
    Validates all fields, temporarily stores data in Redis,
    sends OTP to phone. Account is NOT created yet.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # Check phone not already registered
        phone = request.data.get('phone', '').strip()
        if User.objects.filter(phone=phone).exists():
            return Response(
                {'detail': 'This phone number is already registered. Please login.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate all registration fields first
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Resend cooldown
        if is_resend_blocked(phone, 'REGISTER_OTP'):
            return Response(
                {'detail': 'Please wait before requesting a new OTP.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Temporarily store validated form data in Redis (10 min TTL)
        cache_key = f'register_pending:{phone}'
        cache.set(cache_key, json.dumps(request.data), timeout=600)

        # Generate and store OTP
        otp = generate_otp()
        expires_at = now_ist() + timezone.timedelta(seconds=300)

        OTPVerification.objects.filter(
            phone=phone,
            purpose=OTPVerification.Purpose.USER_LOGIN,
            is_used=False,
            consent_request_id=None,
        ).update(is_used=True)

        OTPVerification.objects.create(
            phone=phone,
            otp_hash=hash_otp(otp),
            purpose=OTPVerification.Purpose.USER_LOGIN,
            expires_at=expires_at,
        )

        set_resend_block(phone, 'REGISTER_OTP')

        # Send OTP async
        send_otp_task.delay(phone, otp, 'REGISTER')

        return Response({
            'detail': 'OTP sent to your WhatsApp and SMS. Please verify to complete registration.',
            'phone': phone,
        })


class UserRegisterVerifyView(APIView):
    """
    Step 2: User enters OTP received on WhatsApp.
    Verifies OTP, retrieves stored form data from Redis,
    creates the actual user account.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get('phone', '').strip()
        otp = request.data.get('otp', '').strip()

        if not phone or not otp:
            return Response(
                {'detail': 'Phone and OTP are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check phone not already registered
        if User.objects.filter(phone=phone).exists():
            return Response(
                {'detail': 'This phone number is already registered.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Redis attempt limit
        if is_attempt_limit_reached(phone, 'REGISTER_OTP'):
            return Response(
                {'detail': 'Maximum OTP attempts reached. Please restart registration.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Fetch OTP record
        otp_record = (
            OTPVerification.objects
            .filter(
                phone=phone,
                purpose=OTPVerification.Purpose.USER_LOGIN,
                is_used=False,
                consent_request_id=None,
            )
            .order_by('-created_at')
            .first()
        )

        attempt_count = record_otp_attempt(phone, 'REGISTER_OTP')

        if not otp_record or otp_record.is_expired:
            remaining = max(0, 5 - attempt_count)
            # Clear pending registration data too
            cache.delete(f'register_pending:{phone}')
            return Response(
                {'detail': f'OTP expired. {remaining} attempts remaining. Please restart registration.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not verify_otp(otp, otp_record.otp_hash):
            remaining = max(0, 5 - attempt_count)
            return Response(
                {'detail': f'Invalid OTP. {remaining} attempts remaining.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # OTP valid — retrieve stored form data from Redis
        cache_key = f'register_pending:{phone}'
        stored_data = cache.get(cache_key)

        if not stored_data:
            return Response(
                {'detail': 'Registration session expired. Please fill the form again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark OTP used and clear attempts
        otp_record.is_used = True
        otp_record.save(update_fields=['is_used'])
        clear_otp_attempts(phone, 'REGISTER_OTP')
        cache.delete(cache_key)

        # Create the user
        form_data = json.loads(stored_data)
        serializer = UserRegistrationSerializer(data=form_data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                'detail': 'Registration successful. You can now login.',
                'user_uid': user.user_uid,
            },
            status=status.HTTP_201_CREATED,
        )

# ─── Admin Portal views ───────────────────────────────────────────────────────

class AdminLabListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminPortal]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'email', 'phone', 'lab_id']
    filterset_fields = ['type', 'is_active']
    ordering_fields = ['name', 'created_at', 'plan_end', 'storage_used_mb']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LabRegistrationSerializer
        return LabDetailSerializer

    def get_queryset(self):
        return LabHospital.objects.select_related('subscription_plan', 'registered_by')


class AdminLabDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminPortal]
    queryset = LabHospital.objects.select_related('subscription_plan')

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return LabUpdateSerializer
        return LabDetailSerializer


class AdminLabDeactivateView(APIView):
    permission_classes = [IsAdminPortal]

    def post(self, request, pk):
        try:
            lab = LabHospital.objects.get(pk=pk)
        except LabHospital.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        lab.is_active = not lab.is_active
        lab.save(update_fields=['is_active'])
        state = 'activated' if lab.is_active else 'deactivated'
        return Response({'detail': f'Lab {state} successfully.', 'is_active': lab.is_active})


class AdminUserListView(generics.ListAPIView):
    permission_classes = [IsAdminPortal]
    serializer_class = UserListSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'phone', 'email', 'user_uid']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']
    queryset = User.objects.all()


class AdminUserDeactivateView(APIView):
    permission_classes = [IsAdminPortal]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        state = 'activated' if user.is_active else 'deactivated'
        return Response({'detail': f'User {state} successfully.', 'is_active': user.is_active})


# ─── User Portal views ────────────────────────────────────────────────────────

class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsUserPortal]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UserProfileUpdateSerializer
        return UserProfileSerializer

    def get_object(self):
        return self.request.user




#new
class LabProfileView(APIView):
    permission_classes = [IsLabPortal]

    def get(self, request):
        lab = request.user
        from apps.reports.models import Report
        from apps.accounts.models import User
        from django.db.models import Count

        report_count = Report.objects.filter(
            uploaded_by_lab=lab, is_deleted=False
        ).count()

        user_count = Report.objects.filter(
            uploaded_by_lab=lab, is_deleted=False
        ).values('belongs_to_user').distinct().count()

        return Response({
            'id': str(lab.id),
            'lab_id': lab.lab_id,
            'name': lab.name,
            'email': lab.email,
            'phone': lab.phone,
            'address': lab.address,
            'type': lab.type,
            'is_active': lab.is_active,
            'is_plan_active': lab.is_plan_active,
            'plan_start': lab.plan_start,
            'plan_end': lab.plan_end,
            'subscription_plan': lab.subscription_plan.name if lab.subscription_plan else None,
            'storage': {
                'used_mb': round(lab.storage_used_mb, 2),
                'used_gb': lab.storage_used_gb,
                'limit_mb': round(lab.storage_limit_mb, 2),
                'limit_gb': lab.storage_limit_gb,
                'utilisation_percent': round(
                    (lab.storage_used_mb / lab.storage_limit_mb * 100)
                    if lab.storage_limit_mb else 0, 1
                ),
            },
            'stats': {
                'total_reports': report_count,
                'total_users': user_count,
            },
            'created_at': lab.created_at,
            'last_login': lab.last_login,
        })