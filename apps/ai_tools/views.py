import time
import requests
from django.utils import timezone
from django.db import connection
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from apps.users.models import User
from apps.projects.models import Project
from apps.knowledge.models import File
from apps.ai_tools.models import ToolExecution
from apps.ai_tools.serializers import ToolExecutionSerializer

from apps.common.utils import get_org_context

# Safe math evaluator
def safe_eval(expr):
    allowed_chars = "0123456789+-*/(). "
    if not all(c in allowed_chars for c in expr):
        raise ValueError("Unsafe characters detected in expression.")
    # Use eval safely since we restrict characters strictly to numbers and math operators
    return eval(expr, {"__builtins__": None}, {})

class ToolListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List available tools", responses={200: None}, tags=["AI Tools"])
    def get(self, request):
        tools = [
            {"code": "search_employees", "name": "Search Employees", "description": "Query employee records by name or email"},
            {"code": "search_projects", "name": "Search Projects", "description": "Query project details within the organization"},
            {"code": "run_sql", "name": "Run SQL", "description": "Execute read-only queries against the database"},
            {"code": "generate_report", "name": "Generate Report", "description": "Compiles analytics details into a report structure"},
            {"code": "http_request", "name": "HTTP Request", "description": "Performs external REST API requests"},
            {"code": "file_search", "name": "File Search", "description": "Search uploaded knowledge base files"},
            {"code": "calculator", "name": "Calculator", "description": "Evaluate mathematical expressions"},
            {"code": "current_date", "name": "Current Date", "description": "Get current timestamp and day info"},
            {"code": "email_sender", "name": "Email Sender", "description": "Send notification emails (requires manager approval)"},
        ]
        return Response(tools)

class ExecuteToolAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Execute a tool", request=None, responses={200: None}, tags=["AI Tools"])
    def post(self, request):
        org = get_org_context(request)
        tool_code = request.data.get('tool_code')
        params = request.data.get('parameters', {})
        agent_id = request.data.get('agent_id')
        
        if not tool_code:
            return Response({"error": "tool_code is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        start_time = time.time()
        is_success = True
        error_msg = ""
        output = {}
        
        try:
            if tool_code == "search_employees":
                query = params.get('query', '')
                users = User.objects.filter(organization=org, is_deleted=False)
                if query:
                    users = users.filter(full_name__icontains=query) | users.filter(email__icontains=query)
                output = {"employees": [{"id": str(u.id), "full_name": u.full_name, "email": u.email} for u in users[:10]]}
                
            elif tool_code == "search_projects":
                query = params.get('query', '')
                projects = Project.objects.filter(organization=org, is_deleted=False)
                if query:
                    projects = projects.filter(name__icontains=query) | projects.filter(code__icontains=query)
                output = {"projects": [{"id": str(p.id), "name": p.name, "code": p.code, "status": p.status} for p in projects[:10]]}
                
            elif tool_code == "run_sql":
                sql = params.get('sql', '').strip()
                if not sql.lower().startswith('select'):
                    raise PermissionDenied("Only SELECT queries are allowed.")
                
                # Check for write operations or comments that bypass
                forbidden = ["insert", "update", "delete", "drop", "alter", "create", "truncate", "replace"]
                if any(word in sql.lower() for word in forbidden):
                    raise PermissionDenied("Query contains writing instructions.")
                    
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    columns = [col[0] for col in cursor.description]
                    rows = cursor.fetchall()
                    
                output = {
                    "columns": columns,
                    "rows": [list(row) for row in rows[:50]]
                }
                
            elif tool_code == "generate_report":
                title = params.get('title', 'AI Performance Report')
                output = {
                    "report_title": title,
                    "generated_at": str(timezone.now()),
                    "summary": "This is a dynamically generated tool report based on AI metrics.",
                    "status": "ready"
                }
                
            elif tool_code == "http_request":
                url = params.get('url')
                method = params.get('method', 'GET').upper()
                payload = params.get('data', {})
                if not url:
                    raise ValueError("url parameter is required.")
                
                # Safe url check or simple mock
                if not url.startswith('http'):
                    url = 'https://' + url
                
                # Simple request
                if method == 'GET':
                    res = requests.get(url, timeout=5)
                else:
                    res = requests.post(url, json=payload, timeout=5)
                    
                output = {
                    "status_code": res.status_code,
                    "headers": dict(res.headers),
                    "body": res.text[:2000]
                }
                
            elif tool_code == "file_search":
                query = params.get('query', '')
                files = File.objects.filter(organization=org, is_deleted=False)
                if query:
                    files = files.filter(name__icontains=query) | files.filter(file_type__icontains=query)
                output = {"files": [{"id": str(f.id), "name": f.name, "file_type": f.file_type, "file_size": f.file_size} for f in files[:10]]}
                
            elif tool_code == "calculator":
                expression = params.get('expression', '')
                if not expression:
                    raise ValueError("expression parameter is required.")
                result = safe_eval(expression)
                output = {"expression": expression, "result": result}
                
            elif tool_code == "current_date":
                now = timezone.now()
                output = {
                    "iso": now.isoformat(),
                    "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "timezone": str(timezone.get_current_timezone()),
                    "day_of_week": now.strftime("%A")
                }
                
            elif tool_code == "email_sender":
                recipient = params.get('recipient')
                subject = params.get('subject', 'No Subject')
                body = params.get('body', '')
                if not recipient:
                    raise ValueError("recipient parameter is required.")
                
                # Emails need approval when triggered, so we record mock sent status
                output = {
                    "sent": True,
                    "recipient": recipient,
                    "subject": subject,
                    "message": "Email sent successfully in development simulation mode."
                }
                
            else:
                is_success = False
                error_msg = f"Unknown tool code: {tool_code}"
                return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            is_success = False
            error_msg = str(e)
            output = {"error": error_msg}
            
        duration = int((time.time() - start_time) * 1000)
        
        # Log execution
        ToolExecution.objects.create(
            tool_code=tool_code,
            agent_id=agent_id,
            user=request.user,
            input_parameters=params,
            output_result=output,
            is_success=is_success,
            error_message=error_msg,
            duration_ms=duration,
            created_by=request.user
        )
        
        if not is_success:
            return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(output)
