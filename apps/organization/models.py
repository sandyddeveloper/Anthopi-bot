from django.db import models
from apps.common.models import BaseModel

class Organization(BaseModel):
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=100, default='UTC')
    language = models.CharField(max_length=10, default='en')
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    subscription = models.CharField(max_length=50, default='free')

    def __str__(self):
        return self.name

class Department(BaseModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='departments'
    )
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.organization.name} - {self.name}"

class Team(BaseModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='teams'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='teams',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.organization.name} - {self.name}"

class Designation(BaseModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='designations'
    )
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.organization.name} - {self.name}"

class Invitation(BaseModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    role = models.ForeignKey(
        'authentication.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    designation = models.ForeignKey(
        Designation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    email = models.EmailField()
    token = models.CharField(max_length=255, unique=True)
    invited_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_invitations'
    )
    expires_at = models.DateTimeField()
    is_accepted = models.BooleanField(default=False)

    def __str__(self):
        return f"Invite to {self.email} for {self.organization.name}"
