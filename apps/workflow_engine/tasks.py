from celery import shared_task
import logging

logger = logging.getLogger('api')

@shared_task(name="apps.workflow_engine.tasks.execute_workflow_task")
def execute_workflow_task(execution_id):
    """
    Asynchronously runs a workflow execution using the WorkflowExecutionEngine.
    """
    logger.info(f"Celery task execute_workflow_task started for execution_id: {execution_id}")
    from apps.workflow_engine.engine import WorkflowExecutionEngine
    try:
        engine = WorkflowExecutionEngine(execution_id)
        engine.run()
    except Exception as e:
        logger.error(f"Error running execute_workflow_task: {str(e)}")
        raise e
