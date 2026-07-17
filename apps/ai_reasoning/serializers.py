from rest_framework import serializers
from apps.ai_reasoning.models import ReasoningLog

class ReasoningLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReasoningLog
        fields = ['id', 'execution_id', 'step_id', 'chain_of_thought', 'reflection', 'self_check_passed', 'error_recovery_actions', 'created_at']
        read_only_fields = ['id', 'created_at']
