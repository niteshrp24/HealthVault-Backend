from django.urls import path
from apps.analytics.views import AdminDashboardView, AdminLabStorageView

urlpatterns = [
    path('dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('storage/', AdminLabStorageView.as_view(), name='admin-storage'),
]
