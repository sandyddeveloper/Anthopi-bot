from rest_framework import serializers
from apps.knowledge.models import Folder, File, FileVersion
from apps.users.serializers import UserSerializer

class FolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Folder
        fields = ['id', 'organization', 'name', 'parent_folder', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']

class FileVersionSerializer(serializers.ModelSerializer):
    created_by_details = UserSerializer(source='created_by', read_only=True)

    class Meta:
        model = FileVersion
        fields = ['id', 'file', 'file_path', 'version_number', 'size', 'created_by', 'created_by_details', 'created_at']
        read_only_fields = ['id', 'version_number', 'size', 'created_by', 'created_at']

class FileSerializer(serializers.ModelSerializer):
    created_by_details = UserSerializer(source='created_by', read_only=True)
    versions = FileVersionSerializer(many=True, read_only=True)

    class Meta:
        model = File
        fields = [
            'id', 'organization', 'name', 'folder', 'file_path', 'file_size',
            'file_type', 'project', 'department', 'visibility', 'created_by',
            'created_by_details', 'versions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'file_size', 'file_type', 'created_by', 'created_at', 'updated_at']
