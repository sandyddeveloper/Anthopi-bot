import csv
import io
from django.db import transaction
from django.db.models import Q
from django.http import StreamingHttpResponse, HttpResponse
from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiTypes

from apps.users.models import User, EmploymentType, EmploymentStatus, EmployeeProfile, EmployeeDocument
from apps.users.serializers import (
    UserSerializer, UserRegisterSerializer, EmployeeProfileSerializer,
    EmployeeDocumentSerializer, EmploymentTypeSerializer, EmploymentStatusSerializer
)
from apps.organization.models import Department, Team, Designation
from apps.authentication.models import Role, UserSession
from apps.audit_logs.models import AuditLog

# ----------------- User Authentication & Base Profiles -----------------

class UserRegisterAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register a new user",
        description="Creates a new user profile with active status. Accepts email and password.",
        request=UserRegisterSerializer,
        responses={201: UserSerializer},
        tags=["signup"]
    )
    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        validated_data = serializer.validated_data
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data.get('full_name', ''),
            phone=validated_data.get('phone', ''),
            username=validated_data.get('username')
        )
        user.status = 'active'
        user.is_active = True
        user.save()
        
        AuditLog.objects.create(
            user=user,
            organization=None,
            action="USER_REGISTER",
            ip_address=request.META.get('REMOTE_ADDR', ''),
            path=request.path,
            method=request.method,
            status_code=201,
            details={"email": user.email}
        )

        response = Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED
        )
        response.custom_message = "User registered successfully."
        return response

class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Retrieve profile of the active user",
        responses={200: UserSerializer},
        tags=["Profile"]
    )
    def get(self, request):
        response = Response(UserSerializer(request.user).data)
        response.custom_message = "Profile retrieved successfully."
        return response

    @extend_schema(
        summary="Update profile of the active user",
        request=UserSerializer,
        responses={200: UserSerializer},
        tags=["Profile"]
    )
    def put(self, request):
        data = request.data.copy()
        # Protect read-only organizational fields from profile updates
        for field in ['organization', 'department', 'team', 'role', 'designation', 'status']:
            if field in data:
                data.pop(field)
                
        serializer = UserSerializer(request.user, data=data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Sync profile changes if EmployeeProfile exists
        if hasattr(user, 'employee_profile'):
            profile = user.employee_profile
            profile_data = request.data.get('employee_profile', {})
            if 'work_location' in profile_data:
                profile.work_location = profile_data['work_location']
            if 'skills' in profile_data:
                profile.skills = profile_data['skills']
            if 'emergency_contact' in profile_data:
                profile.emergency_contact = profile_data['emergency_contact']
            if 'profile_picture' in request.FILES:
                profile.profile_picture = request.FILES['profile_picture']
            profile.save()

        response = Response(UserSerializer(user).data)
        response.custom_message = "Profile updated successfully."
        return response

class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Change user password",
        request=inline_serializer(
            name="ChangePasswordRequest",
            fields={
                "old_password": serializers.CharField(),
                "new_password": serializers.CharField(min_length=8)
            }
        ),
        responses={200: inline_serializer(name="ChangePasswordResponse", fields={"detail": serializers.CharField()})},
        tags=["Profile"]
    )
    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        
        if not old_password or not new_password:
            return Response({"detail": "Both old and new passwords are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        if not user.check_password(old_password):
            return Response({"detail": "Incorrect old password."}, status=status.HTTP_400_BAD_REQUEST)
            
        user.set_password(new_password)
        user.save()
        
        AuditLog.objects.create(
            user=user,
            organization=user.organization,
            action="PASSWORD_CHANGED",
            ip_address=request.META.get('REMOTE_ADDR', ''),
            path=request.path,
            method=request.method,
            status_code=200,
            details={"message": "Password changed successfully"}
        )
        
        response = Response(status=status.HTTP_200_OK)
        response.custom_message = "Password changed successfully."
        return response

class LogoutOtherDevicesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Logout other devices",
        request=None,
        responses={200: inline_serializer(name="LogoutOthersResponse", fields={"detail": serializers.CharField()})},
        tags=["Profile"]
    )
    def post(self, request):
        user = request.user
        current_session_id = request.auth.get('session_id') if hasattr(request, 'auth') and request.auth else None
        
        sessions = UserSession.objects.filter(user=user, is_active=True)
        if current_session_id:
            sessions = sessions.exclude(id=current_session_id)
            
        count = sessions.count()
        sessions.update(is_active=False)
        
        response = Response({"detail": f"Logged out from {count} other devices."})
        response.custom_message = f"Logged out from {count} other devices."
        return response

class UserListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List all users within the organization",
        responses={200: UserSerializer(many=True)},
        tags=["Users"]
    )
    def get(self, request):
        queryset = User.objects.filter(is_active=True)
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=request.user.organization)
            
        search_query = request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(Q(email__icontains=search_query) | Q(full_name__icontains=search_query))
            
        from apps.common.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request, view=self)
        if paginated_queryset is not None:
            serializer = UserSerializer(paginated_queryset, many=True)
            return paginator.get_paginated_response(serializer.data)
            
        serializer = UserSerializer(queryset, many=True)
        return Response(serializer.data)

class UserDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, request):
        try:
            user = User.objects.get(pk=pk, is_active=True)
            if not request.user.is_superuser and user.organization != request.user.organization:
                raise PermissionDenied("You do not have access to this user's records.")
            return user
        except User.DoesNotExist:
            raise NotFound("User not found.")

    @extend_schema(
        summary="Retrieve details of a user",
        responses={200: UserSerializer},
        tags=["Users"]
    )
    def get(self, request, pk):
        user = self.get_object(pk, request)
        response = Response(UserSerializer(user).data)
        response.custom_message = "User details retrieved successfully."
        return response

    @extend_schema(
        summary="Update details of a user",
        request=UserSerializer,
        responses={200: UserSerializer},
        tags=["Users"]
    )
    def put(self, request, pk):
        user = self.get_object(pk, request)
        serializer = UserSerializer(user, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        updated_user = serializer.save()
        response = Response(UserSerializer(updated_user).data)
        response.custom_message = "User updated successfully."
        return response

    @extend_schema(
        summary="Soft delete a user record",
        responses={200: inline_serializer(name="UserDeleteResponse", fields={"detail": serializers.CharField()})},
        tags=["Users"]
    )
    def delete(self, request, pk):
        user = self.get_object(pk, request)
        user.status = 'inactive'
        user.is_active = False
        user.save()
        
        response = Response(status=status.HTTP_200_OK)
        response.custom_message = "User soft deleted successfully."
        return response

# ----------------- Employee Profile CRUD & Actions -----------------

class EmploymentTypeListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List all employment types",
        responses={200: EmploymentTypeSerializer(many=True)},
        tags=["Employees"]
    )
    def get(self, request):
        types = EmploymentType.objects.filter(is_deleted=False)
        return Response(EmploymentTypeSerializer(types, many=True).data)

class EmploymentStatusListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List all employment statuses",
        responses={200: EmploymentStatusSerializer(many=True)},
        tags=["Employees"]
    )
    def get(self, request):
        statuses = EmploymentStatus.objects.filter(is_deleted=False)
        return Response(EmploymentStatusSerializer(statuses, many=True).data)

class EmployeeListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List and filter employees",
        responses={200: UserSerializer(many=True)},
        tags=["Employees"]
    )
    def get(self, request):
        org = request.organization or request.user.organization
        if not org and not request.user.is_superuser:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = User.objects.filter(is_active=True).select_related(
            'organization', 'department', 'team', 'designation', 'role', 'employee_profile'
        )
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=org)

        # Filters
        dept = request.query_params.get('department')
        if dept:
            queryset = queryset.filter(department_id=dept)
            
        team = request.query_params.get('team')
        if team:
            queryset = queryset.filter(team_id=team)
            
        designation = request.query_params.get('designation')
        if designation:
            queryset = queryset.filter(designation_id=designation)
            
        manager = request.query_params.get('reporting_manager')
        if manager:
            queryset = queryset.filter(employee_profile__reporting_manager_id=manager)

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search) |
                Q(employee_profile__employee_id__icontains=search)
            )

        # Ordering
        ordering = request.query_params.get('ordering', '-created_at')
        queryset = queryset.order_by(ordering)

        from apps.common.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request, view=self)
        if paginated_queryset is not None:
            serializer = UserSerializer(paginated_queryset, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = UserSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a new employee profile",
        request=inline_serializer(
            name="EmployeeCreateRequest",
            fields={
                "email": serializers.EmailField(),
                "full_name": serializers.CharField(),
                "phone": serializers.CharField(required=False),
                "username": serializers.CharField(required=False),
                "department": serializers.UUIDField(required=False, allow_null=True),
                "team": serializers.UUIDField(required=False, allow_null=True),
                "designation": serializers.UUIDField(required=False, allow_null=True),
                "role": serializers.UUIDField(required=False, allow_null=True),
                "employee_id": serializers.CharField(required=False),
                "reporting_manager": serializers.UUIDField(required=False, allow_null=True),
                "date_of_joining": serializers.DateField(required=False, allow_null=True),
                "employment_type": serializers.UUIDField(required=False, allow_null=True),
                "employment_status": serializers.UUIDField(required=False, allow_null=True),
                "work_location": serializers.CharField(required=False),
                "skills": serializers.ListField(child=serializers.CharField(), required=False),
                "emergency_contact": serializers.JSONField(required=False)
            }
        ),
        responses={201: UserSerializer},
        tags=["Employees"]
    )
    @transaction.atomic
    def post(self, request):
        org = request.organization or request.user.organization
        if not org and not request.user.is_superuser:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data
        email = data.get('email')
        if not email:
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(email=email).exists():
            return Response({"detail": "User with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

        # Create User
        user = User.objects.create_user(
            email=email,
            full_name=data.get('full_name', ''),
            phone=data.get('phone', ''),
            username=data.get('username')
        )
        user.organization = org
        user.department_id = data.get('department')
        user.team_id = data.get('team')
        user.designation_id = data.get('designation')
        user.role_id = data.get('role')
        user.status = 'active'
        user.is_active = True
        user.save()

        # Create Profile
        EmployeeProfile.objects.create(
            user=user,
            employee_id=data.get('employee_id'),
            organization=org,
            department_id=data.get('department'),
            team_id=data.get('team'),
            designation_id=data.get('designation'),
            reporting_manager_id=data.get('reporting_manager'),
            date_of_joining=data.get('date_of_joining'),
            employment_type_id=data.get('employment_type'),
            employment_status_id=data.get('employment_status'),
            work_location=data.get('work_location', ''),
            emergency_contact=data.get('emergency_contact', {}),
            skills=data.get('skills', [])
        )

        response = Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        response.custom_message = "Employee created successfully."
        return response

class EmployeeDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, request):
        try:
            user = User.objects.get(pk=pk, is_active=True)
            if not request.user.is_superuser and user.organization != (request.organization or request.user.organization):
                raise PermissionDenied("Access denied.")
            return user
        except User.DoesNotExist:
            raise NotFound("Employee not found.")

    @extend_schema(
        summary="Retrieve employee profile details",
        responses={200: UserSerializer},
        tags=["Employees"]
    )
    def get(self, request, pk):
        user = self.get_object(pk, request)
        return Response(UserSerializer(user).data)

    @extend_schema(
        summary="Update employee details",
        request=UserSerializer,
        responses={200: UserSerializer},
        tags=["Employees"]
    )
    @transaction.atomic
    def put(self, request, pk):
        user = self.get_object(pk, request)
        data = request.data

        # Update User
        user.full_name = data.get('full_name', user.full_name)
        user.phone = data.get('phone', user.phone)
        user.username = data.get('username', user.username)
        if 'department' in data:
            user.department_id = data['department']
        if 'team' in data:
            user.team_id = data['team']
        if 'designation' in data:
            user.designation_id = data['designation']
        if 'role' in data:
            user.role_id = data['role']
        if 'status' in data:
            user.status = data['status']
        user.save()

        # Update Profile
        profile, _ = EmployeeProfile.objects.get_or_create(
            user=user,
            defaults={'organization': user.organization}
        )
        profile.employee_id = data.get('employee_id', profile.employee_id)
        if 'department' in data:
            profile.department_id = data['department']
        if 'team' in data:
            profile.team_id = data['team']
        if 'designation' in data:
            profile.designation_id = data['designation']
        if 'reporting_manager' in data:
            profile.reporting_manager_id = data['reporting_manager']
        if 'date_of_joining' in data:
            profile.date_of_joining = data['date_of_joining']
        if 'employment_type' in data:
            profile.employment_type_id = data['employment_type']
        if 'employment_status' in data:
            profile.employment_status_id = data['employment_status']
        profile.work_location = data.get('work_location', profile.work_location)
        profile.emergency_contact = data.get('emergency_contact', profile.emergency_contact)
        profile.skills = data.get('skills', profile.skills)
        
        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
        profile.save()

        return Response(UserSerializer(user).data)

    @extend_schema(
        summary="Delete an employee",
        responses={200: inline_serializer(name="EmployeeDeleteMsg", fields={"detail": serializers.CharField()})},
        tags=["Employees"]
    )
    def delete(self, request, pk):
        user = self.get_object(pk, request)
        user.is_active = False
        user.status = 'inactive'
        user.save()
        return Response({"detail": "Employee soft deleted successfully."})

class EmployeeActivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Activate employee",
        request=None,
        responses={200: inline_serializer(name="EmployeeActivateResponse", fields={"detail": serializers.CharField()})},
        tags=["Employees"]
    )
    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            raise NotFound("Employee not found.")
        
        user.is_active = True
        user.status = 'active'
        user.save()
        
        return Response({"detail": "Employee profile activated successfully."})

class EmployeeDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Deactivate employee",
        request=None,
        responses={200: inline_serializer(name="EmployeeDeactivateResponse", fields={"detail": serializers.CharField()})},
        tags=["Employees"]
    )
    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            raise NotFound("Employee not found.")
        
        user.status = 'inactive'
        user.save()
        
        return Response({"detail": "Employee profile deactivated successfully."})

class EmployeeBulkStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Bulk update employee statuses",
        request=inline_serializer(
            name="BulkStatusRequest",
            fields={
                "ids": serializers.ListField(child=serializers.UUIDField()),
                "status": serializers.CharField()
            }
        ),
        responses={200: inline_serializer(name="BulkStatusResponse", fields={"detail": serializers.CharField()})},
        tags=["Employees"]
    )
    def post(self, request):
        ids = request.data.get('ids', [])
        new_status = request.data.get('status')
        if not ids or not new_status:
            return Response({"detail": "Both ids and status are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        org = request.organization or request.user.organization
        queryset = User.objects.filter(id__in=ids)
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=org)
            
        count = queryset.update(status=new_status)
        return Response({"detail": f"Updated status of {count} employees."})

class EmployeeImportAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Import employees from CSV",
        request=inline_serializer(
            name="EmployeeImportRequest",
            fields={
                "file": serializers.FileField()
            }
        ),
        responses={201: inline_serializer(name="EmployeeImportResponse", fields={"detail": serializers.CharField()})},
        tags=["Employees"]
    )
    @transaction.atomic
    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
        
        org = request.organization or request.user.organization
        if not org:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)

        file_data = uploaded_file.read().decode("utf-8-sig")
        io_string = io.StringIO(file_data)
        reader = csv.DictReader(io_string)
        
        imported_count = 0
        for row in reader:
            email = row.get('email')
            if not email or User.objects.filter(email=email).exists():
                continue
                
            full_name = row.get('full_name', '')
            phone = row.get('phone', '')
            employee_id = row.get('employee_id')
            
            # Resolve organizational records
            dept_name = row.get('department')
            dept = None
            if dept_name:
                dept, _ = Department.objects.get_or_create(organization=org, name=dept_name)
                
            team_name = row.get('team')
            team = None
            if team_name:
                team, _ = Team.objects.get_or_create(organization=org, name=team_name, department=dept)
                
            desig_name = row.get('designation')
            desig = None
            if desig_name:
                desig, _ = Designation.objects.get_or_create(organization=org, name=desig_name)
                
            role_code = row.get('role_code', 'employee')
            role = Role.objects.filter(organization=org, code=role_code).first()
            
            user = User.objects.create_user(
                email=email,
                full_name=full_name,
                phone=phone
            )
            user.organization = org
            user.department = dept
            user.team = team
            user.designation = desig
            user.role = role
            user.status = 'active'
            user.is_active = True
            user.save()
            
            EmployeeProfile.objects.create(
                user=user,
                employee_id=employee_id,
                organization=org,
                department=dept,
                team=team,
                designation=desig,
                work_location=row.get('work_location', '')
            )
            imported_count += 1
            
        return Response({"detail": f"Successfully imported {imported_count} employees."}, status=status.HTTP_201_CREATED)

class EmployeeExportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Export employees to CSV",
        responses={200: OpenApiTypes.BINARY},
        tags=["Employees"]
    )
    def get(self, request):
        org = request.organization or request.user.organization
        queryset = User.objects.filter(is_active=True).select_related(
            'department', 'team', 'designation', 'role', 'employee_profile'
        )
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=org)
            
        def csv_generator():
            output = io.StringIO()
            writer = csv.writer(output)
            # Write header
            writer.writerow([
                'Email', 'Full Name', 'Phone', 'Employee ID', 'Department', 
                'Team', 'Designation', 'Role', 'Status', 'Work Location'
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

            for user in queryset:
                profile = getattr(user, 'employee_profile', None)
                writer.writerow([
                    user.email,
                    user.full_name,
                    user.phone,
                    profile.employee_id if profile else '',
                    user.department.name if user.department else '',
                    user.team.name if user.team else '',
                    user.designation.name if user.designation else '',
                    user.role.name if user.role else '',
                    user.status,
                    profile.work_location if profile else ''
                ])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

        response = StreamingHttpResponse(csv_generator(), content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename="employees.csv"'
        return response

class EmployeeDocumentListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="List all documents of an employee",
        responses={200: EmployeeDocumentSerializer(many=True)},
        tags=["Employees"]
    )
    def get(self, request, employee_id):
        # employee_id here is User's ID
        try:
            profile = EmployeeProfile.objects.get(user_id=employee_id)
        except EmployeeProfile.DoesNotExist:
            raise NotFound("Employee profile not found.")
            
        if not request.user.is_superuser and profile.organization != (request.organization or request.user.organization):
            raise PermissionDenied("Access denied.")
            
        docs = profile.documents.filter(is_deleted=False)
        return Response(EmployeeDocumentSerializer(docs, many=True).data)

    @extend_schema(
        summary="Upload document for an employee",
        request=inline_serializer(
            name="EmployeeDocumentUploadRequest",
            fields={
                "document_name": serializers.CharField(),
                "document_file": serializers.FileField(),
                "document_type": serializers.CharField(required=False)
            }
        ),
        responses={201: EmployeeDocumentSerializer},
        tags=["Employees"]
    )
    def post(self, request, employee_id):
        try:
            profile = EmployeeProfile.objects.get(user_id=employee_id)
        except EmployeeProfile.DoesNotExist:
            raise NotFound("Employee profile not found.")
            
        if not request.user.is_superuser and profile.organization != (request.organization or request.user.organization):
            raise PermissionDenied("Access denied.")
            
        doc_file = request.FILES.get('document_file')
        doc_name = request.data.get('document_name')
        doc_type = request.data.get('document_type', '')
        
        if not doc_file or not doc_name:
            return Response({"detail": "document_file and document_name are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        doc = EmployeeDocument.objects.create(
            employee_profile=profile,
            document_name=doc_name,
            document_file=doc_file,
            document_type=doc_type
        )
        
        return Response(EmployeeDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)

class EmployeeDocumentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Delete an employee document",
        responses={200: inline_serializer(name="DocDeleteResponse", fields={"detail": serializers.CharField()})},
        tags=["Employees"]
    )
    def delete(self, request, pk):
        try:
            doc = EmployeeDocument.objects.get(pk=pk)
        except EmployeeDocument.DoesNotExist:
            raise NotFound("Document not found.")
            
        if not request.user.is_superuser and doc.employee_profile.organization != (request.organization or request.user.organization):
            raise PermissionDenied("Access denied.")
            
        doc.delete() # Soft delete support via BaseModel
        return Response({"detail": "Document deleted successfully."})
