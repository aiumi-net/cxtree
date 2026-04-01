"""Versioned v1 API endpoint handlers."""

from domain.models import User
from domain.services import UserService


async def get_user(user_id: int, svc: UserService) -> dict:
    """Fetch a single user by ID. Returns 404-style dict if not found."""
    user = svc.get(user_id)
    if user is None:
        return {"error": "not found", "id": user_id}
    return {"id": user.id, "username": user.username, "email": user.email}


async def list_users(svc: UserService, limit: int = 50) -> list[dict]:
    """Return up to *limit* users as serialised dicts."""
    return [{"id": u.id, "username": u.username} for u in svc.list_all()[:limit]]


async def create_user(payload: dict, svc: UserService) -> dict:
    """Create a new user from a payload dict and persist it.

    Expected keys: username, email.
    Returns the created user as a dict including the assigned id.
    """
    user = User(
        id=svc.next_id(),
        username=payload["username"],
        email=payload["email"],
    )
    svc.save(user)
    return {"id": user.id, "username": user.username}


async def delete_user(user_id: int, svc: UserService) -> dict:
    """Delete a user by ID."""
    removed = svc.delete(user_id)
    return {"deleted": removed, "id": user_id}
