from django.urls import path
from apps.consent.views import (
    LabConsentListView, LabConsentRequestView, LabConsentDetailView,
    UserConsentListView, UserConsentVerifyOTPView,
    UserConsentShareView, UserConsentRevokeView, UserActiveSharesView,
)

urlpatterns = [
    # Lab-facing (also accessible via /api/v1/lab/consent/ in lab_portal.py)
    path('lab/', LabConsentListView.as_view(), name='lab-consent-list'),
    path('lab/request/', LabConsentRequestView.as_view(), name='lab-consent-request'),
    path('lab/<uuid:pk>/', LabConsentDetailView.as_view(), name='lab-consent-detail'),

    # User-facing
    path('user/', UserConsentListView.as_view(), name='user-consent-list'),
    path('user/active-shares/', UserActiveSharesView.as_view(), name='user-active-shares'),
    path('user/<uuid:pk>/verify-otp/', UserConsentVerifyOTPView.as_view(), name='user-consent-verify'),
    path('user/<uuid:pk>/share/', UserConsentShareView.as_view(), name='user-consent-share'),
    path('user/<uuid:pk>/revoke/', UserConsentRevokeView.as_view(), name='user-consent-revoke'),
]
