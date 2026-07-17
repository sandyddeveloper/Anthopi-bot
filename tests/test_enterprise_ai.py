import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.organization.models import Organization
from apps.projects.models import Project
from apps.knowledge.models import File, Folder, KnowledgeCollection, KnowledgeItem
from apps.ai_agents.models import AgentCategory, Agent, AIProvider, AIModel, Prompt, PromptCategory
from apps.ai_memory.models import Memory
from apps.ai_rag.models import DocumentChunk
from apps.ai_approvals.models import ApprovalRequest
from apps.ai_orchestrator.models import AgentExecution

@pytest.mark.django_db
def test_enterprise_ai_intelligence_layer():
    client = APIClient()

    # 1. Setup Organization & User
    org = Organization.objects.create(name="DeepMind Enterprise", industry="AI")
    user = User.objects.create_user(email="chief_ai@deepmind.com", password="password123", full_name="Dr. Agent")
    user.organization = org
    user.save()

    # Authenticate
    login_url = reverse('token_obtain_pair')
    login_res = client.post(login_url, {"email": "chief_ai@deepmind.com", "password": "password123"})
    assert login_res.status_code == status.HTTP_200_OK
    access_token = login_res.json()['data']['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}', HTTP_X_ORGANIZATION_ID=str(org.id))

    # 2. Setup AI Models
    provider = AIProvider.objects.create(name="Anthropic", code="anthropic")
    model = AIModel.objects.create(
        provider=provider,
        name="Claude 3.5 Sonnet",
        code="claude-3-5-sonnet-latest",
        context_window=200000,
        input_token_cost=3.0,
        output_token_cost=15.0
    )

    category = AgentCategory.objects.create(name="Orchestrator Agent", code="orchestrator_agent", description="Task coordinator")
    agent = Agent.objects.create(
        organization=org,
        name="SuperOrch",
        category=category,
        system_prompt="You are a system coordinator.",
        temperature=0.4,
        model=model
    )

    project = Project.objects.create(organization=org, name="Intelligence Layer", code="AIL")

    # 3. Setup Knowledge Base (Files)
    folder = Folder.objects.create(organization=org, name="Security Manuals")
    file_obj = File.objects.create(
        organization=org,
        name="security_guideline.txt",
        folder=folder,
        file_size=2048,
        file_type="txt",
        visibility="organization"
    )

    collection = KnowledgeCollection.objects.create(organization=org, name="Compliance docs")
    collection.agents.add(agent)
    KnowledgeItem.objects.create(collection=collection, file=file_obj)

    # 4. Prompt Rollback Setup
    p_cat = PromptCategory.objects.create(name="SysPrompts", code="sys_prompts")
    prompt_obj = Prompt.objects.create(
        organization=org,
        category=p_cat,
        name="Main System",
        template_text="Version 1 System Text"
    )
    # Create versions
    from apps.ai_agents.models import PromptVersion
    PromptVersion.objects.create(prompt=prompt_obj, version_number=1, template_text="Version 1 System Text")
    PromptVersion.objects.create(prompt=prompt_obj, version_number=2, template_text="Version 2 System Text")

    # Rollback prompt
    rollback_url = reverse('prompt-rollback', kwargs={'pk': prompt_obj.id})
    rollback_res = client.post(rollback_url, {"version_number": 1})
    assert rollback_res.status_code == status.HTTP_200_OK
    assert rollback_res.json()['data']['template_text'] == "Version 1 System Text"

    # 5. RAG Pipeline verification
    chunk_url = reverse('rag-chunk-file')
    chunk_res = client.post(chunk_url, {"file_id": str(file_obj.id)})
    assert chunk_res.status_code == status.HTTP_200_OK
    assert DocumentChunk.objects.filter(file=file_obj).exists()

    rag_search_url = reverse('rag-search')
    search_res = client.post(rag_search_url, {"query": "security coding guideline", "agent_id": str(agent.id)})
    assert search_res.status_code == status.HTTP_200_OK
    search_data = search_res.json()['data']
    assert len(search_data) > 0
    assert "security_guideline.txt" in search_data[0]['file_name']

    # 6. Memory Merge verification
    mem1 = Memory.objects.create(organization=org, level='user', type='preference', content="User likes clean logs.", user=user)
    mem2 = Memory.objects.create(organization=org, level='user', type='preference', content="User likes colored outputs.", user=user)
    
    merge_url = reverse('memory-merge')
    merge_res = client.post(merge_url, {"primary_id": str(mem1.id), "secondary_id": str(mem2.id)})
    assert merge_res.status_code == status.HTTP_200_OK
    merge_data = merge_res.json()['data']
    assert "User likes clean logs." in merge_data['content']
    assert "User likes colored outputs." in merge_data['content']
    assert Memory.objects.filter(id=mem2.id, is_deleted=True).exists()

    # 7. Orchestration & Approval Flow
    # Attempting to execute prompt triggering email sender (governed tool)
    execute_url = reverse('orchestrator-execute')
    execute_res = client.post(execute_url, {
        "agent_id": str(agent.id),
        "prompt": "Please send email to the developers regarding security guidelines",
        "project_id": str(project.id)
    })
    
    assert execute_res.status_code == status.HTTP_200_OK
    execution_data = execute_res.json()['data']
    assert execution_data['status'] == "awaiting_approval"
    execution_id = execution_data['id']

    # Find the pending approval
    approval = ApprovalRequest.objects.get(execution_id=execution_id, status='pending')
    assert approval.tool_code == "email_sender"

    # Approve request
    approve_url = reverse('approval-approve', kwargs={'pk': approval.id})
    approve_res = client.post(approve_url, {"comments": "Approved by senior manager."})
    assert approve_res.status_code == status.HTTP_200_OK
    assert approve_res.json()['data']['status'] == "approved"

    # Resume/Continue Orchestrator Execution
    continue_url = reverse('orchestrator-continue', kwargs={'execution_id': execution_id})
    continue_res = client.post(continue_url)
    assert continue_res.status_code == status.HTTP_200_OK
    continue_data = continue_res.json()['data']
    assert continue_data['status'] == "completed"
    assert "email" in continue_data['response_text'].lower()

    # 8. Feedback verification
    feedback_url = reverse('feedback-list-create')
    # Find last message
    from apps.ai_chat.models import Message
    last_msg = Message.objects.filter(conversation__executions__id=execution_id, sender_type='assistant').first()
    assert last_msg is not None
    
    feedback_res = client.post(feedback_url, {
        "conversation": str(last_msg.conversation.id),
        "message": str(last_msg.id),
        "score": 1,
        "comment": "Perfect answer."
    })
    assert feedback_res.status_code == status.HTTP_201_CREATED

    # 9. Reports verification
    report_url = reverse('report-list-create')
    report_res = client.post(report_url, {
        "report_type": "cost",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31"
    })
    assert report_res.status_code == status.HTTP_201_CREATED
    assert report_res.json()['data']['data']['total_conversations'] > 0

    # 10. Analytics overview verification
    analytics_url = reverse('analytics-overview')
    analytics_res = client.get(analytics_url)
    assert analytics_res.status_code == status.HTTP_200_OK
    analytics_data = analytics_res.json()['data']
    assert analytics_data['token_usage']['total_tokens'] > 0
    assert analytics_data['feedback']['positive_count'] == 1
