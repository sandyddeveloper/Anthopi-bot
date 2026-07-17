from django.urls import path
from apps.ai_jobs.views import AIJobListCreateAPIView, AIJobDetailAPIView

urlpatterns = [
    path('', AIJobListCreateAPIView.as_view(), name='job-list-create'),
    path('<uuid:pk>/', AIJobDetailAPIView.as_view(), name='job-detail'),
]
