from django.db import models
from apps.common.models import BaseModel
from apps.organization.models import Organization, Department
from apps.projects.models import Project
from apps.users.models import User

class Folder(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='folders')
    name = models.CharField(max_length=255)
    parent_folder = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')

    def __str__(self):
        return self.name

class File(BaseModel):
    VISIBILITY_CHOICES = [
        ('private', 'Private'),
        ('department', 'Department'),
        ('project', 'Project'),
        ('organization', 'Organization'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='files')
    name = models.CharField(max_length=255)
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, null=True, blank=True, related_name='files')
    file_path = models.FileField(upload_to='knowledge_files/')
    file_size = models.IntegerField() # in bytes
    file_type = models.CharField(max_length=100) # e.g. pdf, docx, xlsx, zip, png
    
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='files')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='files')
    visibility = models.CharField(max_length=50, choices=VISIBILITY_CHOICES, default='organization')

    def __str__(self):
        return self.name

class FileVersion(BaseModel):
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='versions')
    file_path = models.FileField(upload_to='file_versions/')
    version_number = models.IntegerField(default=1)
    size = models.IntegerField() # in bytes

    def __str__(self):
        return f"{self.file.name} v{self.version_number}"
