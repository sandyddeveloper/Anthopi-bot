from rest_framework import serializers
from apps.scheduler.models import Schedule, ScheduleExecution

class ScheduleExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleExecution
        fields = '__all__'


class ScheduleSerializer(serializers.ModelSerializer):
    schedule_executions = ScheduleExecutionSerializer(many=True, read_only=True)
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)

    class Meta:
        model = Schedule
        fields = [
            'id', 'workflow', 'workflow_name', 'schedule_type', 'cron_expression',
            'start_time', 'end_time', 'is_active', 'last_run_at', 'next_run_at',
            'schedule_executions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['last_run_at', 'next_run_at']
