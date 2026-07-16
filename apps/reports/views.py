from django.utils import timezone
from rest_framework import status, generics, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.permissions import IsLabPortal, IsUserPortal
from apps.core.utils.storage import (
    generate_presigned_view_url,
    generate_presigned_download_url,
)
from apps.reports.models import Report
from apps.reports.serializers import (
    ReportUploadSerializer, ReportListSerializer,
    ReportDetailSerializer, UserReportSerializer,
)
from apps.consent.models import ConsentFile

from rest_framework.parsers import MultiPartParser, FormParser

from apps.core.utils.timezone_utils import now_ist

# ─── Lab Portal ───────────────────────────────────────────────────────────────

# class LabReportUploadView(APIView):
#     """
#     Lab uploads a new report for a user.
#     After creation, the report is automatically visible in the user's portal.
#     """
#     permission_classes = [IsLabPortal]

#     def post(self, request):
#         serializer = ReportUploadSerializer(
#             data=request.data,
#             context={'lab': request.user, 'request': request},
#         )
#         serializer.is_valid(raise_exception=True)
#         report = serializer.save()

#         # Notify user async (task defined in reports/tasks.py)
#         from apps.reports.tasks import notify_user_new_report
#         notify_user_new_report.delay(str(report.id))

#         return Response(
#             ReportDetailSerializer(report).data,
#             status=status.HTTP_201_CREATED,
#         )

