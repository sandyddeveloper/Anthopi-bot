from django.urls import path
from apps.ai_memory.views import MemoryListCreateAPIView, MemoryDetailAPIView, MemoryMergeAPIView

urlpatterns = [
    path('', MemoryListCreateAPIView.as_view(), name='memory-list-create'),
    path('merge/', MemoryMergeAPIView.as_view(), name='memory-merge'),
    path('<uuid:pk>/', MemoryDetailAPIView.as_view(), name='memory-detail'),
]
