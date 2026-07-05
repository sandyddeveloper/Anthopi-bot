import uuid
from django.db import models

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    organization = models.ForeignKey('organization.Organization', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.created_at} - {self.action} by {self.user.email if self.user else 'Anonymous'}"

class ActivityLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='activities')
    action = models.CharField(max_length=255) # e.g. created, updated, uploaded, deleted
    module = models.CharField(max_length=100) # e.g. project, file, employee, department
    object_id = models.UUIDField(null=True, blank=True)
    object_repr = models.CharField(max_length=255) # e.g. "Project Alpha", "resume.pdf"
    organization = models.ForeignKey('organization.Organization', on_delete=models.CASCADE, related_name='activities')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.actor.email if self.actor else 'System'} {self.action} {self.module} {self.object_repr}"

def log_activity(actor, action, module, object_id, object_repr, organization, metadata=None):
    if metadata is None:
        metadata = {}
    
    # Create Activity Log
    activity = ActivityLog.objects.create(
        actor=actor,
        action=action,
        module=module,
        object_id=object_id,
        object_repr=object_repr,
        organization=organization,
        metadata=metadata
    )

    # Automatically send events based on actions
    from apps.notifications.models import send_notification
    
    if module == 'project' and action == 'created':
        # Notify project manager
        project_name = object_repr
        # Notify managers/admins or managers
        pass
        
    return activity

