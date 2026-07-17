from django.db import models
from apps.common.models import BaseModel
from apps.organization.models import Organization
from apps.users.models import User
from apps.projects.models import Project
from apps.ai_agents.models import Agent
from apps.ai_chat.models import Conversation
from apps.workflow_engine.models import WorkflowExecution

class Memory(BaseModel):
    LEVEL_CHOICES = [
        ('organization', 'Organization'),
        ('project', 'Project'),
        ('agent', 'Agent'),
        ('user', 'User'),
        ('conversation', 'Conversation'),
        ('workflow', 'Workflow'),
    ]
    
    TYPE_CHOICES = [
        ('preference', 'Preference'),
        ('fact', 'Fact'),
        ('decision', 'Decision'),
        ('relationship', 'Relationship'),
        ('task', 'Task'),
        ('summary', 'Summary'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='enterprise_memories')
    level = models.CharField(max_length=50, choices=LEVEL_CHOICES)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    content = models.TextField()
    confidence_score = models.FloatField(default=1.0)
    
    # Overriding created_by and updated_by to avoid related_name collision with ai_chat.Memory
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enterprise_memory_created',
        db_constraint=False
    )
    updated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enterprise_memory_updated',
        db_constraint=False
    )
    
    # Associated entities
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='enterprise_memories')
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='enterprise_memories')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='enterprise_memories')
    conversation = models.ForeignKey(Conversation, on_delete=models.SET_NULL, null=True, blank=True, related_name='enterprise_memories')
    workflow_execution = models.ForeignKey(WorkflowExecution, on_delete=models.SET_NULL, null=True, blank=True, related_name='enterprise_memories')

    def __str__(self):
        return f"{self.level.capitalize()} Memory ({self.type.capitalize()}): {self.content[:30]}"
