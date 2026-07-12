from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from apps.scheduler.models import Schedule, ScheduleExecution
from apps.scheduler.serializers import ScheduleSerializer, ScheduleExecutionSerializer

@extend_schema(tags=['Workflow Scheduler'])
class ScheduleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ScheduleSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request or not self.request.user or self.request.user.is_anonymous:
            return Schedule.objects.none()
        org = self.request.organization or self.request.user.organization
        if self.request.user.is_superuser:
            return Schedule.objects.all().filter(is_deleted=False)
        return Schedule.objects.filter(workflow__organization=org, is_deleted=False).order_by('-created_at')

    def perform_create(self, serializer):
        from apps.scheduler.tasks import calculate_next_run
        # Calculate initial next run at create time
        schedule = serializer.save()
        schedule.next_run_at = calculate_next_run(schedule.schedule_type)
        schedule.save()


@extend_schema(tags=['Workflow Scheduler'])
class ScheduleExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ScheduleExecutionSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request or not self.request.user or self.request.user.is_anonymous:
            return ScheduleExecution.objects.none()
        org = self.request.organization or self.request.user.organization
        if self.request.user.is_superuser:
            return ScheduleExecution.objects.all()
        return ScheduleExecution.objects.filter(schedule__workflow__organization=org)
