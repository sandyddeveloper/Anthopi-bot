from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from apps.ai_jobs.models import AIJob
from apps.ai_jobs.serializers import AIJobSerializer
from apps.ai_jobs.tasks import run_ai_job_task

from apps.common.utils import get_org_context

class AIJobListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List background AI jobs", responses={200: AIJobSerializer(many=True)}, tags=["AI Jobs"])
    def get(self, request):
        org = get_org_context(request)
        if request.user.is_superuser:
            jobs = AIJob.objects.filter(is_deleted=False)
        else:
            jobs = AIJob.objects.filter(organization=org, is_deleted=False)
        serializer = AIJobSerializer(jobs, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Submit a background AI job", request=AIJobSerializer, responses={201: AIJobSerializer}, tags=["AI Jobs"])
    def post(self, request):
        org = get_org_context(request)
        serializer = AIJobSerializer(data=request.data)
        if serializer.is_valid():
            # Set default total_items to 50 if not specified
            total_items = request.data.get('total_items', 50)
            job = serializer.save(
                organization=org,
                total_items=total_items,
                status='pending',
                created_by=request.user
            )
            
            # Start background Celery task
            task_res = run_ai_job_task.delay(str(job.id))
            job.celery_task_id = task_res.id
            job.save()
            
            return Response(AIJobSerializer(job).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AIJobDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get AI job status", responses={200: AIJobSerializer}, tags=["AI Jobs"])
    def get(self, request, pk):
        org = get_org_context(request)
        job = get_object_or_404(AIJob, id=pk, organization=org, is_deleted=False)
        return Response(AIJobSerializer(job).data)
