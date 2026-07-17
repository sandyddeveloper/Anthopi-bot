from django.db import models
from apps.common.models import BaseModel
from apps.organization.models import Organization
from apps.ai_agents.models import Agent

class AIJob(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ai_jobs')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='ai_jobs')
    task_name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    celery_task_id = models.CharField(max_length=255, blank=True)
    
    total_items = models.IntegerField(default=0)
    processed_items = models.IntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"AI Job {self.task_name} ({self.status})"
