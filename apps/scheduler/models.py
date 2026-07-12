from django.db import models
from django.utils import timezone
from apps.common.models import BaseModel
from apps.workflow_engine.models import Workflow, WorkflowExecution

class Schedule(BaseModel):
    SCHEDULE_TYPES = [
        ('once', 'Once'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('cron', 'Cron Expression'),
    ]

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='schedules')
    schedule_type = models.CharField(max_length=50, choices=SCHEDULE_TYPES, default='daily')
    cron_expression = models.CharField(max_length=100, null=True, blank=True, help_text="Standard crontab formatting")
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Schedule ({self.schedule_type}) for {self.workflow.name}"


class ScheduleExecution(BaseModel):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='schedule_executions')
    workflow_execution = models.ForeignKey(WorkflowExecution, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='success')
    run_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Schedule Run at {self.run_at} - Status: {self.status}"
