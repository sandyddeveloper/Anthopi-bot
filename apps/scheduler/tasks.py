import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from apps.scheduler.models import Schedule, ScheduleExecution
from apps.workflow_engine.models import WorkflowExecution, WorkflowVersion
from apps.workflow_engine.tasks import execute_workflow_task

logger = logging.getLogger('api')

def calculate_next_run(schedule_type, current_time=None):
    if not current_time:
        current_time = timezone.now()
    if schedule_type == 'hourly':
        return current_time + timedelta(hours=1)
    elif schedule_type == 'daily':
        return current_time + timedelta(days=1)
    elif schedule_type == 'weekly':
        return current_time + timedelta(weeks=1)
    elif schedule_type == 'monthly':
        return current_time + timedelta(days=30)
    # cron fallback or once
    return None

@shared_task(name="apps.scheduler.tasks.process_scheduled_workflows")
def process_scheduled_workflows():
    """
    Heartbeat Celery task that processes due workflow schedules.
    """
    logger.info("Scanning for scheduled workflow triggers.")
    now = timezone.now()
    
    # Select active schedules where next_run_at is due
    due_schedules = Schedule.objects.filter(
        is_active=True,
        next_run_at__lte=now
    ).filter(
        Q(end_time__isnull=True) | Q(end_time__gt=now)
    )

    for schedule in due_schedules:
        workflow = schedule.workflow
        active_version = workflow.active_version
        
        if not active_version:
            logger.warning(f"Workflow schedule '{schedule.id}' skipped because no active version is published.")
            # Record failed execution log
            ScheduleExecution.objects.create(
                schedule=schedule,
                status='failed',
                run_at=now
            )
            continue

        try:
            # Create execution
            execution = WorkflowExecution.objects.create(
                workflow=workflow,
                workflow_version=active_version,
                status='queued',
                input_data={
                    "trigger_type": "schedule",
                    "scheduled_run_time": str(now),
                    "schedule_id": str(schedule.id)
                }
            )

            # Record schedule trigger logs
            ScheduleExecution.objects.create(
                schedule=schedule,
                workflow_execution=execution,
                status='success',
                run_at=now
            )

            # Schedule execution engine
            execute_workflow_task.delay(str(execution.id))

            # Update schedule run times
            schedule.last_run_at = now
            schedule.next_run_at = calculate_next_run(schedule.schedule_type, now)
            if schedule.schedule_type == 'once':
                schedule.is_active = False
            schedule.save()

            logger.info(f"Triggered workflow execution {execution.id} for schedule {schedule.id}")

        except Exception as e:
            logger.error(f"Error triggering schedule run: {str(e)}")
            ScheduleExecution.objects.create(
                schedule=schedule,
                status='failed',
                run_at=now
            )
