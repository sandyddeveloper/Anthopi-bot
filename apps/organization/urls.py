from django.urls import path
from apps.organization.views import (
    OrganizationListCreateAPIView, OrganizationDetailAPIView,
    DepartmentListCreateAPIView, DepartmentDetailAPIView,
    TeamListCreateAPIView, TeamDetailAPIView,
    DesignationListCreateAPIView, DesignationDetailAPIView,
    InvitationListCreateAPIView, InvitationAcceptAPIView
)

urlpatterns = [
    path('organizations/', OrganizationListCreateAPIView.as_view(), name='organization-list'),
    path('organizations/<uuid:pk>/', OrganizationDetailAPIView.as_view(), name='organization-detail'),
    
    path('departments/', DepartmentListCreateAPIView.as_view(), name='department-list'),
    path('departments/<uuid:pk>/', DepartmentDetailAPIView.as_view(), name='department-detail'),
    
    path('teams/', TeamListCreateAPIView.as_view(), name='team-list'),
    path('teams/<uuid:pk>/', TeamDetailAPIView.as_view(), name='team-detail'),
    
    path('designations/', DesignationListCreateAPIView.as_view(), name='designation-list'),
    path('designations/<uuid:pk>/', DesignationDetailAPIView.as_view(), name='designation-detail'),
    
    path('invitations/', InvitationListCreateAPIView.as_view(), name='invitation-list'),
    path('invitations/accept/', InvitationAcceptAPIView.as_view(), name='invitation_accept'),
]
