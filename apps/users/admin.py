from django.contrib import admin
from apps.users.models import User

@admin.register(User)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'organization', 'role', 'status', 'is_staff', 'is_active')
    list_filter = ('status', 'is_staff', 'is_active', 'organization')
    search_fields = ('email', 'full_name')
    ordering = ('email',)
