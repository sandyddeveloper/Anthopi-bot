from django.urls import path
from apps.ai_planner.views import ExecutionPlanListAPIView, ExecutionPlanDetailAPIView

urlpatterns = [
    path('', ExecutionPlanListAPIView.as_view(), name='plan-list'),
    path('<uuid:pk>/', ExecutionPlanDetailAPIView.as_view(), name='plan-detail'),
]
