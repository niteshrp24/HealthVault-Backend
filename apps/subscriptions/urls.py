from django.urls import path
from apps.subscriptions.views import SubscriptionPlanListCreateView, SubscriptionPlanDetailView

urlpatterns = [
    path('', SubscriptionPlanListCreateView.as_view(), name='subscription-list'),
    path('<uuid:pk>/', SubscriptionPlanDetailView.as_view(), name='subscription-detail'),
]
