from django.db import models
from apps.common.models import BaseModel
from apps.organization.models import Organization
from apps.users.models import User

class ApprovalRequest(BaseModel):
    APPROVAL_TYPES = [
        ('user', 'User Approval'),
        ('manager', 'Manager Approval'),
        ('team_lead', 'Team Lead Approval'),
        ('automatic', 'Automatic'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='approval_requests')
    execution_id = models.UUIDField(null=True, blank=True)  # Associated AgentExecution ID
    tool_code = models.CharField(max_length=100)
    parameters = models.JSONField(default=dict, blank=True)
    
    approval_type = models.CharField(max_length=50, choices=APPROVAL_TYPES, default='manager')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requested_approvals')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requests')
    comments = models.TextField(blank=True)

    def __str__(self):
        return f"Approval request for {self.tool_code} ({self.status})"
