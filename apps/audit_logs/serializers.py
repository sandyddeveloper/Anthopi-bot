from rest_framework import serializers
from apps.audit_logs.models import AuditLog, ActivityLog
from apps.users.serializers import UserSerializer

class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'user_email', 'organization', 'organization_name', 'action', 'ip_address', 'path', 'method', 'status_code', 'details', 'created_at']

class ActivityLogSerializer(serializers.ModelSerializer):
    actor_details = UserSerializer(source='actor', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)

    class Meta:
        model = ActivityLog
        fields = [
            'id', 'actor', 'actor_details', 'action', 'module', 'object_id',
            'object_repr', 'organization', 'organization_name', 'metadata', 'created_at'
        ]
