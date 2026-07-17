from rest_framework import serializers
from apps.ai_rag.models import DocumentChunk

class DocumentChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentChunk
        fields = ['id', 'file', 'chunk_index', 'content', 'embedding', 'created_at']
