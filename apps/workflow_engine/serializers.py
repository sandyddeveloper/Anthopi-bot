from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from apps.workflow_engine.models import (
    WorkflowCategory, WorkflowFolder, WorkflowTag, Workflow, WorkflowVersion,
    WorkflowNode, NodePosition, NodeConnection, VariableScope, Variable,
    WorkflowExecution, NodeExecution, ExecutionLog, RetryPolicy,
    TemplateCategory, WorkflowTemplate, Webhook, WebhookLog
)

class WorkflowCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowCategory
        fields = '__all__'


class WorkflowFolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowFolder
        fields = '__all__'


class WorkflowTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowTag
        fields = '__all__'


class NodePositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NodePosition
        fields = ['position_x', 'position_y']


class WorkflowNodeSerializer(serializers.ModelSerializer):
    position = NodePositionSerializer(required=False)

    class Meta:
        model = WorkflowNode
        fields = ['id', 'node_id', 'name', 'node_type', 'sub_type', 'configuration', 'position']

    def create(self, validated_data):
        position_data = validated_data.pop('position', None)
        node = WorkflowNode.objects.create(**validated_data)
        if position_data:
            NodePosition.objects.create(node=node, **position_data)
        else:
            NodePosition.objects.create(node=node)
        return node

    def update(self, instance, validated_data):
        position_data = validated_data.pop('position', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if position_data:
            pos, created = NodePosition.objects.get_or_create(node=instance)
            pos.position_x = position_data.get('position_x', pos.position_x)
            pos.position_y = position_data.get('position_y', pos.position_y)
            pos.save()
        return instance


class NodeConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NodeConnection
        fields = ['id', 'source_node', 'target_node', 'condition']


class WorkflowVersionSerializer(serializers.ModelSerializer):
    nodes = WorkflowNodeSerializer(many=True, read_only=True)
    connections = NodeConnectionSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowVersion
        fields = ['id', 'version_number', 'description', 'is_published', 'nodes', 'connections', 'created_at']


class WorkflowSerializer(serializers.ModelSerializer):
    tags_details = WorkflowTagSerializer(many=True, source='tags', read_only=True)
    active_version_number = serializers.IntegerField(source='active_version.version_number', read_only=True)

    class Meta:
        model = Workflow
        fields = [
            'id', 'organization', 'project', 'owner', 'category', 'folder',
            'tags', 'tags_details', 'name', 'description', 'status',
            'active_version', 'active_version_number', 'created_at', 'updated_at'
        ]
        read_only_fields = ['organization', 'owner', 'active_version']


class VariableScopeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariableScope
        fields = '__all__'


class VariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variable
        fields = '__all__'


class NodeExecutionSerializer(serializers.ModelSerializer):
    node_name = serializers.CharField(source='node.name', read_only=True)
    node_type = serializers.CharField(source='node.node_type', read_only=True)

    class Meta:
        model = NodeExecution
        fields = '__all__'


class ExecutionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExecutionLog
        fields = '__all__'


class WorkflowExecutionSerializer(serializers.ModelSerializer):
    node_executions = NodeExecutionSerializer(many=True, read_only=True)
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)

    class Meta:
        model = WorkflowExecution
        fields = '__all__'


class RetryPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RetryPolicy
        fields = '__all__'


class TemplateCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateCategory
        fields = '__all__'


class WorkflowTemplateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = WorkflowTemplate
        fields = '__all__'


class WebhookSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Webhook
        fields = ['id', 'workflow', 'webhook_token', 'is_active', 'url', 'created_at']
        read_only_fields = ['webhook_token']

    @extend_schema_field(serializers.CharField)
    def get_url(self, obj):
        request = self.context.get('request')
        path = f"/api/v1/webhooks/incoming/{obj.webhook_token}/"
        if request:
            return request.build_absolute_uri(path)
        return path


class WebhookLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookLog
        fields = '__all__'
