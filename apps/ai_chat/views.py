from django.db.models import Sum
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, PermissionDenied
from django.shortcuts import get_object_or_404
from django.db import transaction
from drf_spectacular.utils import extend_schema

from apps.ai_chat.models import (
    Conversation, ConversationParticipant, Message, MessageAttachment,
    Memory, AIUsage, AIActivityLog, MemoryCategory
)
from apps.ai_chat.serializers import (
    ConversationSerializer, MessageSerializer, MemorySerializer,
    AIUsageSerializer, AIActivityLogSerializer, MemoryCategorySerializer
)
from apps.ai_chat.orchestrator import AIOrchestrator
from apps.ai_agents.models import Agent

def get_org_context(request):
    org = getattr(request, 'organization', None) or request.user.organization
    if not org and not request.user.is_superuser:
        raise PermissionDenied("Organization context required.")
    return org


# ----------------- Conversations -----------------

class ConversationListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List conversations", responses={200: ConversationSerializer(many=True)}, tags=["Conversations"])
    def get(self, request):
        org = get_org_context(request)
        if request.user.is_superuser:
            queryset = Conversation.objects.filter(is_deleted=False)
        else:
            queryset = Conversation.objects.filter(organization=org, is_deleted=False)
            
        agent_id = request.query_params.get('agent')
        if agent_id:
            queryset = queryset.filter(agent_id=agent_id)
            
        project_id = request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        queryset = queryset.order_by('-is_pinned', '-updated_at')
        serializer = ConversationSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Start a conversation", request=ConversationSerializer, responses={201: ConversationSerializer}, tags=["Conversations"])
    def post(self, request):
        org = get_org_context(request)
        serializer = ConversationSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                conversation = serializer.save(
                    organization=org,
                    created_by=request.user
                )
                # Register creator as participant
                ConversationParticipant.objects.create(
                    conversation=conversation,
                    user=request.user
                )
                # Log Activity
                AIActivityLog.objects.create(
                    organization=org,
                    user=request.user,
                    action="conversation_started",
                    description=f"Conversation started with Agent: {conversation.agent.name if conversation.agent else 'None'}",
                    entity_type="conversation",
                    entity_id=conversation.id
                )
            return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ConversationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, org):
        try:
            if org is None:
                return Conversation.objects.get(id=pk, is_deleted=False)
            return Conversation.objects.get(id=pk, organization=org, is_deleted=False)
        except Conversation.DoesNotExist:
            raise NotFound("Conversation not found.")

    @extend_schema(summary="Retrieve conversation details", responses={200: ConversationSerializer}, tags=["Conversations"])
    def get(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        conversation = self.get_object(pk, org)
        serializer = ConversationSerializer(conversation)
        return Response(serializer.data)

    @extend_schema(summary="Rename or Pin conversation", request=ConversationSerializer, responses={200: ConversationSerializer}, tags=["Conversations"])
    def put(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        conversation = self.get_object(pk, org)
        serializer = ConversationSerializer(conversation, data=request.data, partial=True)
        if serializer.is_valid():
            conversation = serializer.save(updated_by=request.user)
            return Response(ConversationSerializer(conversation).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Delete a conversation", responses={204: None}, tags=["Conversations"])
    def delete(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        conversation = self.get_object(pk, org)
        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----------------- Messages -----------------

class MessageListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_conversation(self, conversation_id, org):
        if org is None:
            return get_object_or_404(Conversation, id=conversation_id, is_deleted=False)
        return get_object_or_404(Conversation, id=conversation_id, organization=org, is_deleted=False)

    @extend_schema(summary="List messages in conversation", responses={200: MessageSerializer(many=True)}, tags=["Conversations"])
    def get(self, request, conversation_id):
        org = get_org_context(request) if not request.user.is_superuser else None
        conversation = self.get_conversation(conversation_id, org)
        messages = conversation.messages.filter(is_deleted=False).order_by('created_at')
        
        # Paginate manually if query params present
        page = self.paginate_queryset(messages, request)
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    def paginate_queryset(self, queryset, request):
        limit = request.query_params.get('limit')
        offset = request.query_params.get('offset')
        if not limit:
            return None
        try:
            limit = int(limit)
            offset = int(offset) if offset else 0
            return queryset[offset:offset + limit]
        except ValueError:
            return None

    def get_paginated_response(self, data):
        return Response({
            'count': len(data),
            'results': data
        })

    @extend_schema(summary="Post a message / continue conversation", request=MessageSerializer, responses={201: MessageSerializer}, tags=["Conversations"])
    def post(self, request, conversation_id):
        org = get_org_context(request) if not request.user.is_superuser else None
        conversation = self.get_conversation(conversation_id, org)
        
        serializer = MessageSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                # 1. Save User Message
                user_msg = serializer.save(
                    conversation=conversation,
                    sender=request.user,
                    sender_type='user',
                    created_by=request.user
                )
                
            # 2. Invoke Orchestrator to generate Assistant Response
            orchestrator = AIOrchestrator(conversation.id, request.user)
            assistant_msg = orchestrator.call_llm(user_msg.content)
            
            # Return both user and assistant message
            return Response({
                "user_message": MessageSerializer(user_msg).data,
                "assistant_message": MessageSerializer(assistant_msg).data
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------- AI Memory -----------------

class MemoryCategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List memory categories", responses={200: MemoryCategorySerializer(many=True)}, tags=["Memory"])
    def get(self, request):
        queryset = MemoryCategory.objects.filter(is_deleted=False)
        serializer = MemoryCategorySerializer(queryset, many=True)
        return Response(serializer.data)


class MemoryListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List or search memory", responses={200: MemorySerializer(many=True)}, tags=["Memory"])
    def get(self, request):
        org = get_org_context(request)
        queryset = Memory.objects.filter(organization=org, is_deleted=False)
        
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(content__icontains=search)
            
        category_code = request.query_params.get('category')
        if category_code:
            queryset = queryset.filter(category__code=category_code)
            
        serializer = MemorySerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Save a memory context", request=MemorySerializer, responses={201: MemorySerializer}, tags=["Memory"])
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
        return get_object_or_404(Memory, id=pk, organization=org, is_deleted=False)

    @extend_schema(summary="Retrieve dynamic memory info", responses={200: MemorySerializer}, tags=["Memory"])
    def get(self, request, pk):
        org = get_org_context(request)
        memory = self.get_object(pk, org)
        serializer = MemorySerializer(memory)
        return Response(serializer.data)

    @extend_schema(summary="Update memory details", request=MemorySerializer, responses={200: MemorySerializer}, tags=["Memory"])
    def put(self, request, pk):
        org = get_org_context(request)
        memory = self.get_object(pk, org)
        serializer = MemorySerializer(memory, data=request.data, partial=True)
        if serializer.is_valid():
            memory = serializer.save(updated_by=request.user)
            return Response(MemorySerializer(memory).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Delete memory context", responses={204: None}, tags=["Memory"])
    def delete(self, request, pk):
        org = get_org_context(request)
        memory = self.get_object(pk, org)
        memory.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----------------- AI Usage Reporting -----------------

class AIUsageListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List usage reports", responses={200: AIUsageSerializer(many=True)}, tags=["Usage Reporting"])
    def get(self, request):
        org = get_org_context(request)
        queryset = AIUsage.objects.filter(organization=org)
        
        # Summary metrics
        total_tokens = queryset.aggregate(Sum('total_tokens'))['total_tokens__sum'] or 0
        total_cost = queryset.aggregate(Sum('cost'))['cost__sum'] or 0
        
        serializer = AIUsageSerializer(queryset, many=True)
        return Response({
            'total_tokens': total_tokens,
            'total_cost': total_cost,
            'usage_records': serializer.data
        })
