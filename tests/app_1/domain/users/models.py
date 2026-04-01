"""User domain models."""

from dataclasses import dataclass, field

from domain.base import Entity


@dataclass
class User(Entity):
    """Represents an authenticated user in the system.

    Inherits identity from Entity. Passwords are never stored here —
    authentication is delegated to AuthService.
    """

    username: str = ""
    email: str = ""
    is_active: bool = True
    roles: list[str] = field(default_factory=list)

    def deactivate(self) -> None:
        """Soft-deactivate this user. Sets is_active to False."""
        self.is_active = False

    def promote(self, role: str) -> None:
        if role not in self.roles:
            self.roles.append(role)

    def has_role(self, role: str) -> bool:
        return role in self.roles


@dataclass
class Session:
    """Represents an active user session bound to a token."""

    user_id: int
    token: str
    expires_at: float | None = None

    def is_expired(self, now: float) -> bool:
        if self.expires_at is None:
            return False
        return now > self.expires_at
