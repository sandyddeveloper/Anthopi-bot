from django.db import models
from apps.common.models import BaseModel
from apps.users.models import User
from apps.ai_agents.models import Agent

class ToolExecution(BaseModel):
    tool_code = models.CharField(max_length=100)
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='tool_executions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tool_executions')
    input_parameters = models.JSONField(default=dict, blank=True)
    output_result = models.JSONField(default=dict, blank=True)
    is_success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    duration_ms = models.IntegerField(default=0)

    def __str__(self):
        status_str = "Success" if self.is_success else "Failed"
        return f"Tool {self.tool_code} run by {self.user.email} ({status_str})"
