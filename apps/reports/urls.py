from django.urls import path
from apps.reports.views import (
    LabReportListView, LabReportDetailView, LabReportUploadView,
    LabReportStreamView,
)

urlpatterns = [
    path('', LabReportListView.as_view(), name='report-list'),
    path('upload/', LabReportUploadView.as_view(), name='report-upload'),
    path('<uuid:pk>/', LabReportDetailView.as_view(), name='report-detail'),
    path('<uuid:pk>/stream/', LabReportStreamView.as_view(), name='report-stream'),
]
