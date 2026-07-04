from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, NotFound
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
import secrets

from apps.common.viewsets import BaseViewSet
from apps.organization.models import Organization, Department, Team, Designation, Invitation
from apps.organization.serializers import (
    OrganizationSerializer, DepartmentSerializer, TeamSerializer, DesignationSerializer,
    InvitationSerializer, InvitationAcceptSerializer
)
from apps.users.models import User
from apps.audit_logs.models import AuditLog

class OrganizationListCreateAPIView(APIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]
        return [IsAuthenticated()]

    @extend_schema(
        summary="List all organizations",
        responses={200: OrganizationSerializer(many=True)},
        tags=["Organizations"]
    )
    def get(self, request):
        queryset = Organization.objects.filter(is_deleted=False)
        # Non-superusers should only see their own organization
        if not request.user.is_superuser:
            queryset = queryset.filter(id=request.user.organization_id)
            
        serializer = OrganizationSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a new organization",
        request=OrganizationSerializer,
        responses={201: OrganizationSerializer},
        tags=["Organizations"]
    )
    def post(self, request):
        serializer = OrganizationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # Core API logic in view
        org = Organization.objects.create(
            name=serializer.validated_data['name'],
            industry=serializer.validated_data.get('industry', ''),
            timezone=serializer.validated_data.get('timezone', 'UTC'),
            language=serializer.validated_data.get('language', 'en'),
            address=serializer.validated_data.get('address', ''),
            phone=serializer.validated_data.get('phone', ''),
            email=serializer.validated_data.get('email', ''),
            subscription=serializer.validated_data.get('subscription', 'free')
        )
        
        # Seed default roles and permissions for this organization
        from apps.authentication.models import Role, Permission
        permissions_data = [
            ("permission.view", "View Permissions"),
            ("role.view", "View Roles"),
            ("role.manage", "Manage Roles"),
            ("user.invite", "Invite Users"),
            ("audit.view", "View Audit Logs"),
        ]
        perms = {}
        for code, name in permissions_data:
            perm, _ = Permission.objects.get_or_create(code=code, defaults={"name": name})
            perms[code] = perm
            
        admin_role = Role.objects.create(organization=org, name="Admin", code="admin")
        manager_role = Role.objects.create(organization=org, name="Manager", code="manager")
        employee_role = Role.objects.create(organization=org, name="Employee", code="employee")
        
        admin_role.permissions.set(list(perms.values()))
        manager_role.permissions.set([perms["role.view"], perms["user.invite"]])
        employee_role.permissions.set([perms["role.view"]])
        
        # Associate user
        if request.user and request.user.is_authenticated:
            request.user.organization = org
            request.user.role = admin_role
            request.user.save(update_fields=['organization', 'role'])
            
        response = Response(OrganizationSerializer(org).data, status=status.HTTP_201_CREATED)
        response.custom_message = "Organization created successfully."
        return response

class OrganizationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, request):
        try:
            org = Organization.objects.get(pk=pk, is_deleted=False)
            if not request.user.is_superuser and org != request.user.organization:
                raise PermissionDenied("Access denied.")
            return org
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")

    @extend_schema(
        summary="Retrieve organization details",
        responses={200: OrganizationSerializer},
        tags=["Organizations"]
    )
    def get(self, request, pk):
        org = self.get_object(pk, request)
        response = Response(OrganizationSerializer(org).data)
        response.custom_message = "Organization retrieved successfully."
        return response

    @extend_schema(
        summary="Update organization details",
        request=OrganizationSerializer,
        responses={200: OrganizationSerializer},
        tags=["Organizations"]
    )
    def put(self, request, pk):
        org = self.get_object(pk, request)
        serializer = OrganizationSerializer(org, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        org.name = serializer.validated_data.get('name', org.name)
        org.industry = serializer.validated_data.get('industry', org.industry)
        org.timezone = serializer.validated_data.get('timezone', org.timezone)
        org.language = serializer.validated_data.get('language', org.language)
        org.address = serializer.validated_data.get('address', org.address)
        org.phone = serializer.validated_data.get('phone', org.phone)
        org.email = serializer.validated_data.get('email', org.email)
        org.subscription = serializer.validated_data.get('subscription', org.subscription)
        org.save()

        response = Response(OrganizationSerializer(org).data)
        response.custom_message = "Organization updated successfully."
        return response

    @extend_schema(
        summary="Soft delete an organization",
        responses={200: inline_serializer(name="OrgDeleteResponse", fields={"detail": serializers.CharField()})},
        tags=["Organizations"]
    )
    def delete(self, request, pk):
        org = self.get_object(pk, request)
        org.is_deleted = True
        org.deleted_at = timezone.now()
        org.save()
        
        response = Response(status=status.HTTP_200_OK)
        response.custom_message = "Organization soft deleted successfully."
        return response

class DepartmentListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List departments",
        responses={200: DepartmentSerializer(many=True)},
        tags=["Departments"]
    )
    def get(self, request):
        queryset = Department.objects.filter(is_deleted=False)
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=request.user.organization)
            
        search_query = request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        serializer = DepartmentSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a new department",
        request=DepartmentSerializer,
        responses={201: DepartmentSerializer},
        tags=["Departments"]
    )
    def post(self, request):
        serializer = DepartmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        org = serializer.validated_data.get('organization')
        if not org:
            org = request.user.organization
            
        if not request.user.is_superuser and org != request.user.organization:
            raise PermissionDenied("Cannot create department for another organization.")

        dept = Department.objects.create(
            organization=org,
            name=serializer.validated_data['name']
        )
        
        response = Response(DepartmentSerializer(dept).data, status=status.HTTP_201_CREATED)
        response.custom_message = "Department created successfully."
        return response

class DepartmentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, request):
        try:
            dept = Department.objects.get(pk=pk, is_deleted=False)
            if not request.user.is_superuser and dept.organization != request.user.organization:
                raise PermissionDenied("Access denied.")
            return dept
        except Department.DoesNotExist:
            raise NotFound("Department not found.")

    @extend_schema(
        summary="Retrieve department details",
        responses={200: DepartmentSerializer},
        tags=["Departments"]
    )
    def get(self, request, pk):
        dept = self.get_object(pk, request)
        response = Response(DepartmentSerializer(dept).data)
        response.custom_message = "Department retrieved successfully."
        return response

    @extend_schema(
        summary="Update department details",
        request=DepartmentSerializer,
        responses={200: DepartmentSerializer},
        tags=["Departments"]
    )
    def put(self, request, pk):
        dept = self.get_object(pk, request)
        serializer = DepartmentSerializer(dept, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        dept.name = serializer.validated_data.get('name', dept.name)
        dept.save()

        response = Response(DepartmentSerializer(dept).data)
        response.custom_message = "Department updated successfully."
        return response

    @extend_schema(
        summary="Soft delete a department",
        responses={200: inline_serializer(name="DeptDeleteResponse", fields={"detail": serializers.CharField()})},
        tags=["Departments"]
    )
    def delete(self, request, pk):
        dept = self.get_object(pk, request)
        dept.is_deleted = True
        dept.deleted_at = timezone.now()
        dept.save()

        response = Response(status=status.HTTP_200_OK)
        response.custom_message = "Department soft deleted successfully."
        return response

class TeamListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List teams",
        responses={200: TeamSerializer(many=True)},
        tags=["Teams"]
    )
    def get(self, request):
        queryset = Team.objects.filter(is_deleted=False)
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=request.user.organization)
            
        search_query = request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        serializer = TeamSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a new team",
        request=TeamSerializer,
        responses={201: TeamSerializer},
        tags=["Teams"]
    )
    def post(self, request):
        serializer = TeamSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        org = serializer.validated_data.get('organization')
        if not org:
            org = request.user.organization
            
        if not request.user.is_superuser and org != request.user.organization:
            raise PermissionDenied("Cannot create team for another organization.")

        team = Team.objects.create(
            organization=org,
            department=serializer.validated_data.get('department'),
            name=serializer.validated_data['name']
        )
        
        response = Response(TeamSerializer(team).data, status=status.HTTP_201_CREATED)
        response.custom_message = "Team created successfully."
        return response

class TeamDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, request):
        try:
            team = Team.objects.get(pk=pk, is_deleted=False)
            if not request.user.is_superuser and team.organization != request.user.organization:
                raise PermissionDenied("Access denied.")
            return team
        except Team.DoesNotExist:
            raise NotFound("Team not found.")

    @extend_schema(
        summary="Retrieve team details",
        responses={200: TeamSerializer},
        tags=["Teams"]
    )
    def get(self, request, pk):
        team = self.get_object(pk, request)
        response = Response(TeamSerializer(team).data)
        response.custom_message = "Team retrieved successfully."
        return response

    @extend_schema(
        summary="Update team details",
        request=TeamSerializer,
        responses={200: TeamSerializer},
        tags=["Teams"]
    )
    def put(self, request, pk):
        team = self.get_object(pk, request)
        serializer = TeamSerializer(team, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        team.name = serializer.validated_data.get('name', team.name)
        team.department = serializer.validated_data.get('department', team.department)
        team.save()

        response = Response(TeamSerializer(team).data)
        response.custom_message = "Team updated successfully."
        return response

    @extend_schema(
        summary="Soft delete a team",
        responses={200: inline_serializer(name="TeamDeleteResponse", fields={"detail": serializers.CharField()})},
        tags=["Teams"]
    )
    def delete(self, request, pk):
        team = self.get_object(pk, request)
        team.is_deleted = True
        team.deleted_at = timezone.now()
        team.save()

        response = Response(status=status.HTTP_200_OK)
        response.custom_message = "Team soft deleted successfully."
        return response

class DesignationListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List designations",
        responses={200: DesignationSerializer(many=True)},
        tags=["Designations"]
    )
    def get(self, request):
        queryset = Designation.objects.filter(is_deleted=False)
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=request.user.organization)
            
        search_query = request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        serializer = DesignationSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a new designation",
        request=DesignationSerializer,
        responses={201: DesignationSerializer},
        tags=["Designations"]
    )
    def post(self, request):
        serializer = DesignationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        org = serializer.validated_data.get('organization')
        if not org:
            org = request.user.organization
            
        if not request.user.is_superuser and org != request.user.organization:
            raise PermissionDenied("Cannot create designation for another organization.")

        desg = Designation.objects.create(
            organization=org,
            name=serializer.validated_data['name']
        )
        
        response = Response(DesignationSerializer(desg).data, status=status.HTTP_201_CREATED)
        response.custom_message = "Designation created successfully."
        return response

class DesignationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, request):
        try:
            desg = Designation.objects.get(pk=pk, is_deleted=False)
            if not request.user.is_superuser and desg.organization != request.user.organization:
                raise PermissionDenied("Access denied.")
            return desg
        except Designation.DoesNotExist:
            raise NotFound("Designation not found.")

    @extend_schema(
        summary="Retrieve designation details",
        responses={200: DesignationSerializer},
        tags=["Designations"]
    )
    def get(self, request, pk):
        desg = self.get_object(pk, request)
        response = Response(DesignationSerializer(desg).data)
        response.custom_message = "Designation retrieved successfully."
        return response

    @extend_schema(
        summary="Update designation details",
        request=DesignationSerializer,
        responses={200: DesignationSerializer},
        tags=["Designations"]
    )
    def put(self, request, pk):
        desg = self.get_object(pk, request)
        serializer = DesignationSerializer(desg, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        desg.name = serializer.validated_data.get('name', desg.name)
        desg.save()

        response = Response(DesignationSerializer(desg).data)
        response.custom_message = "Designation updated successfully."
        return response

    @extend_schema(
        summary="Soft delete a designation",
        responses={200: inline_serializer(name="DesignationDeleteResponse", fields={"detail": serializers.CharField()})},
        tags=["Designations"]
    )
    def delete(self, request, pk):
        desg = self.get_object(pk, request)
        desg.is_deleted = True
        desg.deleted_at = timezone.now()
        desg.save()

        response = Response(status=status.HTTP_200_OK)
        response.custom_message = "Designation soft deleted successfully."
        return response

class InvitationListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List invitations",
        responses={200: InvitationSerializer(many=True)},
        tags=["Invitations"]
    )
    def get(self, request):
        # RBAC Check
        user_role = request.user.role
        if not request.user.is_superuser:
            if not user_role or not user_role.permissions.filter(code='user.invite').exists():
                raise PermissionDenied("You do not have permission to view invitations.")

        queryset = Invitation.objects.filter(is_deleted=False)
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=request.user.organization)
            
        serializer = InvitationSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create an invitation",
        request=InvitationSerializer,
        responses={201: InvitationSerializer},
        tags=["Invitations"]
    )
    def post(self, request):
        user_role = request.user.role
        if not request.user.is_superuser:
            if not user_role or not user_role.permissions.filter(code='user.invite').exists():
                raise PermissionDenied("You do not have permission to invite users.")

        serializer = InvitationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # API logic in view
        org = serializer.validated_data.get('organization')
        if not org:
            org = request.user.organization
            
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timezone.timedelta(days=7)
        
        invite = Invitation.objects.create(
            organization=org,
            department=serializer.validated_data.get('department'),
            team=serializer.validated_data.get('team'),
            role=serializer.validated_data.get('role'),
            designation=serializer.validated_data.get('designation'),
            email=serializer.validated_data['email'],
            token=token,
            invited_by=request.user,
            expires_at=expires_at
        )

        response = Response(InvitationSerializer(invite).data, status=status.HTTP_201_CREATED)
        response.custom_message = "Invitation created successfully."
        return response

class InvitationAcceptAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Accept an invitation",
        request=InvitationAcceptSerializer,
        responses={200: inline_serializer(name="InviteAcceptResponse", fields={"detail": serializers.CharField()})},
        tags=["Invitations"]
    )
    def post(self, request):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        password = serializer.validated_data['password']
        full_name = serializer.validated_data.get('full_name', '')
        phone = serializer.validated_data.get('phone', '')
        
        try:
            invite = Invitation.objects.get(token=token, is_deleted=False)
        except Invitation.DoesNotExist:
            return Response(
                {"success": False, "message": "Invalid or expired invitation token.", "errors": None, "meta": {}},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if invite.is_accepted:
            return Response(
                {"success": False, "message": "Invitation has already been accepted.", "errors": None, "meta": {}},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if invite.expires_at < timezone.now():
            return Response(
                {"success": False, "message": "Invitation has expired.", "errors": None, "meta": {}},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # User creation in view
        user, created = User.objects.get_or_create(email=invite.email)
        user.organization = invite.organization
        user.department = invite.department
        user.team = invite.team
        user.role = invite.role
        user.designation = invite.designation
        user.status = 'active'
        user.full_name = full_name or user.full_name
        user.phone = phone or user.phone
        user.set_password(password)
        user.is_active = True
        user.save()
        
        invite.is_accepted = True
        invite.save()
        
        AuditLog.objects.create(
            user=user,
            organization=invite.organization,
            action="INVITATION_ACCEPT",
            ip_address=request.META.get('REMOTE_ADDR', ''),
            path=request.path,
            method=request.method,
            status_code=200,
            details={"email": invite.email, "invitation_id": str(invite.id)}
        )
        
        response = Response(status=status.HTTP_200_OK)
        response.custom_message = "Invitation accepted successfully. Account activated."
        return response
