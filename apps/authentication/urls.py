from django.urls import path
from apps.authentication.views import (
    LoginAPIView, LogoutAPIView, LogoutAllAPIView, TokenRefreshAPIView,
    UserSessionListAPIView, UserSessionRevokeAPIView, PermissionListAPIView,
    RoleListCreateAPIView, RoleDetailAPIView, UserPermissionsAPIView
)

urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='token_obtain_pair'),
    path('logout/', LogoutAPIView.as_view(), name='logout'),
    path('logout-all/', LogoutAllAPIView.as_view(), name='logout_all'),
    path('refresh/', TokenRefreshAPIView.as_view(), name='token_refresh'),
    
    path('sessions/', UserSessionListAPIView.as_view(), name='session-list'),
    path('sessions/<uuid:pk>/', UserSessionRevokeAPIView.as_view(), name='session-detail'),
    
    path('permissions/', PermissionListAPIView.as_view(), name='permission-list'),
    path('my-permissions/', UserPermissionsAPIView.as_view(), name='my-permissions'),
    
    path('roles/', RoleListCreateAPIView.as_view(), name='role-list'),
    path('roles/<uuid:pk>/', RoleDetailAPIView.as_view(), name='role-detail'),
]
