from django.urls import path
from apps.ai_reports.views import ReportListCreateAPIView, ReportDetailAPIView

urlpatterns = [
    path('', ReportListCreateAPIView.as_view(), name='report-list-create'),
    path('<uuid:pk>/', ReportDetailAPIView.as_view(), name='report-detail'),
]
