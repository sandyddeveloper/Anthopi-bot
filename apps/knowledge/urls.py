from django.urls import path
from apps.knowledge.views import (
    FolderListCreateAPIView, FolderDetailAPIView,
    FileListCreateAPIView, FileDetailAPIView,
    FileDownloadAPIView, FileVersionListCreateAPIView
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
]
