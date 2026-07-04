from django.urls import path
from apps.users.views import UserRegisterAPIView, UserProfileAPIView, UserListAPIView, UserDetailAPIView

urlpatterns = [
    path('auth/register/', UserRegisterAPIView.as_view(), name='user_register'),
    path('users/profile/', UserProfileAPIView.as_view(), name='user_profile'),
    path('users/', UserListAPIView.as_view(), name='user-list'),
    path('users/<uuid:pk>/', UserDetailAPIView.as_view(), name='user-detail'),
]
