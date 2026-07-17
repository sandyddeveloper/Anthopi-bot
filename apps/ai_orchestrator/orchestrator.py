import time
import requests
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import PermissionDenied

from apps.ai_agents.models import OrganizationModel
from apps.ai_chat.models import Conversation, Message, AIUsage, AIActivityLog
from apps.ai_memory.models import Memory
from apps.ai_rag.models import DocumentChunk
from apps.ai_rag.views import get_character_embedding, cosine_similarity

class AIOrchestrator:
    def __init__(self, conversation_id, user=None):
        self.conversation = Conversation.objects.get(id=conversation_id)
        self.agent = self.conversation.agent
        self.organization = self.conversation.organization
        self.project = self.conversation.project
        self.user = user

    def check_safety_limits(self, prompt):
        # 1. Content Moderation
        lower_prompt = prompt.lower()
        blocked_keywords = ["execute code delete all", "hack mainframe", "bypass limits"]
        if any(kw in lower_prompt for kw in blocked_keywords):
            raise PermissionDenied("Prompt flagged by safety content moderation.")

        # 2. Daily & Monthly Cost Limits
        ai_settings = getattr(self.organization, 'ai_settings', None)
        if ai_settings:
            total_org_cost = AIUsage.objects.filter(organization=self.organization).aggregate(Sum('cost'))['cost__sum'] or 0.0
            if ai_settings.cost_limit and total_org_cost >= float(ai_settings.cost_limit):
                raise PermissionDenied("Organization monthly AI cost limit reached.")

            today = timezone.now().date()
            daily_cost = AIUsage.objects.filter(organization=self.organization, date=today).aggregate(Sum('cost'))['cost__sum'] or 0.0
            if ai_settings.daily_limit and daily_cost >= float(ai_settings.daily_limit):
                raise PermissionDenied("Organization daily AI cost limit reached.")

    def build_context(self, prompt=None):
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

        # 3. Knowledge Base Context (RAG)
        # Fetch knowledge collections mapping
        collections = self.agent.knowledge_collections.all() if self.agent else []
        files = []
        for col in collections:
            files.extend(col.items.values_list('file__name', flat=True))
            
        if files:
            context_parts.append(f"Linked Knowledge Files: {', '.join(files)}")

        if prompt:
            query_vector = get_character_embedding(prompt)
            chunks = DocumentChunk.objects.filter(file__organization=self.organization, file__is_deleted=False)
            rag_context = ""
            best_score = 0.0
            for chunk in chunks:
                score = cosine_similarity(query_vector, chunk.embedding)
                if score > best_score:
                    best_score = score
                    rag_context = chunk.content
            if rag_context:
                context_parts.append(f"Retrieved RAG Context (Similarity Score: {round(best_score, 4)}):\n{rag_context}")

        # 4. Long-Term Memory context (Union from both ai_chat and ai_memory apps)
        from apps.ai_chat.models import Memory as ChatMemory
        
        # Query Chat Memories
        chat_mems = ChatMemory.objects.filter(organization=self.organization, status='active')
        chat_user = chat_mems.filter(user=self.user) if self.user else chat_mems.none()
        chat_agent = chat_mems.filter(agent=self.agent) if self.agent else chat_mems.none()
        chat_project = chat_mems.filter(project=self.project) if self.project else chat_mems.none()
        combined_chat = (chat_user | chat_agent | chat_project).distinct()
        
        # Query Enterprise Memories
        ent_mems = Memory.objects.filter(organization=self.organization, is_deleted=False)
        ent_user = ent_mems.filter(user=self.user) if self.user else ent_mems.none()
        ent_agent = ent_mems.filter(agent=self.agent) if self.agent else ent_mems.none()
        ent_project = ent_mems.filter(project=self.project) if self.project else ent_mems.none()
        combined_ent = (ent_user | ent_agent | ent_project).distinct()
        
        memory_contents = []
        for mem in combined_chat:
            memory_contents.append(mem.content)
        for mem in combined_ent:
            memory_contents.append(mem.content)
            
        if memory_contents:
            context_parts.append("Remembered Facts (Long-Term Memory):")
            for content in memory_contents:
                context_parts.append(f"- Remembered: {content}")

        # 5. Organization Details
        if self.organization:
            context_parts.append(
                f"Organization context:\n"
                f"- Name: {self.organization.name}\n"
                f"- Industry: {self.organization.industry or 'Unknown'}"
            )

        return "\n\n".join(context_parts)

    def select_provider_and_key(self):
        if not self.agent or not self.agent.model:
            settings = getattr(self.organization, 'ai_settings', None)
            model = settings.default_model if settings else None
            if not model:
                return None, None, None
        else:
            model = self.agent.model

        provider = model.provider
        org_model = OrganizationModel.objects.filter(
            organization=self.organization,
            provider=provider,
            is_enabled=True
        ).first()

        api_key = org_model.api_key if org_model else provider.api_key
        return model, provider, api_key

    def call_llm(self, user_message_text):
        """
        Main LLM pipeline used by the standard chat interface.
        """
        self.check_safety_limits(user_message_text)
        
        start_time = time.time()
        system_context = self.build_context(user_message_text)
        model, provider, api_key = self.select_provider_and_key()
        
        history = []
        past_messages = self.conversation.messages.order_by('created_at')[:15]
        for msg in past_messages:
            history.append({
                "role": "user" if msg.sender_type == "user" else "assistant",
                "content": msg.content
            })
        history.append({"role": "user", "content": user_message_text})

        response_text = ""
        prompt_tokens = 0
        completion_tokens = 0
        cost = 0.0

        if not api_key or not model:
            response_text = self._generate_mock_response(user_message_text, system_context)
            prompt_tokens = len(system_context + user_message_text) // 4
            completion_tokens = len(response_text) // 4
        else:
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

        if model:
            cost = (prompt_tokens * float(model.input_token_cost)) + (completion_tokens * float(model.output_token_cost))
        
        duration = time.time() - start_time
        
        with transaction.atomic():
            assistant_message = Message.objects.create(
                conversation=self.conversation,
                sender_type='assistant',
                content=response_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost=cost,
                response_time=duration
            )

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
            f"I have loaded the following information:\n"
        )
        if self.project:
            response += f"- Project: {self.project.name}\n"
        if self.organization:
            response += f"- Organization: {self.organization.name}\n"
        
        prompt_lower = prompt.lower()
        if "hello" in prompt_lower or "hi" in prompt_lower:
            response += "\nHow can I help you build your workspace employee platform today?"
        elif "python" in prompt_lower or "code" in prompt_lower:
            response += "\nHere is a snippet of Python code for your reference:\n```python\ndef greet():\n    print('Hello from Anthopi-bot')\n```"
        else:
            response += "\nI am fully configured with context and ready for execution."
            
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
        res = requests.post(url, headers=headers, json=data, timeout=30)
        res.raise_for_status()
        res_json = res.json()
        return (
            res_json['choices'][0]['message']['content'],
            res_json.get('usage', {}).get('prompt_tokens', 0),
            res_json.get('usage', {}).get('completion_tokens', 0)
        )

    def _call_anthropic(self, model_code, api_key, system_context, history):
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        formatted_messages = [msg for msg in history if msg['role'] != 'system']
        data = {
            "model": model_code,
            "system": system_context,
            "messages": formatted_messages,
            "max_tokens": 4096,
            "temperature": self.agent.temperature if self.agent else 0.7
        }
        res = requests.post(url, headers=headers, json=data, timeout=30)
        res.raise_for_status()
        res_json = res.json()
        return (
            res_json['content'][0]['text'],
            res_json.get('usage', {}).get('input_tokens', 0),
            res_json.get('usage', {}).get('output_tokens', 0)
        )
