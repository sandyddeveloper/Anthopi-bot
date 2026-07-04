from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject
from apps.organization.models import Organization

def get_organization(request):
    if not hasattr(request, '_cached_organization'):
        org_id = request.headers.get('X-Organization-ID') or request.META.get('HTTP_X_ORGANIZATION_ID')
        if org_id:
            try:
                request._cached_organization = Organization.objects.get(id=org_id, is_deleted=False)
                return request._cached_organization
            except (Organization.DoesNotExist, ValueError):
                pass
        
        # Fallback to user organization
        if request.user and request.user.is_authenticated:
            request._cached_organization = request.user.organization
            return request._cached_organization
            
        request._cached_organization = None
    return request._cached_organization

class OrganizationResolverMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.organization = SimpleLazyObject(lambda: get_organization(request))
