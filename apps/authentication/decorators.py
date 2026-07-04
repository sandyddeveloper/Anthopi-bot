from functools import wraps
from rest_framework.exceptions import PermissionDenied

def permission_required(permission_code):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if not request.user.role:
                raise PermissionDenied("No role assigned to user.")
            if not request.user.role.permissions.filter(code=permission_code).exists():
                raise PermissionDenied(f"Permission '{permission_code}' is required.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def role_required(role_codes):
    if isinstance(role_codes, str):
        role_codes = [role_codes]
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if not request.user.role:
                raise PermissionDenied("No role assigned to user.")
            if request.user.role.code not in role_codes:
                raise PermissionDenied(f"One of the following roles is required: {', '.join(role_codes)}")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
