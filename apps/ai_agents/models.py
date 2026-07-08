import uuid
from django.db import models
from apps.common.models import BaseModel
from apps.organization.models import Organization
from apps.projects.models import Project
from apps.users.models import User

class AgentCategory(BaseModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class AIProvider(BaseModel):
    name = models.CharField(max_length=255) # e.g. Anthropic, OpenAI, Google
    code = models.CharField(max_length=100, unique=True) # e.g. anthropic, openai, google, deepseek, ollama, azure
    base_url = models.CharField(max_length=255, null=True, blank=True)
    api_key = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class AIModel(BaseModel):
    provider = models.ForeignKey(AIProvider, on_delete=models.CASCADE, related_name='models')
    name = models.CharField(max_length=255) # e.g. Claude 3.5 Sonnet, GPT-4o
    code = models.CharField(max_length=100) # e.g. claude-3-5-sonnet-latest, gpt-4o
    context_window = models.IntegerField(default=128000)
    input_token_cost = models.DecimalField(max_digits=10, decimal_places=6, default=0.0) # Cost per 1k or 1m tokens
    output_token_cost = models.DecimalField(max_digits=10, decimal_places=6, default=0.0)
    is_streaming_supported = models.BooleanField(default=True)

    class Meta:
        unique_together = ('provider', 'code')

    def __str__(self):
        return f"{self.provider.name} - {self.name}"


class OrganizationModel(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='org_models')
    provider = models.ForeignKey(AIProvider, on_delete=models.CASCADE)
    api_key = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('organization', 'provider')


class Agent(BaseModel):
    VISIBILITY_CHOICES = [
        ('private', 'Private'),
        ('organization', 'Organization'),
        ('public', 'Public'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='agents')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='agents')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_agents')
    
    name = models.CharField(max_length=255)
    avatar = models.ImageField(upload_to='agent_avatars/', null=True, blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(AgentCategory, on_delete=models.PROTECT, related_name='agents')
    
    system_prompt = models.TextField(blank=True)
    temperature = models.FloatField(default=0.7)
    model = models.ForeignKey(AIModel, on_delete=models.SET_NULL, null=True, blank=True, related_name='agents')
    
    visibility = models.CharField(max_length=50, choices=VISIBILITY_CHOICES, default='organization')

    def __str__(self):
        return self.name


class AgentInstruction(BaseModel):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='instructions')
    title = models.CharField(max_length=255)
    instruction_text = models.TextField()
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.agent.name} - {self.title}"


class AgentConfiguration(BaseModel):
    agent = models.OneToOneField(Agent, on_delete=models.CASCADE, related_name='configuration')
    extra_settings = models.JSONField(default=dict, blank=True)


class AISettings(BaseModel):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='ai_settings')
    default_model = models.ForeignKey(AIModel, on_delete=models.SET_NULL, null=True, blank=True)
    temperature = models.FloatField(default=0.7)
    max_tokens = models.IntegerField(default=4096)
    allowed_providers = models.JSONField(default=list, blank=True)
    cost_limit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    daily_limit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)


class PromptCategory(BaseModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Prompt(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='prompts')
    category = models.ForeignKey(PromptCategory, on_delete=models.PROTECT, related_name='prompts')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    template_text = models.TextField()
    variables = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.name


class PromptVersion(BaseModel):
    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField(default=1)
    template_text = models.TextField()

    class Meta:
        unique_together = ('prompt', 'version_number')


class Tool(BaseModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    schema = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name


class AgentTool(BaseModel):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='agent_tools')
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='agent_tools')
    is_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('agent', 'tool')


class ToolParameter(BaseModel):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='parameters')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50) # e.g. string, integer, boolean
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=False)

    class Meta:
        unique_together = ('tool', 'name')
