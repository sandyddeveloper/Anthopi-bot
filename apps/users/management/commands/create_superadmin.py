"""
Management command to create a super admin user.
Intended to be run inside the production Docker container:

    python manage.py create_superadmin

Or locally with appropriate DB env vars:

    DB_ENGINE=django.db.backends.postgresql DB_NAME=anthopi_prod \
    DB_USER=anthopi DB_PASSWORD=iloveyouindhu16092003 \
    DB_HOST=<reachable_host> DB_PORT=5432 \
    python manage.py create_superadmin
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.users.models import User
from apps.authentication.models import Role, Permission, RolePermission


SUPERADMIN_EMAIL = "indhu@pro.com"
SUPERADMIN_PASSWORD = "16092003"

# Every permission code the system defines
ALL_PERMISSION_CODES = [
    # Dashboard & monitoring
    "view_dashboard", "view_system_health", "view_analytics",
    # Organization management
    "manage_organization", "view_organization",
    "manage_departments", "view_departments",
    "manage_teams", "view_teams",
    "manage_designations", "view_designations",
    # User management
    "manage_users", "view_users", "create_users", "delete_users",
    # Role & permission management
    "manage_roles", "view_roles",
    "manage_permissions", "view_permissions",
    # Workflow / Automation
    "manage_workflows", "view_workflows",
    "execute_workflows", "view_executions",
    "manage_webhooks", "view_webhooks",
    "manage_schedules", "view_schedules",
    # Content & data
    "manage_content", "view_content",
    "manage_settings", "view_settings",
    # Audit & logs
    "view_audit_logs", "view_system_logs",
    # Billing & subscription
    "manage_billing", "view_billing",
    # API keys
    "manage_api_keys", "view_api_keys",
]


class Command(BaseCommand):
    help = "Create or update the super_admin role and the primary super admin user."

    def handle(self, *args, **options):
        with transaction.atomic():
            # ── 1. Ensure every permission exists ──────────────────────────
            self.stdout.write("[*] Syncing permissions ...")
            for code in ALL_PERMISSION_CODES:
                Permission.objects.get_or_create(
                    code=code,
                    defaults={"name": code.replace("_", " ").title()},
                )
            self.stdout.write(self.style.SUCCESS(
                f"   [OK] {len(ALL_PERMISSION_CODES)} permissions ensured."
            ))

            # ── 2. Create / fetch the super_admin Role (global, no org) ───
            role, created = Role.objects.get_or_create(
                organization=None,
                code="super_admin",
                defaults={"name": "Super Admin"},
            )
            verb = "Created" if created else "Found existing"
            self.stdout.write(self.style.SUCCESS(f"   [OK] {verb} global role: {role}"))

            # ── 3. Attach ALL permissions to the role ─────────────────────
            all_perms = Permission.objects.filter(code__in=ALL_PERMISSION_CODES)
            added = 0
            for perm in all_perms:
                _, was_created = RolePermission.objects.get_or_create(
                    role=role, permission=perm
                )
                if was_created:
                    added += 1
            self.stdout.write(self.style.SUCCESS(
                f"   [OK] {added} new role-permission links added "
                f"(total: {RolePermission.objects.filter(role=role).count()})."
            ))

            # ── 4. Create / update the super admin user ───────────────────
            user, created = User.objects.get_or_create(
                email=SUPERADMIN_EMAIL,
                defaults={
                    "first_name": "Indhu",
                    "last_name": "Pro",
                    "is_staff": True,
                    "is_superuser": True,
                    "status": "active",
                    "role": role,
                },
            )
            if created:
                user.set_password(SUPERADMIN_PASSWORD)
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f"   [OK] Created super admin user: {user.email}"
                ))
            else:
                # Ensure existing user has correct flags
                user.is_staff = True
                user.is_superuser = True
                user.status = "active"
                user.role = role
                user.set_password(SUPERADMIN_PASSWORD)
                user.save()
                self.stdout.write(self.style.WARNING(
                    f"   [WARN] User {user.email} already existed - updated role & flags."
                ))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 52))
        self.stdout.write(self.style.SUCCESS("  [SUCCESS] Super Admin ready!"))
        self.stdout.write(self.style.SUCCESS(f"  Email:       {SUPERADMIN_EMAIL}"))
        self.stdout.write(self.style.SUCCESS(f"  Password:    {'*' * len(SUPERADMIN_PASSWORD)}"))
        self.stdout.write(self.style.SUCCESS(f"  Role:        {role.name} (code={role.code})"))
        self.stdout.write(self.style.SUCCESS(
            f"  Permissions: {RolePermission.objects.filter(role=role).count()}"
        ))
        self.stdout.write(self.style.SUCCESS("=" * 52))
