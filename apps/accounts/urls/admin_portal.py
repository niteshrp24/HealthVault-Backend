from django.urls import path
from apps.accounts.views import (
    AdminLabListCreateView, AdminLabDetailView, AdminLabDeactivateView,
    AdminUserListView, AdminUserDeactivateView,
)

urlpatterns = [
    path('labs/', AdminLabListCreateView.as_view(), name='admin-lab-list'),
    path('labs/<uuid:pk>/', AdminLabDetailView.as_view(), name='admin-lab-detail'),
    path('labs/<uuid:pk>/toggle-active/', AdminLabDeactivateView.as_view(), name='admin-lab-toggle'),
    path('users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('users/<uuid:pk>/toggle-active/', AdminUserDeactivateView.as_view(), name='admin-user-toggle'),
]
