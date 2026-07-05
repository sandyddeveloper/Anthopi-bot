from django.urls import path
from apps.projects.views import (
    ProjectListCreateAPIView, ProjectDetailAPIView,
    ProjectArchiveAPIView, ProjectRestoreAPIView,
    ProjectMemberListCreateAPIView, ProjectMemberDetailAPIView
)

urlpatterns = [
    path('projects/', ProjectListCreateAPIView.as_view(), name='project-list-create'),
    path('projects/<uuid:pk>/', ProjectDetailAPIView.as_view(), name='project-detail'),
    path('projects/<uuid:pk>/archive/', ProjectArchiveAPIView.as_view(), name='project-archive'),
    path('projects/<uuid:pk>/restore/', ProjectRestoreAPIView.as_view(), name='project-restore'),
    
    # Members
    path('projects/<uuid:project_id>/members/', ProjectMemberListCreateAPIView.as_view(), name='project-member-list-create'),
    path('projects/members/<uuid:pk>/', ProjectMemberDetailAPIView.as_view(), name='project-member-detail'),
]
