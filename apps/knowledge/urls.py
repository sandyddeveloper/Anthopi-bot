from django.urls import path
from apps.knowledge.views import (
    FolderListCreateAPIView, FolderDetailAPIView,
    FileListCreateAPIView, FileDetailAPIView,
    FileDownloadAPIView, FileVersionListCreateAPIView,
    KnowledgeCollectionListCreateAPIView, KnowledgeCollectionDetailAPIView,
    KnowledgeCollectionAssignAgentAPIView, KnowledgeCollectionAddItemAPIView
)

urlpatterns = [
    # Folders
    path('folders/', FolderListCreateAPIView.as_view(), name='folder-list-create'),
    path('folders/<uuid:pk>/', FolderDetailAPIView.as_view(), name='folder-detail'),
    
    # Files
    path('files/', FileListCreateAPIView.as_view(), name='file-list-create'),
    path('files/<uuid:pk>/', FileDetailAPIView.as_view(), name='file-detail'),
    path('files/<uuid:pk>/download/', FileDownloadAPIView.as_view(), name='file-download'),
    path('files/<uuid:file_id>/versions/', FileVersionListCreateAPIView.as_view(), name='file-version-list-create'),
    
    # Knowledge Collections
    path('knowledge/collections/', KnowledgeCollectionListCreateAPIView.as_view(), name='knowledge-collection-list-create'),
    path('knowledge/collections/<uuid:pk>/', KnowledgeCollectionDetailAPIView.as_view(), name='knowledge-collection-detail'),
    path('knowledge/collections/<uuid:pk>/assign-agent/', KnowledgeCollectionAssignAgentAPIView.as_view(), name='knowledge-collection-assign-agent'),
    path('knowledge/collections/<uuid:pk>/add-file/', KnowledgeCollectionAddItemAPIView.as_view(), name='knowledge-collection-add-file'),
]
