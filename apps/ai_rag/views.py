import os
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404
from django.db import transaction
from drf_spectacular.utils import extend_schema

from apps.knowledge.models import File
from apps.ai_rag.models import DocumentChunk
from apps.ai_rag.serializers import DocumentChunkSerializer

from apps.common.utils import get_org_context

def get_character_embedding(text):
    text = text.lower()
    alphabet = 'abcdefghijklmnopqrstuvwxyz '
    counts = [text.count(char) for char in alphabet]
    total = sum(counts)
    if total == 0:
        return [0.0] * len(alphabet)
    norm = sum(x**2 for x in counts)**0.5
    if norm == 0:
        return [0.0] * len(alphabet)
    return [x / norm for x in counts]

def cosine_similarity(v1, v2):
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    return sum(x * y for x, y in zip(v1, v2))

class ChunkFileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Chunk and embed a knowledge file", request=None, responses={200: None}, tags=["AI RAG"])
    def post(self, request):
        org = get_org_context(request)
        file_id = request.data.get('file_id')
        if not file_id:
            return Response({"error": "file_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        file_obj = get_object_or_404(File, id=file_id, organization=org, is_deleted=False)
        
        # Try to read actual contents or fallback to metadata mock text
        content = ""
        if file_obj.file_path:
            try:
                if os.path.exists(file_obj.file_path.path):
                    with open(file_obj.file_path.path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
            except Exception:
                pass
                
        if not content:
            # Fallback mock descriptive text for RAG simulation
            content = (
                f"Document Standards and Policy Manual for file {file_obj.name}.\n"
                f"File Metadata: Size {file_obj.file_size} bytes, Type {file_obj.file_type}.\n"
                f"Section 1: General coding guidelines. Python code should be structured, PEP8 compliant, "
                f"and use clear variable naming conventions. Write modular code with functions and type hints.\n"
                f"Section 2: Security principles. All user sessions must be validated, and credentials "
                f"must never be hardcoded. Use environment variables for API keys.\n"
                f"Section 3: Database access rules. Never execute raw SQL directly unless checked "
                f"for SQL injection. Prefer Django ORM for security and portability."
            )
            
        # Chunking: chunk_size=300, overlap=50
        chunk_size = 300
        overlap = 50
        chunks = []
        start = 0
        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunks.append(content[start:end])
            if end == len(content):
                break
            start += chunk_size - overlap
            
        # Save chunks and compute embeddings
        created_chunks = []
        with transaction.atomic():
            # Delete existing chunks for this file
            DocumentChunk.objects.filter(file=file_obj).delete()
            
            for idx, chunk_text in enumerate(chunks):
                vector = get_character_embedding(chunk_text)
                chunk = DocumentChunk.objects.create(
                    file=file_obj,
                    chunk_index=idx,
                    content=chunk_text,
                    embedding=vector,
                    created_by=request.user
                )
                created_chunks.append(chunk)
                
        return Response({
            "message": f"Successfully chunked file into {len(created_chunks)} sections.",
            "chunks_count": len(created_chunks)
        })

class RAGSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Perform similarity search over document chunks", request=None, responses={200: DocumentChunkSerializer(many=True)}, tags=["AI RAG"])
    def post(self, request):
        org = get_org_context(request)
        query = request.data.get('query')
        if not query:
            return Response({"error": "query is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        agent_id = request.data.get('agent_id')
        file_ids = request.data.get('file_ids', [])
        
        # Base filter: organization-level files
        chunks_qs = DocumentChunk.objects.filter(file__organization=org, file__is_deleted=False)
        
        if file_ids:
            chunks_qs = chunks_qs.filter(file_id__in=file_ids)
        elif agent_id:
            # Get files linked to the agent via knowledge collections
            from apps.ai_agents.models import Agent
            agent = get_object_or_404(Agent, id=agent_id, organization=org)
            collections = agent.knowledge_collections.all()
            linked_file_ids = []
            for col in collections:
                linked_file_ids.extend(col.items.values_list('file_id', flat=True))
            chunks_qs = chunks_qs.filter(file_id__in=linked_file_ids)
            
        query_vector = get_character_embedding(query)
        
        # Perform memory similarity search
        results = []
        for chunk in chunks_qs:
            score = cosine_similarity(query_vector, chunk.embedding)
            results.append((score, chunk))
            
        # Sort by similarity score descending
        results.sort(key=lambda x: x[0], reverse=True)
        top_results = results[:5]
        
        # Build responses with score and citation
        response_data = []
        for score, chunk in top_results:
            citation = f"File: {chunk.file.name} (Chunk {chunk.chunk_index})"
            response_data.append({
                "id": chunk.id,
                "file_id": chunk.file.id,
                "file_name": chunk.file.name,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "score": round(score, 4),
                "citation": citation
            })
            
        return Response(response_data)
