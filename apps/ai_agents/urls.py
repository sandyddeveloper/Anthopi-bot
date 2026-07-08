from django.urls import path
from apps.ai_agents.views import (
    AgentCategoryListAPIView, AgentListCreateAPIView, AgentDetailAPIView,
    AgentDuplicateAPIView, AgentInstructionListCreateAPIView, AgentInstructionDetailAPIView,
    ToolListCreateAPIView, AgentToolListCreateAPIView, AgentToolDetailAPIView,
    AIProviderListAPIView, AIModelListAPIView, OrganizationModelListCreateAPIView,
    AISettingsDetailAPIView, PromptCategoryListAPIView, PromptListCreateAPIView, PromptDetailAPIView
)

urlpatterns = [
    path('agents/categories/', AgentCategoryListAPIView.as_view(), name='agent-category-list'),
    path('agents/', AgentListCreateAPIView.as_view(), name='agent-list-create'),
    path('agents/<uuid:pk>/', AgentDetailAPIView.as_view(), name='agent-detail'),
    path('agents/<uuid:pk>/duplicate/', AgentDuplicateAPIView.as_view(), name='agent-duplicate'),
    
    path('agents/<uuid:agent_id>/instructions/', AgentInstructionListCreateAPIView.as_view(), name='agent-instruction-list-create'),
    path('agents/<uuid:agent_id>/instructions/<uuid:pk>/', AgentInstructionDetailAPIView.as_view(), name='agent-instruction-detail'),
    
    path('agents/<uuid:agent_id>/tools/', AgentToolListCreateAPIView.as_view(), name='agent-tool-list-create'),
    path('agents/<uuid:agent_id>/tools/<uuid:pk>/', AgentToolDetailAPIView.as_view(), name='agent-tool-detail'),
    
    path('tools/', ToolListCreateAPIView.as_view(), name='tool-list-create'),
    path('providers/', AIProviderListAPIView.as_view(), name='provider-list'),
    path('models/', AIModelListAPIView.as_view(), name='model-list'),
    path('provider-keys/', OrganizationModelListCreateAPIView.as_view(), name='org-provider-key-list-create'),
    path('settings/', AISettingsDetailAPIView.as_view(), name='ai-settings-detail'),
    
    path('prompts/categories/', PromptCategoryListAPIView.as_view(), name='prompt-category-list'),
    path('prompts/', PromptListCreateAPIView.as_view(), name='prompt-list-create'),
    path('prompts/<uuid:pk>/', PromptDetailAPIView.as_view(), name='prompt-detail'),
]
