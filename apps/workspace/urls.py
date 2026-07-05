from django.urls import path
from apps.workspace.views import DashboardAPIView, DashboardWidgetsAPIView, GlobalSearchAPIView

urlpatterns = [
    path('dashboard/', DashboardAPIView.as_view(), name='dashboard-stats'),
    path('dashboard/widgets/', DashboardWidgetsAPIView.as_view(), name='dashboard-widgets'),
    path('search/', GlobalSearchAPIView.as_view(), name='global-search'),
]
