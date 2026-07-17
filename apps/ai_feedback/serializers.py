from rest_framework import serializers
from apps.ai_feedback.models import Feedback

class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'conversation', 'message', 'score', 'comment', 'user', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
