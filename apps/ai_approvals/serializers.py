from rest_framework import serializers
from apps.ai_approvals.models import ApprovalRequest

class ApprovalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalRequest
        fields = [
            'id', 'organization', 'execution_id', 'tool_code', 'parameters',
            'approval_type', 'status', 'requested_by', 'approved_by', 'comments',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'requested_by', 'approved_by', 'created_at', 'updated_at']
