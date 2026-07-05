from django.urls import path
from apps.notifications.views import (
    NotificationListAPIView, NotificationMarkReadAPIView, NotificationPreferencesAPIView
)

urlpatterns = [
    path('notifications/', NotificationListAPIView.as_view(), name='notification-list'),
    path('notifications/mark-read/', NotificationMarkReadAPIView.as_view(), name='notification-mark-read'),
    path('notifications/preferences/', NotificationPreferencesAPIView.as_view(), name='notification-preferences'),
]
