from django.db import models
from apps.common.models import BaseModel
from apps.organization.models import Organization
from apps.ai_chat.models import Conversation

class ExecutionPlan(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='execution_plans')
    conversation = models.ForeignKey(Conversation, on_delete=models.SET_NULL, null=True, blank=True, related_name='execution_plans')
    goal = models.TextField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"Plan for Goal: {self.goal[:30]} ({self.status})"

class PlanStep(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('executing', 'Executing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    plan = models.ForeignKey(ExecutionPlan, on_delete=models.CASCADE, related_name='steps')
    step_number = models.IntegerField()
    description = models.TextField()
    tool_code = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['step_number']

    def __str__(self):
        return f"Step {self.step_number} of {self.plan.id[:8]} - {self.description[:30]}"

class PlanResult(BaseModel):
    plan = models.OneToOneField(ExecutionPlan, on_delete=models.CASCADE, related_name='result')
    result_summary = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Result for Plan {self.plan.id[:8]}"
