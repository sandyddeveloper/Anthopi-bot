from rest_framework import serializers

class BaseSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    created_by_email = serializers.SerializerMethodField(read_only=True)
    updated_by_email = serializers.SerializerMethodField(read_only=True)

    class Meta:
        abstract = True

    def get_created_by_email(self, obj):
        if hasattr(obj, 'created_by') and obj.created_by:
            return obj.created_by.email
        return None

    def get_updated_by_email(self, obj):
        if hasattr(obj, 'updated_by') and obj.updated_by:
            return obj.updated_by.email
        return None

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            model = self.Meta.model
            if hasattr(model, 'created_by'):
                validated_data['created_by'] = request.user
            if hasattr(model, 'updated_by'):
                validated_data['updated_by'] = request.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            model = self.Meta.model
            if hasattr(model, 'updated_by'):
                validated_data['updated_by'] = request.user
        return super().update(instance, validated_data)
