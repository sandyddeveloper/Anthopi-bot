import re
import logging
import httpx
from django.utils import timezone
from apps.workflow_engine.models import (
    Variable, WorkflowExecution, NodeExecution,
    ExecutionLog, RetryPolicy
)
from apps.projects.models import Project
from apps.users.models import User
from apps.ai_agents.models import Agent
from apps.ai_chat.models import Conversation
from apps.ai_orchestrator.orchestrator import AIOrchestrator
from apps.notifications.models import send_notification

logger = logging.getLogger('api')

class WorkflowExecutionEngine:
    def __init__(self, execution_id):
        self.execution_id = execution_id
        self.state = {
            "global": {},
            "input": {},
            "nodes": {},
            "variables": {}
        }

    def run(self):
        """
        Executes the workflow graph.
        """
        try:
            execution = WorkflowExecution.objects.get(id=self.execution_id)
        except WorkflowExecution.DoesNotExist:
            logger.error(f"Execution {self.execution_id} not found.")
            return

        if execution.status in ['completed', 'failed', 'cancelled']:
            return

        execution.status = 'running'
        execution.started_at = timezone.now()
        execution.save()

        # 1. Initialize variables state
        self._init_variables_state(execution)
        ExecutionLog.objects.create(
            workflow_execution=execution,
            level='info',
            message=f"Initialized workflow state. Variables count: {len(self.state['variables'])}"
        )

        try:
            # 2. Build graph/traverse
            version = execution.workflow_version
            # Find trigger nodes or the specified trigger_node
            start_nodes = []
            if execution.trigger_node:
                start_nodes = [execution.trigger_node]
            else:
                # Fallback: Find all trigger nodes in version
                start_nodes = list(version.nodes.filter(node_type='trigger'))

            if not start_nodes:
                # If no triggers defined, find any node that has no incoming connections
                connected_targets = set(version.connections.values_list('target_node_id', flat=True))
                start_nodes = list(version.nodes.exclude(id__in=connected_targets))

            if not start_nodes:
                raise ValueError("No entry nodes found in the workflow version definition.")

            # Queue of nodes to process (node, parent_node_execution)
            queue = [(node, None) for node in start_nodes]
            executed_nodes = set()

            while queue:
                current_node, parent_exec = queue.pop(0)

                # Avoid duplicate runs in same path cycle
                if current_node.id in executed_nodes:
                    continue

                # Run the node
                node_exec = self._execute_node(execution, current_node)
                executed_nodes.add(current_node.id)

                if node_exec.status == 'failed':
                    # Node failed, stop execution path and throw exception
                    raise ValueError(f"Node execution failed: {node_exec.error_message}")

                # Determine next nodes based on connections
                connections = version.connections.filter(source_node=current_node)
                for conn in connections:
                    # Evaluate connection condition if present
                    if self._evaluate_connection_condition(conn, node_exec):
                        queue.append((conn.target_node, node_exec))

            # Mark workflow execution complete
            execution.status = 'completed'
            execution.output_data = self.state["nodes"]
            ExecutionLog.objects.create(
                workflow_execution=execution,
                level='info',
                message="Workflow execution completed successfully."
            )

        except Exception as e:
            execution.status = 'failed'
            ExecutionLog.objects.create(
                workflow_execution=execution,
                level='error',
                message=f"Workflow execution failed: {str(e)}"
            )
            # Try to run retry policy
            self._handle_retry(execution, str(e))

        finally:
            execution.finished_at = timezone.now()
            if execution.started_at:
                delta = execution.finished_at - execution.started_at
                execution.duration_ms = int(delta.total_seconds() * 1000)
            execution.variables_state = self.state["variables"]
            execution.save()

    def _init_variables_state(self, execution):
        # Initial input data
        self.state["input"] = execution.input_data or {}
        
        # Load global variables
        global_vars = Variable.objects.filter(
            organization=execution.workflow.organization,
            scope__code='global'
        )
        for var in global_vars:
            self.state["global"][var.key] = var.value
            self.state["variables"][var.key] = var.value

        # Load workflow scope variables
        workflow_vars = Variable.objects.filter(
            organization=execution.workflow.organization,
            workflow=execution.workflow,
            scope__code='workflow'
        )
        for var in workflow_vars:
            self.state["variables"][var.key] = var.value

    def _resolve_template_vars(self, config):
        """
        Recursively searches and replaces variables in dictionary config structure using double curly braces format.
        """
        if isinstance(config, str):
            pattern = r'\{\{\s*([a-zA-Z0-9_\.]+)\s*\}\}'
            def replace_match(match):
                path = match.group(1).split('.')
                val = self.state
                try:
                    for key in path:
                        if isinstance(val, dict):
                            val = val.get(key)
                        else:
                            val = getattr(val, key, None)
                    return str(val) if val is not None else ""
                except Exception:
                    return ""
            return re.sub(pattern, replace_match, config)
        elif isinstance(config, dict):
            return {k: self._resolve_template_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._resolve_template_vars(item) for item in config]
        return config

    def _execute_node(self, execution, node):
        """
        Runs node step logic.
        """
        node_exec = NodeExecution.objects.create(
            workflow_execution=execution,
            node=node,
            status='running',
            started_at=timezone.now()
        )

        # Resolve inputs using state template rendering
        resolved_config = self._resolve_template_vars(node.configuration)
        node_exec.input_data = resolved_config
        node_exec.save()

        ExecutionLog.objects.create(
            workflow_execution=execution,
            node_execution=node_exec,
            level='info',
            message=f"Starting execution of node '{node.name}' ({node.node_type})"
        )

        try:
            output = {}
            if node.node_type == 'trigger':
                # Trigger passes inputs to outputs
                output = resolved_config

            elif node.node_type == 'action':
                output = self._run_action_node(execution, node.sub_type, resolved_config)

            elif node.node_type == 'ai_agent':
                output = self._run_ai_agent_node(execution, resolved_config)

            elif node.node_type == 'api_request':
                output = self._run_api_request_node(resolved_config)

            elif node.node_type == 'condition':
                # Condition nodes just pass their inputs to output
                output = self._run_condition_node(resolved_config)

            else:
                # Fallback default
                output = {"status": "ok"}

            node_exec.status = 'completed'
            node_exec.output_data = output
            self.state["nodes"][node.node_id] = output

            # Also update variables if node outputs are captured
            self.state["variables"][node.node_id] = output

            ExecutionLog.objects.create(
                workflow_execution=execution,
                node_execution=node_exec,
                level='info',
                message=f"Node '{node.name}' completed execution."
            )

        except Exception as e:
            node_exec.status = 'failed'
            node_exec.error_message = str(e)
            ExecutionLog.objects.create(
                workflow_execution=execution,
                node_execution=node_exec,
                level='error',
                message=f"Node '{node.name}' failed: {str(e)}"
            )

        finally:
            node_exec.finished_at = timezone.now()
            if node_exec.started_at:
                delta = node_exec.finished_at - node_exec.started_at
                node_exec.duration_ms = int(delta.total_seconds() * 1000)
            node_exec.save()

        return node_exec

    def _run_action_node(self, execution, sub_type, config):
        """
        Executes internal platform actions.
        """
        # Create Project Action
        if sub_type == 'create_project':
            proj = Project.objects.create(
                organization=execution.workflow.organization,
                name=config.get('name', 'New Automated Project'),
                description=config.get('description', ''),
                status=config.get('status', 'planning'),
                priority=config.get('priority', 'medium'),
                created_by=execution.workflow.owner
            )
            return {"project_id": str(proj.id), "name": proj.name}

        # Update Employee Profile Action
        elif sub_type == 'update_employee':
            from apps.users.models import EmployeeProfile
            profile_id = config.get('employee_profile_id')
            profile = EmployeeProfile.objects.get(id=profile_id)
            if 'work_location' in config:
                profile.work_location = config['work_location']
            if 'skills' in config:
                profile.skills = config['skills']
            profile.save()
            return {"employee_id": str(profile.id), "status": "updated"}

        # Send Email / Notification Action
        elif sub_type == 'send_email' or sub_type == 'create_notification':
            recipient_id = config.get('recipient_id')
            title = config.get('title', 'Workflow Notification')
            message = config.get('message', '')
            
            # Send standard Notification database entry
            if recipient_id:
                recipient = User.objects.get(id=recipient_id)
                notif = send_notification(
                    recipient=recipient,
                    sender=execution.workflow.owner,
                    title=title,
                    message=message,
                    event_type='workflow_event'
                )
                return {"notification_id": str(notif.id) if notif else None, "status": "sent"}
            return {"status": "skipped", "reason": "No recipient_id provided"}

        # Upload File Action
        elif sub_type == 'upload_file':
            from apps.knowledge.models import File
            # Mock or register uploaded file in DB
            new_file = File.objects.create(
                organization=execution.workflow.organization,
                name=config.get('name', 'workflow_file.txt'),
                file_type=config.get('file_type', 'text/plain'),
                file_size=config.get('file_size', 0),
                created_by=execution.workflow.owner
            )
            return {"file_id": str(new_file.id), "name": new_file.name}

        # Run safe raw query mock/interpreter
        elif sub_type == 'run_sql':
            # Safe SQL Mock response containing execution details
            sql = config.get('sql', '')
            return {"query": sql, "rows_affected": 0, "status": "mock_executed"}

        # Generate custom execution stats report
        elif sub_type == 'generate_report':
            title = config.get('title', 'System Report')
            report_text = f"--- {title} ---\nGenerated by Anthopi-bot Automation Engine.\nWorkflow: {execution.workflow.name}\nTimestamp: {timezone.now()}"
            return {"report_text": report_text, "status": "generated"}

        # Assign Task Action
        elif sub_type == 'assign_task':
            title = config.get('title', 'Automated Task')
            description = config.get('description', '')
            return {"task_title": title, "status": "assigned"}

        raise ValueError(f"Action subtype '{sub_type}' not supported.")

    def _run_ai_agent_node(self, execution, config):
        """
        Executes internal AI orchestrator with loaded agent parameters.
        """
        agent_id = config.get('agent_id')
        prompt_text = config.get('prompt', 'Hello Agent')

        if not agent_id:
            raise ValueError("AI Agent Node configuration must include 'agent_id'.")

        agent = Agent.objects.get(id=agent_id)
        
        # Build conversational context using existing AIOrchestrator and temporary Conversation
        conversation = Conversation.objects.create(
            organization=execution.workflow.organization,
            agent=agent,
            project=execution.workflow.project,
            title=f"Workflow Run Execution: {execution.id}",
            created_by=execution.workflow.owner
        )

        orchestrator = AIOrchestrator(conversation_id=conversation.id, user=execution.workflow.owner)
        assistant_message = orchestrator.call_llm(prompt_text)

        return {
            "conversation_id": str(conversation.id),
            "response": assistant_message.content,
            "prompt_tokens": assistant_message.prompt_tokens,
            "completion_tokens": assistant_message.completion_tokens,
            "cost": float(assistant_message.cost)
        }

    def _run_api_request_node(self, config):
        """
        Performs external HTTP REST request.
        """
        url = config.get('url')
        method = config.get('method', 'GET').upper()
        headers = config.get('headers', {})
        body = config.get('body', {})
        auth_type = config.get('auth_type') # e.g. bearer, basic

        if not url:
            raise ValueError("API Node configuration must include 'url'.")

        # Inject auth headers if required
        if auth_type == 'bearer':
            token = config.get('auth_token')
            if token:
                headers['Authorization'] = f"Bearer {token}"

        # Make HTTP request using httpx
        with httpx.Client(timeout=15.0) as client:
            if method == 'GET':
                res = client.get(url, headers=headers)
            elif method == 'POST':
                res = client.post(url, headers=headers, json=body)
            elif method == 'PUT':
                res = client.put(url, headers=headers, json=body)
            elif method == 'PATCH':
                res = client.patch(url, headers=headers, json=body)
            elif method == 'DELETE':
                res = client.delete(url, headers=headers)
            else:
                raise ValueError(f"HTTP method '{method}' not supported.")

        # Try parsing JSON response, fallback to text
        try:
            response_data = res.json()
        except ValueError:
            response_data = res.text

        return {
            "status_code": res.status_code,
            "response": response_data
        }

    def _run_condition_node(self, config):
        """
        Parses condition configurations. Returns matched input state.
        """
        return config

    def _evaluate_connection_condition(self, connection, prev_node_exec):
        """
        Evaluates condition expression on transitions.
        """
        cond_rule = connection.condition
        if not cond_rule:
            return True # unconditional transition

        # Example rule: {"field": "status_code", "operator": "equals", "value": 200}
        field = cond_rule.get('field')
        operator = cond_rule.get('operator', 'equals')
        target_val = cond_rule.get('value')

        if not field:
            return True

        # Fetch field value from previous node execution output or fallback to context variables
        output = prev_node_exec.output_data or {}
        actual_val = output.get(field)
        if actual_val is None:
            actual_val = self.state["variables"].get(field)
        if actual_val is None:
            actual_val = self.state["input"].get(field)
        if actual_val is None and field and '{{' in str(field):
            actual_val = self._resolve_template_vars(field)

        # Basic type resolution/comparisons
        try:
            if operator == 'equals' or operator == '==':
                return str(actual_val) == str(target_val)
            elif operator == 'not_equals' or operator == '!=':
                return str(actual_val) != str(target_val)
            elif operator == 'greater_than' or operator == '>':
                return float(actual_val) > float(target_val)
            elif operator == 'greater_than_or_equal' or operator == '>=':
                return float(actual_val) >= float(target_val)
            elif operator == 'less_than' or operator == '<':
                return float(actual_val) < float(target_val)
            elif operator == 'less_than_or_equal' or operator == '<=':
                return float(actual_val) <= float(target_val)
            elif operator == 'contains':
                return str(target_val) in str(actual_val)
            elif operator == 'in':
                return actual_val in target_val
        except Exception as e:
            logger.error(f"Error evaluating rule: {str(e)}")
            return False

        return False

    def _handle_retry(self, execution, error_msg):
        """
        Triggers exponential backoff or immediate workflow retry task if retry policy is configured.
        """
        policy = RetryPolicy.objects.filter(workflow=execution.workflow).first()
        if not policy:
            return

        # Check existing retry counts in execution log
        retry_count = execution.logs.filter(message__contains="Retry Started").count()
        if retry_count >= policy.max_retries:
            ExecutionLog.objects.create(
                workflow_execution=execution,
                level='warning',
                message="Workflow execution failed and exceeded maximum retries policy limits."
            )
            return

        # Trigger background Celery Task retry with delay
        from apps.workflow_engine.tasks import execute_workflow_task
        delay = policy.delay_seconds
        if policy.backoff_type == 'exponential':
            delay = policy.delay_seconds * (2 ** retry_count)

        # Log retry info
        ExecutionLog.objects.create(
            workflow_execution=execution,
            level='warning',
            message=f"Retry Started: Attempt {retry_count + 1}/{policy.max_retries}. Scheduling execution in {delay} seconds."
        )

        # Schedule async retry task
        execute_workflow_task.apply_async(
            args=[str(execution.id)],
            countdown=delay
        )
