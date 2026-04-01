"""Core domain models shared across the application."""

from dataclasses import dataclass, field


@dataclass
class User:
    """Represents an application user.

    id is assigned by the repository upon first save.
    """

    id: int
    username: str
    email: str
    is_active: bool = True
    roles: list[str] = field(default_factory=list)

    def deactivate(self) -> None:
        """Soft-delete: set is_active to False."""
        self.is_active = False

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def grant_role(self, role: str) -> None:
        if role not in self.roles:
            self.roles.append(role)


@dataclass
class Notification:
    """A notification to be dispatched to a user."""

    recipient_id: int
    subject: str
    body: str
    channel: str = "email"  # "email" | "sms"
    sent: bool = False

    def mark_sent(self) -> None:
        self.sent = True
