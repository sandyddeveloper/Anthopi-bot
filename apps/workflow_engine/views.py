from rest_framework import status, viewsets, mixins, serializers
from rest_framework.views import APIView
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter, OpenApiTypes, inline_serializer
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from apps.workflow_engine.models import (
    WorkflowCategory, WorkflowFolder, WorkflowTag, Workflow, WorkflowVersion,
    WorkflowNode, NodePosition, NodeConnection, VariableScope, Variable,
    WorkflowExecution, NodeExecution, ExecutionLog, RetryPolicy,
    TemplateCategory, WorkflowTemplate, Webhook, WebhookLog
)
from apps.workflow_engine.serializers import (
    WorkflowCategorySerializer, WorkflowFolderSerializer, WorkflowTagSerializer,
    WorkflowSerializer, WorkflowVersionSerializer, WorkflowNodeSerializer,
    NodeConnectionSerializer, VariableScopeSerializer, VariableSerializer,
    WorkflowExecutionSerializer, NodeExecutionSerializer, ExecutionLogSerializer,
    RetryPolicySerializer, TemplateCategorySerializer, WorkflowTemplateSerializer,
    WebhookSerializer, WebhookLogSerializer
)
from apps.workflow_engine.tasks import execute_workflow_task

@extend_schema(tags=['Workflows'])
class WorkflowViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkflowSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request or not self.request.user or self.request.user.is_anonymous:
            return Workflow.objects.none()
        org = self.request.organization or self.request.user.organization
        if self.request.user.is_superuser:
            return Workflow.objects.all().filter(is_deleted=False)
        return Workflow.objects.filter(organization=org, is_deleted=False)

    def perform_create(self, serializer):
        org = self.request.organization or self.request.user.organization
        serializer.save(
            organization=org,
            owner=self.request.user
        )

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Publishes the current workflow definition, creating a new published version snapshot.
        """
        workflow = self.get_object()
        org = request.organization or request.user.organization

        with transaction.atomic():
            # Deactivate previous published versions
            workflow.versions.all().update(is_published=False)

            latest_version = workflow.versions.order_by('-version_number').first()

            if latest_version and not latest_version.is_published:
                latest_version.is_published = True
                latest_version.save()
                new_version = latest_version
            else:
                next_num = (latest_version.version_number + 1) if latest_version else 1
                new_version = WorkflowVersion.objects.create(
                    workflow=workflow,
                    version_number=next_num,
                    is_published=True,
                    created_by=request.user
                )

                # Clone nodes and connections from the latest version if exists
                if latest_version:
                    node_map = {}
                    for node in latest_version.nodes.all():
                        pos = getattr(node, 'position', None)
                        cloned_node = WorkflowNode.objects.create(
                            workflow_version=new_version,
                            node_id=node.node_id,
                            name=node.name,
                            node_type=node.node_type,
                            sub_type=node.sub_type,
                            configuration=node.configuration,
                            created_by=request.user
                        )
                        node_map[node.id] = cloned_node
                        if pos:
                            NodePosition.objects.create(
                                node=cloned_node,
                                position_x=pos.position_x,
                                position_y=pos.position_y,
                                created_by=request.user
                            )

                    for conn in latest_version.connections.all():
                        NodeConnection.objects.create(
                            workflow_version=new_version,
                            source_node=node_map[conn.source_node.id],
                            target_node=node_map[conn.target_node.id],
                            condition=conn.condition,
                            created_by=request.user
                        )

            # Link as active version
            workflow.active_version = new_version
            workflow.save()

        return Response(WorkflowVersionSerializer(new_version).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        workflow = self.get_object()
        workflow.status = 'paused' if workflow.status != 'paused' else 'active'
        workflow.save()
        return Response({"status": workflow.status})

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        workflow = self.get_object()
        workflow.status = 'archived'
        workflow.save()
        return Response({"status": "archived"})

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        original = self.get_object()
        
        with transaction.atomic():
            # Duplicate Workflow container
            new_workflow = Workflow.objects.create(
                organization=original.organization,
                project=original.project,
                owner=request.user,
                category=original.category,
                folder=original.folder,
                name=f"{original.name} (Copy)",
                description=original.description,
                status='draft'
            )

            # Copy active version if exists
            orig_version = original.active_version or original.versions.order_by('-version_number').first()
            if orig_version:
                new_version = WorkflowVersion.objects.create(
                    workflow=new_workflow,
                    version_number=1,
                    is_published=False,
                    created_by=request.user
                )

                node_map = {}
                for node in orig_version.nodes.all():
                    pos = getattr(node, 'position', None)
                    cloned_node = WorkflowNode.objects.create(
                        workflow_version=new_version,
                        node_id=node.node_id,
                        name=node.name,
                        node_type=node.node_type,
                        sub_type=node.sub_type,
                        configuration=node.configuration,
                        created_by=request.user
                    )
                    node_map[node.id] = cloned_node
                    if pos:
                        NodePosition.objects.create(
                            node=cloned_node,
                            position_x=pos.position_x,
                            position_y=pos.position_y,
                            created_by=request.user
                        )

                for conn in orig_version.connections.all():
                    NodeConnection.objects.create(
                        workflow_version=new_version,
                        source_node=node_map[conn.source_node.id],
                        target_node=node_map[conn.target_node.id],
                        condition=conn.condition,
                        created_by=request.user
                    )

                new_workflow.active_version = new_version
                new_workflow.save()

        return Response(WorkflowSerializer(new_workflow).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def rollback(self, request, pk=None):
        workflow = self.get_object()
        version_num = request.data.get('version_number')
        if not version_num:
            return Response({"detail": "version_number parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        version = get_object_or_404(WorkflowVersion, workflow=workflow, version_number=version_num)
        workflow.active_version = version
        workflow.save()
        return Response({"detail": f"Workflow rolled back to version {version_num} successfully."})

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        """
        Manually triggers a workflow execution.
        """
        workflow = self.get_object()
        version = workflow.active_version or workflow.versions.order_by('-version_number').first()
        
        if not version:
            return Response({"detail": "This workflow has no versions built yet."}, status=status.HTTP_400_BAD_REQUEST)

        input_data = request.data.get('input_data', {})

        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            workflow_version=version,
            status='queued',
            input_data=input_data,
            created_by=request.user
        )

        # Trigger background execution
        execute_workflow_task.delay(str(execution.id))

        return Response(WorkflowExecutionSerializer(execution).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Workflow Nodes'])
class WorkflowNodeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkflowNodeSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request or not self.request.user or self.request.user.is_anonymous:
            return WorkflowNode.objects.none()
        org = self.request.organization or self.request.user.organization
        return WorkflowNode.objects.filter(workflow_version__workflow__organization=org, is_deleted=False)


@extend_schema(tags=['Node Connections'])
class NodeConnectionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = NodeConnectionSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request or not self.request.user or self.request.user.is_anonymous:
            return NodeConnection.objects.none()
        org = self.request.organization or self.request.user.organization
        return NodeConnection.objects.filter(workflow_version__workflow__organization=org, is_deleted=False)


class WorkflowBuilderAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Retrieve draft workflow canvas definition",
        parameters=[
            OpenApiParameter(
                name="workflow_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
                description="ID of the workflow to fetch builder canvas"
            )
        ],
        responses={200: WorkflowVersionSerializer},
        tags=['Workflow Builder']
    )
    def get(self, request):
        workflow_id = request.query_params.get('workflow_id')
        if not workflow_id:
            return Response({"detail": "workflow_id parameter required."}, status=status.HTTP_400_BAD_REQUEST)

        org = request.organization or request.user.organization
        workflow = get_object_or_404(Workflow, id=workflow_id, organization=org)
        
        # Get latest version or active version
        version = workflow.active_version or workflow.versions.order_by('-version_number').first()
        if not version:
            # Create a default first version container
            version = WorkflowVersion.objects.create(
                workflow=workflow,
                version_number=1,
                is_published=False,
                created_by=request.user
            )

        serializer = WorkflowVersionSerializer(version)
        return Response(serializer.data)

    @extend_schema(
        summary="Save draft workflow canvas definition (nodes & connections)",
        request=inline_serializer(
            name="WorkflowBuilderSaveRequest",
            fields={
                "workflow_id": serializers.UUIDField(),
                "nodes": WorkflowNodeSerializer(many=True),
                "connections": NodeConnectionSerializer(many=True)
            }
        ),
        responses={201: WorkflowVersionSerializer},
        tags=['Workflow Builder']
    )
    def post(self, request):
        """
        Saves canvas nodes and connections snapshot to current draft.
        """
        workflow_id = request.data.get('workflow_id')
        if not workflow_id:
            return Response({"detail": "workflow_id required."}, status=status.HTTP_400_BAD_REQUEST)

        org = request.organization or request.user.organization
        workflow = get_object_or_404(Workflow, id=workflow_id, organization=org)

        nodes_data = request.data.get('nodes', [])
        connections_data = request.data.get('connections', [])

        with transaction.atomic():
            # Get latest version or create new version
            version = workflow.active_version or workflow.versions.order_by('-version_number').first()
            if not version or version.is_published:
                # If active is published, we create a new draft version to hold updates
                next_num = (version.version_number + 1) if version else 1
                version = WorkflowVersion.objects.create(
                    workflow=workflow,
                    version_number=next_num,
                    is_published=False,
                    created_by=request.user
                )

            # Clear existing draft nodes and connections
            version.nodes.all().delete()
            version.connections.all().delete()

            # Create new nodes
            node_map = {}
            for nd in nodes_data:
                pos_data = nd.get('position', {'position_x': 0.0, 'position_y': 0.0})
                node = WorkflowNode.objects.create(
                    workflow_version=version,
                    node_id=nd.get('node_id'),
                    name=nd.get('name', 'Node'),
                    node_type=nd.get('node_type'),
                    sub_type=nd.get('sub_type', ''),
                    configuration=nd.get('configuration', {}),
                    created_by=request.user
                )
                NodePosition.objects.create(
                    node=node,
                    position_x=pos_data.get('position_x', 0.0),
                    position_y=pos_data.get('position_y', 0.0),
                    created_by=request.user
                )
                node_map[nd.get('node_id')] = node

            # Create connections
            for conn in connections_data:
                src_id = conn.get('source_node_id') or conn.get('source_node')
                tgt_id = conn.get('target_node_id') or conn.get('target_node')
                
                # Fetch matching node records
                src_node = node_map.get(src_id) or version.nodes.filter(node_id=src_id).first()
                tgt_node = node_map.get(tgt_id) or version.nodes.filter(node_id=tgt_id).first()

                if src_node and tgt_node:
                    NodeConnection.objects.create(
                        workflow_version=version,
                        source_node=src_node,
                        target_node=tgt_node,
                        condition=conn.get('condition', {}),
                        created_by=request.user
                    )

        serializer = WorkflowVersionSerializer(version)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Workflow Executions'])
class WorkflowExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkflowExecutionSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request or not self.request.user or self.request.user.is_anonymous:
            return WorkflowExecution.objects.none()
        org = self.request.organization or self.request.user.organization
        return WorkflowExecution.objects.filter(workflow__organization=org, is_deleted=False).order_by('-created_at')

    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        execution = self.get_object()
        logs = execution.logs.all().order_by('timestamp')
        return Response(ExecutionLogSerializer(logs, many=True).data)

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        execution = self.get_object()
        if execution.status != 'failed':
            return Response({"detail": "Only failed executions can be retried."}, status=status.HTTP_400_BAD_REQUEST)

        # Create copy of execution
        retry_exec = WorkflowExecution.objects.create(
            workflow=execution.workflow,
            workflow_version=execution.workflow_version,
            trigger_node=execution.trigger_node,
            status='queued',
            input_data=execution.input_data,
            created_by=request.user
        )

        execute_workflow_task.delay(str(retry_exec.id))
        return Response(WorkflowExecutionSerializer(retry_exec).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Workflow Variables'])
class VariableViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = VariableSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request or not self.request.user or self.request.user.is_anonymous:
            return Variable.objects.none()
        org = self.request.organization or self.request.user.organization
        return Variable.objects.filter(organization=org, is_deleted=False)

    def perform_create(self, serializer):
        org = self.request.organization or self.request.user.organization
        serializer.save(organization=org)


@extend_schema(tags=['Workflow Templates'])
class WorkflowTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkflowTemplateSerializer
    queryset = WorkflowTemplate.objects.filter(is_deleted=False)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request or not self.request.user or self.request.user.is_anonymous:
            return WorkflowTemplate.objects.none()
        return super().get_queryset()

    @action(detail=True, methods=['post'])
    def use(self, request, pk=None):
        template = self.get_object()
        org = request.organization or request.user.organization

        with transaction.atomic():
            workflow = Workflow.objects.create(
                organization=org,
                owner=request.user,
                name=f"{template.name} (Template)",
                description=template.description,
                status='draft'
            )

            # Build version and load nodes
            version = WorkflowVersion.objects.create(
                workflow=workflow,
                version_number=1,
                is_published=False,
                created_by=request.user
            )

            definition = template.definition or {}
            nodes_data = definition.get('nodes', [])
            connections_data = definition.get('connections', [])

            node_map = {}
            for nd in nodes_data:
                pos_data = nd.get('position', {'position_x': 0.0, 'position_y': 0.0})
                node = WorkflowNode.objects.create(
                    workflow_version=version,
                    node_id=nd.get('node_id'),
                    name=nd.get('name', 'Node'),
                    node_type=nd.get('node_type'),
                    sub_type=nd.get('sub_type', ''),
                    configuration=nd.get('configuration', {}),
                    created_by=request.user
                )
                NodePosition.objects.create(
                    node=node,
                    position_x=pos_data.get('position_x', 0.0),
                    position_y=pos_data.get('position_y', 0.0),
                    created_by=request.user
                )
                node_map[nd.get('node_id')] = node

            for conn in connections_data:
                src_node = node_map.get(conn.get('source_node_id'))
                tgt_node = node_map.get(conn.get('target_node_id'))
                if src_node and tgt_node:
                    NodeConnection.objects.create(
                        workflow_version=version,
                        source_node=src_node,
                        target_node=tgt_node,
                        condition=conn.get('condition', {}),
                        created_by=request.user
                    )

            # Link as active version
            workflow.active_version = version
            workflow.save()

        return Response(WorkflowSerializer(workflow).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Workflow Webhooks'])
class WebhookViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WebhookSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request or not self.request.user or self.request.user.is_anonymous:
            return Webhook.objects.none()
        org = self.request.organization or self.request.user.organization
        return Webhook.objects.filter(workflow__organization=org, is_deleted=False)

    def perform_create(self, serializer):
        import secrets
        token = secrets.token_urlsafe(32)
        serializer.save(webhook_token=token)


@extend_schema(tags=['Workflow Webhooks'])
class IncomingWebhookAPIView(APIView):
    """
    Publicly accessible endpoint that receives external triggers.
    """
    permission_classes = []
    authentication_classes = []

    @extend_schema(
        summary="Trigger workflow via incoming webhook (POST)",
        parameters=[
            OpenApiParameter(name="token", type=OpenApiTypes.STR, location=OpenApiParameter.PATH, required=True)
        ],
        request=inline_serializer(name="IncomingWebhookDataPost", fields={}),
        responses={202: inline_serializer(name="WebhookAcceptedPost", fields={"status": serializers.CharField(), "execution_id": serializers.UUIDField()})}
    )
    def post(self, request, token):
        return self._handle_webhook(request, token)

    @extend_schema(
        summary="Trigger workflow via incoming webhook (PUT)",
        parameters=[
            OpenApiParameter(name="token", type=OpenApiTypes.STR, location=OpenApiParameter.PATH, required=True)
        ],
        request=inline_serializer(name="IncomingWebhookDataPut", fields={}),
        responses={202: inline_serializer(name="WebhookAcceptedPut", fields={"status": serializers.CharField(), "execution_id": serializers.UUIDField()})}
    )
    def put(self, request, token):
        return self._handle_webhook(request, token)

    @extend_schema(
        summary="Trigger workflow via incoming webhook (PATCH)",
        parameters=[
            OpenApiParameter(name="token", type=OpenApiTypes.STR, location=OpenApiParameter.PATH, required=True)
        ],
        request=inline_serializer(name="IncomingWebhookDataPatch", fields={}),
        responses={202: inline_serializer(name="WebhookAcceptedPatch", fields={"status": serializers.CharField(), "execution_id": serializers.UUIDField()})}
    )
    def patch(self, request, token):
        return self._handle_webhook(request, token)

    def _handle_webhook(self, request, token):
        webhook = get_object_or_404(Webhook, webhook_token=token, is_active=True)
        workflow = webhook.workflow

        # Ensure active version is present
        version = workflow.active_version
        if not version or workflow.status != 'active':
            return Response({"detail": "Workflow is inactive or has no published versions."}, status=status.HTTP_400_BAD_REQUEST)

        # Parse request details
        headers = dict(request.headers)
        body = request.data

        # Create workflow execution container
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            workflow_version=version,
            status='queued',
            input_data={
                "headers": headers,
                "body": body,
                "method": request.method
            }
        )

        # Log Webhook Audit
        WebhookLog.objects.create(
            webhook=webhook,
            request_method=request.method,
            request_headers=headers,
            request_body=str(body),
            response_status=202,
            workflow_execution=execution
        )

        # Trigger Celery job runner (gracefully handle missing broker)
        try:
            execute_workflow_task.delay(str(execution.id))
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Celery broker unavailable; execution %s queued but not dispatched.", execution.id
            )

        return Response({
            "status": "accepted",
            "execution_id": str(execution.id)
        }, status=status.HTTP_202_ACCEPTED)
