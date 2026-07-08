from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, PermissionDenied
from django.shortcuts import get_object_or_404
from django.db import transaction
from drf_spectacular.utils import extend_schema

from apps.ai_agents.models import (
    AgentCategory, AIProvider, AIModel, OrganizationModel, Agent,
    AgentInstruction, AgentConfiguration, AISettings, PromptCategory,
    Prompt, PromptVersion, Tool, AgentTool
)
from apps.ai_agents.serializers import (
    AgentCategorySerializer, AIProviderSerializer, AIModelSerializer,
    OrganizationModelSerializer, AgentSerializer, AgentInstructionSerializer,
    AgentConfigurationSerializer, AISettingsSerializer, PromptCategorySerializer,
    PromptSerializer, PromptVersionSerializer, ToolSerializer, AgentToolSerializer
)

def get_org_context(request):
    org = getattr(request, 'organization', None) or request.user.organization
    if not org and not request.user.is_superuser:
        raise PermissionDenied("Organization context required.")
    return org


# ----------------- Agent Categories -----------------

class AgentCategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List agent categories", responses={200: AgentCategorySerializer(many=True)}, tags=["AI Agents"])
    def get(self, request):
        categories = AgentCategory.objects.filter(is_deleted=False)
        serializer = AgentCategorySerializer(categories, many=True)
        return Response(serializer.data)


# ----------------- Agents -----------------

class AgentListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List AI agents", responses={200: AgentSerializer(many=True)}, tags=["AI Agents"])
    def get(self, request):
        org = get_org_context(request)
        if request.user.is_superuser:
            queryset = Agent.objects.filter(is_deleted=False)
        else:
            queryset = Agent.objects.filter(organization=org, is_deleted=False)
        
        project_id = request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        serializer = AgentSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Create an AI agent", request=AgentSerializer, responses={201: AgentSerializer}, tags=["AI Agents"])
    def post(self, request):
        org = get_org_context(request)
        serializer = AgentSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                agent = serializer.save(
                    organization=org,
                    owner=request.user,
                    created_by=request.user
                )
                # Auto-initialize AgentConfiguration
                AgentConfiguration.objects.create(agent=agent)
            return Response(AgentSerializer(agent).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AgentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, org):
        try:
            if org is None: # Superuser context
                return Agent.objects.get(id=pk, is_deleted=False)
            return Agent.objects.get(id=pk, organization=org, is_deleted=False)
        except Agent.DoesNotExist:
            raise NotFound("Agent not found.")

    @extend_schema(summary="Retrieve an AI agent", responses={200: AgentSerializer}, tags=["AI Agents"])
    def get(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        agent = self.get_object(pk, org)
        serializer = AgentSerializer(agent)
        return Response(serializer.data)

    @extend_schema(summary="Update an AI agent", request=AgentSerializer, responses={200: AgentSerializer}, tags=["AI Agents"])
    def put(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        agent = self.get_object(pk, org)
        serializer = AgentSerializer(agent, data=request.data, partial=True)
        if serializer.is_valid():
            agent = serializer.save(updated_by=request.user)
            return Response(AgentSerializer(agent).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Delete an AI agent", responses={204: None}, tags=["AI Agents"])
    def delete(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        agent = self.get_object(pk, org)
        agent.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgentDuplicateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Duplicate an agent", responses={201: AgentSerializer}, tags=["AI Agents"])
    def post(self, request, pk):
        org = get_org_context(request)
        agent = get_object_or_404(Agent, id=pk, organization=org, is_deleted=False)
        
        with transaction.atomic():
            duplicated_agent = Agent.objects.create(
                organization=org,
                project=agent.project,
                owner=request.user,
                name=f"{agent.name} (Copy)",
                avatar=agent.avatar,
                description=agent.description,
                category=agent.category,
                system_prompt=agent.system_prompt,
                temperature=agent.temperature,
                model=agent.model,
                visibility=agent.visibility,
                created_by=request.user
            )
            # Copy instructions
            for instruction in agent.instructions.all():
                AgentInstruction.objects.create(
                    agent=duplicated_agent,
                    title=instruction.title,
                    instruction_text=instruction.instruction_text,
                    order=instruction.order,
                    created_by=request.user
                )
            # Copy config
            extra = getattr(agent, 'configuration', None)
            AgentConfiguration.objects.create(
                agent=duplicated_agent,
                extra_settings=extra.extra_settings if extra else {}
            )
            # Copy tools
            for agent_tool in agent.agent_tools.all():
                AgentTool.objects.create(
                    agent=duplicated_agent,
                    tool=agent_tool.tool,
                    is_enabled=agent_tool.is_enabled
                )
        return Response(AgentSerializer(duplicated_agent).data, status=status.HTTP_201_CREATED)


# ----------------- Agent Instructions -----------------

class AgentInstructionListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List agent instructions", responses={200: AgentInstructionSerializer(many=True)}, tags=["AI Agents"])
    def get(self, request, agent_id):
        org = get_org_context(request)
        agent = get_object_or_404(Agent, id=agent_id, organization=org, is_deleted=False)
        instructions = agent.instructions.all()
        serializer = AgentInstructionSerializer(instructions, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Create agent instruction", request=AgentInstructionSerializer, responses={201: AgentInstructionSerializer}, tags=["AI Agents"])
    def post(self, request, agent_id):
        org = get_org_context(request)
        agent = get_object_or_404(Agent, id=agent_id, organization=org, is_deleted=False)
        serializer = AgentInstructionSerializer(data=request.data)
        if serializer.is_valid():
            instruction = serializer.save(agent=agent, created_by=request.user)
            return Response(AgentInstructionSerializer(instruction).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AgentInstructionDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, agent_id, pk, org):
        agent = get_object_or_404(Agent, id=agent_id, organization=org, is_deleted=False)
        return get_object_or_404(AgentInstruction, id=pk, agent=agent)

    @extend_schema(summary="Update instruction", request=AgentInstructionSerializer, responses={200: AgentInstructionSerializer}, tags=["AI Agents"])
    def put(self, request, agent_id, pk):
        org = get_org_context(request)
        instruction = self.get_object(agent_id, pk, org)
        serializer = AgentInstructionSerializer(instruction, data=request.data, partial=True)
        if serializer.is_valid():
            instruction = serializer.save(updated_by=request.user)
            return Response(AgentInstructionSerializer(instruction).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Delete instruction", responses={204: None}, tags=["AI Agents"])
    def delete(self, request, agent_id, pk):
        org = get_org_context(request)
        instruction = self.get_object(agent_id, pk, org)
        instruction.hard_delete() # Hard delete config helper
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----------------- Tools -----------------

class ToolListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List all available tools", responses={200: ToolSerializer(many=True)}, tags=["AI Tools"])
    def get(self, request):
        tools = Tool.objects.filter(is_deleted=False)
        serializer = ToolSerializer(tools, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Register a tool", request=ToolSerializer, responses={201: ToolSerializer}, tags=["AI Tools"])
    def post(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied("Only administrators can register global tools.")
        serializer = ToolSerializer(data=request.data)
        if serializer.is_valid():
            tool = serializer.save(created_by=request.user)
            return Response(ToolSerializer(tool).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AgentToolListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List tools assigned to agent", responses={200: AgentToolSerializer(many=True)}, tags=["AI Tools"])
    def get(self, request, agent_id):
        org = get_org_context(request)
        agent = get_object_or_404(Agent, id=agent_id, organization=org, is_deleted=False)
        queryset = agent.agent_tools.all()
        serializer = AgentToolSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Assign tool to agent", request=AgentToolSerializer, responses={201: AgentToolSerializer}, tags=["AI Tools"])
    def post(self, request, agent_id):
        org = get_org_context(request)
        agent = get_object_or_404(Agent, id=agent_id, organization=org, is_deleted=False)
        serializer = AgentToolSerializer(data=request.data)
        if serializer.is_valid():
            agent_tool = serializer.save(agent=agent, created_by=request.user)
            return Response(AgentToolSerializer(agent_tool).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AgentToolDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Toggle tool assignment", request=AgentToolSerializer, responses={200: AgentToolSerializer}, tags=["AI Tools"])
    def put(self, request, agent_id, pk):
        org = get_org_context(request)
        agent = get_object_or_404(Agent, id=agent_id, organization=org, is_deleted=False)
        agent_tool = get_object_or_404(AgentTool, id=pk, agent=agent)
        
        serializer = AgentToolSerializer(agent_tool, data=request.data, partial=True)
        if serializer.is_valid():
            agent_tool = serializer.save(updated_by=request.user)
            return Response(AgentToolSerializer(agent_tool).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Remove tool assignment", responses={204: None}, tags=["AI Tools"])
    def delete(self, request, agent_id, pk):
        org = get_org_context(request)
        agent = get_object_or_404(Agent, id=agent_id, organization=org, is_deleted=False)
        agent_tool = get_object_or_404(AgentTool, id=pk, agent=agent)
        agent_tool.hard_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----------------- Model & Provider Management -----------------

class AIProviderListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List providers", responses={200: AIProviderSerializer(many=True)}, tags=["Model Management"])
    def get(self, request):
        queryset = AIProvider.objects.filter(is_deleted=False)
        serializer = AIProviderSerializer(queryset, many=True)
        return Response(serializer.data)


class AIModelListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List AI Models", responses={200: AIModelSerializer(many=True)}, tags=["Model Management"])
    def get(self, request):
        queryset = AIModel.objects.filter(is_deleted=False)
        
        provider_id = request.query_params.get('provider')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
            
        serializer = AIModelSerializer(queryset, many=True)
        return Response(serializer.data)


class OrganizationModelListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List org API keys overrides", responses={200: OrganizationModelSerializer(many=True)}, tags=["Model Management"])
    def get(self, request):
        org = get_org_context(request)
        queryset = OrganizationModel.objects.filter(organization=org, is_deleted=False)
        serializer = OrganizationModelSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Configure org API key override", request=OrganizationModelSerializer, responses={201: OrganizationModelSerializer}, tags=["Model Management"])
    def post(self, request):
        org = get_org_context(request)
        serializer = OrganizationModelSerializer(data=request.data)
        if serializer.is_valid():
            org_model, created = OrganizationModel.objects.update_or_create(
                organization=org,
                provider=serializer.validated_data['provider'],
                defaults={
                    'api_key': serializer.validated_data['api_key'],
                    'is_enabled': serializer.validated_data.get('is_enabled', True),
                    'updated_by': request.user
                }
            )
            if created:
                org_model.created_by = request.user
                org_model.save()
            return Response(OrganizationModelSerializer(org_model).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------- AI Settings -----------------

class AISettingsDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Retrieve Org AI settings", responses={200: AISettingsSerializer}, tags=["AI Settings"])
    def get(self, request):
        org = get_org_context(request)
        settings, _ = AISettings.objects.get_or_create(
            organization=org,
            defaults={'created_by': request.user}
        )
        serializer = AISettingsSerializer(settings)
        return Response(serializer.data)

    @extend_schema(summary="Update Org AI settings", request=AISettingsSerializer, responses={200: AISettingsSerializer}, tags=["AI Settings"])
    def put(self, request):
        org = get_org_context(request)
        settings, _ = AISettings.objects.get_or_create(
            organization=org,
            defaults={'created_by': request.user}
        )
        serializer = AISettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            settings = serializer.save(updated_by=request.user)
            return Response(AISettingsSerializer(settings).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------- Prompt Templates -----------------

class PromptCategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List prompt categories", responses={200: PromptCategorySerializer(many=True)}, tags=["Prompts"])
    def get(self, request):
        categories = PromptCategory.objects.filter(is_deleted=False)
        serializer = PromptCategorySerializer(categories, many=True)
        return Response(serializer.data)


class PromptListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List prompts", responses={200: PromptSerializer(many=True)}, tags=["Prompts"])
    def get(self, request):
        org = get_org_context(request)
        queryset = Prompt.objects.filter(organization=org, is_deleted=False)
        
        category_id = request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
            
        serializer = PromptSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Create a prompt template", request=PromptSerializer, responses={201: PromptSerializer}, tags=["Prompts"])
    def post(self, request):
        org = get_org_context(request)
        serializer = PromptSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                prompt = serializer.save(organization=org, created_by=request.user)
                # Create initial version
                PromptVersion.objects.create(
                    prompt=prompt,
                    version_number=1,
                    template_text=prompt.template_text,
                    created_by=request.user
                )
            return Response(PromptSerializer(prompt).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PromptDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, org):
        return get_object_or_404(Prompt, id=pk, organization=org, is_deleted=False)

    @extend_schema(summary="Retrieve a prompt template", responses={200: PromptSerializer}, tags=["Prompts"])
    def get(self, request, pk):
        org = get_org_context(request)
        prompt = self.get_object(pk, org)
        serializer = PromptSerializer(prompt)
        return Response(serializer.data)

    @extend_schema(summary="Update a prompt template", request=PromptSerializer, responses={200: PromptSerializer}, tags=["Prompts"])
    def put(self, request, pk):
        org = get_org_context(request)
        prompt = self.get_object(pk, org)
        serializer = PromptSerializer(prompt, data=request.data, partial=True)
        if serializer.is_valid():
            with transaction.atomic():
                prompt = serializer.save(updated_by=request.user)
                if 'template_text' in serializer.validated_data:
                    # Increment version number
                    last_version = prompt.versions.order_by('-version_number').first()
                    next_version_num = (last_version.version_number + 1) if last_version else 1
                    PromptVersion.objects.create(
                        prompt=prompt,
                        version_number=next_version_num,
                        template_text=serializer.validated_data['template_text'],
                        created_by=request.user
                    )
            return Response(PromptSerializer(prompt).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Delete a prompt template", responses={204: None}, tags=["Prompts"])
    def delete(self, request, pk):
        org = get_org_context(request)
        prompt = self.get_object(pk, org)
        prompt.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
