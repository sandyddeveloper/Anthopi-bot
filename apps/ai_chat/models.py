from django.db import models
from apps.common.models import BaseModel
from apps.organization.models import Organization
from apps.projects.models import Project
from apps.users.models import User
from apps.ai_agents.models import Agent, AIModel
from apps.knowledge.models import File

class Conversation(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='conversations')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    
    title = models.CharField(max_length=255, blank=True)
    is_pinned = models.BooleanField(default=False)

    def __str__(self):
        return self.title or f"Conversation with {self.agent.name if self.agent else 'Unknown'}"


class ConversationParticipant(BaseModel):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('conversation', 'user')


class Message(BaseModel):
    SENDER_TYPES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
        ('tool', 'Tool'),
        ('error', 'Error'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    sender_type = models.CharField(max_length=50, choices=SENDER_TYPES, default='user')
    content = models.TextField()
    
    # Usage metrics
    prompt_tokens = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    response_time = models.FloatField(null=True, blank=True) # in seconds

    def __str__(self):
        return f"{self.sender_type.capitalize()}: {self.content[:50]}"


class MessageAttachment(BaseModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.ForeignKey(File, on_delete=models.SET_NULL, null=True, blank=True, related_name='message_attachments')
    name = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='chat_attachments/')
    file_size = models.IntegerField() # in bytes
    file_type = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class MemoryCategory(BaseModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True) # e.g. user_preferences, project_memory, agent_memory, conversation_memory, organization_memory

    def __str__(self):
        return self.name


class Memory(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memories')
    category = models.ForeignKey(MemoryCategory, on_delete=models.PROTECT, related_name='memories')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='memories')
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='memories')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='memories')
    conversation = models.ForeignKey(Conversation, on_delete=models.SET_NULL, null=True, blank=True, related_name='memories')
    
    content = models.TextField()
    confidence_score = models.FloatField(default=1.0)

    def __str__(self):
        return f"Memory ({self.category.name}): {self.content[:50]}"


class MemorySource(BaseModel):
    memory = models.ForeignKey(Memory, on_delete=models.CASCADE, related_name='sources')
    source_type = models.CharField(max_length=100) # e.g. conversation, direct_input
    message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True, related_name='memory_sources')


class AIUsage(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ai_usage')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_usage')
    model = models.ForeignKey(AIModel, on_delete=models.CASCADE, related_name='ai_usage')
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_usage')
    
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=6, default=0.0)
    duration_ms = models.IntegerField(default=0) # response time in ms
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.model.name} - {self.date}"


class AIActivityLog(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ai_activities')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_activities')
    action = models.CharField(max_length=255) # e.g. conversation_started, agent_created, etc.
    description = models.TextField(blank=True)
    entity_type = models.CharField(max_length=100) # e.g. agent, conversation
    entity_id = models.UUIDField(null=True, blank=True)

    def __str__(self):
        return f"{self.action} by {self.user.email if self.user else 'System'}"
