from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from apps.common.views import HealthCheckAPIView

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # OpenAPI schema views
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    
    # Health endpoint
    path("api/v1/health/", HealthCheckAPIView.as_view(), name="health_check"),
    
    # API endpoints
    path("api/v1/auth/", include("apps.authentication.urls")),
    path("api/v1/", include("apps.organization.urls")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.audit_logs.urls")),
]
