from django.urls import path
from apps.ai_rag.views import ChunkFileAPIView, RAGSearchAPIView

urlpatterns = [
    path('chunk-file/', ChunkFileAPIView.as_view(), name='rag-chunk-file'),
    path('search/', RAGSearchAPIView.as_view(), name='rag-search'),
]
