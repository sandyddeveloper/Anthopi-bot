from rest_framework import serializers
from apps.ai_analytics.models import AIEvent

class AIEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIEvent
        fields = ['id', 'organization', 'event_type', 'description', 'user', 'metadata', 'created_at']
        read_only_fields = ['id', 'organization', 'created_at']
