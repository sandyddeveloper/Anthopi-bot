from django.db import models
from apps.common.models import BaseModel
from apps.organization.models import Organization
from apps.users.models import User

class AIReport(BaseModel):
    REPORT_TYPES = [
        ('usage', 'Usage Report'),
        ('cost', 'Cost Report'),
        ('productivity', 'Productivity Report'),
        ('agent', 'Agent Report'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ai_reports')
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    data = models.JSONField(default=dict, blank=True)
    generated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generated_reports')

    def __str__(self):
        return f"{self.get_report_type_display()} ({self.start_date} to {self.end_date})"
