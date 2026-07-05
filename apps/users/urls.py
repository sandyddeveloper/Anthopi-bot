from django.urls import path
from apps.users.views import (
    UserRegisterAPIView, UserProfileAPIView, ChangePasswordAPIView,
    LogoutOtherDevicesAPIView, UserListAPIView, UserDetailAPIView,
    EmploymentTypeListView, EmploymentStatusListView,
    EmployeeListCreateAPIView, EmployeeDetailAPIView,
    EmployeeActivateAPIView, EmployeeDeactivateAPIView,
    EmployeeBulkStatusAPIView, EmployeeImportAPIView,
    EmployeeExportAPIView, EmployeeDocumentListCreateAPIView,
    EmployeeDocumentDetailAPIView
)

urlpatterns = [
    # Auth & Base User
    path('auth/register/', UserRegisterAPIView.as_view(), name='user_register'),
    path('users/profile/', UserProfileAPIView.as_view(), name='user_profile'),
    path('users/profile/change-password/', ChangePasswordAPIView.as_view(), name='change_password'),
    path('users/profile/sessions/revoke-others/', LogoutOtherDevicesAPIView.as_view(), name='revoke_other_sessions'),
    path('users/', UserListAPIView.as_view(), name='user-list'),
    path('users/<uuid:pk>/', UserDetailAPIView.as_view(), name='user-detail'),
    
    # Employee Management
    path('employees/', EmployeeListCreateAPIView.as_view(), name='employee-list-create'),
    path('employees/employment-types/', EmploymentTypeListView.as_view(), name='employment-types-list'),
    path('employees/employment-statuses/', EmploymentStatusListView.as_view(), name='employment-statuses-list'),
    path('employees/bulk-status/', EmployeeBulkStatusAPIView.as_view(), name='employee-bulk-status'),
    path('employees/import/', EmployeeImportAPIView.as_view(), name='employee-import'),
    path('employees/export/', EmployeeExportAPIView.as_view(), name='employee-export'),
    path('employees/<uuid:pk>/', EmployeeDetailAPIView.as_view(), name='employee-detail'),
    path('employees/<uuid:pk>/activate/', EmployeeActivateAPIView.as_view(), name='employee-activate'),
    path('employees/<uuid:pk>/deactivate/', EmployeeDeactivateAPIView.as_view(), name='employee-deactivate'),
    
    # Employee Documents
    path('employees/<uuid:employee_id>/documents/', EmployeeDocumentListCreateAPIView.as_view(), name='employee-doc-list-create'),
    path('employees/documents/<uuid:pk>/', EmployeeDocumentDetailAPIView.as_view(), name='employee-doc-detail'),
]
