import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.organization.models import Organization, Department, Team, Designation, Invitation
from apps.authentication.models import Role, Permission, UserSession, RolePermission
from apps.audit_logs.models import AuditLog

@pytest.mark.django_db
def test_complete_platform_flow():
    client = APIClient()

    # 1. Create an Organization
    org = Organization.objects.create(
        name="Acme Corp",
        industry="Technology",
        timezone="America/New_York",
        language="en"
    )
    assert org.id is not None
    assert org.name == "Acme Corp"

    # 2. Create Departments and Teams
    dept = Department.objects.create(organization=org, name="Engineering")
    team = Team.objects.create(organization=org, department=dept, name="Backend Team")
    designation = Designation.objects.create(organization=org, name="Senior Engineer")
    
    assert dept.name == "Engineering"
    assert team.name == "Backend Team"

    # 3. Super Admin registers
    super_admin = User.objects.create_superuser(
        email="superadmin@acme.com",
        password="securepassword123",
        full_name="Super Admin"
    )
    assert super_admin.is_superuser
    assert super_admin.email == "superadmin@acme.com"

    # Associate superadmin with organization for multi-tenancy testing
    super_admin.organization = org
    super_admin.save()

    # 4. Super Admin logs in (creates session)
    login_url = reverse('token_obtain_pair')
    login_response = client.post(login_url, {
        "email": "superadmin@acme.com",
        "password": "securepassword123"
    })
    assert login_response.status_code == status.HTTP_200_OK
    
    json_data = login_response.json()
    assert json_data['success'] is True
    assert 'access' in json_data['data']
    assert 'refresh' in json_data['data']
    
    access_token = json_data['data']['access']
    refresh_token = json_data['data']['refresh']

    # Verify that a UserSession was created
    session = UserSession.objects.get(user=super_admin)
    assert session.is_active is True
    assert session.device == "Desktop"

    # Set authentication header for client
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

    # 5. Super Admin creates Roles
    manager_role = Role.objects.create(organization=org, name="Manager", code="manager")
    employee_role = Role.objects.create(organization=org, name="Employee", code="employee")

    # 6. Assign Permissions to Roles
    invite_perm = Permission.objects.create(name="Invite User", code="user.invite")
    view_dashboard_perm = Permission.objects.create(name="View Dashboard", code="dashboard.view")
    create_project_perm = Permission.objects.create(name="Create Project", code="project.create")

    # Assign permissions to manager
    RolePermission.objects.create(role=manager_role, permission=invite_perm)
    RolePermission.objects.create(role=manager_role, permission=view_dashboard_perm)
    
    # Assign permissions to employee
    RolePermission.objects.create(role=employee_role, permission=view_dashboard_perm)

    # 7. Invite a Manager
    invite_url = reverse('invitation-list')
    invite_response = client.post(invite_url, {
        "email": "manager@acme.com",
        "role": str(manager_role.id),
        "department": str(dept.id),
        "team": str(team.id),
        "designation": str(designation.id)
    })
    
    # If it failed, print error response for debugging
    if invite_response.status_code != status.HTTP_201_CREATED:
        print("Invitation Error:", invite_response.json())
        
    assert invite_response.status_code == status.HTTP_201_CREATED
    assert invite_response.json()['success'] is True
    
    invitation = Invitation.objects.get(email="manager@acme.com")
    token = invitation.token
    assert token is not None

    # Clear credentials for anonymous action (accept invite)
    client.credentials()

    # 8. Manager accepts invitation (sets password, activates account)
    accept_url = reverse('invitation_accept')
    accept_response = client.post(accept_url, {
        "token": token,
        "password": "managerpassword123",
        "full_name": "John Manager",
        "phone": "+123456789"
    })
    assert accept_response.status_code == status.HTTP_200_OK
    assert accept_response.json()['success'] is True

    # Verify Manager User profile
    manager_user = User.objects.get(email="manager@acme.com")
    assert manager_user.status == 'active'
    assert manager_user.organization == org
    assert manager_user.role == manager_role
    assert manager_user.department == dept
    assert manager_user.team == team
    assert manager_user.designation == designation
    assert manager_user.check_password("managerpassword123") is True

    # 9. Manager logs in
    login_response2 = client.post(login_url, {
        "email": "manager@acme.com",
        "password": "managerpassword123"
    })
    assert login_response2.status_code == status.HTTP_200_OK
    
    json_data2 = login_response2.json()
    manager_access = json_data2['data']['access']
    manager_refresh = json_data2['data']['refresh']

    # Set manager credentials
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {manager_access}')

    # 10. Manager attempts to access authorized vs unauthorized APIs (RBAC check)
    manager_invite_response = client.get(invite_url)
    assert manager_invite_response.status_code == status.HTTP_200_OK

    # Manager does NOT have audit.view permission
    audit_log_url = reverse('auditlog-list')
    audit_response = client.get(audit_log_url)
    assert audit_response.status_code == status.HTTP_403_FORBIDDEN

    # 11. Audit logs check (ensure actions are logged)
    assert AuditLog.objects.filter(action="USER_LOGIN").exists()
    assert AuditLog.objects.filter(action="INVITATION_ACCEPT").exists()

    # 12. Sessions check (verify sessions can be viewed and revoked)
    sessions_url = reverse('session-list')
    sessions_response = client.get(sessions_url)
    assert sessions_response.status_code == status.HTTP_200_OK
    assert len(sessions_response.json()['data']) > 0

    # Invalidate session (Logout)
    logout_url = reverse('logout')
    logout_response = client.post(logout_url, {"refresh": manager_refresh})
    assert logout_response.status_code == status.HTTP_200_OK

    # Verify session is marked inactive
    manager_session = UserSession.objects.filter(user=manager_user).first()
    assert manager_session.is_active is False
