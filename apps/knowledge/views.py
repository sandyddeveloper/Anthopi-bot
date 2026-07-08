import os
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.knowledge.models import Folder, File, FileVersion, KnowledgeCollection, KnowledgeItem, KnowledgePermission
from apps.knowledge.serializers import FolderSerializer, FileSerializer, FileVersionSerializer, KnowledgeCollectionSerializer, KnowledgeItemSerializer, KnowledgePermissionSerializer
from apps.projects.models import ProjectMember
from apps.ai_agents.models import Agent

def filter_visible_files(queryset, user):
    if user.is_superuser:
        return queryset
        
    user_role = user.role
    if user_role and user_role.code in ['admin', 'super_admin']:
        return queryset

    # Get active project memberships for this user
    user_projects = ProjectMember.objects.filter(user=user, status='active').values_list('project_id', flat=True)

    # General conditions:
    # 1. Organization-wide visibility
    # 2. Created by the user
    # 3. Department match (if department visibility is set and user matches)
    # 4. Project match (if project visibility is set and user is in project)
    conditions = Q(visibility='organization') | Q(created_by=user)
    
    if user.department:
        conditions |= Q(visibility='department', department=user.department)
        
    if user_projects:
        conditions |= Q(visibility='project', project_id__in=user_projects)

    return queryset.filter(conditions)

def check_file_access(file_obj, user):
    if user.is_superuser:
        return True
        
    user_role = user.role
    if user_role and user_role.code in ['admin', 'super_admin']:
        return True
        
    if file_obj.created_by == user:
        return True
        
    if file_obj.visibility == 'organization':
        return True
        
    if file_obj.visibility == 'department' and user.department == file_obj.department:
        return True
        
    if file_obj.visibility == 'project' and file_obj.project:
        return ProjectMember.objects.filter(project=file_obj.project, user=user, status='active').exists()
        
    return False

# ----------------- Folders -----------------

class FolderListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List folders",
        responses={200: FolderSerializer(many=True)},
        tags=["Files & Folders"]
    )
    def get(self, request):
        org = request.organization or request.user.organization
        if not org and not request.user.is_superuser:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = Folder.objects.filter(is_deleted=False)
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=org)
            
        parent_id = request.query_params.get('parent_folder')
        if parent_id:
            queryset = queryset.filter(parent_folder_id=parent_id)
        else:
            queryset = queryset.filter(parent_folder__isnull=True)

        serializer = FolderSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a folder",
        request=FolderSerializer,
        responses={201: FolderSerializer},
        tags=["Files & Folders"]
    )
    def post(self, request):
        org = request.organization or request.user.organization
        if not org and not request.user.is_superuser:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = FolderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        folder = serializer.save(
            organization=org,
            created_by=request.user
        )
        
        # Log Audit Log
        from apps.audit_logs.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            organization=org,
            action="FOLDER_CREATE",
            ip_address=request.META.get('REMOTE_ADDR', ''),
            path=request.path,
            method=request.method,
            status_code=201,
            details={"folder_id": str(folder.id), "name": folder.name}
        )

        return Response(FolderSerializer(folder).data, status=status.HTTP_201_CREATED)

class FolderDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, request):
        org = request.organization or request.user.organization
        try:
            queryset = Folder.objects.filter(is_deleted=False)
            if not request.user.is_superuser:
                queryset = queryset.filter(organization=org)
            return queryset.get(pk=pk)
        except Folder.DoesNotExist:
            raise NotFound("Folder not found.")

    @extend_schema(
        summary="Retrieve folder details",
        responses={200: FolderSerializer},
        tags=["Files & Folders"]
    )
    def get(self, request, pk):
        folder = self.get_object(pk, request)
        return Response(FolderSerializer(folder).data)

    @extend_schema(
        summary="Update a folder",
        request=FolderSerializer,
        responses={200: FolderSerializer},
        tags=["Files & Folders"]
    )
    def put(self, request, pk):
        folder = self.get_object(pk, request)
        serializer = FolderSerializer(folder, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_folder = serializer.save()
        return Response(FolderSerializer(updated_folder).data)

    @extend_schema(
        summary="Delete a folder",
        responses={200: inline_serializer(name="FolderDelResponse", fields={"detail": serializers.CharField()})},
        tags=["Files & Folders"]
    )
    def delete(self, request, pk):
        folder = self.get_object(pk, request)
        folder.delete() # Soft delete
        return Response({"detail": "Folder deleted successfully."})

# ----------------- Files -----------------

class FileListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="List files in organization",
        responses={200: FileSerializer(many=True)},
        tags=["Files & Folders"]
    )
    def get(self, request):
        org = request.organization or request.user.organization
        if not org and not request.user.is_superuser:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = File.objects.filter(is_deleted=False).select_related('created_by')
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=org)

        # Filters
        folder_id = request.query_params.get('folder')
        if folder_id:
            queryset = queryset.filter(folder_id=folder_id)
        else:
            queryset = queryset.filter(folder__isnull=True)

        project_id = request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        # Security/Visibility Filter
        queryset = filter_visible_files(queryset, request.user)

        serializer = FileSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Upload a file",
        request=inline_serializer(
            name="FileUploadRequest",
            fields={
                "name": serializers.CharField(),
                "file_path": serializers.FileField(),
                "folder": serializers.UUIDField(required=False, allow_null=True),
                "project": serializers.UUIDField(required=False, allow_null=True),
                "department": serializers.UUIDField(required=False, allow_null=True),
                "visibility": serializers.ChoiceField(choices=File.VISIBILITY_CHOICES, default='organization')
            }
        ),
        responses={201: FileSerializer},
        tags=["Files & Folders"]
    )
    def post(self, request):
        org = request.organization or request.user.organization
        if not org and not request.user.is_superuser:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)

        file_obj = request.FILES.get('file_path')
        if not file_obj:
            return Response({"detail": "file_path is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate File Extensions (PDF, DOCX, XLSX, Images, ZIP)
        ext = os.path.splitext(file_obj.name)[1].lower().replace('.', '')
        allowed_exts = ['pdf', 'docx', 'xlsx', 'zip', 'png', 'jpg', 'jpeg', 'gif']
        if ext not in allowed_exts:
            return Response({"detail": f"File type .{ext} not supported. Allowed: PDF, DOCX, XLSX, Images, ZIP."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = FileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_record = serializer.save(
            organization=org,
            file_size=file_obj.size,
            file_type=ext,
            created_by=request.user
        )

        # Add initial version 1
        FileVersion.objects.create(
            file=file_record,
            file_path=file_record.file_path,
            version_number=1,
            size=file_obj.size,
            created_by=request.user
        )

        # Log audit log
        from apps.audit_logs.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            organization=org,
            action="FILE_UPLOAD",
            ip_address=request.META.get('REMOTE_ADDR', ''),
            path=request.path,
            method=request.method,
            status_code=201,
            details={"file_id": str(file_record.id), "name": file_record.name}
        )

        return Response(FileSerializer(file_record).data, status=status.HTTP_201_CREATED)

class FileDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, request):
        org = request.organization or request.user.organization
        try:
            file_obj = File.objects.get(pk=pk, is_deleted=False)
            if not request.user.is_superuser and file_obj.organization != org:
                raise PermissionDenied("Access denied.")
            if not check_file_access(file_obj, request.user):
                raise PermissionDenied("You do not have access to view this file.")
            return file_obj
        except File.DoesNotExist:
            raise NotFound("File not found.")

    @extend_schema(
        summary="Retrieve file metadata",
        responses={200: FileSerializer},
        tags=["Files & Folders"]
    )
    def get(self, request, pk):
        file_obj = self.get_object(pk, request)
        return Response(FileSerializer(file_obj).data)

    @extend_schema(
        summary="Update file details (rename / move / update visibility)",
        request=FileSerializer,
        responses={200: FileSerializer},
        tags=["Files & Folders"]
    )
    def put(self, request, pk):
        file_obj = self.get_object(pk, request)
        # Verify user has write permission on the file
        if not request.user.is_superuser and file_obj.created_by != request.user and request.user.role.code not in ['admin', 'super_admin']:
            raise PermissionDenied("Only administrators or the owner can edit this file.")

        serializer = FileSerializer(file_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_file = serializer.save()
        return Response(FileSerializer(updated_file).data)

    @extend_schema(
        summary="Soft delete a file",
        responses={200: inline_serializer(name="FileDelResponse", fields={"detail": serializers.CharField()})},
        tags=["Files & Folders"]
    )
    def delete(self, request, pk):
        file_obj = self.get_object(pk, request)
        if not request.user.is_superuser and file_obj.created_by != request.user and request.user.role.code not in ['admin', 'super_admin']:
            raise PermissionDenied("Only administrators or the owner can delete this file.")

        file_obj.delete() # Soft delete
        return Response({"detail": "File deleted successfully."})

class FileDownloadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Download a file securely",
        tags=["Files & Folders"]
    )
    def get(self, request, pk):
        org = request.organization or request.user.organization
        try:
            file_obj = File.objects.get(pk=pk, is_deleted=False)
            if not request.user.is_superuser and file_obj.organization != org:
                raise PermissionDenied("Access denied.")
            if not check_file_access(file_obj, request.user):
                raise PermissionDenied("Access denied.")
        except File.DoesNotExist:
            raise Http404("File not found.")

        # Determine version if query parameter 'version' is passed
        version_num = request.query_params.get('version')
        file_to_serve = file_obj.file_path
        if version_num:
            version_rec = file_obj.versions.filter(version_number=version_num).first()
            if version_rec:
                file_to_serve = version_rec.file_path
            else:
                raise NotFound(f"Version {version_num} of this file not found.")

        response = FileResponse(file_to_serve.open('rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{file_obj.name}"'
        return response

class FileVersionListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_file(self, file_id, request):
        org = request.organization or request.user.organization
        try:
            file_obj = File.objects.get(pk=file_id, is_deleted=False)
            if not request.user.is_superuser and file_obj.organization != org:
                raise PermissionDenied("Access denied.")
            if not check_file_access(file_obj, request.user):
                raise PermissionDenied("Access denied.")
            return file_obj
        except File.DoesNotExist:
            raise NotFound("File not found.")

    @extend_schema(
        summary="List all versions of a file",
        responses={200: FileVersionSerializer(many=True)},
        tags=["Files & Folders"]
    )
    def get(self, request, file_id):
        file_obj = self.get_file(file_id, request)
        versions = file_obj.versions.all().order_by('-version_number')
        return Response(FileVersionSerializer(versions, many=True).data)

    @extend_schema(
        summary="Upload a new version of a file",
        request=inline_serializer(
            name="FileVersionUploadRequest",
            fields={
                "file_path": serializers.FileField()
            }
        ),
        responses={201: FileVersionSerializer},
        tags=["Files & Folders"]
    )
    @transaction.atomic
    def post(self, request, file_id):
        file_obj = self.get_file(file_id, request)
        
        # Verify user has write permission on the file
        if not request.user.is_superuser and file_obj.created_by != request.user and request.user.role.code not in ['admin', 'super_admin']:
            raise PermissionDenied("Only administrators or the owner can add new versions.")

        new_file = request.FILES.get('file_path')
        if not new_file:
            return Response({"detail": "file_path is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Get latest version number
        latest_ver = file_obj.versions.all().order_by('-version_number').first()
        next_ver_num = (latest_ver.version_number + 1) if latest_ver else 1

        # Create FileVersion
        version_rec = FileVersion.objects.create(
            file=file_obj,
            file_path=new_file,
            version_number=next_ver_num,
            size=new_file.size,
            created_by=request.user
        )

        # Update main File record file path & size
        file_obj.file_path = version_rec.file_path
        file_obj.file_size = version_rec.size
        file_obj.save(update_fields=['file_path', 'file_size'])

        return Response(FileVersionSerializer(version_rec).data, status=status.HTTP_201_CREATED)


# ----------------- Knowledge Collections -----------------

def get_org_context(request):
    org = getattr(request, 'organization', None) or request.user.organization
    if not org and not request.user.is_superuser:
        raise PermissionDenied("Organization context required.")
    return org


class KnowledgeCollectionListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List knowledge collections", responses={200: KnowledgeCollectionSerializer(many=True)}, tags=["Knowledge Collections"])
    def get(self, request):
        org = get_org_context(request)
        if request.user.is_superuser:
            queryset = KnowledgeCollection.objects.filter(is_deleted=False)
        else:
            queryset = KnowledgeCollection.objects.filter(organization=org, is_deleted=False)
            
        serializer = KnowledgeCollectionSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Create a knowledge collection", request=KnowledgeCollectionSerializer, responses={201: KnowledgeCollectionSerializer}, tags=["Knowledge Collections"])
    def post(self, request):
        org = get_org_context(request)
        serializer = KnowledgeCollectionSerializer(data=request.data)
        if serializer.is_valid():
            collection = serializer.save(organization=org, created_by=request.user)
            return Response(KnowledgeCollectionSerializer(collection).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class KnowledgeCollectionDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, org):
        try:
            if org is None:
                return KnowledgeCollection.objects.get(id=pk, is_deleted=False)
            return KnowledgeCollection.objects.get(id=pk, organization=org, is_deleted=False)
        except KnowledgeCollection.DoesNotExist:
            raise NotFound("Knowledge collection not found.")

    @extend_schema(summary="Retrieve knowledge collection details", responses={200: KnowledgeCollectionSerializer}, tags=["Knowledge Collections"])
    def get(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        collection = self.get_object(pk, org)
        serializer = KnowledgeCollectionSerializer(collection)
        return Response(serializer.data)

    @extend_schema(summary="Update knowledge collection", request=KnowledgeCollectionSerializer, responses={200: KnowledgeCollectionSerializer}, tags=["Knowledge Collections"])
    def put(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        collection = self.get_object(pk, org)
        serializer = KnowledgeCollectionSerializer(collection, data=request.data, partial=True)
        if serializer.is_valid():
            collection = serializer.save(updated_by=request.user)
            return Response(KnowledgeCollectionSerializer(collection).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Delete a knowledge collection", responses={204: None}, tags=["Knowledge Collections"])
    def delete(self, request, pk):
        org = get_org_context(request) if not request.user.is_superuser else None
        collection = self.get_object(pk, org)
        collection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class KnowledgeCollectionAssignAgentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Assign or remove agent from collection", request=inline_serializer(
        name="AgentAssignmentRequest",
        fields={
            "agent_id": serializers.UUIDField(),
            "action": serializers.ChoiceField(choices=["assign", "remove"])
        }
    ), responses={200: KnowledgeCollectionSerializer}, tags=["Knowledge Collections"])
    def post(self, request, pk):
        org = get_org_context(request)
        collection = get_object_or_404(KnowledgeCollection, id=pk, organization=org, is_deleted=False)
        
        agent_id = request.data.get('agent_id')
        action = request.data.get('action')
        
        if not agent_id or action not in ['assign', 'remove']:
            return Response({"detail": "agent_id and action ('assign' or 'remove') are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        agent = get_object_or_404(Agent, id=agent_id, organization=org, is_deleted=False)
        
        if action == 'assign':
            collection.agents.add(agent)
        else:
            collection.agents.remove(agent)
            
        return Response(KnowledgeCollectionSerializer(collection).data)


class KnowledgeCollectionAddItemAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Add or remove file from collection", request=inline_serializer(
        name="FileAssignmentRequest",
        fields={
            "file_id": serializers.UUIDField(),
            "action": serializers.ChoiceField(choices=["add", "remove"])
        }
    ), responses={200: KnowledgeCollectionSerializer}, tags=["Knowledge Collections"])
    def post(self, request, pk):
        org = get_org_context(request)
        collection = get_object_or_404(KnowledgeCollection, id=pk, organization=org, is_deleted=False)
        
        file_id = request.data.get('file_id')
        action = request.data.get('action')
        
        if not file_id or action not in ['add', 'remove']:
            return Response({"detail": "file_id and action ('add' or 'remove') are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        file_obj = get_object_or_404(File, id=file_id, organization=org, is_deleted=False)
        
        if action == 'add':
            KnowledgeItem.objects.get_or_create(collection=collection, file=file_obj)
        else:
            KnowledgeItem.objects.filter(collection=collection, file=file_obj).delete()
            
        return Response(KnowledgeCollectionSerializer(collection).data)

