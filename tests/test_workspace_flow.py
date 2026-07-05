import io
import csv
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User, EmploymentType, EmploymentStatus, EmployeeProfile, EmployeeDocument
from apps.organization.models import Organization, Department, Team, Designation
from apps.projects.models import Project, ProjectMember
from apps.knowledge.models import Folder, File, FileVersion
from apps.notifications.models import Notification, NotificationPreference
from apps.audit_logs.models import ActivityLog
from apps.authentication.models import Role

@pytest.mark.django_db
def test_workspace_and_enterprise_flows():
    client = APIClient()

    # 1. Setup Base Organization Structure
    org = Organization.objects.create(name="Acme Corp", industry="Tech")
    dept_eng = Department.objects.create(organization=org, name="Engineering")
    dept_hr = Department.objects.create(organization=org, name="HR")
    team_be = Team.objects.create(organization=org, department=dept_eng, name="Backend")
    desig_eng = Designation.objects.create(organization=org, name="Software Engineer")

    # Roles
    admin_role = Role.objects.create(organization=org, name="Admin", code="admin")
    manager_role = Role.objects.create(organization=org, name="Manager", code="manager")
    employee_role = Role.objects.create(organization=org, name="Employee", code="employee")

    # Employment Setup
    emp_type_ft = EmploymentType.objects.create(name="Full-Time", code="full_time")
    emp_status_act = EmploymentStatus.objects.create(name="Active", code="active")
    emp_status_inact = EmploymentStatus.objects.create(name="Inactive", code="inactive")

    # 2. Setup Users
    super_admin = User.objects.create_superuser(email="superadmin@acme.com", password="password123")
    super_admin.organization = org
    super_admin.save()

    org_admin = User.objects.create_user(email="admin@acme.com", password="password123", full_name="Admin Alice")
    org_admin.organization = org
    org_admin.role = admin_role
    org_admin.department = dept_eng
    org_admin.save()

    manager_user = User.objects.create_user(email="manager@acme.com", password="password123", full_name="Bob Manager")
    manager_user.organization = org
    manager_user.role = manager_role
    manager_user.department = dept_eng
    manager_user.save()

    employee_user = User.objects.create_user(email="employee@acme.com", password="password123", full_name="Charlie Employee")
    employee_user.organization = org
    employee_user.role = employee_role
    employee_user.department = dept_eng
    employee_user.save()

    hr_user = User.objects.create_user(email="hr@acme.com", password="password123", full_name="Helen HR")
    hr_user.organization = org
    hr_user.role = employee_role
    hr_user.department = dept_hr
    hr_user.save()

    # Authenticate as Org Admin
    login_url = reverse('token_obtain_pair')
    login_response = client.post(login_url, {"email": "admin@acme.com", "password": "password123"})
    assert login_response.status_code == status.HTTP_200_OK
    access_token = login_response.json()['data']['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}', HTTP_X_ORGANIZATION_ID=str(org.id))

    # 3. Test Employee Profile CRUD & Actions
    # List Employees
    emp_list_url = reverse('employee-list-create')
    response = client.get(emp_list_url)
    assert response.status_code == status.HTTP_200_OK
    # Expect admin, manager, employee, hr (4 users)
    assert len(response.json()['data']) == 4

    # Create Employee Profile via API
    new_emp_response = client.post(emp_list_url, {
        "email": "new_dev@acme.com",
        "full_name": "Dave Newdev",
        "department": str(dept_eng.id),
        "team": str(team_be.id),
        "designation": str(desig_eng.id),
        "role": str(employee_role.id),
        "employee_id": "EMP-999",
        "employment_type": str(emp_type_ft.id),
        "employment_status": str(emp_status_act.id),
        "work_location": "Remote",
        "skills": ["Python", "Django"]
    })
    assert new_emp_response.status_code == status.HTTP_201_CREATED
    new_user = User.objects.get(email="new_dev@acme.com")
    assert new_user.employee_profile.employee_id == "EMP-999"
    assert new_user.employee_profile.skills == ["Python", "Django"]

    # Deactivate Employee
    deactivate_url = reverse('employee-deactivate', kwargs={'pk': str(new_user.id)})
    response = client.post(deactivate_url)
    assert response.status_code == status.HTTP_200_OK
    new_user.refresh_from_db()
    assert new_user.status == 'inactive'

    # Activate Employee
    activate_url = reverse('employee-activate', kwargs={'pk': str(new_user.id)})
    response = client.post(activate_url)
    assert response.status_code == status.HTTP_200_OK
    new_user.refresh_from_db()
    assert new_user.status == 'active'

    # Bulk Status Update
    bulk_status_url = reverse('employee-bulk-status')
    response = client.post(bulk_status_url, {
        "ids": [str(new_user.id)],
        "status": "pending"
    })
    assert response.status_code == status.HTTP_200_OK
    new_user.refresh_from_db()
    assert new_user.status == 'pending'

    # Export Employees
    export_url = reverse('employee-export')
    response = client.get(export_url)
    assert response.status_code == status.HTTP_200_OK
    assert response['Content-Type'] == 'text/csv'

    # Import Employees
    csv_data = "email,full_name,employee_id,work_location\ncsv_dev@acme.com,Csv Developer,EMP-777,Office"
    csv_file = io.BytesIO(csv_data.encode('utf-8'))
    csv_file.name = "employees.csv"
    import_url = reverse('employee-import')
    response = client.post(import_url, {"file": csv_file}, format='multipart')
    assert response.status_code == status.HTTP_201_CREATED
    assert User.objects.filter(email="csv_dev@acme.com").exists()

    # 4. Test Project Management
    project_list_url = reverse('project-list-create')
    proj_response = client.post(project_list_url, {
        "name": "Apollo Project",
        "code": "AP-101",
        "description": "To the moon!",
        "manager": str(manager_user.id),
        "priority": "high",
        "status": "in_progress",
        "visibility": "organization"
    })
    assert proj_response.status_code == status.HTTP_201_CREATED
    project = Project.objects.get(code="AP-101")
    assert project.name == "Apollo Project"

    # Assign member (unauthorized user fails)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {client.post(login_url, {"email": "employee@acme.com", "password": "password123"}).json()['data']['access']}', HTTP_X_ORGANIZATION_ID=str(org.id))
    member_url = reverse('project-member-list-create', kwargs={'project_id': str(project.id)})
    response = client.post(member_url, {
        "user": str(employee_user.id),
        "role": "employee"
    })
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Assign member (admin succeeds)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}', HTTP_X_ORGANIZATION_ID=str(org.id))
    response = client.post(member_url, {
        "user": str(employee_user.id),
        "role": "employee"
    })
    assert response.status_code == status.HTTP_201_CREATED
    assert ProjectMember.objects.filter(project=project, user=employee_user).exists()

    # Archive / Restore Project
    archive_url = reverse('project-archive', kwargs={'pk': str(project.id)})
    response = client.post(archive_url)
    assert response.status_code == status.HTTP_200_OK
    project.refresh_from_db()
    assert project.is_deleted is True

    restore_url = reverse('project-restore', kwargs={'pk': str(project.id)})
    response = client.post(restore_url)
    assert response.status_code == status.HTTP_200_OK
    project.refresh_from_db()
    assert project.is_deleted is False

    # 5. Test File Manager & Security Visibility
    # Upload Private File
    folder_url = reverse('folder-list-create')
    folder_res = client.post(folder_url, {"name": "Confidential"})
    assert folder_res.status_code == status.HTTP_201_CREATED
    folder = Folder.objects.get(name="Confidential")

    file_data = b"private content"
    file_bytes = io.BytesIO(file_data)
    file_bytes.name = "salary.pdf"
    
    file_list_url = reverse('file-list-create')
    file_res = client.post(file_list_url, {
        "name": "salary.pdf",
        "file_path": file_bytes,
        "folder": str(folder.id),
        "visibility": "private"
    }, format='multipart')
    assert file_res.status_code == status.HTTP_201_CREATED
    file_obj = File.objects.get(name="salary.pdf")

    # Employee user checks file list (Private file should NOT appear)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {client.post(login_url, {"email": "employee@acme.com", "password": "password123"}).json()['data']['access']}', HTTP_X_ORGANIZATION_ID=str(org.id))
    list_files_res = client.get(file_list_url, {"folder": str(folder.id)})
    assert len(list_files_res.json()['data']) == 0

    # Department File Check
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}', HTTP_X_ORGANIZATION_ID=str(org.id))
    dept_file_bytes = io.BytesIO(b"engineering secrets")
    dept_file_bytes.name = "secrets.pdf"
    dept_file_res = client.post(file_list_url, {
        "name": "secrets.pdf",
        "file_path": dept_file_bytes,
        "department": str(dept_eng.id),
        "visibility": "department"
    }, format='multipart')
    assert dept_file_res.status_code == status.HTTP_201_CREATED

    # Employee in same department (Engineering) can see secrets.pdf
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {client.post(login_url, {"email": "employee@acme.com", "password": "password123"}).json()['data']['access']}', HTTP_X_ORGANIZATION_ID=str(org.id))
    list_files_res = client.get(file_list_url)
    assert len([f for f in list_files_res.json()['data'] if f['name'] == 'secrets.pdf']) == 1

    # Employee in HR department cannot see secrets.pdf
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {client.post(login_url, {"email": "hr@acme.com", "password": "password123"}).json()['data']['access']}', HTTP_X_ORGANIZATION_ID=str(org.id))
    list_files_res = client.get(file_list_url)
    assert len([f for f in list_files_res.json()['data'] if f['name'] == 'secrets.pdf']) == 0

    # 6. Notifications & Activities
    # Log Activity
    from apps.audit_logs.models import log_activity
    log_activity(org_admin, "created", "project", project.id, project.name, org)
    assert ActivityLog.objects.filter(actor=org_admin, action="created", module="project").exists()

    # Send notification
    from apps.notifications.models import send_notification
    send_notification(employee_user, org_admin, "New Task", "You have been assigned to Apollo Project", "info", "project_assigned")
    assert Notification.objects.filter(recipient=employee_user, event_type="project_assigned").exists()

    # 7. Test Dashboard APIs
    # Authenticate as admin
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}', HTTP_X_ORGANIZATION_ID=str(org.id))
    dashboard_url = reverse('dashboard-stats')
    dash_res = client.get(dashboard_url)
    assert dash_res.status_code == status.HTTP_200_OK
    dash_json = dash_res.json()
    assert dash_json['cards']['total_employees'] >= 4
    assert dash_json['cards']['projects'] == 1

    # Widgets
    widgets_url = reverse('dashboard-widgets')
    widgets_res = client.get(widgets_url)
    assert widgets_res.status_code == status.HTTP_200_OK

    # Global Search
    search_url = reverse('global-search')
    search_res = client.get(f"{search_url}?q=Apollo")
    assert search_res.status_code == status.HTTP_200_OK
    assert len(search_res.json()['projects']) > 0
