import pytest
import uuid
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.utils import timezone

from apps.users.models import User
from apps.organization.models import Organization
from apps.authentication.models import Role, Permission
from apps.workflow_engine.models import (
    WorkflowCategory, WorkflowFolder, WorkflowTag, Workflow, WorkflowVersion,
    WorkflowNode, NodePosition, NodeConnection, VariableScope, Variable,
    WorkflowExecution, NodeExecution, ExecutionLog, RetryPolicy, Webhook
)
from apps.workflow_engine.engine import WorkflowExecutionEngine

@pytest.fixture
def api_setup():
    org = Organization.objects.create(name="Automation Corp", industry="Software")
    
    owner = User.objects.create_user(
        email="owner@automation.com",
        password="securepass123",
        full_name="Workflow Owner",
        organization=org
    )
    
    category = WorkflowCategory.objects.create(name="Marketing", code="marketing")
    folder = WorkflowFolder.objects.create(organization=org, name="Onboarding Tasks")
    tag = WorkflowTag.objects.create(organization=org, name="Urgent", code="urgent")
    
    # Set up basic scopes
    global_scope, _ = VariableScope.objects.get_or_create(name="Global Scope", code="global")
    workflow_scope, _ = VariableScope.objects.get_or_create(name="Workflow Scope", code="workflow")
    
    # Set up global variable
    Variable.objects.create(
        organization=org,
        scope=global_scope,
        key="company_name",
        value="Automation Corp"
    )

    client = APIClient()
    client.force_authenticate(user=owner)
    
    return {
        "client": client,
        "org": org,
        "owner": owner,
        "category": category,
        "folder": folder,
        "tag": tag,
        "global_scope": global_scope,
        "workflow_scope": workflow_scope
    }

@pytest.mark.django_db
def test_workflow_crud_and_publishing(api_setup):
    client = api_setup["client"]
    org = api_setup["org"]
    category = api_setup["category"]
    
    # 1. Create Workflow via API
    url = reverse('workflow-list')
    data = {
        "name": "Auto Welcome Campaign",
        "description": "Sends greetings to new users",
        "category": str(category.id),
        "status": "draft"
    }
    res = client.post(url, data, format='json')
    assert res.status_code == status.HTTP_201_CREATED
    workflow_id = res.data['id']
    
    # 2. Add node via builder API
    builder_url = reverse('workflow-builder')
    builder_data = {
        "workflow_id": workflow_id,
        "nodes": [
            {
                "node_id": "trigger_1",
                "name": "Manual Run Button",
                "node_type": "trigger",
                "sub_type": "manual",
                "configuration": {"welcome_title": "Welcome!"},
                "position": {"position_x": 100.0, "position_y": 150.0}
            },
            {
                "node_id": "action_1",
                "name": "Send Announcement",
                "node_type": "action",
                "sub_type": "create_project",
                "configuration": {
                    "name": "Project for {{ input.welcome_title }}",
                    "description": "Created automatically by {{ global.company_name }}"
                },
                "position": {"position_x": 300.0, "position_y": 150.0}
            }
        ],
        "connections": [
            {
                "source_node_id": "trigger_1",
                "target_node_id": "action_1",
                "condition": {}
            }
        ]
    }
    
    res = client.post(builder_url, builder_data, format='json')
    assert res.status_code == status.HTTP_201_CREATED
    assert len(res.data['nodes']) == 2
    assert len(res.data['connections']) == 1
    
    # 3. Publish the workflow
    publish_url = reverse('workflow-publish', args=[workflow_id])
    res = client.post(publish_url)
    assert res.status_code == status.HTTP_201_CREATED
    assert res.data['is_published'] is True
    
    # Verify active version is updated
    workflow = Workflow.objects.get(id=workflow_id)
    assert workflow.active_version is not None
    assert workflow.active_version.version_number == 1

