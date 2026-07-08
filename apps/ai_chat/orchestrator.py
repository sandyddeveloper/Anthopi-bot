import time
import requests
from django.utils import timezone
from apps.ai_agents.models import Agent, AIModel, AIProvider, OrganizationModel
from apps.ai_chat.models import Conversation, Message, Memory, AIUsage, AIActivityLog
from apps.knowledge.models import File

class AIOrchestrator:
    def __init__(self, conversation_id, user=None):
        self.conversation = Conversation.objects.get(id=conversation_id)
        self.agent = self.conversation.agent
        self.organization = self.conversation.organization
        self.project = self.conversation.project
        self.user = user

    def build_context(self):
        """
        Combines Agent Prompt, Project Context, Knowledge, and Memory into a system context.
        """
        context_parts = []

        # 1. Base Agent System Prompt
        if self.agent and self.agent.system_prompt:
            context_parts.append(f"Agent System Instructions:\n{self.agent.system_prompt}")

        # 2. Project Context
        if self.project:
            context_parts.append(
                f"Project Context:\n"
                f"- Name: {self.project.name}\n"
                f"- Description: {self.project.description or 'No description'}\n"
                f"- Status: {self.project.status}"
            )

        # 3. Knowledge Base context
        if self.agent:
            collections = self.agent.knowledge_collections.all()
            if collections.exists():
                context_parts.append("Available Knowledge Base Files:")
                for col in collections:
                    for item in col.items.all():
                        context_parts.append(
                            f"- File: {item.file.name} ({item.file.file_type}) | Size: {item.file.file_size} bytes"
                        )

        # 4. Memory context
        memories = Memory.objects.filter(
            organization=self.organization,
            status='active'
        )
        # Filter memories relevant to user, agent, or project
        user_memories = memories.filter(user=self.user) if self.user else memories.none()
        agent_memories = memories.filter(agent=self.agent) if self.agent else memories.none()
        project_memories = memories.filter(project=self.project) if self.project else memories.none()
        
        combined_memories = (user_memories | agent_memories | project_memories).distinct()
        if combined_memories.exists():
            context_parts.append("Memory (Retrieved Facts):")
            for mem in combined_memories:
                context_parts.append(f"- Remembered: {mem.content}")

        # 5. Organization Details
        if self.organization:
            context_parts.append(
                f"Organization context:\n"
                f"- Name: {self.organization.name}\n"
                f"- Industry: {self.organization.industry or 'Unknown'}"
            )

        return "\n\n".join(context_parts)

    def select_provider_and_key(self):
        """
        Determines the LLM model, provider, and API key to use.
        """
        if not self.agent or not self.agent.model:
            # Get default model if configured in organization settings
            settings = getattr(self.organization, 'ai_settings', None)
            model = settings.default_model if settings else None
            if not model:
                # Return a default fallback model structure
                return None, None, None
        else:
            model = self.agent.model

        provider = model.provider
        
        # Check for Org-specific API Key override
        org_model = OrganizationModel.objects.filter(
            organization=self.organization,
            provider=provider,
            is_enabled=True
        ).first()

        api_key = org_model.api_key if org_model else provider.api_key
        return model, provider, api_key

    def call_llm(self, user_message_text):
        """
        Executes the main orchestration pipeline:
        1. Build context
        2. Resolve model/provider
        3. Make call (mock or live)
        4. Track token usage & logs
        """
        start_time = time.time()
        
        # Construct dynamic context
        system_context = self.build_context()
        
        # Resolve credentials
        model, provider, api_key = self.select_provider_and_key()
        
        # Assemble message history
        history = []
        past_messages = self.conversation.messages.order_by('created_at')[:15]
        for msg in past_messages:
            history.append({
                "role": "user" if msg.sender_type == "user" else "assistant",
                "content": msg.content
            })
        
        # Append latest user prompt
        history.append({"role": "user", "content": user_message_text})

        response_text = ""
        prompt_tokens = 0
        completion_tokens = 0
        cost = 0.0

        if not api_key or not model:
            # Graceful fallback: Mock response logic
            response_text = self._generate_mock_response(user_message_text, system_context)
            # Estimate tokens: ~4 chars per token
            prompt_tokens = len(system_context + user_message_text) // 4
            completion_tokens = len(response_text) // 4
        else:
            # Execute actual provider calls using requests
            try:
                if provider.code == 'openai':
                    response_text, prompt_tokens, completion_tokens = self._call_openai(
                        model.code, api_key, system_context, history
                    )
                elif provider.code == 'anthropic':
                    response_text, prompt_tokens, completion_tokens = self._call_anthropic(
                        model.code, api_key, system_context, history
                    )
                else:
                    response_text = self._generate_mock_response(user_message_text, system_context)
                    prompt_tokens = len(system_context + user_message_text) // 4
                    completion_tokens = len(response_text) // 4
            except Exception as e:
                response_text = f"API Error executing LLM call: {str(e)}"
                prompt_tokens = 0
                completion_tokens = 0

        # Calculate cost if model costs are specified
        if model:
            cost = (
                (prompt_tokens * float(model.input_token_cost)) +
                (completion_tokens * float(model.output_token_cost))
            )
        
        duration = time.time() - start_time
        
        # 1. Save Assistant Message
        assistant_message = Message.objects.create(
            conversation=self.conversation,
            sender_type='assistant',
            content=response_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            response_time=duration
        )

        # 2. Record Usage
        if model:
            AIUsage.objects.create(
                organization=self.organization,
                user=self.user if self.user and self.user.is_authenticated else self.conversation.created_by,
                model=model,
                agent=self.agent,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost=cost,
                duration_ms=int(duration * 1000)
            )

        # 3. Log Activity
        AIActivityLog.objects.create(
            organization=self.organization,
            user=self.user if self.user and self.user.is_authenticated else self.conversation.created_by,
            action="ai_response_generated",
            description=f"Generated response using {model.name if model else 'mock model'}.",
            entity_type="conversation",
            entity_id=self.conversation.id
        )

        return assistant_message

    def _generate_mock_response(self, prompt, system_context):
        agent_name = self.agent.name if self.agent else "AI Assistant"
        category_name = self.agent.category.name if self.agent and self.agent.category else "General Assistant"
        
        response = (
            f"Hello! I am {agent_name}, your {category_name}.\n\n"
            f"I have received your prompt: \"{prompt}\".\n\n"
            f"Currently, my credentials are set to mock/local mode. "
            f"However, my Context Builder has loaded the following information:\n"
        )
        
        if self.project:
            response += f"- Project: {self.project.name}\n"
        if self.organization:
            response += f"- Organization: {self.organization.name}\n"
        
        # Simple rule reflection mock responses
        prompt_lower = prompt.lower()
        if "hello" in prompt_lower or "hi" in prompt_lower:
            response += "\nHow can I help you build your workspace employee platform today?"
        elif "python" in prompt_lower or "code" in prompt_lower:
            response += "\nHere is a snippet of Python code for your reference:\n```python\ndef greet():\n    print('Hello from Anthopi-bot')\n```"
        else:
            response += "\nI am fully configured with context and ready for your live LLM credentials to be added!"
            
        return response

    def _call_openai(self, model_code, api_key, system_context, history):
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        messages = [{"role": "system", "content": system_context}]
        messages.extend(history)
        
        data = {
            "model": model_code,
            "messages": messages,
            "temperature": self.agent.temperature if self.agent else 0.7
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        res_json = response.json()
        
        content = res_json['choices'][0]['message']['content']
        usage = res_json.get('usage', {})
        
        return (
            content,
            usage.get('prompt_tokens', 0),
            usage.get('completion_tokens', 0)
        )

    def _call_anthropic(self, model_code, api_key, system_context, history):
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        # Anthropic separates system prompt
        formatted_messages = [msg for msg in history if msg['role'] != 'system']
        
        data = {
            "model": model_code,
            "system": system_context,
            "messages": formatted_messages,
            "max_tokens": 4096,
            "temperature": self.agent.temperature if self.agent else 0.7
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        res_json = response.json()
        
        content = res_json['content'][0]['text']
        usage = res_json.get('usage', {})
        
        return (
            content,
            usage.get('input_tokens', 0),
            usage.get('output_tokens', 0)
        )
