from rest_framework import serializers
from apps.ai_memory.models import Memory

class MemorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Memory
        fields = [
            'id', 'organization', 'level', 'type', 'content', 
            'confidence_score', 'user', 'agent', 'project', 
            'conversation', 'workflow_execution', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']
