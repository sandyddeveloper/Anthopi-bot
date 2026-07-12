from django.db.models import Q
from django.utils import timezone
from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.projects.models import Project, ProjectMember
from apps.projects.serializers import ProjectSerializer, ProjectMemberSerializer

class ProjectListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List projects",
        description="Lists all projects in the organization. Filters projects by priority, status, manager, and active/archived state.",
        responses={200: ProjectSerializer(many=True)},
        tags=["Projects"]
    )
    def get(self, request):
        org = request.organization or request.user.organization
        if not org and not request.user.is_superuser:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)

        include_deleted = request.query_params.get('include_deleted', 'false').lower() == 'true'
        
        queryset = Project.objects.all().select_related('manager', 'created_by')
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=org)
            
        if not include_deleted:
            queryset = queryset.filter(is_deleted=False)

        # Filters
        priority = request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        manager = request.query_params.get('manager')
        if manager:
            queryset = queryset.filter(manager_id=manager)

        # Search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )

        # Pagination
        from apps.common.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request, view=self)
        if paginated_queryset is not None:
            serializer = ProjectSerializer(paginated_queryset, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ProjectSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a new project",
        request=ProjectSerializer,
        responses={201: ProjectSerializer},
        tags=["Projects"]
    )
    def post(self, request):
        org = request.organization or request.user.organization
        if not org and not request.user.is_superuser:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        project = serializer.save(
            organization=org,
            created_by=request.user
        )
        
        # Log to activity feed later in Activity components
        from apps.audit_logs.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            organization=org,
            action="PROJECT_CREATE",
            ip_address=request.META.get('REMOTE_ADDR', ''),
            path=request.path,
            method=request.method,
            status_code=201,
            details={"project_id": str(project.id), "name": project.name}
        )

        # Automatically add the creator/manager as a project member with Manager role
        ProjectMember.objects.create(
            project=project,
            user=project.manager or request.user,
            role='manager',
            status='active'
        )

        response = Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)
        response.custom_message = "Project created successfully."
        return response

class ProjectDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, request):
        org = request.organization or request.user.organization
        try:
            queryset = Project.objects.all()
            if not request.user.is_superuser:
                queryset = queryset.filter(organization=org)
            return queryset.get(pk=pk)
        except Project.DoesNotExist:
            raise NotFound("Project not found.")

    @extend_schema(
        summary="Retrieve project details",
        responses={200: ProjectSerializer},
        tags=["Projects"]
    )
    def get(self, request, pk):
        project = self.get_object(pk, request)
        return Response(ProjectSerializer(project).data)

    @extend_schema(
        summary="Update a project",
        request=ProjectSerializer,
        responses={200: ProjectSerializer},
        tags=["Projects"]
    )
    def put(self, request, pk):
        project = self.get_object(pk, request)
        serializer = ProjectSerializer(project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        updated_project = serializer.save()
        return Response(ProjectSerializer(updated_project).data)

    @extend_schema(
        summary="Soft delete a project",
        responses={200: inline_serializer(name="ProjectDelResponse", fields={"detail": serializers.CharField()})},
        tags=["Projects"]
    )
    def delete(self, request, pk):
        project = self.get_object(pk, request)
        project.delete() # Soft delete support via BaseModel
        return Response({"detail": "Project soft deleted successfully."})

class ProjectArchiveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Archive a project",
        request=None,
        responses={200: inline_serializer(name="ProjectArchiveResponse", fields={"detail": serializers.CharField()})},
        tags=["Projects"]
    )
    def post(self, request, pk):
        org = request.organization or request.user.organization
        try:
            project = Project.objects.get(pk=pk, organization=org)
        except Project.DoesNotExist:
            raise NotFound("Project not found.")
        
        project.delete() # Soft delete
        return Response({"detail": "Project archived successfully."})

class ProjectRestoreAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Restore an archived project",
        request=None,
        responses={200: inline_serializer(name="ProjectRestoreResponse", fields={"detail": serializers.CharField()})},
        tags=["Projects"]
    )
    def post(self, request, pk):
        org = request.organization or request.user.organization
        try:
            project = Project.objects.get(pk=pk, organization=org)
        except Project.DoesNotExist:
            raise NotFound("Project not found.")
        
        project.is_deleted = False
        project.deleted_at = None
        project.save(update_fields=['is_deleted', 'deleted_at'])
        return Response({"detail": "Project restored successfully."})

# ----------------- Project Member Management -----------------

class ProjectMemberListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self, project_id, request):
        org = request.organization or request.user.organization
        try:
            queryset = Project.objects.all()
            if not request.user.is_superuser:
                queryset = queryset.filter(organization=org)
            return queryset.get(pk=project_id)
        except Project.DoesNotExist:
            raise NotFound("Project not found.")

    @extend_schema(
        summary="List members in a project",
        responses={200: ProjectMemberSerializer(many=True)},
        tags=["Projects"]
    )
    def get(self, request, project_id):
        project = self.get_project(project_id, request)
        members = ProjectMember.objects.filter(project=project, is_deleted=False).select_related('user')
        return Response(ProjectMemberSerializer(members, many=True).data)

    @extend_schema(
        summary="Assign a member to the project",
        request=inline_serializer(
            name="ProjectMemberCreateRequest",
            fields={
                "user": serializers.UUIDField(),
                "role": serializers.ChoiceField(choices=ProjectMember.ROLE_CHOICES, default='employee')
            }
        ),
        responses={201: ProjectMemberSerializer},
        tags=["Projects"]
    )
    def post(self, request, project_id):
        project = self.get_project(project_id, request)
        
        # Check permissions: Only Super Admin, Org Admin, or Project Manager can assign members
        user_role = request.user.role
        is_org_admin = user_role and user_role.code in ['admin', 'super_admin']
        is_project_manager = project.manager == request.user or ProjectMember.objects.filter(
            project=project, user=request.user, role='manager', status='active'
        ).exists()
        
        if not request.user.is_superuser and not is_org_admin and not is_project_manager:
            raise PermissionDenied("Only administrators or project managers can assign members to this project.")

        serializer = ProjectMemberSerializer(data={**request.data, "project": str(project.id)})
        serializer.is_valid(raise_exception=True)
        
        # Check if already a member
        member_user_id = serializer.validated_data['user']
        existing = ProjectMember.objects.filter(project=project, user=member_user_id).first()
        if existing:
            if existing.status == 'inactive':
                existing.status = 'active'
                existing.role = serializer.validated_data.get('role', 'employee')
                existing.save()
                return Response(ProjectMemberSerializer(existing).data)
            return Response({"detail": "User is already a member of this project."}, status=status.HTTP_400_BAD_REQUEST)

        member = serializer.save()
        return Response(ProjectMemberSerializer(member).data, status=status.HTTP_201_CREATED)

class ProjectMemberDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_member(self, pk, request):
        org = request.organization or request.user.organization
        try:
            member = ProjectMember.objects.get(pk=pk, is_deleted=False)
            if not request.user.is_superuser and member.project.organization != org:
                raise PermissionDenied("Access denied.")
            return member
        except ProjectMember.DoesNotExist:
            raise NotFound("Project member not found.")

    @extend_schema(
        summary="Update a project member's role or status",
        request=ProjectMemberSerializer,
        responses={200: ProjectMemberSerializer},
        tags=["Projects"]
    )
    def put(self, request, pk):
        member = self.get_member(pk, request)
        
        # Check permissions: Only Super Admin, Org Admin, or Project Manager can change details
        project = member.project
        user_role = request.user.role
        is_org_admin = user_role and user_role.code in ['admin', 'super_admin']
        is_project_manager = project.manager == request.user or ProjectMember.objects.filter(
            project=project, user=request.user, role='manager', status='active'
        ).exists()
        
        if not request.user.is_superuser and not is_org_admin and not is_project_manager:
            raise PermissionDenied("Only administrators or project managers can manage members.")

        serializer = ProjectMemberSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_member = serializer.save()
        return Response(ProjectMemberSerializer(updated_member).data)

    @extend_schema(
        summary="Remove a member from a project",
        responses={200: inline_serializer(name="MemberRemoveResponse", fields={"detail": serializers.CharField()})},
        tags=["Projects"]
    )
    def delete(self, request, pk):
        member = self.get_member(pk, request)
        
        # Check permissions
        project = member.project
        user_role = request.user.role
        is_org_admin = user_role and user_role.code in ['admin', 'super_admin']
        is_project_manager = project.manager == request.user or ProjectMember.objects.filter(
            project=project, user=request.user, role='manager', status='active'
        ).exists()
        
        if not request.user.is_superuser and not is_org_admin and not is_project_manager:
            raise PermissionDenied("Only administrators or project managers can remove members.")

        member.status = 'inactive'
        member.save()
        return Response({"detail": "Member removed from project successfully."})
