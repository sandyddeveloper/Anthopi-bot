from importlib import import_module


def test_backend_architecture_modules_are_importable():
    modules = [
        "apps.authentication",
        "apps.organization",
        "apps.workspace",
        "apps.users",
        "apps.projects",
        "apps.ai_agents",
        "apps.integrations",
        "apps.knowledge",
        "apps.workflow_engine",
        "apps.scheduler",
        "apps.ai_chat",
        "apps.notifications",
        "apps.audit_logs",
    ]

    for module_name in modules:
        module = import_module(module_name)
        assert module is not None
