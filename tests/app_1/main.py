"""Entry point for app_1. Wires together auth, users and permissions. #cxtree"""

from domain.users.auth import AuthService  # CX -3
from domain.users.models import User
from domain.users.permissions import PermissionChecker
from settings.config import Settings


def create_app(settings: Settings) -> dict:
    """Create and return the application context.

    Returns a dict with auth, permissions, and settings.
    # cxtree
    """
    auth = AuthService(secret=settings.secret_key)  # cxtree
    perms = PermissionChecker()
    return {"auth": auth, "permissions": perms, "settings": settings}


def run():
    settings = Settings()
    app = create_app(settings)
    user = User(id=1, username="alice", email="alice@example.com", roles=["editor"])
    token = app["auth"].login(user, password="correct")  # CX -2
    print(f"Token: {token}")
    valid = app["auth"].validate_token(token)
    print(f"Valid: {valid}")
    print(f"Can delete: {app['permissions'].can(user, 'users:delete')}")
    print(f"Can edit: {app['permissions'].can(user, 'users:edit')}")


if __name__ == "__main__":
    run()
