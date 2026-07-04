from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

class HealthCheckAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Check service health status",
        description="Returns the active health status and timestamp of the server.",
        tags=["System"],
        responses={
            200: inline_serializer(
                name='HealthCheckResponse',
                fields={
                    'status': serializers.CharField(),
                    'timestamp': serializers.DateTimeField()
                }
            )
        }
    )
    def get(self, request):
        response = Response({
            "status": "healthy",
            "timestamp": timezone.now().isoformat()
        })
        response.custom_message = "Health check successful."
        return response
