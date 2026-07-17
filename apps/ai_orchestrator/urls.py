from django.urls import path
from apps.ai_orchestrator.views import ExecuteAgentAPIView, ContinueExecutionAPIView, CancelExecutionAPIView, ExecutionStatusAPIView

urlpatterns = [
    path('execute/', ExecuteAgentAPIView.as_view(), name='orchestrator-execute'),
    path('execute/<uuid:execution_id>/continue/', ContinueExecutionAPIView.as_view(), name='orchestrator-continue'),
    path('execute/<uuid:execution_id>/cancel/', CancelExecutionAPIView.as_view(), name='orchestrator-cancel'),
    path('execute/<uuid:execution_id>/status/', ExecutionStatusAPIView.as_view(), name='orchestrator-status'),
]
