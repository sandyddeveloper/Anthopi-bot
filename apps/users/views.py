from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, NotFound
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

from apps.users.models import User
from apps.users.serializers import UserSerializer, UserRegisterSerializer
from apps.audit_logs.models import AuditLog

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
        
        # Core API logic in view
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
        tags=["Users"]
    )
    def get(self, request):
        response = Response(UserSerializer(request.user).data)
        response.custom_message = "Profile retrieved successfully."
        return response

    @extend_schema(
        summary="Update profile of the active user",
        request=UserSerializer,
        responses={200: UserSerializer},
        tags=["Users"]
    )
    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # Save detail changes
        user = serializer.save()
        response = Response(UserSerializer(user).data)
        response.custom_message = "Profile updated successfully."
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
            from django.db.models import Q
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
