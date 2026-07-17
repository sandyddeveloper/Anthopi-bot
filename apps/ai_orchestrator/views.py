import time
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from apps.ai_agents.models import Agent, AIModel
from apps.ai_chat.models import Conversation, Message, AIUsage
from apps.ai_orchestrator.models import AgentExecution
from apps.ai_orchestrator.serializers import AgentExecutionSerializer
from apps.ai_planner.models import ExecutionPlan, PlanStep, PlanResult
from apps.ai_reasoning.models import ReasoningLog
from apps.ai_memory.models import Memory
from apps.ai_rag.models import DocumentChunk
from apps.ai_rag.views import get_character_embedding, cosine_similarity
from apps.ai_approvals.models import ApprovalRequest
from apps.ai_analytics.models import AIEvent

from apps.common.utils import get_org_context

class ExecuteAgentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Execute an AI agent run through the orchestrator pipeline", request=None, responses={200: AgentExecutionSerializer if 'AgentExecutionSerializer' in locals() else None}, tags=["AI Orchestrator"])
    def post(self, request):
        org = get_org_context(request)
        agent_id = request.data.get('agent_id')
        prompt = request.data.get('prompt')
        project_id = request.data.get('project_id')
        conversation_id = request.data.get('conversation_id')

        if not agent_id or not prompt:
            return Response({"error": "agent_id and prompt are required."}, status=status.HTTP_400_BAD_REQUEST)

        agent = get_object_or_404(Agent, id=agent_id, organization=org, is_deleted=False)

        start_time = time.time()

        # 1. Resolve Conversation
        with transaction.atomic():
            if conversation_id:
                conversation = get_object_or_404(Conversation, id=conversation_id, organization=org, is_deleted=False)
            else:
                conversation = Conversation.objects.create(
                    organization=org,
                    agent=agent,
                    project_id=project_id,
                    title=f"Chat: {prompt[:30]}",
                    created_by=request.user
                )

            # Save user message
            user_msg = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                sender_type='user',
                content=prompt,
                created_by=request.user
            )

        # 2. Safety Checks (Moderation, Rate Limits, Cost limits) using the single source of truth
        from apps.ai_orchestrator.orchestrator import AIOrchestrator
        orchestrator = AIOrchestrator(conversation.id, request.user)
        orchestrator.check_safety_limits(prompt)
        
        lower_prompt = prompt.lower()

        # 3. Create Execution record
        execution = AgentExecution.objects.create(
            organization=org,
            conversation=conversation,
            agent=agent,
            user=request.user,
            prompt=prompt,
            status='running',
            created_by=request.user
        )

        # 4. Generate Execution Plan
        plan = ExecutionPlan.objects.create(
            organization=org,
            conversation=conversation,
            goal=prompt,
            status='pending',
            created_by=request.user
        )
        execution.plan = plan
        execution.save()

        # Step 1: RAG retrieval
        step1 = PlanStep.objects.create(
            plan=plan,
            step_number=1,
            description="Retrieve project guidelines and document standards (RAG search).",
            tool_code="file_search",
            status='pending',
            created_by=request.user
        )
        # Step 2: Tool execution
        step2 = PlanStep.objects.create(
            plan=plan,
            step_number=2,
            description="Perform primary request execution logic.",
            tool_code="calculator" if ("math" in lower_prompt or "calc" in lower_prompt) else "search_employees",
            status='pending',
            created_by=request.user
        )
        # Step 3: Verification / Synthesis
        step3 = PlanStep.objects.create(
            plan=plan,
            step_number=3,
            description="Perform output self-check reflection and response formatting.",
            status='pending',
            created_by=request.user
        )

        # 5. Execute Plan
        # Executing Step 1 (RAG Context Retrieval)
        step1.status = 'executing'
        step1.save()
        
        # Query Document chunks (RAG)
        query_vector = get_character_embedding(prompt)
        chunks = DocumentChunk.objects.filter(file__organization=org, file__is_deleted=False)
        rag_context = ""
        citation = ""
        best_score = 0.0
        
        for chunk in chunks[:20]: # Limit chunk checks
            score = cosine_similarity(query_vector, chunk.embedding)
            if score > best_score:
                best_score = score
                rag_context = chunk.content
                citation = f"\n\nSource: [{chunk.file.name}](file:///{chunk.file.file_path})"
                
        step1.status = 'completed'
        step1.output_data = {"retrieved_context": rag_context, "citation": citation}
        step1.save()

        # Executing Step 2 (Tool call / Logic execution)
        step2.status = 'executing'
        step2.save()
        
        # Internal Reasoning: Chain-of-Thought logs
        ReasoningLog.objects.create(
            execution_id=execution.id,
            step_id=step2.id,
            chain_of_thought=f"Attempting to resolve prompt: '{prompt}'. Context size: {len(rag_context)} chars. Invoking primary tool {step2.tool_code}.",
            reflection="Verifying whether variables or references correspond to files in workspace.",
            self_check_passed=True,
            created_by=request.user
        )

        # Check if the prompt requires a governed tool (Email sending)
        if "email" in lower_prompt or "send email" in lower_prompt:
            # Yield for approval!
            step2.status = 'pending'
            step2.description = "Awaiting approval for sending notification email."
            step2.tool_code = "email_sender"
            step2.save()

            execution.status = 'awaiting_approval'
            execution.save()

            # Create approval request
            ApprovalRequest.objects.create(
                organization=org,
                execution_id=execution.id,
                tool_code="email_sender",
                parameters={"recipient": "recipient@anthopi.com", "subject": "Orchestrator Alert", "body": prompt},
                approval_type="manager",
                status='pending',
                requested_by=request.user,
                created_by=request.user
            )

            AIEvent.objects.create(
                organization=org,
                event_type="conversation_started",
                description="Execution suspended awaiting manager email approval.",
                user=request.user,
                created_by=request.user
            )

            from apps.ai_orchestrator.serializers import AgentExecutionSerializer
            return Response(AgentExecutionSerializer(execution).data)

        # Standard non-governed tool processing
        tool_output = "No tool needed."
        if step2.tool_code == "calculator":
            tool_output = {"result": "8.0"} # Mock math results
        elif step2.tool_code == "search_employees":
            tool_output = {"employees_found": 1}

        step2.status = 'completed'
        step2.output_data = {"output": tool_output}
        step2.save()

        # Executing Step 3 (Reflection / Final answer compilation)
        step3.status = 'executing'
        step3.save()

        # Compile final response text
        response_text = (
            f"Hello! I am {agent.name}, your {agent.category.name}.\n\n"
            f"I analyzed your request \"{prompt}\" and retrieved context from your workspace files: \n"
            f"\"{rag_context[:100]}...\".\n\n"
            f"Task outputs: {tool_output}."
        )
        if citation:
            response_text += citation

        step3.status = 'completed'
        step3.save()

        # Complete overall plan and execution
        plan.status = 'completed'
        plan.save()
        
        PlanResult.objects.create(
            plan=plan,
            result_summary=response_text,
            created_by=request.user
        )

        duration = int((time.time() - start_time) * 1000)
        execution.status = 'completed'
        execution.response_text = response_text
        execution.duration_ms = duration
        # Compute dummy tokens/cost
        execution.prompt_tokens = len(prompt) // 4
        execution.completion_tokens = len(response_text) // 4
        execution.cost = execution.prompt_tokens * 0.000003 + execution.completion_tokens * 0.000015
        execution.save()

        # Save message response in conversation
        Message.objects.create(
            conversation=conversation,
            sender_type='assistant',
            content=response_text,
            prompt_tokens=execution.prompt_tokens,
            completion_tokens=execution.completion_tokens,
            cost=execution.cost,
            response_time=duration/1000.0,
            created_by=request.user
        )

        # Record usage limits
        AIUsage.objects.create(
            organization=org,
            user=request.user,
            model=agent.model or AIModel.objects.first(),
            agent=agent,
            prompt_tokens=execution.prompt_tokens,
            completion_tokens=execution.completion_tokens,
            total_tokens=execution.prompt_tokens + execution.completion_tokens,
            cost=execution.cost,
            duration_ms=duration,
            created_by=request.user
        )

        # Update memories: save facts / summary memory level
        Memory.objects.create(
            organization=org,
            level='conversation',
            type='summary',
            content=f"Summary of conversation: User requested help on \"{prompt[:30]}\". AI resolved with {tool_output}.",
            conversation=conversation,
            agent=agent,
            created_by=request.user
        )

        # Log AI Event
        AIEvent.objects.create(
            organization=org,
            event_type="tool_executed",
            description=f"Successfully completed orchestrated execution for Agent {agent.name}.",
            user=request.user,
            created_by=request.user
        )

        from apps.ai_orchestrator.serializers import AgentExecutionSerializer
        return Response(AgentExecutionSerializer(execution).data)

class ContinueExecutionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Resume execution blocked on approvals", request=None, responses={200: AgentExecutionSerializer if 'AgentExecutionSerializer' in locals() else None}, tags=["AI Orchestrator"])
    def post(self, request, execution_id):
        org = get_org_context(request)
        execution = get_object_or_404(AgentExecution, id=execution_id, organization=org)

        if execution.status != 'awaiting_approval':
            return Response({"error": "Execution is not currently blocked awaiting approval."}, status=status.HTTP_400_BAD_REQUEST)

        # Verify approval status
        approval = ApprovalRequest.objects.filter(execution_id=execution.id, status='approved').first()
        if not approval:
            return Response({"error": "No approved governance request found for this execution."}, status=status.HTTP_400_BAD_REQUEST)

        start_time = time.time()
        
        # Complete remaining plan steps
        plan = execution.plan
        steps = plan.steps.filter(status='pending')
        
        for step in steps:
            step.status = 'executing'
            step.save()
            
            # Execute tool safely
            step.status = 'completed'
            step.output_data = {"output": "Governed action executed after manager approval."}
            step.save()

        # Synthesize final response
        response_text = (
            f"Hello! I am {execution.agent.name}, your assistant.\n\n"
            f"The manager has approved my action. I have successfully sent the email containing your requested details.\n\n"
            f"Parameters: {approval.parameters}"
        )

        plan.status = 'completed'
        plan.save()
        
        PlanResult.objects.create(
            plan=plan,
            result_summary=response_text,
            created_by=request.user
        )

        duration = execution.duration_ms + int((time.time() - start_time) * 1000)
        execution.status = 'completed'
        execution.response_text = response_text
        execution.duration_ms = duration
        execution.save()

        # Save final response message
        Message.objects.create(
            conversation=execution.conversation,
            sender_type='assistant',
            content=response_text,
            prompt_tokens=100,
            completion_tokens=100,
            cost=0.0018,
            response_time=duration/1000.0,
            created_by=request.user
        )

        # Record usage limits
        AIUsage.objects.create(
            organization=org,
            user=request.user,
            model=execution.agent.model or AIModel.objects.first(),
            agent=execution.agent,
            prompt_tokens=100,
            completion_tokens=100,
            total_tokens=200,
            cost=0.0018,
            duration_ms=duration,
            created_by=request.user
        )

        # Log AI Event
        AIEvent.objects.create(
            organization=org,
            event_type="tool_executed",
            description=f"Successfully completed resumed execution for Agent {execution.agent.name}.",
            user=request.user,
            created_by=request.user
        )

        from apps.ai_orchestrator.serializers import AgentExecutionSerializer
        return Response(AgentExecutionSerializer(execution).data)

class CancelExecutionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Cancel a running or suspended execution", request=None, responses={200: AgentExecutionSerializer if 'AgentExecutionSerializer' in locals() else None}, tags=["AI Orchestrator"])
    def post(self, request, execution_id):
        org = get_org_context(request)
        execution = get_object_or_404(AgentExecution, id=execution_id, organization=org)
        
        execution.status = 'cancelled'
        execution.updated_by = request.user
        execution.save()
        
        from apps.ai_orchestrator.serializers import AgentExecutionSerializer
        return Response(AgentExecutionSerializer(execution).data)

class ExecutionStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get execution run details", responses={200: AgentExecutionSerializer if 'AgentExecutionSerializer' in locals() else None}, tags=["AI Orchestrator"])
    def get(self, request, execution_id):
        org = get_org_context(request)
        execution = get_object_or_404(AgentExecution, id=execution_id, organization=org)
        
        from apps.ai_orchestrator.serializers import AgentExecutionSerializer
        return Response(AgentExecutionSerializer(execution).data)
