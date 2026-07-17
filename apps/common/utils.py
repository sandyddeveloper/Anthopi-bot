from rest_framework.exceptions import PermissionDenied

def get_org_context(request):
    org = getattr(request, 'organization', None) or request.user.organization
    if not org and not request.user.is_superuser:
        raise PermissionDenied("Organization context required.")
    return org
