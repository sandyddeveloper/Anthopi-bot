from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from drf_spectacular.utils import extend_schema
from apps.audit_logs.models import AuditLog
from apps.audit_logs.serializers import AuditLogSerializer

class AuditLogListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List all audit logs",
        description="Lists database-logged system actions. Restricted to users with audit.view permission. Scoped to the user's organization.",
        responses={200: AuditLogSerializer(many=True)},
        tags=["Audit Logs"]
    )
    def get(self, request):
        if not request.user.is_superuser:
            user_role = request.user.role
            if not user_role or not user_role.permissions.filter(code='audit.view').exists():
                raise PermissionDenied("You do not have permission to view audit logs.")

        queryset = AuditLog.objects.all().order_by('-created_at')
        if not request.user.is_superuser:
            queryset = queryset.filter(organization=request.user.organization)
            
        search_query = request.query_params.get('search')
        if search_query:
            from django.db.models import Q
            queryset = queryset.filter(Q(action__icontains=search_query) | Q(user__email__icontains=search_query) | Q(ip_address__icontains=search_query))
            
        from apps.common.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request, view=self)
        if paginated_queryset is not None:
            serializer = AuditLogSerializer(paginated_queryset, many=True)
            return paginator.get_paginated_response(serializer.data)
            
        serializer = AuditLogSerializer(queryset, many=True)
        return Response(serializer.data)

class AuditLogDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, request):
        try:
            log = AuditLog.objects.get(pk=pk)
            if not request.user.is_superuser and log.organization != request.user.organization:
                raise PermissionDenied("Access denied.")
            return log
        except AuditLog.DoesNotExist:
            raise NotFound("Audit log not found.")

    @extend_schema(
        summary="Retrieve audit log details",
        responses={200: AuditLogSerializer},
        tags=["Audit Logs"]
    )
    def get(self, request, pk):
        if not request.user.is_superuser:
            user_role = request.user.role
            if not user_role or not user_role.permissions.filter(code='audit.view').exists():
                raise PermissionDenied("You do not have permission to view audit logs.")

        log = self.get_object(pk, request)
        response = Response(AuditLogSerializer(log).data)
        response.custom_message = "Audit log retrieved successfully."
        return response
