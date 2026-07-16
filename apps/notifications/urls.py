from django.urls import path
from apps.notifications.views import AdminSendNotificationView, AdminNotificationListView

urlpatterns = [
    path('', AdminNotificationListView.as_view(), name='notification-list'),
    path('send/', AdminSendNotificationView.as_view(), name='notification-send'),
]
