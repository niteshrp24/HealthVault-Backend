from django.urls import path
from apps.reports.views import (
    LabReportListView, LabReportDetailView, LabReportUploadView,
    LabReportStreamView, LabUserListView, LabUserReportListView,
)
from apps.consent.views import (
    LabConsentListView, LabConsentRequestView, LabConsentDetailView,
)
from apps.notifications.views import LabNotificationListView

from apps.accounts.views import LabProfileView


urlpatterns = [
    path('dashboard/', LabProfileView.as_view(), name='lab-dashboard'),
    # Reports
    path('reports/', LabReportListView.as_view(), name='lab-report-list'),
    path('reports/upload/', LabReportUploadView.as_view(), name='lab-report-upload'),
    path('reports/<uuid:pk>/', LabReportDetailView.as_view(), name='lab-report-detail'),
    path('reports/<uuid:pk>/stream/', LabReportStreamView.as_view(), name='lab-report-stream'),

    # Users
    path('users/', LabUserListView.as_view(), name='lab-user-list'),
    path('users/<uuid:user_id>/reports/', LabUserReportListView.as_view(), name='lab-user-reports'),

    # Consent
    path('consent/', LabConsentListView.as_view(), name='lab-consent-list'),
    path('consent/request/', LabConsentRequestView.as_view(), name='lab-consent-request'),
    path('consent/<uuid:pk>/', LabConsentDetailView.as_view(), name='lab-consent-detail'),

    # Notifications
    path('notifications/', LabNotificationListView.as_view(), name='lab-notifications'),
]
