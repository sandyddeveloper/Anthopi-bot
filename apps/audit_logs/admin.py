from django.contrib import admin
from apps.audit_logs.models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'organization', 'action', 'method', 'status_code')
    list_filter = ('action', 'method', 'status_code')
    search_fields = ('user__email', 'action')
    readonly_fields = ('created_at', 'user', 'organization', 'action', 'ip_address', 'path', 'method', 'status_code', 'details')
