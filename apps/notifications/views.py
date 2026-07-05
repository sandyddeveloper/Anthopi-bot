from django.utils import timezone
from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, PermissionDenied
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.serializers import NotificationSerializer, NotificationPreferenceSerializer

class NotificationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List all notifications for active user",
        responses={200: NotificationSerializer(many=True)},
        tags=["Notifications"]
    )
    def get(self, request):
        queryset = Notification.objects.filter(recipient=request.user, is_deleted=False).order_by('-created_at')
        
        unread_only = request.query_params.get('unread_only', 'false').lower() == 'true'
        if unread_only:
            queryset = queryset.filter(is_read=False)

        # Paginate
        from apps.common.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request, view=self)
        if paginated_queryset is not None:
            serializer = NotificationSerializer(paginated_queryset, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = NotificationSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Clear all notifications for active user",
        responses={200: inline_serializer(name="ClearNotificationsResponse", fields={"detail": serializers.CharField()})},
        tags=["Notifications"]
    )
    def delete(self, request):
        Notification.objects.filter(recipient=request.user).update(is_deleted=True)
        return Response({"detail": "All notifications cleared."})

class NotificationMarkReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Mark a notification or all notifications as read",
        request=inline_serializer(
            name="MarkReadRequest",
            fields={
                "notification_id": serializers.UUIDField(required=False, allow_null=True)
            }
        ),
        responses={200: inline_serializer(name="MarkReadResponse", fields={"detail": serializers.CharField()})},
        tags=["Notifications"]
    )
    def post(self, request):
        notif_id = request.data.get('notification_id')
        if notif_id:
            try:
                notif = Notification.objects.get(pk=notif_id, recipient=request.user)
                notif.is_read = True
                notif.read_at = timezone.now()
                notif.save(update_fields=['is_read', 'read_at'])
                return Response({"detail": "Notification marked as read."})
            except Notification.DoesNotExist:
                raise NotFound("Notification not found.")
        else:
            # Mark all as read
            Notification.objects.filter(recipient=request.user, is_read=False).update(
                is_read=True,
                read_at=timezone.now()
            )
            return Response({"detail": "All notifications marked as read."})

class NotificationPreferencesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List user notification preferences",
        responses={200: NotificationPreferenceSerializer(many=True)},
        tags=["Notifications"]
    )
    def get(self, request):
        # Ensure default preferences exist for standard events
        event_types = ['user_invited', 'user_joined', 'project_assigned', 'file_uploaded', 'password_changed']
        for event in event_types:
            NotificationPreference.objects.get_or_create(
                user=request.user,
                event_type=event,
                defaults={'is_enabled_in_app': True, 'is_enabled_email': True}
            )
            
        prefs = NotificationPreference.objects.filter(user=request.user)
        return Response(NotificationPreferenceSerializer(prefs, many=True).data)

    @extend_schema(
        summary="Update notification preferences",
        request=inline_serializer(
            name="UpdatePrefsRequest",
            fields={
                "event_type": serializers.CharField(),
                "is_enabled_in_app": serializers.BooleanField(required=False),
                "is_enabled_email": serializers.BooleanField(required=False)
            }
        ),
        responses={200: NotificationPreferenceSerializer},
        tags=["Notifications"]
    )
    def put(self, request):
        event_type = request.data.get('event_type')
        if not event_type:
            return Response({"detail": "event_type is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        pref, _ = NotificationPreference.objects.get_or_create(
            user=request.user,
            event_type=event_type
        )
        
        if 'is_enabled_in_app' in request.data:
            pref.is_enabled_in_app = request.data['is_enabled_in_app']
        if 'is_enabled_email' in request.data:
            pref.is_enabled_email = request.data['is_enabled_email']
            
        pref.save()
        return Response(NotificationPreferenceSerializer(pref).data)
