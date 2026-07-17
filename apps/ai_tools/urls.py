from django.urls import path
from apps.ai_tools.views import ToolListAPIView, ExecuteToolAPIView

urlpatterns = [
    path('', ToolListAPIView.as_view(), name='tool-list'),
    path('execute/', ExecuteToolAPIView.as_view(), name='tool-execute'),
]
