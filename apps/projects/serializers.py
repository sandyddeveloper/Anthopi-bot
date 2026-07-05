from rest_framework import serializers
from apps.projects.models import Project, ProjectMember
from apps.users.serializers import UserSerializer

class ProjectSerializer(serializers.ModelSerializer):
    manager_details = UserSerializer(source='manager', read_only=True)
    created_by_details = UserSerializer(source='created_by', read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'organization', 'name', 'code', 'description', 'client',
            'manager', 'manager_details', 'start_date', 'end_date', 'priority',
            'status', 'visibility', 'created_by', 'created_by_details',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_by', 'created_at', 'updated_at']

class ProjectMemberSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = ProjectMember
        fields = [
            'id', 'project', 'user', 'user_details', 'role', 'joined_date', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
