from rest_framework import serializers
from apps.ai_agents.models import (
    AgentCategory, AIProvider, AIModel, OrganizationModel, Agent,
    AgentInstruction, AgentConfiguration, AISettings, PromptCategory,
    Prompt, PromptVersion, Tool, AgentTool, ToolParameter
)
from apps.users.serializers import UserSerializer

class AgentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentCategory
        fields = ['id', 'name', 'code', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AIProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIProvider
        fields = ['id', 'name', 'code', 'base_url', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AIModelSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)

    class Meta:
        model = AIModel
        fields = [
            'id', 'provider', 'provider_name', 'name', 'code',
            'context_window', 'input_token_cost', 'output_token_cost',
            'is_streaming_supported', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OrganizationModelSerializer(serializers.ModelSerializer):
    provider_details = AIProviderSerializer(source='provider', read_only=True)

    class Meta:
        model = OrganizationModel
        fields = ['id', 'organization', 'provider', 'provider_details', 'api_key', 'is_enabled', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']
        extra_kwargs = {'api_key': {'write_only': True}}


class AgentInstructionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentInstruction
        fields = ['id', 'agent', 'title', 'instruction_text', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']


class AgentConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentConfiguration
        fields = ['id', 'agent', 'extra_settings']
        read_only_fields = ['id', 'agent']


class ToolParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolParameter
        fields = ['id', 'name', 'type', 'description', 'is_required']
        read_only_fields = ['id']


class ToolSerializer(serializers.ModelSerializer):
    parameters = ToolParameterSerializer(many=True, read_only=True)

    class Meta:
        model = Tool
        fields = ['id', 'name', 'code', 'description', 'schema', 'parameters', 'created_at']
        read_only_fields = ['id', 'created_at']


class AgentToolSerializer(serializers.ModelSerializer):
    tool_details = ToolSerializer(source='tool', read_only=True)

    class Meta:
        model = AgentTool
        fields = ['id', 'agent', 'tool', 'tool_details', 'is_enabled', 'created_at']
        read_only_fields = ['id', 'created_at']


class AgentSerializer(serializers.ModelSerializer):
    category_details = AgentCategorySerializer(source='category', read_only=True)
    model_details = AIModelSerializer(source='model', read_only=True)
    owner_details = UserSerializer(source='owner', read_only=True)
    instructions = AgentInstructionSerializer(many=True, read_only=True)
    configuration = AgentConfigurationSerializer(read_only=True)
    tools = AgentToolSerializer(source='agent_tools', many=True, read_only=True)

    class Meta:
        model = Agent
        fields = [
            'id', 'organization', 'project', 'owner', 'owner_details',
            'name', 'avatar', 'description', 'category', 'category_details',
            'system_prompt', 'temperature', 'model', 'model_details',
            'visibility', 'instructions', 'configuration', 'tools', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']


class AISettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AISettings
        fields = [
            'id', 'organization', 'default_model', 'temperature',
            'max_tokens', 'allowed_providers', 'cost_limit', 'daily_limit',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']


class PromptCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PromptCategory
        fields = ['id', 'name', 'code', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class PromptVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromptVersion
        fields = ['id', 'prompt', 'version_number', 'template_text', 'created_at']
        read_only_fields = ['id', 'version_number', 'created_at']


class PromptSerializer(serializers.ModelSerializer):
    category_details = PromptCategorySerializer(source='category', read_only=True)
    versions = PromptVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Prompt
        fields = [
            'id', 'organization', 'category', 'category_details',
            'name', 'description', 'template_text', 'variables',
            'versions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']
