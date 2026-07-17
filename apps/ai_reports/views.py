from django.db.models import Sum, Avg, Count
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from apps.ai_chat.models import AIUsage
from apps.ai_reports.models import AIReport
from apps.ai_reports.serializers import AIReportSerializer

from apps.common.utils import get_org_context

class ReportListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List generated reports", responses={200: AIReportSerializer(many=True)}, tags=["AI Reports"])
    def get(self, request):
        org = get_org_context(request)
        if request.user.is_superuser:
            reports = AIReport.objects.filter(is_deleted=False)
        else:
            reports = AIReport.objects.filter(organization=org, is_deleted=False)
        serializer = AIReportSerializer(reports, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Generate an AI usage or cost report", request=AIReportSerializer, responses={201: AIReportSerializer}, tags=["AI Reports"])
    def post(self, request):
        org = get_org_context(request)
        serializer = AIReportSerializer(data=request.data)
        if serializer.is_valid():
            start_date = serializer.validated_data['start_date']
            end_date = serializer.validated_data['end_date']
            report_type = serializer.validated_data['report_type']
            
            # Fetch actual metrics
            usage_qs = AIUsage.objects.filter(
                organization=org,
                date__gte=start_date,
                date__lte=end_date
            )
            aggregates = usage_qs.aggregate(
                total_cost=Sum('cost'),
                total_tokens=Sum('total_tokens'),
                runs_count=Count('id'),
                avg_latency=Avg('duration_ms')
            )
            
            # Formulate report metrics payload
            report_data = {
                "summary": f"Generated {report_type} report for organization {org.name} from {start_date} to {end_date}.",
                "total_cost": float(aggregates.get('total_cost') or 0.0),
                "total_tokens": aggregates.get('total_tokens') or 0,
                "total_conversations": aggregates.get('runs_count') or 0,
                "average_latency_ms": round(aggregates.get('avg_latency') or 0.0, 2),
                "status": "completed"
            }
            
            report = serializer.save(
                organization=org,
                data=report_data,
                generated_by=request.user,
                created_by=request.user
            )
            return Response(AIReportSerializer(report).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ReportDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Retrieve detailed report content", responses={200: AIReportSerializer}, tags=["AI Reports"])
    def get(self, request, pk):
        org = get_org_context(request)
        report = get_object_or_404(AIReport, id=pk, organization=org, is_deleted=False)
        return Response(AIReportSerializer(report).data)
