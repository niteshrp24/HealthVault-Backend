from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from apps.accounts.views import (
    AdminLoginView, LabLoginView,
    UserRequestOTPView, UserVerifyOTPView, UserRegisterInitiateView, UserRegisterVerifyView
)

urlpatterns = [
    path('admin/login/', AdminLoginView.as_view(), name='admin-login'),
    path('lab/login/', LabLoginView.as_view(), name='lab-login'),
    path('user/register/', UserRegisterInitiateView.as_view(), name='user-register'),
    path('user/register/verify/', UserRegisterVerifyView.as_view(), name='user-register-verify'),
    # path('user/register/', UserRegisterView.as_view(), name='user-register'),
    path('user/request-otp/', UserRequestOTPView.as_view(), name='user-request-otp'),
    path('user/verify-otp/', UserVerifyOTPView.as_view(), name='user-verify-otp'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]
