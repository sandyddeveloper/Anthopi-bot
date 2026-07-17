from django.urls import path
from apps.ai_reasoning.views import ReasoningLogListAPIView

urlpatterns = [
    path('', ReasoningLogListAPIView.as_view(), name='reasoning-list'),
]
