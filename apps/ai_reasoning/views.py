from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from apps.ai_reasoning.models import ReasoningLog
from apps.ai_reasoning.serializers import ReasoningLogSerializer

class ReasoningLogListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List reasoning logs (internal chain of thought)", responses={200: ReasoningLogSerializer(many=True)}, tags=["AI Reasoning"])
    def get(self, request):
        queryset = ReasoningLog.objects.filter(is_deleted=False)
        execution_id = request.query_params.get('execution_id')
        if execution_id:
            queryset = queryset.filter(execution_id=execution_id)
            
        serializer = ReasoningLogSerializer(queryset, many=True)
        return Response(serializer.data)
