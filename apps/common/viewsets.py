from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from apps.common.pagination import StandardResultsSetPagination
from django.utils import timezone

class BaseViewSet(viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = []
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        # Fallback to verify we have a valid queryset
        if self.queryset is None:
            model = self.serializer_class.Meta.model
            queryset = model.objects.all()
        else:
            queryset = self.queryset

        # Introspect if the model inherits from BaseModel (has is_deleted attribute)
        model = queryset.model
        if hasattr(model, 'is_deleted'):
            include_deleted = self.request.query_params.get('include_deleted', 'false').lower() == 'true'
            if not include_deleted:
                queryset = queryset.filter(is_deleted=False)
        
        # If model belongs to an organization and request has resolved organization, filter by organization_id
        # Note: organization is the root entity, so we automatically isolate tenants.
        if hasattr(model, 'organization') and hasattr(self.request, 'organization') and self.request.organization:
            # Check if organization field is present on model
            queryset = queryset.filter(organization=self.request.organization)

        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        if hasattr(instance, 'is_deleted'):
            instance.is_deleted = True
            instance.deleted_at = timezone.now()
            if hasattr(instance, 'updated_by') and request.user and request.user.is_authenticated:
                instance.updated_by = request.user
            
            update_fields = ['is_deleted', 'deleted_at']
            if hasattr(instance, 'updated_by'):
                update_fields.append('updated_by')
                
            instance.save(update_fields=update_fields)
            
            response = Response(status=status.HTTP_200_OK)
            response.custom_message = f"{instance.__class__.__name__} soft deleted successfully."
            return response
            
        return super().destroy(request, *args, **kwargs)
