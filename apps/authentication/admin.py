from django.contrib import admin
from apps.authentication.models import Role, Permission, RolePermission, UserRole, UserSession

admin.site.register(Role)
admin.site.register(Permission)
admin.site.register(RolePermission)
admin.site.register(UserRole)
admin.site.register(UserSession)
