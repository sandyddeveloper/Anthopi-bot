from rest_framework import serializers
from apps.users.models import User
from apps.organization.serializers import OrganizationSerializer, DepartmentSerializer, TeamSerializer, DesignationSerializer
from apps.authentication.serializers import RoleSerializer

class UserSerializer(serializers.ModelSerializer):
    organization_details = OrganizationSerializer(source='organization', read_only=True)
    department_details = DepartmentSerializer(source='department', read_only=True)
    team_details = TeamSerializer(source='team', read_only=True)
    designation_details = DesignationSerializer(source='designation', read_only=True)
    role_details = RoleSerializer(source='role', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'full_name', 'phone', 'profile_image',
            'organization', 'organization_details', 'department', 'department_details',
            'team', 'team_details', 'role', 'role_details', 'designation', 'designation_details',
            'status', 'timezone', 'language', 'last_login', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'email', 'last_login', 'created_at', 'updated_at', 'status']

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'password', 'full_name', 'phone', 'username']

    def create(self, validated_data):
        # Default registration is set to pending or active (if superadmin etc.)
        user = User.objects.create_user(**validated_data)
        user.status = 'active' # active for direct registration, invitation accepts go through invitation flow
        user.is_active = True
        user.save()
        return user
