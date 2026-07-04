from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db.models import Q
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

from apps.authentication.models import Role, Permission, UserSession, RolePermission
from apps.authentication.serializers import (
    RoleSerializer, PermissionSerializer, UserSessionSerializer, CustomTokenObtainPairSerializer
)
from apps.audit_logs.models import AuditLog

class LoginAPIView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(
        summary="User Authentication (JWT)",
        description="Authenticates credentials and returns access/refresh token pair, creating an active login session.",
        tags=["login"]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class TokenRefreshAPIView(TokenRefreshView):
    @extend_schema(
        summary="Refresh Access Token",
        description="Provides a new access token using a valid refresh token.",
        tags=["refresh"]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="User Logout",
        description="Invalidates the provided refresh token and sets the active session to inactive.",
        request=inline_serializer(
            name="LogoutRequest",
            fields={"refresh": serializers.CharField(help_text="The refresh token to invalidate")}
        ),
        responses={200: inline_serializer(name="LogoutResponse", fields={"detail": serializers.CharField()})},
        tags=["login"]
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
                jti = token["jti"]
                UserSession.objects.filter(refresh_token_id=jti).update(
                    is_active=False,
                    logout_time=timezone.now()
                )
            
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                raw_token = auth_header.split(' ')[1]
                from rest_framework_simplejwt.backends import TokenBackend
                try:
                    valid_data = TokenBackend(algorithm='HS256').decode(raw_token, verify=False)
                    session_id = valid_data.get('session_id')
                    if session_id:
                        UserSession.objects.filter(id=session_id).update(
                            is_active=False,
                            logout_time=timezone.now()
                        )
                except Exception:
                    pass

            AuditLog.objects.create(
                user=request.user,
                organization=request.user.organization,
                action="USER_LOGOUT",
                ip_address=request.META.get('REMOTE_ADDR', ''),
                path=request.path,
                method=request.method,
                status_code=200,
                details={"message": "Logged out successfully"}
            )

            response = Response(status=status.HTTP_200_OK)
            response.custom_message = "Logged out successfully."
            return response
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class LogoutAllAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Logout from All Devices",
        description="Terminates all active login sessions for the requesting user.",
        request=None,
        responses={200: inline_serializer(name="LogoutAllResponse", fields={"detail": serializers.CharField()})},
        tags=["login"]
    )
    def post(self, request):
        sessions = UserSession.objects.filter(user=request.user, is_active=True)
        count = sessions.count()
        sessions.update(
            is_active=False,
            logout_time=timezone.now()
        )

        AuditLog.objects.create(
            user=request.user,
            organization=request.user.organization,
            action="USER_LOGOUT_ALL_DEVICES",
            ip_address=request.META.get('REMOTE_ADDR', ''),
            path=request.path,
            method=request.method,
            status_code=200,
            details={"revoked_sessions_count": count}
        )

        response = Response(status=status.HTTP_200_OK)
        response.custom_message = f"Successfully logged out from all devices. Revoked {count} sessions."
        return response

class UserSessionListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List active sessions",
        description="Retrieves a list of login sessions associated with the active user.",
        responses={200: UserSessionSerializer(many=True)},
        tags=["sessions"]
    )
    def get(self, request):
        queryset = UserSession.objects.filter(user=request.user).order_by('-login_time')
        serializer = UserSessionSerializer(queryset, many=True)
        return Response(serializer.data)

class UserSessionRevokeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Revoke a login session",
        description="Invalidates a specific session ID, forcing logout on the target device.",
        responses={200: inline_serializer(name="SessionRevokeResponse", fields={"detail": serializers.CharField()})},
        tags=["sessions"]
    )
    def delete(self, request, pk):
        try:
            session = UserSession.objects.get(pk=pk)
        except UserSession.DoesNotExist:
            raise NotFound("Session not found.")
            
        if session.user != request.user and not request.user.is_superuser:
            raise PermissionDenied("Permission denied.")
            
        session.is_active = False
        session.logout_time = timezone.now()
        session.save(update_fields=['is_active', 'logout_time'])

        AuditLog.objects.create(
            user=request.user,
            organization=request.user.organization,
            action="SESSION_REVOKE",
            ip_address=request.META.get('REMOTE_ADDR', ''),
            path=request.path,
            method=request.method,
            status_code=200,
            details={"revoked_session_id": str(session.id)}
        )

        response = Response(status=status.HTTP_200_OK)
        response.custom_message = "Session revoked successfully."
        return response

class PermissionListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="List all permissions",
        responses={200: PermissionSerializer(many=True)},
        tags=["role"]
    )
    def get(self, request):
        # Only allow users with permission.view to read permissions
        if not request.user.is_superuser:
            user_role = request.user.role
            if not user_role or not user_role.permissions.filter(code='permission.view').exists():
                raise PermissionDenied("You do not have permission to view permissions.")

        queryset = Permission.objects.filter(is_deleted=False)
        
        search_query = request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(Q(name__icontains=search_query) | Q(code__icontains=search_query))

        serializer = PermissionSerializer(queryset, many=True)
        return Response(serializer.data)

class RoleListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List roles",
        description="Lists all roles. Scopes lists to the user's organization.",
        responses={200: RoleSerializer(many=True)},
        tags=["role"]
    )
    def get(self, request):
        if not request.user.is_superuser:
            user_role = request.user.role
            if not user_role or not user_role.permissions.filter(code='role.view').exists():
                raise PermissionDenied("You do not have permission to view roles.")

        queryset = Role.objects.filter(is_deleted=False)
        if hasattr(request, 'organization') and request.organization:
            queryset = queryset.filter(Q(organization=request.organization) | Q(organization__isnull=True))
            
        search_query = request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(Q(name__icontains=search_query) | Q(code__icontains=search_query))

        serializer = RoleSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a new role",
        request=RoleSerializer,
        responses={201: RoleSerializer},
        tags=["role"]
    )
    def post(self, request):
        if not request.user.is_superuser:
            user_role = request.user.role
            if not user_role or not user_role.permissions.filter(code='role.manage').exists():
                raise PermissionDenied("You do not have permission to manage roles.")

        serializer = RoleSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # API logic in view
        role = Role.objects.create(
            organization=request.organization,
            name=serializer.validated_data['name'],
            code=serializer.validated_data['code']
        )
        if 'permissions' in serializer.validated_data:
            role.permissions.set(serializer.validated_data['permissions'])

        response = Response(
            RoleSerializer(role).data,
            status=status.HTTP_201_CREATED
        )
        response.custom_message = "Role created successfully."
        return response

class RoleDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, request):
        try:
            role = Role.objects.get(pk=pk, is_deleted=False)
            if not request.user.is_superuser and role.organization != request.user.organization:
                raise PermissionDenied("Access denied.")
            return role
        except Role.DoesNotExist:
            raise NotFound("Role not found.")

    @extend_schema(
        summary="Retrieve role details",
        responses={200: RoleSerializer},
        tags=["role"]
    )
    def get(self, request, pk):
        if not request.user.is_superuser:
            user_role = request.user.role
            if not user_role or not user_role.permissions.filter(code='role.view').exists():
                raise PermissionDenied("You do not have permission to view roles.")

        role = self.get_object(pk, request)
        response = Response(RoleSerializer(role).data)
        response.custom_message = "Role retrieved successfully."
        return response

    @extend_schema(
        summary="Update a role",
        request=RoleSerializer,
        responses={200: RoleSerializer},
        tags=["role"]
    )
    def put(self, request, pk):
        if not request.user.is_superuser:
            user_role = request.user.role
            if not user_role or not user_role.permissions.filter(code='role.manage').exists():
                raise PermissionDenied("You do not have permission to manage roles.")

        role = self.get_object(pk, request)
        serializer = RoleSerializer(role, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # API logic in view
        role.name = serializer.validated_data.get('name', role.name)
        role.code = serializer.validated_data.get('code', role.code)
        role.save()
        if 'permissions' in serializer.validated_data:
            role.permissions.set(serializer.validated_data['permissions'])

        response = Response(RoleSerializer(role).data)
        response.custom_message = "Role updated successfully."
        return response

    @extend_schema(
        summary="Soft delete a role",
        responses={200: inline_serializer(name="RoleDeleteResponse", fields={"detail": serializers.CharField()})},
        tags=["role"]
    )
    def delete(self, request, pk):
        if not request.user.is_superuser:
            user_role = request.user.role
            if not user_role or not user_role.permissions.filter(code='role.manage').exists():
                raise PermissionDenied("You do not have permission to manage roles.")

        role = self.get_object(pk, request)
        role.is_deleted = True
        role.deleted_at = timezone.now()
        role.save()

        response = Response(status=status.HTTP_200_OK)
        response.custom_message = "Role soft deleted successfully."
        return response
