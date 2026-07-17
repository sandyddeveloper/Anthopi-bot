from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema

from apps.ai_feedback.models import Feedback
from apps.ai_feedback.serializers import FeedbackSerializer

from apps.common.utils import get_org_context

class FeedbackListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List message feedbacks", responses={200: FeedbackSerializer(many=True)}, tags=["AI Feedback"])
    def get(self, request):
        org = get_org_context(request)
        if request.user.is_superuser:
            feedbacks = Feedback.objects.filter(is_deleted=False)
        else:
            feedbacks = Feedback.objects.filter(conversation__organization=org, is_deleted=False)
        serializer = FeedbackSerializer(feedbacks, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Submit feedback on a message response", request=FeedbackSerializer, responses={201: FeedbackSerializer}, tags=["AI Feedback"])
    def post(self, request):
        serializer = FeedbackSerializer(data=request.data)
        if serializer.is_valid():
            feedback = serializer.save(user=request.user, created_by=request.user)
            return Response(FeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
