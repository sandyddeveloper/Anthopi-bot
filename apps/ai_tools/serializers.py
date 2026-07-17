from rest_framework import serializers
from apps.ai_tools.models import ToolExecution

class ToolExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolExecution
        fields = ['id', 'tool_code', 'agent', 'user', 'input_parameters', 'output_result', 'is_success', 'error_message', 'duration_ms', 'created_at']