@pytest.mark.django_db
def test_execution_engine_variables_and_branching(api_setup):
    org = api_setup["org"]
    owner = api_setup["owner"]
    
    # Build a workflow with variables and branching (IF/ELSE)
    workflow = Workflow.objects.create(
        organization=org,
        owner=owner,
        name="Lead Assignment Routing",
        status="active"
    )
    
    version = WorkflowVersion.objects.create(
        workflow=workflow,
        version_number=1,
        is_published=True
    )
    
    # Trigger node
    trigger = WorkflowNode.objects.create(
        workflow_version=version,
        node_id="trigger_lead",
        name="Lead Received",
        node_type="trigger",
        sub_type="webhook",
        configuration={}
    )
    NodePosition.objects.create(node=trigger)
    
    # Condition Node (checks: input.score > 80)
    # The condition operator routes to either manager or general queue
    condition = WorkflowNode.objects.create(
        workflow_version=version,
        node_id="check_score",
        name="Score > 80?",
        node_type="condition",
        configuration={}
    )
    NodePosition.objects.create(node=condition)
    
    # Manager assignment node
    manager_act = WorkflowNode.objects.create(
        workflow_version=version,
        node_id="assign_manager",
        name="Assign Manager",
        node_type="action",
        sub_type="assign_task",
        configuration={"title": "High Priority Assign to Manager for {{ input.lead_name }}"}
    )
    NodePosition.objects.create(node=manager_act)

    # General queue assignment node
    general_act = WorkflowNode.objects.create(
        workflow_version=version,
        node_id="assign_general",
        name="Assign General Queue",
        node_type="action",
        sub_type="assign_task",
        configuration={"title": "General assignment queue for {{ input.lead_name }}"}
    )
    NodePosition.objects.create(node=general_act)

    # Connect trigger to condition
    NodeConnection.objects.create(
        workflow_version=version,
        source_node=trigger,
        target_node=condition,
        condition={}
    )
    
    # Connect condition to manager queue (Condition rule check: score > 80)
    NodeConnection.objects.create(
        workflow_version=version,
        source_node=condition,
        target_node=manager_act,
        condition={"field": "score", "operator": ">", "value": "80"}
    )

    # Connect condition to general queue (Condition rule check: score <= 80)
    NodeConnection.objects.create(
        workflow_version=version,
        source_node=condition,
        target_node=general_act,
        condition={"field": "score", "operator": "<=", "value": "80"}
    )
    
    workflow.active_version = version
    workflow.save()

    # 1. Run engine with score = 95
    execution = WorkflowExecution.objects.create(
        workflow=workflow,
        workflow_version=version,
        trigger_node=trigger,
        status='queued',
        input_data={"lead_name": "Alice Developer", "score": 95}
    )
    
    engine = WorkflowExecutionEngine(str(execution.id))
    engine.run()
    
    # Verify execution complete and assigned to manager node (Alice)
    execution.refresh_from_db()
    assert execution.status == 'completed'
    
    node_execs = NodeExecution.objects.filter(workflow_execution=execution)
    # Check that "assign_manager" executed but "assign_general" did NOT
    assert node_execs.filter(node__node_id="assign_manager").exists()
    assert node_execs.get(node__node_id="assign_manager").status == 'completed'
    assert not node_execs.filter(node__node_id="assign_general").exists()
    
    # Check resolved title
    manager_output = node_execs.get(node__node_id="assign_manager").input_data
    assert manager_output["title"] == "High Priority Assign to Manager for Alice Developer"

    # 2. Run engine with score = 40 (General queue route)
    execution2 = WorkflowExecution.objects.create(
        workflow=workflow,
        workflow_version=version,
        trigger_node=trigger,
        status='queued',
        input_data={"lead_name": "Bob Marketer", "score": 40}
    )
    
    engine2 = WorkflowExecutionEngine(str(execution2.id))
    engine2.run()
    
    execution2.refresh_from_db()
    assert execution2.status == 'completed'
    node_execs2 = NodeExecution.objects.filter(workflow_execution=execution2)
    assert not node_execs2.filter(node__node_id="assign_manager").exists()
    assert node_execs2.filter(node__node_id="assign_general").exists()
    assert node_execs2.get(node__node_id="assign_general").input_data["title"] == "General assignment queue for Bob Marketer"

@pytest.mark.django_db
def test_incoming_webhooks_and_logging(api_setup):
    client = api_setup["client"]
    org = api_setup["org"]
    owner = api_setup["owner"]
    
    workflow = Workflow.objects.create(
        organization=org,
        owner=owner,
        name="Webhook listener workflow",
        status="active"
    )
    
    version = WorkflowVersion.objects.create(
        workflow=workflow,
        version_number=1,
        is_published=True
    )
    
    trigger = WorkflowNode.objects.create(
        workflow_version=version,
        node_id="webhook_trigger",
        name="External HTTP Webhook",
        node_type="trigger",
        sub_type="webhook",
        configuration={}
    )
    NodePosition.objects.create(node=trigger)
    
    workflow.active_version = version
    workflow.save()
    
    # Create Webhook registration
    webhook = Webhook.objects.create(
        workflow=workflow,
        webhook_token="test_token_12345",
        is_active=True
    )
    
    # Post payload to webhook view
    webhook_url = reverse('webhook-incoming', args=[webhook.webhook_token])
    payload = {"event": "payment_failed", "amount": 250.0}
    
    # Call incoming webhook publicly (no authentication needed)
    public_client = APIClient()
    res = public_client.post(webhook_url, payload, format='json')
    
    assert res.status_code == status.HTTP_202_ACCEPTED
    assert 'execution_id' in res.data
    
    # Verify execution is created
    execution_id = res.data['execution_id']
    execution = WorkflowExecution.objects.get(id=execution_id)
    assert execution.workflow == workflow
    assert execution.input_data["body"]["event"] == "payment_failed"
