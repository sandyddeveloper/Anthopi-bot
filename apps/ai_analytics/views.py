from django.db.models import Sum, Avg, Count
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema

from apps.ai_chat.models import AIUsage
from apps.ai_tools.models import ToolExecution
from apps.ai_feedback.models import Feedback
from apps.ai_analytics.models import AIEvent
from apps.ai_analytics.serializers import AIEventSerializer

from apps.common.utils import get_org_context

class AnalyticsOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get AI metrics and overview analytics", responses={200: None}, tags=["AI Analytics"])
    def get(self, request):
        org = get_org_context(request)
        
        # 1. Base Usage aggregates
        usage_qs = AIUsage.objects.filter(organization=org)
        metrics = usage_qs.aggregate(
            total_prompt_tokens=Sum('prompt_tokens'),
            total_completion_tokens=Sum('completion_tokens'),
            total_tokens=Sum('total_tokens'),
            total_cost=Sum('cost'),
            avg_latency_ms=Avg('duration_ms')
        )
        
        # 2. Tool Executions metrics
        tools_qs = ToolExecution.objects.filter(user__organization=org)
        # Import models.Q explicitly or use simple query
        from django.db.models import Q
        total_runs = tools_qs.count()
        success_runs = tools_qs.filter(is_success=True).count()
        failed_runs = total_runs - success_runs
        
        # Tool usage breakdown
        tool_counts = tools_qs.values('tool_code').annotate(count=Count('id')).order_by('-count')
        
        # 3. Feedback aggregates
        feedback_qs = Feedback.objects.filter(user__organization=org)
        positive_fb = feedback_qs.filter(score__gt=0).count()
        negative_fb = feedback_qs.filter(score__lte=0).count()
        
        return Response({
            "token_usage": {
                "prompt_tokens": metrics.get('total_prompt_tokens') or 0,
                "completion_tokens": metrics.get('total_completion_tokens') or 0,
                "total_tokens": metrics.get('total_tokens') or 0
            },
            "cost_metrics": {
                "total_cost": float(metrics.get('total_cost') or 0.0)
            },
            "performance": {
                "avg_latency_ms": round(metrics.get('avg_latency_ms') or 0.0, 2)
            },
            "tool_metrics": {
                "total_executions": total_runs,
                "success_rate": round((success_runs / total_runs * 100) if total_runs > 0 else 100.0, 2),
                "failed_executions": failed_runs,
                "breakdown": {item['tool_code']: item['count'] for item in tool_counts}
            },
            "feedback": {
                "positive_count": positive_fb,
                "negative_count": negative_fb,
                "satisfaction_rate": round((positive_fb / (positive_fb + negative_fb) * 100) if (positive_fb + negative_fb) > 0 else 100.0, 2)
            }
        })

class AIEventListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List AI events", responses={200: AIEventSerializer(many=True)}, tags=["AI Analytics"])
    def get(self, request):
        org = get_org_context(request)
        if request.user.is_superuser:
            events = AIEvent.objects.filter(is_deleted=False)
        else:
            events = AIEvent.objects.filter(organization=org, is_deleted=False)
        serializer = AIEventSerializer(events, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Log a new AI event", request=AIEventSerializer, responses={201: AIEventSerializer}, tags=["AI Analytics"])
    def post(self, request):
        org = get_org_context(request)
        serializer = AIEventSerializer(data=request.data)
        if serializer.is_valid():
            event = serializer.save(organization=org, user=request.user, created_by=request.user)
            return Response(AIEventSerializer(event).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
