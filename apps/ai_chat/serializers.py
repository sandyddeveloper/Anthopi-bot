from rest_framework import serializers
from apps.ai_chat.models import (
    Conversation, ConversationParticipant, Message, MessageAttachment,
    MemoryCategory, Memory, MemorySource, AIUsage, AIActivityLog
)
from apps.users.serializers import UserSerializer
from apps.ai_agents.serializers import AgentSerializer, AIModelSerializer

class ConversationParticipantSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = ConversationParticipant
        fields = ['id', 'conversation', 'user', 'user_details', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = ['id', 'message', 'file', 'name', 'file_path', 'file_size', 'file_type', 'created_at']
        read_only_fields = ['id', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    sender_details = UserSerializer(source='sender', read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'sender_details', 'sender_type',
            'content', 'prompt_tokens', 'completion_tokens', 'cost',
            'response_time', 'attachments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'conversation', 'sender', 'sender_type', 'created_at', 'updated_at']


class ConversationSerializer(serializers.ModelSerializer):
    agent_details = AgentSerializer(source='agent', read_only=True)
    participants = ConversationParticipantSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'organization', 'project', 'agent', 'agent_details',
            'title', 'is_pinned', 'participants', 'last_message', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return MessageSerializer(last_msg).data
        return None


class MemoryCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MemoryCategory
        fields = ['id', 'name', 'code', 'created_at']
        read_only_fields = ['id', 'created_at']


class MemorySourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemorySource
        fields = ['id', 'memory', 'source_type', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']


class MemorySerializer(serializers.ModelSerializer):
    category_details = MemoryCategorySerializer(source='category', read_only=True)
    sources = MemorySourceSerializer(many=True, read_only=True)

    class Meta:
        model = Memory
        fields = [
            'id', 'organization', 'category', 'category_details',
            'user', 'agent', 'project', 'conversation', 'content',
            'confidence_score', 'sources', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']


class AIUsageSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    model_details = AIModelSerializer(source='model', read_only=True)

    class Meta:
        model = AIUsage
        fields = [
            'id', 'organization', 'user', 'user_details', 'model', 'model_details',
            'agent', 'prompt_tokens', 'completion_tokens', 'total_tokens',
            'cost', 'duration_ms', 'date', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AIActivityLogSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = AIActivityLog
        fields = [
            'id', 'organization', 'user', 'user_details', 'action',
            'description', 'entity_type', 'entity_id', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
