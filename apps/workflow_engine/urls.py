from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.workflow_engine.views import (
    WorkflowViewSet, WorkflowNodeViewSet, NodeConnectionViewSet,
    WorkflowExecutionViewSet, VariableViewSet, WorkflowTemplateViewSet,
    WebhookViewSet, WorkflowBuilderAPIView, IncomingWebhookAPIView
)

router = DefaultRouter()
router.register('workflows', WorkflowViewSet, basename='workflow')
router.register('nodes', WorkflowNodeViewSet, basename='node')
router.register('connections', NodeConnectionViewSet, basename='connection')
router.register('executions', WorkflowExecutionViewSet, basename='execution')
router.register('variables', VariableViewSet, basename='variable')
router.register('templates', WorkflowTemplateViewSet, basename='template')
router.register('webhooks', WebhookViewSet, basename='webhook')

urlpatterns = [
    path('', include(router.urls)),
    path('workflow-builder/', WorkflowBuilderAPIView.as_view(), name='workflow-builder'),
    path('webhooks/incoming/<str:token>/', IncomingWebhookAPIView.as_view(), name='webhook-incoming'),
]
