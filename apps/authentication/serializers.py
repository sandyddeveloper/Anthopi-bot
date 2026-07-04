import uuid
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from apps.authentication.models import UserSession, Role, Permission
from apps.audit_logs.models import AuditLog

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name', 'code']

class RoleSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        write_only=True,
        many=True,
        source='permissions',
        required=False
    )

    class Meta:
        model = Role
        fields = ['id', 'name', 'code', 'organization', 'permissions', 'permission_ids']

class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = ['id', 'device', 'browser', 'ip_address', 'os', 'location', 'login_time', 'logout_time', 'is_active']
        read_only_fields = fields

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        request = self.context.get('request')
        user = self.user
        
        # Ensure user account is active
        if not user.is_active or user.status == 'inactive':
            raise serializers.ValidationError("Account is inactive or pending activation.")
            
        # Parse Request Details
        user_agent = request.META.get('HTTP_USER_AGENT', '') if request else ''
        ip_address = ''
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR', '')

        # Basic parser for browser, OS, and device
        browser = "Unknown Browser"
        os = "Unknown OS"
        if "Chrome" in user_agent:
            browser = "Chrome"
        elif "Safari" in user_agent:
            browser = "Safari"
        elif "Firefox" in user_agent:
            browser = "Firefox"
        elif "Edge" in user_agent:
            browser = "Edge"
            
        if "Windows" in user_agent:
            os = "Windows"
        elif "Macintosh" in user_agent:
            os = "macOS"
        elif "iPhone" in user_agent:
            os = "iOS"
        elif "Android" in user_agent:
            os = "Android"
        elif "Linux" in user_agent:
            os = "Linux"
            
        device = "Mobile" if any(d in user_agent.lower() for d in ["iphone", "android", "ipad"]) else "Desktop"

        # Create active session
        session_id = uuid.uuid4()
        
        refresh_token = data['refresh']
        token_obj = RefreshToken(refresh_token)
        jti = token_obj['jti']
        
        # Update claims in refresh and access tokens
        token_obj['session_id'] = str(session_id)
        token_obj.access_token['session_id'] = str(session_id)
        
        # Write back custom tokens
        data['refresh'] = str(token_obj)
        data['access'] = str(token_obj.access_token)

        # Create Session record
        session = UserSession.objects.create(
            id=session_id,
            user=user,
            device=device,
            browser=browser,
            ip_address=ip_address,
            os=os,
            location="Unknown",
            refresh_token_id=jti,
            is_active=True
        )

        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        # Include basic user info in response
        data['user'] = {
            'id': str(user.id),
            'email': user.email,
            'full_name': user.full_name,
            'organization': str(user.organization.id) if user.organization else None,
            'role': user.role.code if user.role else None,
            'status': user.status
        }
        
        # Log Audit Log
        AuditLog.objects.create(
            user=user,
            organization=user.organization,
            action="USER_LOGIN",
            ip_address=ip_address,
            path=request.path if request else '',
            method=request.method if request else '',
            status_code=200,
            details={"browser": browser, "os": os, "device": device, "session_id": str(session_id)}
        )

        return data
