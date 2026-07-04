from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from apps.authentication.models import UserSession
from drf_spectacular.extensions import OpenApiAuthenticationExtension

class SessionJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        
        if user and not user.is_active:
            raise AuthenticationFailed("User account is disabled.")
            
        if user and user.status == 'inactive':
            raise AuthenticationFailed("User account is inactive.")

        session_id = validated_token.get('session_id')
        if session_id:
            try:
                session = UserSession.objects.get(id=session_id)
                if not session.is_active:
                    raise AuthenticationFailed("Session has been revoked or logged out.")
            except UserSession.DoesNotExist:
                raise AuthenticationFailed("Session not found or invalid.")
        return user

class SessionJWTScheme(OpenApiAuthenticationExtension):
    target_class = 'apps.authentication.auth_backend.SessionJWTAuthentication'
    name = 'SessionJWTAuth'
    
    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }
