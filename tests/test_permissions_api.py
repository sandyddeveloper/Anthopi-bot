import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.organization.models import Organization
from apps.authentication.models import Role, Permission, RolePermission

@pytest.mark.django_db
def test_my_permissions_endpoint():
    client = APIClient()

    # 1. Create Organization & Role & Permissions
    org = Organization.objects.create(name="Acme Tech", industry="Technology")
    manager_role = Role.objects.create(organization=org, name="Manager", code="manager")
    
    perm1 = Permission.objects.create(name="View Users", code="user.view")
    perm2 = Permission.objects.create(name="Create Workflow", code="workflow.create")
    
    RolePermission.objects.create(role=manager_role, permission=perm1)
    RolePermission.objects.create(role=manager_role, permission=perm2)

    # 2. Create standard manager user
    user = User.objects.create_user(
        email="manager@acme.org",
        password="password123",
        full_name="Manager User",
        organization=org,
        role=manager_role
    )
    user.status = 'active'
    user.is_active = True
    user.save()

    # 3. Authenticate user
    login_url = reverse('token_obtain_pair')
    login_response = client.post(login_url, {
        "email": "manager@acme.org",
        "password": "password123"
    })
    assert login_response.status_code == status.HTTP_200_OK
    access_token = login_response.json()['data']['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

    # 4. Request my-permissions
    perms_url = reverse('my-permissions')
    response = client.get(perms_url)
    assert response.status_code == status.HTTP_200_OK
    
    envelope = response.json()
    assert envelope['success'] is True
    data = envelope['data']
    assert data['is_superuser'] is False
    assert data['role_code'] == 'manager'
    assert "user.view" in data['permissions']
    assert "workflow.create" in data['permissions']

@pytest.mark.django_db
def test_my_permissions_superuser():
    client = APIClient()
    org = Organization.objects.create(name="Admin Org", industry="IT")
    
    superuser = User.objects.create_superuser(
        email="admin@acme.org",
        password="password123",
        full_name="Admin User",
        organization=org
    )
    superuser.status = 'active'
    superuser.is_active = True
    superuser.save()

    # Authenticate
    login_url = reverse('token_obtain_pair')
    login_response = client.post(login_url, {
        "email": "admin@acme.org",
        "password": "password123"
    })
    access_token = login_response.json()['data']['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

    # Request my-permissions
    perms_url = reverse('my-permissions')
    response = client.get(perms_url)
    assert response.status_code == status.HTTP_200_OK
    
    envelope = response.json()
    assert envelope['success'] is True
    data = envelope['data']
    assert data['is_superuser'] is True
    assert "*" in data['permissions']
