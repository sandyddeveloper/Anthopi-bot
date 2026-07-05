from rest_framework import serializers
from apps.users.models import User, EmploymentType, EmploymentStatus, EmployeeProfile, EmployeeDocument
from apps.organization.serializers import OrganizationSerializer, DepartmentSerializer, TeamSerializer, DesignationSerializer
from apps.authentication.serializers import RoleSerializer

class EmploymentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentType
        fields = ['id', 'name', 'code']

class EmploymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentStatus
        fields = ['id', 'name', 'code']

class EmployeeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeDocument
        fields = ['id', 'document_name', 'document_file', 'document_type', 'created_at']

class EmployeeProfileSerializer(serializers.ModelSerializer):
    employment_type_details = EmploymentTypeSerializer(source='employment_type', read_only=True)
    employment_status_details = EmploymentStatusSerializer(source='employment_status', read_only=True)
    documents = EmployeeDocumentSerializer(many=True, read_only=True)
    
    class Meta:
        model = EmployeeProfile
        fields = [
            'id', 'employee_id', 'organization', 'department', 'team', 'designation',
            'reporting_manager', 'date_of_joining', 'employment_type', 'employment_type_details',
            'employment_status', 'employment_status_details', 'work_location', 
            'emergency_contact', 'skills', 'profile_picture', 'documents'
        ]

class UserSerializer(serializers.ModelSerializer):
    organization_details = OrganizationSerializer(source='organization', read_only=True)
    department_details = DepartmentSerializer(source='department', read_only=True)
    team_details = TeamSerializer(source='team', read_only=True)
    designation_details = DesignationSerializer(source='designation', read_only=True)
    role_details = RoleSerializer(source='role', read_only=True)
    employee_profile = EmployeeProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'full_name', 'phone', 'profile_image',
            'organization', 'organization_details', 'department', 'department_details',
            'team', 'team_details', 'role', 'role_details', 'designation', 'designation_details',
            'status', 'timezone', 'language', 'employee_profile', 'last_login', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'email', 'last_login', 'created_at', 'updated_at', 'status']

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'password', 'full_name', 'phone', 'username']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.status = 'active'
        user.is_active = True
        user.save()
        return user
