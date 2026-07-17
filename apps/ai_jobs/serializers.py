from rest_framework import serializers
from apps.ai_jobs.models import AIJob

class AIJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIJob
        fields = ['id', 'organization', 'agent', 'task_name', 'status', 'celery_task_id', 'total_items', 'processed_items', 'result', 'created_at']
        read_only_fields = ['id', 'organization', 'status', 'celery_task_id', 'processed_items', 'result', 'created_at']
