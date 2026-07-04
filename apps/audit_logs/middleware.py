import logging
from django.utils.deprecation import MiddlewareMixin
from apps.audit_logs.models import AuditLog

audit_logger = logging.getLogger('audit')

class AuditLogMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if not hasattr(request, 'user') or not request.user:
            return response

        method = request.method
        if method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            path = request.path
            
            if path.startswith('/api/v1/'):
                user = request.user
                
                # Retrieve resolved organization
                org = None
                if hasattr(request, 'organization') and request.organization:
                    org = request.organization
                elif user.is_authenticated and user.organization:
                    org = user.organization
                
                # Auto-determine clean action name
                action = f"{method} {path}"
                parts = [p for p in path.strip('/').split('/') if p]
                if len(parts) >= 3:
                    resource = parts[2]
                    action_map = {
                        'POST': f"{resource.rstrip('s').upper()}_CREATE",
                        'PUT': f"{resource.rstrip('s').upper()}_UPDATE",
                        'PATCH': f"{resource.rstrip('s').upper()}_UPDATE",
                        'DELETE': f"{resource.rstrip('s').upper()}_DELETE",
                    }
                    action = action_map.get(method, action)

                # Collect IP Address
                ip_address = ''
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip_address = x_forwarded_for.split(',')[0].strip()
                else:
                    ip_address = request.META.get('REMOTE_ADDR', '')

                if user and user.is_authenticated:
                    AuditLog.objects.create(
                        user=user,
                        organization=org,
                        action=action,
                        ip_address=ip_address,
                        path=path,
                        method=method,
                        status_code=response.status_code,
                        details={
                            "query_params": dict(request.GET.items()),
                            "success": response.status_code < 400
                        }
                    )
                    
                    audit_logger.info(
                        "Audit: Action %s by User %s (%s) in Org %s. Status: %s",
                        action, user.email, ip_address, org.name if org else 'None', response.status_code
                    )

        return response
