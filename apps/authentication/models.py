import uuid
from django.db import models
from apps.common.models import BaseModel

class Permission(BaseModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True, db_index=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Role(BaseModel):
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='roles',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100)
    permissions = models.ManyToManyField(
        Permission,
        through='RolePermission',
        related_name='roles'
    )

    class Meta:
        unique_together = ('organization', 'code')

    def __str__(self):
        org_name = self.organization.name if self.organization else "GLOBAL"
        return f"{self.name} ({org_name})"

class RolePermission(BaseModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('role', 'permission')

    def __str__(self):
        return f"{self.role.code} - {self.permission.code}"

class UserRole(BaseModel):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')

    class Meta:
        unique_together = ('user', 'role')

    def __str__(self):
        return f"{self.user.email} - {self.role.code}"

class UserSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='sessions')
    device = models.CharField(max_length=255, blank=True)
    browser = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    os = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    refresh_token_id = models.CharField(max_length=255, db_index=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email} - {self.browser} ({self.ip_address})"