class LabReportUploadView(APIView):
    permission_classes = [IsLabPortal]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = ReportUploadSerializer(
            data=request.data,
            context={'lab': request.user, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        report = serializer.save()

        from apps.reports.tasks import notify_user_new_report
        notify_user_new_report.delay(str(report.id))

        return Response(
            ReportDetailSerializer(report).data,
            status=status.HTTP_201_CREATED,
        )

# class LabReportListView(generics.ListAPIView):
#     """
#     Lab sees all reports it owns PLUS reports accessible via active consent.
#     Supports filter by type: own | consented | expired_consent
#     """
#     permission_classes = [IsLabPortal]
#     serializer_class = ReportListSerializer
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     search_fields = [
#         'original_filename', 'description',
#         'belongs_to_user__name', 'belongs_to_user__phone',
#         'belongs_to_user__user_uid',
#     ]
#     filterset_fields = ['issued_date']
#     ordering_fields = ['created_at', 'issued_date', 'file_size_mb', 'original_filename']
#     ordering = ['-created_at']

#     def get_queryset(self):
#         lab = self.request.user
#         report_type = self.request.query_params.get('type', 'all')
#         now = timezone.now()

#         if report_type == 'own':
#             return (
#                 Report.objects
#                 .filter(uploaded_by_lab=lab, is_deleted=False)
#                 .select_related('belongs_to_user', 'uploaded_by_lab')
#             )

#         if report_type == 'consented':
#             # Only reports with currently active consent
#             consented_ids = (
#                 ConsentFile.objects
#                 .filter(
#                     consent_request__from_lab=lab,
#                     consent_request__status='ACTIVE',
#                     expires_at__gt=now,
#                     is_active=True,
#                 )
#                 .values_list('report_id', flat=True)
#             )
#             return (
#                 Report.objects
#                 .filter(id__in=consented_ids, is_deleted=False)
#                 .select_related('belongs_to_user', 'uploaded_by_lab')
#             )

#         if report_type == 'expired_consent':
#             # Show metadata of expired consent files (unaccessible but visible)
#             expired_ids = (
#                 ConsentFile.objects
#                 .filter(
#                     consent_request__from_lab=lab,
#                     is_active=False,
#                 )
#                 .values_list('report_id', flat=True)
#             )
#             return (
#                 Report.objects
#                 .filter(id__in=expired_ids)
#                 .select_related('belongs_to_user', 'uploaded_by_lab')
#             )

#         # Default: own + active consented combined
#         own_qs = Report.objects.filter(uploaded_by_lab=lab, is_deleted=False)
#         active_consent_ids = (
#             ConsentFile.objects
#             .filter(
#                 consent_request__from_lab=lab,
#                 consent_request__status='ACTIVE',
#                 expires_at__gt=now,
#                 is_active=True,
#             )
#             .values_list('report_id', flat=True)
#         )
#         consented_qs = Report.objects.filter(id__in=active_consent_ids, is_deleted=False)
#         return (own_qs | consented_qs).distinct().select_related(
#             'belongs_to_user', 'uploaded_by_lab'
#         )


class LabReportListView(generics.ListAPIView):
    """
    Lab sees all reports it owns PLUS reports accessible via active consent.
    Supports filter by type: own | consented | expired_consent
    """
    permission_classes = [IsLabPortal]
    serializer_class = ReportListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    search_fields = [
        'original_filename',
        'description',
        'belongs_to_user__name',
        'belongs_to_user__phone',
        'belongs_to_user__user_uid',
    ]

    filterset_fields = ['issued_date']

    ordering_fields = [
        'created_at',
        'issued_date',
        'file_size_mb',
        'original_filename'
    ]

    ordering = ['-created_at']

    def get_queryset(self):

        lab = self.request.user
        report_type = self.request.query_params.get('type', 'all')
        # now = timezone.now()
        now= now_ist()

        print("\n================ DEBUG START ================")
        print("CURRENT LAB ID:", lab.id)
        print("CURRENT LAB NAME:", lab.name)
        print("REPORT TYPE:", report_type)

        # ───────────────── OWN REPORTS ─────────────────
        if report_type == 'own':

            own_qs = (
                Report.objects
                .filter(uploaded_by_lab=lab, is_deleted=False)
                .select_related('belongs_to_user', 'uploaded_by_lab')
            )

            print("\nOWN REPORTS:")
            print(list(
                own_qs.values(
                    'id',
                    'original_filename',
                    'uploaded_by_lab_id',
                    'uploaded_by_lab__name'
                )
            ))

            print("================ DEBUG END ================\n")

            return own_qs

        # ───────────────── CONSENTED REPORTS ─────────────────
        if report_type == 'consented':

            consented_ids = (
                ConsentFile.objects
                .filter(
                    consent_request__from_lab=lab,
                    consent_request__status='ACTIVE',
                    expires_at__gt=now,
                    is_active=True,
                )
                .values_list('report_id', flat=True)
            )

            print("\nCONSENT REPORT IDS:")
            print(list(consented_ids))

            consented_qs = (
                Report.objects
                .filter(id__in=consented_ids, is_deleted=False)
                .select_related('belongs_to_user', 'uploaded_by_lab')
            )

            print("\nCONSENT REPORTS:")
            print(list(
                consented_qs.values(
                    'id',
                    'original_filename',
                    'uploaded_by_lab_id',
                    'uploaded_by_lab__name'
                )
            ))

            print("================ DEBUG END ================\n")

            return consented_qs

        # ───────────────── EXPIRED CONSENT ─────────────────
        if report_type == 'expired_consent':

            expired_ids = (
                ConsentFile.objects
                .filter(
                    consent_request__from_lab=lab,
                    is_active=False,
                )
                .values_list('report_id', flat=True)
            )

            print("\nEXPIRED CONSENT IDS:")
            print(list(expired_ids))

            expired_qs = (
                Report.objects
                .filter(id__in=expired_ids)
                .select_related('belongs_to_user', 'uploaded_by_lab')
            )

            print("\nEXPIRED CONSENT REPORTS:")
            print(list(
                expired_qs.values(
                    'id',
                    'original_filename',
                    'uploaded_by_lab_id',
                    'uploaded_by_lab__name'
                )
            ))

            print("================ DEBUG END ================\n")

            return expired_qs

        # ───────────────── DEFAULT: OWN + CONSENTED ─────────────────

        own_qs = Report.objects.filter(
            uploaded_by_lab=lab,
            is_deleted=False
        )

        print("\nOWN REPORTS:")
        print(list(
            own_qs.values(
                'id',
                'original_filename',
                'uploaded_by_lab_id',
                'uploaded_by_lab__name'
            )
        ))

        active_consent_ids = (
            ConsentFile.objects
            .filter(
                consent_request__from_lab=lab,
                consent_request__status='ACTIVE',
                expires_at__gt=now,
                is_active=True,
            )
            .values_list('report_id', flat=True)
        )

        print("\nACTIVE CONSENT IDS:")
        print(list(active_consent_ids))

        consented_qs = Report.objects.filter(
            id__in=active_consent_ids,
            is_deleted=False
        )

        print("\nCONSENTED REPORTS:")
        print(list(
            consented_qs.values(
                'id',
                'original_filename',
                'uploaded_by_lab_id',
                'uploaded_by_lab__name'
            )
        ))

        final_qs = (
            (own_qs | consented_qs)
            .distinct()
            .select_related('belongs_to_user', 'uploaded_by_lab')
        )

        print("\nFINAL COMBINED REPORTS:")
        print(list(
            final_qs.values(
                'id',
                'original_filename',
                'uploaded_by_lab_id',
                'uploaded_by_lab__name'
            )
        ))

        print("================ DEBUG END ================\n")

        return final_qs



class LabReportDetailView(generics.RetrieveAPIView):
    permission_classes = [IsLabPortal]
    serializer_class = ReportDetailSerializer

    def get_queryset(self):
        return Report.objects.filter(
            uploaded_by_lab=self.request.user, is_deleted=False
        ).select_related('belongs_to_user', 'uploaded_by_lab')


class LabReportStreamView(APIView):
    """
    Generate a short-lived presigned URL for inline PDF viewing.
    Enforces access: report must be owned by lab OR under active consent.
    """
    permission_classes = [IsLabPortal]

    def get(self, request, pk):
        lab = request.user
        # now = timezone.now()
        now = now_ist()

        # Check own report first
        try:
            report = Report.objects.get(pk=pk, is_deleted=False)
        except Report.DoesNotExist:
            return Response({'detail': 'Report not found.'}, status=status.HTTP_404_NOT_FOUND)

        is_own = str(report.uploaded_by_lab_id) == str(lab.id)

        if not is_own:
            # Check active consent — evaluated at request time (not relying on background job)
            has_consent = ConsentFile.objects.filter(
                report=report,
                consent_request__from_lab=lab,
                consent_request__status='ACTIVE',
                expires_at__gt=now,
                is_active=True,
            ).exists()

            if not has_consent:
                return Response(
                    {'detail': 'Access denied. No active consent for this report.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        signed_url = generate_presigned_view_url(report.file_key)
        return Response({
            'url': signed_url,
            'expires_in_seconds': 60,
            'filename': report.original_filename,
        })


class LabUserListView(generics.ListAPIView):
    """
    Lab sees unique users whose reports belong to this lab
    (own uploads + consented access).
    """
    permission_classes = [IsLabPortal]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'phone', 'user_uid']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        from apps.accounts.models import User
        lab = self.request.user
        user_ids = Report.objects.filter(
            uploaded_by_lab=lab, is_deleted=False
        ).values_list('belongs_to_user_id', flat=True).distinct()
        return User.objects.filter(id__in=user_ids)

    def get_serializer_class(self):
        from apps.accounts.serializers import UserListSerializer
        return UserListSerializer


class LabUserReportListView(generics.ListAPIView):
    """
    Lab sees all reports for a specific user that belong to this lab
    (own + consented, including expired consent metadata).
    """
    permission_classes = [IsLabPortal]
    serializer_class = ReportListSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['-created_at']

    # def get_queryset(self):
    #     lab = self.request.user
    #     user_id = self.kwargs['user_id']
    #     now = timezone.now()

    #     own = Report.objects.filter(
    #         uploaded_by_lab=lab,
    #         belongs_to_user_id=user_id,
    #         is_deleted=False,
    #     )

    #     # All consent files for this lab+user, active or expired
    #     all_consent_ids = ConsentFile.objects.filter(
    #         consent_request__from_lab=lab,
    #         report__belongs_to_user_id=user_id,
    #     ).values_list('report_id', flat=True)

    #     consented = Report.objects.filter(id__in=all_consent_ids)
    #     return (own | consented).distinct().select_related(
    #         'belongs_to_user', 'uploaded_by_lab'
    #     )

    def get_queryset(self):
        lab = self.request.user
        user_id = self.kwargs['user_id']
        # now = timezone.now()
        now = now_ist()

        own = Report.objects.filter(
            uploaded_by_lab=lab,
            belongs_to_user_id=user_id,
            is_deleted=False,
        )

        all_consent_ids = ConsentFile.objects.filter(
            consent_request__from_lab=lab,
            report__belongs_to_user_id=user_id,
        ).values_list('report_id', flat=True)

        consented = Report.objects.filter(id__in=all_consent_ids)
        return (own | consented).distinct().select_related(
            'belongs_to_user', 'uploaded_by_lab'
        ).prefetch_related('consent_files')


# ─── User Portal ──────────────────────────────────────────────────────────────

class UserReportListView(generics.ListAPIView):
    """User sees all their own reports across all labs."""
    permission_classes = [IsUserPortal]
    serializer_class = UserReportSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['original_filename', 'description', 'uploaded_by_lab__name']
    ordering_fields = ['created_at', 'issued_date', 'original_filename']
    ordering = ['-created_at']

    def get_queryset(self):
        return Report.objects.filter(
            belongs_to_user=self.request.user, is_deleted=False
        ).select_related('uploaded_by_lab')


class UserReportStreamView(APIView):
    """User streams (views inline) their own report."""
    permission_classes = [IsUserPortal]

    def get(self, request, pk):
        try:
            report = Report.objects.get(
                pk=pk,
                belongs_to_user=request.user,
                is_deleted=False,
            )
        except Report.DoesNotExist:
            return Response({'detail': 'Report not found.'}, status=status.HTTP_404_NOT_FOUND)

        signed_url = generate_presigned_view_url(report.file_key)
        return Response({
            'url': signed_url,
            'expires_in_seconds': 60,
            'filename': report.original_filename,
        })


class UserReportDownloadView(APIView):
    """User downloads their own report (longer-lived signed URL, attachment disposition)."""
    permission_classes = [IsUserPortal]

    def get(self, request, pk):
        try:
            report = Report.objects.get(
                pk=pk,
                belongs_to_user=request.user,
                is_deleted=False,
            )
        except Report.DoesNotExist:
            return Response({'detail': 'Report not found.'}, status=status.HTTP_404_NOT_FOUND)

        signed_url = generate_presigned_download_url(
            report.file_key, report.original_filename
        )
        return Response({
            'url': signed_url,
            'expires_in_seconds': 300,
            'filename': report.original_filename,
        })
