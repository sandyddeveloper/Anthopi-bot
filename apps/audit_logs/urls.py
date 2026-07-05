from django.urls import path
from apps.audit_logs.views import AuditLogListAPIView, AuditLogDetailAPIView, ActivityLogListAPIView

urlpatterns = [
    path('audit-logs/', AuditLogListAPIView.as_view(), name='auditlog-list'),
    path('audit-logs/<uuid:pk>/', AuditLogDetailAPIView.as_view(), name='auditlog-detail'),
    path('activities/', ActivityLogListAPIView.as_view(), name='activitylog-list'),
]

