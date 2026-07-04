from rest_framework import permissions

class HasRequiredPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        # 1. User must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser bypasses all permission checks
        if request.user.is_superuser:
            return True

        # 2. Check organization requirements (if any)
        require_organization = getattr(view, 'require_organization', True)
        if require_organization and not request.user.organization:
            return False

        # 3. Check Role restrictions (if any)
        required_roles = getattr(view, 'role_required', None)
        if required_roles:
            if isinstance(required_roles, str):
                required_roles = [required_roles]
            user_role = request.user.role
            if not user_role or user_role.code not in required_roles:
                return False

        # 4. Check Permission restrictions (if any)
        required_permissions = getattr(view, 'permission_required', None)
        if required_permissions:
            if isinstance(required_permissions, str):
                required_permissions = [required_permissions]
            
            user_role = request.user.role
            if not user_role:
                return False
                
            user_permission_codes = set(user_role.permissions.values_list('code', flat=True))
            for perm in required_permissions:
                if perm not in user_permission_codes:
                    return False

        return True
