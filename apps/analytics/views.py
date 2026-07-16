from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.core.permissions import IsAdminPortal
from apps.accounts.models import LabHospital, User
from apps.reports.models import Report
from apps.consent.models import ConsentRequest
from apps.core.utils.timezone_utils import now_ist


class AdminDashboardView(APIView):
    """
    Aggregate analytics for the admin dashboard.
    All numbers computed via DB aggregates — no extra models needed.
    """
    permission_classes = [IsAdminPortal]

    def get(self, request):
        # now = timezone.now()
        now = now_ist()

        # Lab stats
        lab_stats = LabHospital.objects.aggregate(
            total_labs=Count('id'),
            active_labs=Count('id', filter=Q(is_active=True, plan_end__gt=now)),
            inactive_labs=Count('id', filter=Q(is_active=False)),
            expired_plan_labs=Count('id', filter=Q(is_active=True, plan_end__lt=now)),
            total_storage_used_mb=Sum('storage_used_mb'),
            total_storage_limit_mb=Sum('storage_limit_mb'),
        )

        # User stats
        user_stats = User.objects.aggregate(
            total_users=Count('id'),
            active_users=Count('id', filter=Q(is_active=True)),
        )

        # Report stats
        report_stats = Report.objects.aggregate(
            total_reports=Count('id', filter=Q(is_deleted=False)),
            total_storage_mb=Sum('file_size_mb', filter=Q(is_deleted=False)),
        )

        # Consent stats
        consent_stats = ConsentRequest.objects.aggregate(
            total_consents=Count('id'),
            active_consents=Count(
                'id',
                filter=Q(status='ACTIVE', consent_expires_at__gt=now)
            ),
            expired_consents=Count('id', filter=Q(status='EXPIRED')),
        )

        total_used_mb = lab_stats['total_storage_used_mb'] or 0
        total_limit_mb = lab_stats['total_storage_limit_mb'] or 0

        return Response({
            'labs': {
                'total': lab_stats['total_labs'],
                'active': lab_stats['active_labs'],
                'inactive': lab_stats['inactive_labs'],
                'plan_expired': lab_stats['expired_plan_labs'],
            },
            'users': {
                'total': user_stats['total_users'],
                'active': user_stats['active_users'],
            },
            'storage': {
                'total_used_mb': round(total_used_mb, 2),
                'total_used_gb': round(total_used_mb / 1024, 3),
                'total_limit_mb': round(total_limit_mb, 2),
                'total_limit_gb': round(total_limit_mb / 1024, 3),
                'utilisation_percent': round(
                    (total_used_mb / total_limit_mb * 100) if total_limit_mb else 0, 1
                ),
            },
            'reports': {
                'total': report_stats['total_reports'] or 0,
                'total_size_mb': round(report_stats['total_storage_mb'] or 0, 2),
            },
            'consents': {
                'total': consent_stats['total_consents'],
                'active': consent_stats['active_consents'],
                'expired': consent_stats['expired_consents'],
            },
        })


class AdminLabStorageView(APIView):
    """
    Per-lab storage breakdown — useful for billing/charging decisions.
    """
    permission_classes = [IsAdminPortal]

    def get(self, request):
        labs = LabHospital.objects.annotate(
            report_count=Count('reports', filter=Q(reports__is_deleted=False))
        ).values(
            'id', 'lab_id', 'name', 'type',
            'storage_used_mb', 'storage_limit_mb',
            'plan_end', 'is_active', 'report_count',
        ).order_by('-storage_used_mb')

        data = []
        for lab in labs:
            used = lab['storage_used_mb'] or 0
            limit = lab['storage_limit_mb'] or 1  # avoid division by zero
            data.append({
                **lab,
                'storage_used_gb': round(used / 1024, 4),
                'storage_limit_gb': round(limit / 1024, 2),
                'utilisation_percent': round(used / limit * 100, 1),
            })

        return Response({'results': data, 'count': len(data)})
