from rest_framework import serializers
from apps.audit_logs.models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'user_email', 'organization', 'organization_name', 'action', 'ip_address', 'path', 'method', 'status_code', 'details', 'created_at']
