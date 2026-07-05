import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from apps.common.models import BaseModel


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('status', 'active')
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', null=True, blank=True)
    
    # Relationships
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    department = models.ForeignKey(
        'organization.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    team = models.ForeignKey(
        'organization.Team',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    role = models.ForeignKey(
        'authentication.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    designation = models.ForeignKey(
        'organization.Designation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    
    status = models.CharField(max_length=50, default='pending') # pending, active, inactive
    timezone = models.CharField(max_length=100, default='UTC')
    language = models.CharField(max_length=10, default='en')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users'
    )
    updated_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_users'
    )

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

class EmploymentType(BaseModel):
    name = models.CharField(max_length=100) # e.g. Full-Time
    code = models.CharField(max_length=100, unique=True) # e.g. full_time

    def __str__(self):
        return self.name

class EmploymentStatus(BaseModel):
    name = models.CharField(max_length=100) # e.g. Active, On Leave, Terminated
    code = models.CharField(max_length=100, unique=True) # e.g. active

    def __str__(self):
        return self.name

class EmployeeProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    organization = models.ForeignKey('organization.Organization', on_delete=models.CASCADE, related_name='employee_profiles')
    department = models.ForeignKey('organization.Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_profiles')
    team = models.ForeignKey('organization.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_profiles')
    designation = models.ForeignKey('organization.Designation', on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_profiles')
    reporting_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reportees')
    date_of_joining = models.DateField(null=True, blank=True)
    employment_type = models.ForeignKey(EmploymentType, on_delete=models.SET_NULL, null=True, blank=True)
    employment_status = models.ForeignKey(EmploymentStatus, on_delete=models.SET_NULL, null=True, blank=True)
    work_location = models.CharField(max_length=255, blank=True)
    emergency_contact = models.JSONField(default=dict, blank=True)
    skills = models.JSONField(default=list, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.full_name or self.user.email} Profile"

class EmployeeDocument(BaseModel):
    employee_profile = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='documents')
    document_name = models.CharField(max_length=255)
    document_file = models.FileField(upload_to='employee_docs/')
    document_type = models.CharField(max_length=100, blank=True) # e.g. Resume, Contract, ID

    def __str__(self):
        return f"{self.document_name} for {self.employee_profile.user.email}"

