import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.projects.models import Project
from apps.users.models import EmployeeProfile
from apps.ai_agents.models import Agent
from apps.knowledge.models import File
from apps.workflow_engine.models import Workflow, WorkflowExecution
from apps.workflow_engine.tasks import execute_workflow_task

logger = logging.getLogger('api')

def trigger_workflows_for_event(event_type, input_data, organization):
    """
    Finds and triggers active workflows configured for a specific internal platform event.
    """
    if not organization:
        return

    # Find active workflows in the organization
    workflows = Workflow.objects.filter(
        organization=organization,
        status='active',
        active_version__isnull=False
    )

    for workflow in workflows:
        version = workflow.active_version
        # Match nodes of type 'trigger' and sub_type matching event name
        trigger_nodes = version.nodes.filter(
            node_type='trigger',
            sub_type=event_type
        )
        for node in trigger_nodes:
            try:
                execution = WorkflowExecution.objects.create(
                    workflow=workflow,
                    workflow_version=version,
                    trigger_node=node,
                    status='queued',
                    input_data=input_data,
                    created_by=workflow.owner
                )
                execute_workflow_task.delay(str(execution.id))
                logger.info(f"Triggered workflow execution {execution.id} for event {event_type}")
            except Exception as e:
                logger.error(f"Error launching event-based workflow {workflow.id}: {str(e)}")


@receiver(post_save, sender=EmployeeProfile)
def handle_employee_profile_created(sender, instance, created, **kwargs):
    if created:
        input_data = {
            "employee_id": str(instance.id),
            "email": instance.user.email,
            "full_name": instance.user.full_name,
            "work_location": instance.work_location,
            "skills": instance.skills,
            "date_of_joining": str(instance.date_of_joining) if instance.date_of_joining else ""
        }
        trigger_workflows_for_event('employee_created', input_data, instance.organization)


@receiver(post_save, sender=Project)
def handle_project_updated(sender, instance, **kwargs):
    # Only fire when project status is marked as 'completed'
    if instance.status == 'completed':
        input_data = {
            "project_id": str(instance.id),
            "name": instance.name,
            "code": instance.code,
            "status": instance.status,
            "priority": instance.priority
        }
        trigger_workflows_for_event('project_completed', input_data, instance.organization)


@receiver(post_save, sender=Agent)
def handle_agent_created(sender, instance, created, **kwargs):
    if created:
        input_data = {
            "agent_id": str(instance.id),
            "name": instance.name,
            "description": instance.description,
            "visibility": instance.visibility
        }
        trigger_workflows_for_event('agent_created', input_data, instance.organization)


@receiver(post_save, sender=File)
def handle_file_uploaded(sender, instance, created, **kwargs):
    if created:
        input_data = {
            "file_id": str(instance.id),
            "name": instance.name,
            "file_type": instance.file_type,
            "file_size": instance.file_size
        }
        trigger_workflows_for_event('file_uploaded', input_data, instance.organization)
        trigger_workflows_for_event('knowledge_uploaded', input_data, instance.organization)
