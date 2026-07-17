from django.db import models
from apps.common.models import BaseModel

class ReasoningLog(BaseModel):
    execution_id = models.UUIDField()
    step_id = models.UUIDField(null=True, blank=True)
    chain_of_thought = models.TextField()  # Internal thinking path
    reflection = models.TextField(blank=True)  # Critique and verification
    self_check_passed = models.BooleanField(default=True)
    error_recovery_actions = models.TextField(blank=True)

    def __str__(self):
        passed_str = "Passed" if self.self_check_passed else "Failed"
        return f"Reasoning Log for Execution {self.execution_id[:8]} (Self-check: {passed_str})"
