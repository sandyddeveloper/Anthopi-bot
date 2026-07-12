from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
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
    path("api/v1/", include("apps.projects.urls")),
    path("api/v1/", include("apps.knowledge.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.workspace.urls")),
    path("api/v1/", include("apps.ai_agents.urls")),
    path("api/v1/", include("apps.ai_chat.urls")),
    path("api/v1/", include("apps.workflow_engine.urls")),
    path("api/v1/", include("apps.scheduler.urls")),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

