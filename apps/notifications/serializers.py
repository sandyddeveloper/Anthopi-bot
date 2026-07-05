from rest_framework import serializers
from apps.notifications.models import Notification, NotificationPreference
from apps.users.serializers import UserSerializer

class NotificationSerializer(serializers.ModelSerializer):
    sender_details = UserSerializer(source='sender', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'sender', 'sender_details', 'title', 'message',
            'notification_type', 'is_read', 'read_at', 'event_type', 'action_url', 'created_at'
        ]
        read_only_fields = ['id', 'recipient', 'sender', 'created_at']

class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ['id', 'user', 'event_type', 'is_enabled_in_app', 'is_enabled_email']
        read_only_fields = ['id', 'user']
