from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.scheduler.views import ScheduleViewSet, ScheduleExecutionViewSet

router = DefaultRouter()
router.register('schedules', ScheduleViewSet, basename='schedule')
router.register('schedule-executions', ScheduleExecutionViewSet, basename='schedule-execution')

urlpatterns = [
    path('', include(router.urls)),
]
