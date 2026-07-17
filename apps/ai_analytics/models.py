from django.db import models
from apps.common.models import BaseModel
from apps.organization.models import Organization
from apps.users.models import User

class AIEvent(BaseModel):
    EVENT_TYPES = [
        ('agent_created', 'Agent Created'),
        ('conversation_started', 'Conversation Started'),
        ('memory_saved', 'Memory Saved'),
        ('tool_executed', 'Tool Executed'),
        ('workflow_generated', 'Workflow Generated'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ai_events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    description = models.TextField()
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_events')
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Event {self.event_type} - {self.description[:30]}"
