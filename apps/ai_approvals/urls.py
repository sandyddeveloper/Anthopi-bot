from django.urls import path
from apps.ai_approvals.views import ApprovalListCreateAPIView, ApprovalApproveAPIView, ApprovalRejectAPIView

urlpatterns = [
    path('', ApprovalListCreateAPIView.as_view(), name='approval-list-create'),
    path('<uuid:pk>/approve/', ApprovalApproveAPIView.as_view(), name='approval-approve'),
    path('<uuid:pk>/reject/', ApprovalApproveAPIView.as_view(), name='approval-reject'),
]
