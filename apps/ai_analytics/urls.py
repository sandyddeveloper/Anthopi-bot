from django.urls import path
from apps.ai_analytics.views import AnalyticsOverviewAPIView, AIEventListCreateAPIView

urlpatterns = [
    path('', AnalyticsOverviewAPIView.as_view(), name='analytics-overview'),
    path('events/', AIEventListCreateAPIView.as_view(), name='analytics-events'),
]
