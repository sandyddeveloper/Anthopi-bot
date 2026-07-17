from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from apps.ai_approvals.models import ApprovalRequest
from apps.ai_approvals.serializers import ApprovalRequestSerializer

from apps.common.utils import get_org_context

class ApprovalListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List approval requests", responses={200: ApprovalRequestSerializer(many=True)}, tags=["AI Governance"])
    def get(self, request):
        org = get_org_context(request)
        if request.user.is_superuser:
            requests_qs = ApprovalRequest.objects.filter(is_deleted=False)
        else:
            requests_qs = ApprovalRequest.objects.filter(organization=org, is_deleted=False)
            
        status_filter = request.query_params.get('status')
        if status_filter:
            requests_qs = requests_qs.filter(status=status_filter)
            
        serializer = ApprovalRequestSerializer(requests_qs, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Create a new approval request", request=ApprovalRequestSerializer, responses={201: ApprovalRequestSerializer}, tags=["AI Governance"])
    def post(self, request):
        org = get_org_context(request)
        serializer = ApprovalRequestSerializer(data=request.data)
        if serializer.is_valid():
            req = serializer.save(organization=org, requested_by=request.user, created_by=request.user)
            return Response(ApprovalRequestSerializer(req).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ApprovalApproveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Approve an action request", request=None, responses={200: ApprovalRequestSerializer}, tags=["AI Governance"])
    def post(self, request, pk):
        org = get_org_context(request)
        req = get_object_or_404(ApprovalRequest, id=pk, organization=org, is_deleted=False)
        
        req.status = 'approved'
        req.approved_by = request.user
        req.comments = request.data.get('comments', '')
        req.updated_by = request.user
        req.save()
        
        # If there is a corresponding execution, we can also resume it or continue it
        return Response(ApprovalRequestSerializer(req).data)

class ApprovalRejectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Reject an action request", request=None, responses={200: ApprovalRequestSerializer}, tags=["AI Governance"])
    def post(self, request, pk):
        org = get_org_context(request)
        req = get_object_or_404(ApprovalRequest, id=pk, organization=org, is_deleted=False)
        
        req.status = 'rejected'
        req.approved_by = request.user
        req.comments = request.data.get('comments', '')
        req.updated_by = request.user
        req.save()
        
        return Response(ApprovalRequestSerializer(req).data)
