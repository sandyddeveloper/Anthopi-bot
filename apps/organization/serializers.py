import secrets
from rest_framework import serializers
from django.utils import timezone
from apps.common.serializers import BaseSerializer
from apps.organization.models import Organization, Department, Team, Designation, Invitation

class OrganizationSerializer(BaseSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'logo', 'industry', 'timezone', 'language', 'address', 'phone', 'email', 'status', 'subscription', 'created_at', 'updated_at']

class DepartmentSerializer(BaseSerializer):
    class Meta:
        model = Department
        fields = ['id', 'organization', 'name', 'created_at', 'updated_at']

class TeamSerializer(BaseSerializer):
    class Meta:
        model = Team
        fields = ['id', 'organization', 'department', 'name', 'created_at', 'updated_at']

class DesignationSerializer(BaseSerializer):
    class Meta:
        model = Designation
        fields = ['id', 'organization', 'name', 'created_at', 'updated_at']

class InvitationSerializer(BaseSerializer):
    invited_by_email = serializers.EmailField(source='invited_by.email', read_only=True)
    role_code = serializers.CharField(source='role.code', read_only=True)
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all(), required=False)

    class Meta:
        model = Invitation
        fields = ['id', 'organization', 'department', 'team', 'role', 'designation', 'email', 'token', 'invited_by', 'invited_by_email', 'role_code', 'expires_at', 'is_accepted', 'created_at']
        read_only_fields = ['id', 'token', 'invited_by', 'expires_at', 'is_accepted', 'created_at']

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['token'] = secrets.token_urlsafe(32)
        validated_data['expires_at'] = timezone.now() + timezone.timedelta(days=7)
        if request and request.user and request.user.is_authenticated:
            validated_data['invited_by'] = request.user
            if 'organization' not in validated_data or not validated_data['organization']:
                validated_data['organization'] = request.user.organization
        return super().create(validated_data)

class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    full_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
