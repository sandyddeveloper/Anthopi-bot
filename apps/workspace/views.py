from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

from apps.users.models import User, EmployeeProfile
from apps.organization.models import Department, Team, Invitation
from apps.projects.models import Project, ProjectMember
from apps.knowledge.models import File
from apps.notifications.models import Notification
from apps.authentication.models import UserSession, Role
from apps.audit_logs.models import ActivityLog
from apps.audit_logs.serializers import ActivityLogSerializer
from apps.projects.serializers import ProjectSerializer
from apps.users.serializers import UserSerializer
from apps.knowledge.serializers import FileSerializer
from apps.notifications.serializers import NotificationSerializer
from apps.organization.serializers import DepartmentSerializer, TeamSerializer, InvitationSerializer

class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Retrieve dashboard statistics and activity timeline",
        responses={200: inline_serializer(
            name="DashboardResponse",
            fields={
                "cards": serializers.JSONField(),
                "recent_activity": ActivityLogSerializer(many=True),
                "statistics": serializers.JSONField()
            }
        )},
        tags=["Workspace"]
    )
    def get(self, request):
        org = request.organization or request.user.organization
        if not org and not request.user.is_superuser:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)

        # Base filters
        users_in_org = User.objects.filter(is_active=True)
        depts_in_org = Department.objects.all()
        teams_in_org = Team.objects.all()
        projects_in_org = Project.objects.filter(is_deleted=False)
        files_in_org = File.objects.filter(is_deleted=False)
        activities_in_org = ActivityLog.objects.all()

        if not request.user.is_superuser:
            users_in_org = users_in_org.filter(organization=org)
            depts_in_org = depts_in_org.filter(organization=org)
            teams_in_org = teams_in_org.filter(organization=org)
            projects_in_org = projects_in_org.filter(organization=org)
            files_in_org = files_in_org.filter(organization=org)
            activities_in_org = activities_in_org.filter(organization=org)

        # 1. Cards
        total_employees = users_in_org.count()
        active_employees = users_in_org.filter(status='active').count()
        
        # Managers & Leads
        manager_role = Role.objects.filter(code='manager').first()
        lead_role = Role.objects.filter(code='team_lead').first()
        
        managers_count = users_in_org.filter(role=manager_role).count() if manager_role else users_in_org.filter(employee_profile__reporting_manager__isnull=False).distinct().count()
        team_leads_count = users_in_org.filter(role=lead_role).count() if lead_role else 0

        notifications_count = Notification.objects.filter(recipient=request.user, is_read=False, is_deleted=False).count()

        cards = {
            "total_employees": total_employees,
            "active_employees": active_employees,
            "managers": managers_count,
            "team_leads": team_leads_count,
            "departments": depts_in_org.count(),
            "teams": teams_in_org.count(),
            "projects": projects_in_org.count(),
            "files": files_in_org.count(),
            "notifications": notifications_count
        }

        # 2. Recent Activity Timeline
        recent_activities = activities_in_org.select_related('actor', 'organization').order_by('-created_at')[:10]
        recent_activity_data = ActivityLogSerializer(recent_activities, many=True).data

        # 3. Quick Statistics Charts
        # Employees by Department
        dept_stats = users_in_org.values('department__name').annotate(count=Count('id')).order_by('-count')
        dept_distribution = {item['department__name'] or 'Unassigned': item['count'] for item in dept_stats}

        # Employees by Role
        role_stats = users_in_org.values('role__name').annotate(count=Count('id')).order_by('-count')
        role_distribution = {item['role__name'] or 'Unassigned': item['count'] for item in role_stats}

        # Monthly Joins (Last 12 Months)
        twelve_months_ago = timezone.now().date() - timezone.timedelta(days=365)
        joins_stats = EmployeeProfile.objects.filter(
            organization=org, date_of_joining__gte=twelve_months_ago
        ).values('date_of_joining__month').annotate(count=Count('id')).order_by('date_of_joining__month')
        
        month_names = {
            1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
        }
        monthly_joins = {month_names[item['date_of_joining__month']]: item['count'] for item in joins_stats if item['date_of_joining__month']}

        # Active Sessions
        active_sessions = UserSession.objects.filter(is_active=True)
        if not request.user.is_superuser:
            active_sessions = active_sessions.filter(user__organization=org)
        active_sessions_count = active_sessions.count()

        statistics = {
            "employees_by_department": dept_distribution,
            "employees_by_role": role_distribution,
            "monthly_joins": monthly_joins,
            "active_sessions": active_sessions_count
        }

        return Response({
            "cards": cards,
            "recent_activity": recent_activity_data,
            "statistics": statistics
        })

class DashboardWidgetsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Retrieve dashboard widgets personalized for the active user",
        responses={200: inline_serializer(
            name="DashboardWidgetsResponse",
            fields={
                "my_projects": ProjectSerializer(many=True),
                "my_team": UserSerializer(many=True),
                "recent_files": FileSerializer(many=True),
                "recent_notifications": NotificationSerializer(many=True),
                "pending_invitations": InvitationSerializer(many=True)
            }
        )},
        tags=["Workspace"]
    )
    def get(self, request):
        user = request.user
        org = request.organization or user.organization
        if not org and not user.is_superuser:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. My Projects (projects user is assigned to)
        project_ids = ProjectMember.objects.filter(user=user, status='active').values_list('project_id', flat=True)
        my_projects = Project.objects.filter(id__in=project_ids, is_deleted=False)[:5]
        
        # 2. My Team (same department/team members)
        my_team = User.objects.none()
        if user.team:
            my_team = User.objects.filter(team=user.team, is_active=True).exclude(id=user.id)[:10]
        elif user.department:
            my_team = User.objects.filter(department=user.department, is_active=True).exclude(id=user.id)[:10]

        # 3. Recent Files
        recent_files = File.objects.filter(is_deleted=False)
        if not user.is_superuser:
            # Filter visible files
            from apps.knowledge.views import filter_visible_files
            recent_files = recent_files.filter(organization=org)
            recent_files = filter_visible_files(recent_files, user)
        recent_files = recent_files.order_by('-created_at')[:5]

        # 4. Recent Notifications
        recent_notifications = Notification.objects.filter(recipient=user, is_read=False, is_deleted=False).order_by('-created_at')[:5]

        # 5. Pending Invitations
        pending_invitations = Invitation.objects.filter(organization=org, is_accepted=False, expires_at__gte=timezone.now())[:5]

        return Response({
            "my_projects": ProjectSerializer(my_projects, many=True).data,
            "my_team": UserSerializer(my_team, many=True).data,
            "recent_files": FileSerializer(recent_files, many=True).data,
            "recent_notifications": Notification.objects.filter(recipient=user, is_read=False, is_deleted=False).order_by('-created_at')[:5].values('id', 'title', 'message', 'notification_type', 'created_at'), # inline/simplified
            "pending_invitations": InvitationSerializer(pending_invitations, many=True).data
        })

class GlobalSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Search across employees, projects, departments, teams, and files",
        responses={200: inline_serializer(
            name="SearchResponse",
            fields={
                "employees": UserSerializer(many=True),
                "projects": ProjectSerializer(many=True),
                "departments": DepartmentSerializer(many=True),
                "teams": TeamSerializer(many=True),
                "files": FileSerializer(many=True)
            }
        )},
        tags=["Workspace"]
    )
    def get(self, request):
        query = request.query_params.get('q', '')
        if not query:
            return Response({
                "employees": [],
                "projects": [],
                "departments": [],
                "teams": [],
                "files": []
            })

        org = request.organization or request.user.organization
        if not org and not request.user.is_superuser:
            return Response({"detail": "Organization context required."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Employees Search
        employees = User.objects.filter(is_active=True).filter(
            Q(full_name__icontains=query) | Q(email__icontains=query)
        )
        if not request.user.is_superuser:
            employees = employees.filter(organization=org)
        employees = employees[:10]

        # 2. Projects Search
        projects = Project.objects.filter(is_deleted=False).filter(
            Q(name__icontains=query) | Q(code__icontains=query)
        )
        if not request.user.is_superuser:
            projects = projects.filter(organization=org)
        projects = projects[:10]

        # 3. Departments Search
        departments = Department.objects.filter(name__icontains=query)
        if not request.user.is_superuser:
            departments = departments.filter(organization=org)
        departments = departments[:10]

        # 4. Teams Search
        teams = Team.objects.filter(name__icontains=query)
        if not request.user.is_superuser:
            teams = teams.filter(organization=org)
        teams = teams[:10]

        # 5. Files Search
        files = File.objects.filter(is_deleted=False).filter(name__icontains=query)
        if not request.user.is_superuser:
            from apps.knowledge.views import filter_visible_files
            files = files.filter(organization=org)
            files = filter_visible_files(files, request.user)
        files = files[:10]

        return Response({
            "employees": UserSerializer(employees, many=True).data,
            "projects": ProjectSerializer(projects, many=True).data,
            "departments": DepartmentSerializer(departments, many=True).data,
            "teams": TeamSerializer(teams, many=True).data,
            "files": FileSerializer(files, many=True).data
        })
