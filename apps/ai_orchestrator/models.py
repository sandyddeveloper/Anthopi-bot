from django.db import models
from apps.common.models import BaseModel
from apps.organization.models import Organization
from apps.users.models import User
from apps.ai_agents.models import Agent
from apps.ai_chat.models import Conversation
from apps.ai_planner.models import ExecutionPlan

class AgentExecution(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('awaiting_approval', 'Awaiting Approval'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='executions')
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='executions')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='executions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='executions')
    
    prompt = models.TextField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    plan = models.ForeignKey(ExecutionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='executions')
    response_text = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=6, default=0.0)
    duration_ms = models.IntegerField(default=0)

    def __str__(self):
        return f"Execution {self.id} ({self.status}) for Agent {self.agent.name}"

class AgentTask(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    execution = models.ForeignKey(AgentExecution, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"Task: {self.title} ({self.status})"

class AgentAssignment(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    task = models.ForeignKey(AgentTask, on_delete=models.CASCADE, related_name='assignments')
    delegator_agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='delegated_assignments')
    assignee_agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='received_assignments')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"Assignment: {self.delegator_agent.name} -> {self.assignee_agent.name} ({self.status})"

class AgentResponse(BaseModel):
    assignment = models.OneToOneField(AgentAssignment, on_delete=models.CASCADE, related_name='response')
    response_text = models.TextField()
    output_data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Response for Assignment {self.assignment.id[:8]}"
