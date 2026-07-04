from django.contrib import admin
from apps.organization.models import Organization, Department, Team, Designation, Invitation

admin.site.register(Organization)
admin.site.register(Department)
admin.site.register(Team)
admin.site.register(Designation)
admin.site.register(Invitation)
