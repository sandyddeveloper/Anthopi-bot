import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.organization.models import Organization, Department
from apps.projects.models import Project
from apps.knowledge.models import File, Folder, KnowledgeCollection, KnowledgeItem
from apps.ai_agents.models import AgentCategory, Agent, AIProvider, AIModel, Tool, AgentTool
from apps.ai_chat.models import Conversation, Message, MemoryCategory, Memory, AIUsage, AIActivityLog
from apps.ai_orchestrator.orchestrator import AIOrchestrator

@pytest.mark.django_db
def test_ai_platform_foundation_flow():
    client = APIClient()

    # 1. Setup Base Organization and User
    org = Organization.objects.create(name="Anthopi Corp", industry="Tech")
    user = User.objects.create_user(email="test_dev@anthopi.com", password="password123", full_name="Johnny Dev")
    user.organization = org
    user.save()

    # Authenticate user
    login_url = reverse('token_obtain_pair')
    login_response = client.post(login_url, {"email": "test_dev@anthopi.com", "password": "password123"})
    assert login_response.status_code == status.HTTP_200_OK
    access_token = login_response.json()['data']['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}', HTTP_X_ORGANIZATION_ID=str(org.id))

    # 2. Setup AI Models and Providers
    provider = AIProvider.objects.create(name="Anthropic", code="anthropic")
    model = AIModel.objects.create(
        provider=provider,
        name="Claude 3.5 Sonnet",
        code="claude-3-5-sonnet-latest",
        context_window=200000,
        input_token_cost=3.0,
        output_token_cost=15.0
    )

    # 3. Create Agent Category and Agent via API
    category = AgentCategory.objects.create(name="Developer AI", code="developer_ai", description="Code assistance agent")
    
    agent_create_url = reverse('agent-list-create')
    agent_response = client.post(agent_create_url, {
        "name": "DevBot",
        "description": "Auto developer assistant",
        "category": str(category.id),
        "system_prompt": "You are a professional Python developer. Adhere to PEP-8 guidelines.",
        "temperature": 0.5,
        "model": str(model.id)
    })
    
    assert agent_response.status_code == status.HTTP_201_CREATED
    agent_data = agent_response.json()['data']
    agent_id = agent_data['id']
    assert agent_data['name'] == "DevBot"
    assert agent_data['visibility'] == "organization"

    # 4. Duplicate Agent API
    duplicate_url = reverse('agent-duplicate', kwargs={'pk': agent_id})
    dup_response = client.post(duplicate_url)
    assert dup_response.status_code == status.HTTP_201_CREATED
    assert dup_response.json()['data']['name'] == "DevBot (Copy)"

    # 5. Create a project
    project = Project.objects.create(organization=org, name="Anthopi Web Backend", code="AWB")

    # 6. Start Conversation via API
    conv_create_url = reverse('conversation-list-create')
    conv_response = client.post(conv_create_url, {
        "agent": agent_id,
        "project": str(project.id),
        "title": "Backend Refactoring"
    })
    assert conv_response.status_code == status.HTTP_201_CREATED
    conv_id = conv_response.json()['data']['id']
    assert conv_response.json()['data']['title'] == "Backend Refactoring"

    # 7. Add Knowledge Collection and File mapping
    folder = Folder.objects.create(organization=org, name="Docs")
    file_obj = File.objects.create(
        organization=org,
        name="coding_standard.txt",
        folder=folder,
        file_size=1024,
        file_type="txt",
        visibility="organization"
    )

    collection = KnowledgeCollection.objects.create(organization=org, name="Engineering Standards")
    collection.agents.add(Agent.objects.get(id=agent_id))
    KnowledgeItem.objects.create(collection=collection, file=file_obj)

    # 8. Add Memory Category and Fact context
    mem_cat = MemoryCategory.objects.create(name="User Preferences", code="user_preferences")
    Memory.objects.create(
        organization=org,
        category=mem_cat,
        user=user,
        content="User prefers clear modular code with type hints."
    )

    # 9. Test Context Builder from Orchestrator
    orchestrator = AIOrchestrator(conv_id, user)
    system_context = orchestrator.build_context()
    
    assert "You are a professional Python developer." in system_context
    assert "Anthopi Web Backend" in system_context
    assert "coding_standard.txt" in system_context
    assert "User prefers clear modular code with type hints." in system_context
    assert "Anthopi Corp" in system_context

    # 10. Post a message to continue conversation and trigger mock LLM Orchestration
    message_url = reverse('message-list-create', kwargs={'conversation_id': conv_id})
    message_response = client.post(message_url, {
        "content": "Can you review our project guidelines?"
    })
    assert message_response.status_code == status.HTTP_201_CREATED
    res_data = message_response.json()['data']
    assert "user_message" in res_data
    assert "assistant_message" in res_data
    assert res_data['user_message']['content'] == "Can you review our project guidelines?"
    assert "Johnny Dev" in res_data['user_message']['sender_details']['full_name']
    assert "Hello! I am DevBot, your Developer AI" in res_data['assistant_message']['content']

    # Verify Usage Logs & Activity
    assert AIUsage.objects.filter(organization=org, agent_id=agent_id).exists()
    assert AIActivityLog.objects.filter(organization=org, action="ai_response_generated").exists()
