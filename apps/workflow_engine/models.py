import uuid
from django.db import models
from django.utils import timezone
from apps.common.models import BaseModel
from apps.organization.models import Organization
from apps.projects.models import Project
from apps.users.models import User
from apps.ai_agents.models import Agent

class WorkflowCategory(BaseModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class WorkflowFolder(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='workflow_folders')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subfolders')

    def __str__(self):
        return self.name


class WorkflowTag(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='workflow_tags')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100)

    class Meta:
        unique_together = ('organization', 'code')

    def __str__(self):
        return self.name


class Workflow(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='workflows')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='workflows')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='workflows')
    category = models.ForeignKey(WorkflowCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='workflows')
    folder = models.ForeignKey(WorkflowFolder, on_delete=models.SET_NULL, null=True, blank=True, related_name='workflows')
    tags = models.ManyToManyField(WorkflowTag, blank=True, related_name='workflows')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    active_version = models.ForeignKey('WorkflowVersion', on_delete=models.SET_NULL, null=True, blank=True, related_name='active_for_workflow')

    def __str__(self):
        return self.name


class WorkflowVersion(BaseModel):
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField(default=1)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        unique_together = ('workflow', 'version_number')

    def __str__(self):
        return f"{self.workflow.name} v{self.version_number}"


class WorkflowNode(BaseModel):
    workflow_version = models.ForeignKey(WorkflowVersion, on_delete=models.CASCADE, related_name='nodes')
    node_id = models.CharField(max_length=100)  # e.g., 'trigger_1', 'ai_node_1'
    name = models.CharField(max_length=255)
    node_type = models.CharField(max_length=100)  # trigger, action, condition, ai_agent, api_request, etc.
    sub_type = models.CharField(max_length=100, blank=True)  # e.g., webhook, schedule, manual, send_email, etc.
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('workflow_version', 'node_id')

    def __str__(self):
        return f"{self.name} ({self.node_type})"


class NodePosition(BaseModel):
    node = models.OneToOneField(WorkflowNode, on_delete=models.CASCADE, related_name='position')
    position_x = models.FloatField(default=0.0)
    position_y = models.FloatField(default=0.0)

    def __str__(self):
        return f"Pos ({self.position_x}, {self.position_y}) for {self.node.name}"


class NodeConnection(BaseModel):
    workflow_version = models.ForeignKey(WorkflowVersion, on_delete=models.CASCADE, related_name='connections')
    source_node = models.ForeignKey(WorkflowNode, on_delete=models.CASCADE, related_name='source_connections')
    target_node = models.ForeignKey(WorkflowNode, on_delete=models.CASCADE, related_name='target_connections')
    condition = models.JSONField(default=dict, blank=True)  # e.g. {"field": "status", "operator": "equals", "value": "completed"}

    class Meta:
        unique_together = ('workflow_version', 'source_node', 'target_node')

    def __str__(self):
        return f"{self.source_node.node_id} -> {self.target_node.node_id}"


class VariableScope(BaseModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100, unique=True)  # global, workflow, execution

    def __str__(self):
        return self.name


class Variable(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='variables')
    workflow = models.ForeignKey(Workflow, on_delete=models.SET_NULL, null=True, blank=True, related_name='variables')
    scope = models.ForeignKey(VariableScope, on_delete=models.PROTECT, related_name='variables')
    key = models.CharField(max_length=255)
    value = models.TextField()

    class Meta:
        unique_together = ('organization', 'workflow', 'key')

    def __str__(self):
        return f"{self.key}={self.value[:20]}"


class WorkflowExecution(BaseModel):
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='executions')
    workflow_version = models.ForeignKey(WorkflowVersion, on_delete=models.CASCADE, related_name='executions')
    trigger_node = models.ForeignKey(WorkflowNode, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='queued')
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    variables_state = models.JSONField(default=dict, blank=True)  # captures runtime values snapshot
    duration_ms = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Execution {self.id} for {self.workflow.name} ({self.status})"


class NodeExecution(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]
    workflow_execution = models.ForeignKey(WorkflowExecution, on_delete=models.CASCADE, related_name='node_executions')
    node = models.ForeignKey(WorkflowNode, on_delete=models.CASCADE, related_name='executions')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, null=True)
    duration_ms = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Node {self.node.name} Execution ({self.status})"


class ExecutionLog(BaseModel):
    LEVEL_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]
    workflow_execution = models.ForeignKey(WorkflowExecution, on_delete=models.CASCADE, related_name='logs')
    node_execution = models.ForeignKey(NodeExecution, on_delete=models.CASCADE, null=True, blank=True, related_name='logs')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='info')
    message = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"[{self.level.upper()}] {self.message[:50]}"


class RetryPolicy(BaseModel):
    BACKOFF_CHOICES = [
        ('immediate', 'Immediate'),
        ('fixed', 'Fixed Delay'),
        ('exponential', 'Exponential Backoff'),
    ]
    workflow = models.OneToOneField(Workflow, on_delete=models.CASCADE, related_name='retry_policy')
    max_retries = models.IntegerField(default=3)
    delay_seconds = models.IntegerField(default=5)
    backoff_type = models.CharField(max_length=50, choices=BACKOFF_CHOICES, default='fixed')

    def __str__(self):
        return f"RetryPolicy for {self.workflow.name}"


class TemplateCategory(BaseModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class WorkflowTemplate(BaseModel):
    category = models.ForeignKey(TemplateCategory, on_delete=models.PROTECT, related_name='templates')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    definition = models.JSONField(default=dict)

    def __str__(self):
        return self.name


class Webhook(BaseModel):
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='webhooks')
    webhook_token = models.CharField(max_length=100, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Webhook for {self.workflow.name}"


class WebhookLog(BaseModel):
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='logs')
    request_method = models.CharField(max_length=10)
    request_headers = models.JSONField(default=dict)
    request_body = models.TextField(blank=True)
    response_status = models.IntegerField(default=200)
    response_body = models.TextField(blank=True)
    workflow_execution = models.ForeignKey(WorkflowExecution, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Webhook request status {self.response_status}"
