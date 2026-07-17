from django.urls import path
from apps.ai_feedback.views import FeedbackListCreateAPIView

urlpatterns = [
    path('', FeedbackListCreateAPIView.as_view(), name='feedback-list-create'),
]
