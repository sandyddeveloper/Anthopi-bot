from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound
from django.shortcuts import get_object_or_404
from django.db import transaction
from drf_spectacular.utils import extend_schema

from apps.ai_memory.models import Memory
from apps.ai_memory.serializers import MemorySerializer

from apps.common.utils import get_org_context

class MemoryListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List long-term memories", responses={200: MemorySerializer(many=True)}, tags=["AI Memory"])
    def get(self, request):
        org = get_org_context(request)
        if request.user.is_superuser:
            queryset = Memory.objects.filter(is_deleted=False)
        else:
            queryset = Memory.objects.filter(organization=org, is_deleted=False)
            
        level = request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)
            
        memory_type = request.query_params.get('type')
        if memory_type:
            queryset = queryset.filter(type=memory_type)
            
        serializer = MemorySerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Save a long-term memory", request=MemorySerializer, responses={201: MemorySerializer}, tags=["AI Memory"])
    def post(self, request):
        org = get_org_context(request)
        serializer = MemorySerializer(data=request.data)
        if serializer.is_valid():
            memory = serializer.save(organization=org, created_by=request.user)
            return Response(MemorySerializer(memory).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MemoryDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, org):
        try:
            if org is None:
                return Memory.objects.get(id=pk, is_deleted=False)
            return Memory.objects.get(id=pk, organization=org, is_deleted=False)
        except Memory.DoesNotExist:
            raise NotFound("Memory not found.")

    @extend_schema(summary="Retrieve a memory", responses={200: MemorySerializer}, tags=["AI Memory"])
    def get(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        memory = self.get_object(pk, org)
        serializer = MemorySerializer(memory)
        return Response(serializer.data)

    @extend_schema(summary="Update a memory", request=MemorySerializer, responses={200: MemorySerializer}, tags=["AI Memory"])
    def put(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        memory = self.get_object(pk, org)
        serializer = MemorySerializer(memory, data=request.data, partial=True)
        if serializer.is_valid():
            memory = serializer.save(updated_by=request.user)
            return Response(MemorySerializer(memory).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Forget a memory", responses={204: None}, tags=["AI Memory"])
    def delete(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        memory = self.get_object(pk, org)
        memory.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class MemoryMergeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Merge two memories", responses={200: MemorySerializer}, tags=["AI Memory"])
    def post(self, request):
        org = get_org_context(request)
        primary_id = request.data.get('primary_id')
        secondary_id = request.data.get('secondary_id')
        
        if not primary_id or not secondary_id:
            return Response({"error": "Both primary_id and secondary_id are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        primary = get_object_or_404(Memory, id=primary_id, organization=org, is_deleted=False)
        secondary = get_object_or_404(Memory, id=secondary_id, organization=org, is_deleted=False)
        
        with transaction.atomic():
            primary.content = f"{primary.content}\n{secondary.content}"
            primary.confidence_score = max(primary.confidence_score, secondary.confidence_score)
            primary.updated_by = request.user
            primary.save()
            secondary.delete() # Soft delete
            
        return Response(MemorySerializer(primary).data)
