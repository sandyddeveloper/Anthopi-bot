from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from apps.ai_planner.models import ExecutionPlan
from apps.ai_planner.serializers import ExecutionPlanSerializer

from apps.common.utils import get_org_context

class ExecutionPlanListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List generated execution plans", responses={200: ExecutionPlanSerializer(many=True)}, tags=["AI Planner"])
    def get(self, request):
        org = get_org_context(request)
        if request.user.is_superuser:
            plans = ExecutionPlan.objects.filter(is_deleted=False)
        else:
            plans = ExecutionPlan.objects.filter(organization=org, is_deleted=False)
            
        conv_id = request.query_params.get('conversation')
        if conv_id:
            plans = plans.filter(conversation_id=conv_id)
            
        serializer = ExecutionPlanSerializer(plans, many=True)
        return Response(serializer.data)

class ExecutionPlanDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Retrieve execution plan details", responses={200: ExecutionPlanSerializer}, tags=["AI Planner"])
    def get(self, request, pk):
        org = get_org_context(request)
        plan = get_object_or_404(ExecutionPlan, id=pk, organization=org, is_deleted=False)
        return Response(ExecutionPlanSerializer(plan).data)
