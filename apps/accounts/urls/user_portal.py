from django.urls import path
from apps.accounts.views import UserProfileView
from apps.reports.views import (
    UserReportListView, UserReportStreamView, UserReportDownloadView,
)
from apps.consent.views import (
    UserConsentListView, UserConsentVerifyOTPView,
    UserConsentShareView, UserConsentRevokeView,
    UserActiveSharesView,
)

urlpatterns = [
    # Profile
    path('profile/', UserProfileView.as_view(), name='user-profile'),

    # Reports
    path('reports/', UserReportListView.as_view(), name='user-report-list'),
    path('reports/<uuid:pk>/stream/', UserReportStreamView.as_view(), name='user-report-stream'),
    path('reports/<uuid:pk>/download/', UserReportDownloadView.as_view(), name='user-report-download'),

    # Consent
    path('consent/', UserConsentListView.as_view(), name='user-consent-list'),
    path('consent/<uuid:pk>/verify-otp/', UserConsentVerifyOTPView.as_view(), name='user-consent-verify-otp'),
    path('consent/<uuid:pk>/share/', UserConsentShareView.as_view(), name='user-consent-share'),
    path('consent/<uuid:pk>/revoke/', UserConsentRevokeView.as_view(), name='user-consent-revoke'),
    path('consent/active-shares/', UserActiveSharesView.as_view(), name='user-active-shares'),
]
