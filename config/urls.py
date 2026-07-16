from django.contrib import admin
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('api/v1/', include([
        path('auth/', include('apps.accounts.urls.auth')),
        path('admin/', include('apps.accounts.urls.admin_portal')),
        path('lab/', include('apps.accounts.urls.lab_portal')),
        path('user/', include('apps.accounts.urls.user_portal')),
        path('subscriptions/', include('apps.subscriptions.urls')),
        path('reports/', include('apps.reports.urls')),
        path('consent/', include('apps.consent.urls')),
        path('notifications/', include('apps.notifications.urls')),
        path('analytics/', include('apps.analytics.urls')),
    ])),
]

# if settings.DEBUG:
#     import debug_toolbar
#     urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
