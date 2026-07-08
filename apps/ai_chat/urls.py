from django.urls import path
from apps.ai_chat.views import (
    ConversationListCreateAPIView, ConversationDetailAPIView,
    MessageListCreateAPIView, MemoryCategoryListAPIView,
    MemoryListCreateAPIView, MemoryDetailAPIView, AIUsageListAPIView
)

urlpatterns = [
    path('conversations/', ConversationListCreateAPIView.as_view(), name='conversation-list-create'),
    path('conversations/<uuid:pk>/', ConversationDetailAPIView.as_view(), name='conversation-detail'),
    path('conversations/<uuid:conversation_id>/messages/', MessageListCreateAPIView.as_view(), name='message-list-create'),
    
    path('memory/categories/', MemoryCategoryListAPIView.as_view(), name='memory-category-list'),
    path('memory/', MemoryListCreateAPIView.as_view(), name='memory-list-create'),
    path('memory/<uuid:pk>/', MemoryDetailAPIView.as_view(), name='memory-detail'),
    
    path('usage/', AIUsageListAPIView.as_view(), name='ai-usage-summary'),
]
