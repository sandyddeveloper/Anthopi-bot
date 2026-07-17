from rest_framework import serializers
from apps.ai_planner.models import ExecutionPlan, PlanStep, PlanResult

class PlanStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanStep
        fields = ['id', 'step_number', 'description', 'tool_code', 'status', 'input_data', 'output_data', 'created_at']

class PlanResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanResult
        fields = ['id', 'result_summary', 'metadata', 'created_at']

class ExecutionPlanSerializer(serializers.ModelSerializer):
    steps = PlanStepSerializer(many=True, read_only=True)
    result = PlanResultSerializer(read_only=True)

    class Meta:
        model = ExecutionPlan
        fields = ['id', 'organization', 'conversation', 'goal', 'status', 'steps', 'result', 'created_at']
        read_only_fields = ['id', 'organization', 'created_at']
