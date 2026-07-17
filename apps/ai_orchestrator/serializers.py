from rest_framework import serializers
from apps.ai_orchestrator.models import AgentExecution, AgentTask, AgentAssignment, AgentResponse

class AgentResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentResponse
        fields = ['id', 'assignment', 'response_text', 'output_data', 'created_at']

class AgentAssignmentSerializer(serializers.ModelSerializer):
    response = AgentResponseSerializer(read_only=True)

    class Meta:
        model = AgentAssignment
        fields = ['id', 'task', 'delegator_agent', 'assignee_agent', 'status', 'response', 'created_at']

class AgentTaskSerializer(serializers.ModelSerializer):
    assignments = AgentAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = AgentTask
        fields = ['id', 'execution', 'title', 'description', 'status', 'assignments', 'created_at']

class AgentExecutionSerializer(serializers.ModelSerializer):
    tasks = AgentTaskSerializer(many=True, read_only=True)

    class Meta:
        model = AgentExecution
        fields = [
            'id', 'organization', 'conversation', 'agent', 'user', 'prompt',
            'status', 'plan', 'response_text', 'error_message', 'prompt_tokens',
            'completion_tokens', 'cost', 'duration_ms', 'tasks', 'created_at'
        ]
        read_only_fields = ['id', 'organization', 'status', 'plan', 'response_text', 'error_message', 'prompt_tokens', 'completion_tokens', 'cost', 'duration_ms', 'created_at']
